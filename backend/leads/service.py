"""Durable nationwide lead acquisition orchestration."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.core.exceptions import NotFoundError
from backend.db.base import utc_now
from backend.db.models.leads import Lead, LeadJob, LeadRun
from backend.leads.collectors import CollectionContext, SourceRateLimitError
from backend.leads.config import LeadCatalog, get_lead_catalog
from backend.leads.geography import GeographyService
from backend.leads.normalization import LeadNormalizer, RawLeadRecord
from backend.leads.scoring import LeadScorer
from backend.leads.sources import LeadSourceRegistry
from backend.leads.storage import LeadRawStore
from backend.leads.workbook import LeadWorkbookService
from backend.repositories.lead_repository import LeadRepository
from backend.schemas.leads import LeadRunPlan, LeadRunRequest


class LeadAcquisitionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.catalog: LeadCatalog = get_lead_catalog()
        self.repository = LeadRepository(session)
        self.sources = LeadSourceRegistry(self.catalog)
        self.geography = GeographyService(self.catalog)
        self.normalizer = LeadNormalizer(self.catalog, self.geography)
        self.scorer = LeadScorer(self.catalog)
        self.raw_store = LeadRawStore()
        self.workbook = LeadWorkbookService(session, self.catalog)

    def sync_sources(self) -> list[Any]:
        existing_by_uid = {item.source_uid: item for item in self.repository.list_sources()}
        rows = []
        for descriptor in self.sources.describe_all():
            config = descriptor.config
            values = {
                "source_uid": config["source_uid"],
                "name": config["name"],
                "type": config["type"],
                "enabled": bool(config.get("enabled")),
                "configured": descriptor.configured,
                "bulk_support": bool(config.get("bulk_support")),
                "query_support": bool(config.get("query_support")),
                "geo_support": str(config.get("geo_support", "UNKNOWN")),
                "credentials_required": bool(config.get("credentials_required")),
                "freshness": str(config.get("freshness", "UNKNOWN")),
                "terms_status": str(config.get("terms_status", "UNKNOWN")),
                "storage_policy": str(config.get("storage_policy", "UNKNOWN")),
                "rate_limit": str(config.get("rate_limit", "UNKNOWN")),
                "status": descriptor.status,
                "status_detail": descriptor.status_detail,
            }
            existing = existing_by_uid.get(config["source_uid"])
            if existing:
                values["last_run"] = existing.last_run
                values["last_success"] = existing.last_success
                if existing.status == "RATE_LIMITED":
                    values["status"] = existing.status
                    values["status_detail"] = existing.status_detail
            rows.append(self.repository.upsert_source(values))
        return rows

    def control_options(self) -> dict[str, Any]:
        workbook = self.workbook.preview()
        keywords = self.workbook.effective_keywords()
        segments = self.workbook.effective_segments()
        governorates = self.workbook.effective_governorates()
        return {
            "workbook": workbook,
            "active_command_source": workbook["active_command_source"],
            "query_matrix_rows": workbook.get("query_matrix_rows", 0),
            "enabled_query_jobs": workbook.get("enabled_query_jobs", 0),
            "segments": segments,
            "keywords": {"set": "approved", "count": len(keywords), "languages": sorted({str(item.get("language") or "unknown") for item in keywords})},
            "governorates": governorates,
            "country": self.geography.country_boundary(),
            "run_modes": ["FULL_SCAN", "INCREMENTAL", "REFRESH_STALE", "ENRICH_ONLY", "VERIFY_ONLY"],
        }

    def plan(self, request: LeadRunRequest) -> tuple[LeadRunPlan, list[dict[str, Any]], list[str], list[str], list[str]]:
        workbook = self.workbook.preview()
        effective_segments = self.workbook.effective_segments()
        effective_governorates = self.workbook.effective_governorates()
        segment_by_id = {str(item["category_id"]): item for item in effective_segments}
        governorate_by_id = {str(item["id"]): item for item in effective_governorates}
        source_ids = request.sources or [item["source_uid"] for item in self.catalog.sources if item.get("enabled")]
        governorates = request.governorates or list(governorate_by_id)
        segment_ids = request.segments or list(segment_by_id)
        unknown_sources = sorted(set(source_ids) - set(self.catalog.source_by_uid))
        unknown_segments = sorted(set(segment_ids) - set(segment_by_id))
        if unknown_sources:
            raise ValueError(f"Unknown lead sources: {', '.join(unknown_sources)}")
        if unknown_segments:
            raise ValueError(f"Unknown lead segments: {', '.join(unknown_segments)}")
        # Validates governorates even for national-extract planning.
        all_tiles = self.geography.adaptive_tiles(governorates)
        warnings: list[str] = []
        missing_credentials: list[str] = []
        enabled_sources: list[str] = []
        for source_uid in source_ids:
            descriptor = self.sources.describe(source_uid)
            if descriptor.status == "NOT_CONFIGURED":
                missing_credentials.append(source_uid)
                continue
            if descriptor.status != "READY":
                warnings.append(f"{source_uid} excluded because source status is {descriptor.status}")
                continue
            enabled_sources.append(source_uid)
        keyword_rows = self.workbook.effective_keywords()
        keywords = request.keywords if request.keyword_set == "custom" else [str(item["keyword"]) for item in keyword_rows if not item.get("category_id") or item.get("category_id") in segment_ids]
        jobs: list[dict[str, Any]] = []
        bbox_override = request.source_options.get("bbox_override")
        for source_uid in enabled_sources:
            if source_uid == "SRC_OSM_GEOFABRIK" and not (bbox_override and request.source_options.get("osm_mode") == "overpass"):
                jobs.append({"source_uid": source_uid, "governorate": None, "tile": {"tile_id": "egypt-extract", "bbox": self.catalog.country["bbox"], "polygon": self.catalog.country["polygon"]}})
                continue
            source_tiles = all_tiles
            if bbox_override:
                governorate = governorates[0] if governorates else None
                source_tiles = [type(all_tiles[0])("custom:0:0", governorate or "egypt", tuple(float(value) for value in bbox_override), self.geography._bbox_polygon(tuple(float(value) for value in bbox_override)))]
            for tile in source_tiles:
                jobs.append({"source_uid": source_uid, "governorate": tile.governorate_id, "tile": tile.as_dict()})
        if not enabled_sources:
            warnings.append("No runnable sources are selected")
        if workbook["status"] != "VALID":
            warnings.append(f"Command workbook not found; config defaults are active. Place it at {self.workbook.placement}")
        plan = LeadRunPlan(
            enabled_sources=enabled_sources,
            governorates=governorates,
            segments=segment_ids,
            keyword_count=len(keywords),
            planned_jobs=len(jobs),
            missing_credentials=missing_credentials,
            warnings=warnings,
        )
        return plan, jobs, keywords, governorates, segment_ids

    def create_run(self, request: LeadRunRequest) -> LeadRunPlan | LeadRun:
        plan, jobs, keywords, governorates, segment_ids = self.plan(request)
        if request.dry_run:
            return plan
        if not jobs:
            raise ValueError("Run has no executable jobs; review source status and credentials")
        run = self.repository.create_run(
            {
                "run_uid": f"LRUN_{uuid4().hex.upper()}",
                "name": request.name,
                "mode": request.mode,
                "sources": plan.enabled_sources,
                "geography": {"country": "EG", "governorates": governorates, "adaptive_tiling": request.adaptive_tiling},
                "segments": segment_ids,
                "keywords": keywords,
                "status": "PENDING",
                "dry_run": False,
                "planned_jobs": len(jobs),
                "warnings": plan.warnings,
                "config_snapshot": {"catalog_version": self.catalog.version, "active_command_source": self.workbook.preview()["active_command_source"], "request": request.model_dump(mode="json")},
            }
        )
        for job_plan in jobs:
            self.repository.create_job(
                {
                    "job_uid": f"LJOB_{uuid4().hex.upper()}",
                    "run_id": run.id,
                    "source_uid": job_plan["source_uid"],
                    "governorate": job_plan["governorate"],
                    "tile": job_plan["tile"],
                    "category": "MULTI_SEGMENT",
                    "keyword_set": keywords,
                    "status": "PENDING",
                }
            )
        self.session.flush()
        return self.repository.get_run(run.run_uid) or run

    def execute_run(self, run_uid: str) -> LeadRun:
        run = self._run(run_uid)
        if run.status == "CANCELLED":
            return run
        run.status = "RUNNING"
        run.started_at = run.started_at or utc_now()
        self.session.commit()
        jobs = self.repository.jobs_for_execution(run.id)
        max_records = run.config_snapshot.get("request", {}).get("max_records_per_job")
        options = run.config_snapshot.get("request", {}).get("source_options", {})
        for job in jobs:
            self.session.refresh(run)
            if run.status in {"PAUSED", "CANCELLED", "WAITING_RATE_LIMIT"}:
                break
            self._execute_job(run, job, max_records=max_records, options=options)
        self.session.refresh(run)
        if run.status not in {"PAUSED", "CANCELLED", "WAITING_RATE_LIMIT"}:
            states = [job.status for job in run.jobs]
            if states and all(state == "COMPLETED" for state in states):
                run.status = "COMPLETED"
            elif any(state == "COMPLETED" for state in states):
                run.status = "PARTIAL"
            elif any(state == "FAILED" for state in states):
                run.status = "FAILED"
            run.completed_at = utc_now() if run.status in {"COMPLETED", "PARTIAL", "FAILED"} else None
        self.session.commit()
        return self._run(run_uid)

    def _execute_job(self, run: LeadRun, job: LeadJob, *, max_records: int | None, options: dict[str, Any]) -> None:
        job.status = "RUNNING"
        job.attempt += 1
        job.started_at = job.started_at or utc_now()
        job.error = None
        run.current_source = job.source_uid
        run.current_governorate = job.governorate
        run.current_category = job.category
        self._touch_source(job.source_uid, success=False)
        self.session.commit()
        collector = self.sources.collector(job.source_uid)
        records_since_commit = 0

        def emit(record: RawLeadRecord | None, raw_position: int) -> bool:
            nonlocal records_since_commit
            job.processed += 1
            run.processed += 1
            job.checkpoint = {"raw_position": raw_position, "updated_at": utc_now().isoformat()}
            if record is not None:
                job.found += 1
                run.found += 1
                raw_path = self.raw_store.append(run.run_uid, job.job_uid, record.as_dict())
                job.raw_storage_path = raw_path
                outcome = self._persist_record(run, job, record, raw_path)
                if outcome == "UNIQUE":
                    job.unique_count += 1
                    run.unique_count += 1
                else:
                    job.duplicates += 1
                    run.duplicates += 1
            records_since_commit += 1
            if records_since_commit >= 50:
                self.session.commit()
                records_since_commit = 0
                self.session.refresh(run)
                return run.status not in {"PAUSED", "CANCELLED"}
            return True

        context = CollectionContext(
            source_uid=job.source_uid,
            run_uid=run.run_uid,
            job_uid=job.job_uid,
            governorate=job.governorate,
            tile=job.tile,
            segment_ids=run.segments,
            keywords=run.keywords,
            checkpoint=job.checkpoint,
            max_records=max_records,
            options=options,
        )
        try:
            collector.collect(context, emit)
            self.session.commit()
            self.session.refresh(run)
            if run.status == "PAUSED":
                job.status = "PAUSED"
            elif run.status == "CANCELLED":
                job.status = "CANCELLED"
            else:
                job.status = "COMPLETED"
                job.completed_at = utc_now()
                self._touch_source(job.source_uid, success=True)
        except SourceRateLimitError as exc:
            evidence = exc.as_dict()
            job.error = evidence["provider_message"]
            job.status = "WAITING_RATE_LIMIT"
            job.checkpoint = {**job.checkpoint, "rate_limit": evidence}
            run.status = "WAITING_RATE_LIMIT"
            self._mark_source_rate_limited(job.source_uid, evidence)
        except Exception as exc:
            message = str(exc)
            if any(marker in message.casefold() for marker in ("429", "too many requests", "rate limit", "quota exceeded", "slow down")):
                evidence = {
                    "source": job.source_uid,
                    "http_code": 429 if "429" in message else None,
                    "provider_message": message[:1000],
                    "retry_after": None,
                    "reset_time": "RESET_TIME_UNKNOWN",
                }
                job.error = evidence["provider_message"]
                job.status = "WAITING_RATE_LIMIT"
                job.checkpoint = {**job.checkpoint, "rate_limit": evidence}
                run.status = "WAITING_RATE_LIMIT"
                self._mark_source_rate_limited(job.source_uid, evidence)
                self.session.commit()
                return
            job.error = str(exc)[:2000]
            job.status = "PARTIAL" if job.found else "FAILED"
            job.completed_at = utc_now()
            run.errors += 1
        self.session.commit()

    def _persist_record(self, run: LeadRun, job: LeadJob, raw: RawLeadRecord, raw_path: str) -> str:
        now = utc_now()
        existing_record = self.repository.get_source_record(raw.source_uid, raw.source_record_id)
        normalized = self.normalizer.normalize(raw)
        provenance = {
            "source": raw.source_uid,
            "source_record_id": raw.source_record_id,
            "collector": type(self.sources.collector(raw.source_uid)).__name__,
            "collector_version": "1.0.0",
            "acquisition_timestamp": now.isoformat(),
            "source_version": raw.source_version,
            "keyword": raw.keyword,
            "category": normalized.get("category_id"),
            "governorate": normalized.get("governorate"),
            "tile": job.tile,
            "run_id": run.run_uid,
        }
        if existing_record is not None:
            existing_record.last_seen_at = now
            existing_record.provenance = provenance
            existing_record.raw_storage_path = raw_path
            lead = existing_record.lead
            lead.source_last_seen_at = now
            self._fill_missing(lead, normalized)
            self._rescore(lead)
            return "SAME_SOURCE_DUPLICATE"
        lead, signals, confidence, branch_decision = self._match(normalized)
        outcome = "UNIQUE"
        if lead is None:
            lead = self.repository.add_lead(
                {
                    "lead_uid": f"LEAD_{uuid4().hex.upper()}",
                    **normalized,
                    "source_id": raw.source_uid,
                    "source_record_id": raw.source_record_id,
                    "source_first_seen_at": now,
                    "source_last_seen_at": now,
                    "provenance": [provenance],
                    "dedupe_status": "BRANCH_UNIQUE" if branch_decision == "DISTINCT_BRANCH" else "UNIQUE",
                }
            )
        else:
            outcome = "CROSS_SOURCE_MERGED"
            lead.source_last_seen_at = now
            lead.dedupe_status = outcome
            lead.provenance = [*lead.provenance, provenance]
            self._fill_missing(lead, normalized)
        self.repository.add_source_record(
            {
                "record_uid": f"LSR_{uuid4().hex.upper()}",
                "lead_id": lead.id,
                "source_uid": raw.source_uid,
                "source_record_id": raw.source_record_id,
                "collector": provenance["collector"],
                "collector_version": provenance["collector_version"],
                "acquisition_timestamp": now,
                "source_version": raw.source_version,
                "keyword": raw.keyword,
                "category": normalized.get("category_id"),
                "governorate": normalized.get("governorate"),
                "tile": job.tile,
                "run_uid": run.run_uid,
                "normalized_payload": normalized,
                "raw_storage_path": raw_path,
                "provenance": provenance,
                "first_seen_at": now,
                "last_seen_at": now,
            }
        )
        self.repository.add_dedupe_event(
            {
                "event_uid": f"LDE_{uuid4().hex.upper()}",
                "lead_id": lead.id,
                "incoming_source_uid": raw.source_uid,
                "incoming_source_record_id": raw.source_record_id,
                "outcome": outcome,
                "matched_signals": signals,
                "confidence": confidence,
                "branch_decision": branch_decision,
            }
        )
        self._rescore(lead)
        return outcome

    def _match(self, normalized: dict[str, Any]) -> tuple[Lead | None, list[str], float, str | None]:
        best: tuple[Lead, list[str], float] | None = None
        branch_detected = False
        for candidate in self.repository.dedupe_candidates(normalized):
            signals: list[str] = []
            score = 0.0
            distance = self._distance_meters(candidate.latitude, candidate.longitude, normalized.get("latitude"), normalized.get("longitude"))
            same_name = candidate.business_name_normalized == normalized.get("business_name_normalized")
            different_address = bool(candidate.address_normalized and normalized.get("address_normalized") and candidate.address_normalized != normalized.get("address_normalized"))
            if same_name and distance is not None and distance > 500 and different_address:
                branch_detected = True
                continue
            if normalized.get("phone_normalized") and candidate.phone_normalized == normalized["phone_normalized"]:
                signals.append("phone")
                score = max(score, 0.98)
            if normalized.get("domain_normalized") and candidate.domain_normalized == normalized["domain_normalized"]:
                signals.append("domain")
                score = max(score, 0.92)
            if same_name and candidate.address_normalized and candidate.address_normalized == normalized.get("address_normalized"):
                signals.append("name_address")
                score = max(score, 0.90)
            if same_name and distance is not None and distance <= 150:
                signals.append("name_coordinates")
                score = max(score, 0.88)
            if score >= 0.85 and (best is None or score > best[2]):
                best = (candidate, signals, score)
        if best:
            return best[0], best[1], best[2], "MERGED_SAME_BRANCH"
        return None, [], 0.0, "DISTINCT_BRANCH" if branch_detected else "NEW_BUSINESS"

    @staticmethod
    def _distance_meters(lat1, lon1, lat2, lon2) -> float | None:
        if None in (lat1, lon1, lat2, lon2):
            return None
        radius = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _fill_missing(lead: Lead, normalized: dict[str, Any]) -> None:
        for key, value in normalized.items():
            if value not in (None, "", []) and getattr(lead, key, None) in (None, "", []):
                setattr(lead, key, value)

    def _rescore(self, lead: Lead) -> None:
        self.session.flush()
        score, fit_class, explanation = self.scorer.score(lead, source_count=self.repository.source_count(lead.id))
        lead.fit_score = score
        lead.fit_class = fit_class
        lead.score_explanation = explanation

    def _touch_source(self, source_uid: str, *, success: bool) -> None:
        for source in self.sync_sources():
            if source.source_uid == source_uid:
                source.last_run = utc_now()
                if success:
                    source.last_success = utc_now()
                    source.status = "READY"
                    source.status_detail = None
                break

    def _mark_source_rate_limited(self, source_uid: str, evidence: dict[str, Any]) -> None:
        for source in self.sync_sources():
            if source.source_uid == source_uid:
                source.status = "RATE_LIMITED"
                source.status_detail = (
                    f"HTTP {evidence.get('http_code') or 'UNKNOWN'}; "
                    f"retry_after={evidence.get('retry_after') or 'UNKNOWN'}; "
                    f"reset_time={evidence.get('reset_time') or 'RESET_TIME_UNKNOWN'}"
                )
                break

    def pause(self, run_uid: str) -> LeadRun:
        run = self._run(run_uid)
        if run.status not in {"PENDING", "RUNNING", "WAITING_RATE_LIMIT"}:
            raise ValueError(f"Run cannot be paused from {run.status}")
        run.status = "PAUSED"
        self.session.flush()
        return run

    def resume(self, run_uid: str) -> LeadRun:
        run = self._run(run_uid)
        if run.status not in {"PAUSED", "PARTIAL", "FAILED", "WAITING_RATE_LIMIT"}:
            raise ValueError(f"Run cannot be resumed from {run.status}")
        for job in run.jobs:
            if job.status in {"PAUSED", "PARTIAL", "WAITING_RATE_LIMIT"}:
                job.status = "PENDING"
        run.status = "PENDING"
        run.completed_at = None
        self.session.flush()
        return run

    def cancel(self, run_uid: str) -> LeadRun:
        run = self._run(run_uid)
        if run.status in {"COMPLETED", "CANCELLED"}:
            raise ValueError(f"Run cannot be cancelled from {run.status}")
        run.status = "CANCELLED"
        run.completed_at = utc_now()
        for job in run.jobs:
            if job.status in {"PENDING", "PAUSED", "WAITING_RATE_LIMIT", "WAITING_CREDENTIAL"}:
                job.status = "CANCELLED"
        self.session.flush()
        return run

    def retry(self, run_uid: str) -> LeadRun:
        run = self._run(run_uid)
        retryable = [job for job in run.jobs if job.status in {"FAILED", "PARTIAL"}]
        if not retryable:
            raise ValueError("Run has no failed or partial jobs to retry")
        for job in retryable:
            job.status = "PENDING"
            job.error = None
        run.status = "PENDING"
        run.completed_at = None
        self.session.flush()
        return run

    def list_runs(self, offset: int, limit: int) -> dict[str, Any]:
        rows, total = self.repository.list_runs(offset=offset, limit=limit)
        return {"items": [self.run_dict(row) for row in rows], "total": total, "offset": offset, "limit": limit}

    def get_run(self, run_uid: str) -> dict[str, Any]:
        return self.run_dict(self._run(run_uid), include_jobs=True)

    def list_leads(self, **filters: Any) -> dict[str, Any]:
        rows, total = self.repository.query_leads(**filters)
        return {"items": [self.lead_summary(row) for row in rows], "total": total, "offset": filters["offset"], "limit": filters["limit"]}

    def get_lead(self, lead_uid: str) -> dict[str, Any]:
        lead = self.repository.get_lead(lead_uid)
        if lead is None:
            raise NotFoundError(f"Lead {lead_uid} was not found")
        canonical = {column.name: getattr(lead, column.name) for column in lead.__table__.columns}
        canonical.pop("id", None)
        return {
            "canonical": canonical,
            "source_records": [{column.name: getattr(record, column.name) for column in record.__table__.columns if column.name not in {"id", "lead_id"}} for record in lead.source_records],
            "dedupe_history": [{column.name: getattr(event, column.name) for column in event.__table__.columns if column.name not in {"id", "lead_id"}} for event in lead.dedupe_events],
            "score_explanation": lead.score_explanation,
            "provenance": lead.provenance,
        }

    def stats(self) -> dict[str, Any]:
        return self.repository.stats()

    def _run(self, run_uid: str) -> LeadRun:
        run = self.repository.get_run(run_uid)
        if run is None:
            raise NotFoundError(f"Lead run {run_uid} was not found")
        return run

    @staticmethod
    def lead_summary(lead: Lead) -> dict[str, Any]:
        return {
            "lead_uid": lead.lead_uid,
            "business": lead.business_name_raw,
            "category": lead.category_id,
            "fit_class": lead.fit_class,
            "governorate": lead.governorate,
            "city": lead.city,
            "phone": lead.phone_normalized or lead.phone_raw,
            "website": lead.website,
            "source": lead.source_id,
            "score": lead.fit_score,
            "freshness": lead.source_last_seen_at,
            "verification": "VERIFIED" if lead.last_verified_at else "UNVERIFIED",
        }

    @staticmethod
    def run_dict(run: LeadRun, include_jobs: bool = False) -> dict[str, Any]:
        result = {column.name: getattr(run, column.name) for column in run.__table__.columns if column.name != "id"}
        if include_jobs:
            result["jobs"] = [
                {column.name: getattr(job, column.name) for column in job.__table__.columns if column.name not in {"id", "run_id"}}
                for job in sorted(run.jobs, key=lambda item: item.id)
            ]
        completed = sum(1 for job in run.jobs if job.status == "COMPLETED") if run.jobs else 0
        result["progress_percent"] = round(completed * 100 / run.planned_jobs, 2) if run.planned_jobs else 0
        return result
