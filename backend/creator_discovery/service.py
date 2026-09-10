"""Creator Discovery orchestration, review, merge, refresh, and export."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.enums import AnalysisMode, ContentType, Platform
from backend.core.exceptions import ConflictError, NotFoundError
from backend.creator_discovery.analysis import EvidenceOnlyCreatorAnalyzer
from backend.creator_discovery.config import get_creator_discovery_config
from backend.creator_discovery.connectors import (
    CreatorDiscoveryConnectorRegistry,
    DiscoveredCandidate,
    DiscoveredContent,
)
from backend.creator_discovery.meta import MetaApiError
from backend.creator_discovery.export import build_csv, build_xlsx
from backend.creator_discovery.matching import IdentityMatcher
from backend.creator_discovery.normalization import normalize_creator_name, normalize_discovery_input
from backend.creator_discovery.quality import (
    aggregate_connector_requirement,
    analysis_is_ready,
    collection_status,
    data_completeness,
)
from backend.db.base import utc_now
from backend.db.models.creator import Creator
from backend.db.models.creator_discovery import CreatorCandidate, CreatorDiscoveryProfile
from backend.repositories.content_repository import ContentRepository
from backend.repositories.creator_discovery_repository import CreatorDiscoveryRepository
from backend.repositories.creator_repository import CreatorRepository
from backend.repositories.platform_account_repository import PlatformAccountRepository
from backend.schemas.analysis import AnalysisOptions
from backend.schemas.content import NormalizedContent
from backend.schemas.creator_discovery import (
    CandidateDecisionRequest,
    CreatorDiscoveryRunRequest,
    CreatorExportRequest,
    CreatorProfileUpdate,
    CreatorRefreshRequest,
    DiscoveryPlatform,
)
from backend.services.analysis_service import UniversalContentAnalyzer
from backend.services.normalization import AccountNormalizer


class CreatorDiscoveryService:
    def __init__(
        self,
        session: Session,
        *,
        connectors: CreatorDiscoveryConnectorRegistry | None = None,
    ) -> None:
        self.session = session
        self.config = get_creator_discovery_config()
        self.repository = CreatorDiscoveryRepository(session)
        self.creators = CreatorRepository(session)
        self.core_accounts = PlatformAccountRepository(session)
        self.content = ContentRepository(session)
        self.connectors = connectors or CreatorDiscoveryConnectorRegistry()
        self.matcher = IdentityMatcher(self.config.matching)
        self.analyzer = EvidenceOnlyCreatorAnalyzer(self.config)
        self._sync_industries()

    def connector_capabilities(self) -> list[dict[str, Any]]:
        return self.connectors.capabilities()

    def meta_connection_status(self, *, force: bool = False) -> dict[str, Any]:
        return self.connectors.meta_status(force=force)

    def create_run(self, request: CreatorDiscoveryRunRequest):
        if len(request.inputs) > self.config.execution.max_inputs_per_run:
            raise ValueError(f"A run supports at most {self.config.execution.max_inputs_per_run} inputs")
        run = self.repository.create_run({
            "run_uid": f"CDRUN_{uuid4().hex.upper()}",
            "status": "PENDING",
            "input_count": len(request.inputs),
            "platforms": [item.value for item in request.platforms],
            "options": request.model_dump(mode="json", exclude={"inputs", "platforms"}),
            "warnings": [],
            "errors": [],
        })
        for value in request.inputs:
            job_platforms = [item.value for item in request.platforms]
            try:
                normalized = normalize_discovery_input(value)
                if normalized.platform and normalized.platform.value not in job_platforms:
                    job_platforms.insert(0, normalized.platform.value)
                values = {
                    "normalized_input": normalized.normalized,
                    "input_kind": normalized.kind,
                    "status": "PENDING",
                }
            except Exception as exc:
                values = {
                    "normalized_input": "",
                    "input_kind": "INVALID",
                    "status": "FAILED",
                    "error": str(exc)[:500],
                }
            self.repository.create_job({
                "job_uid": f"CDJOB_{uuid4().hex.upper()}",
                "run_id": run.id,
                "input_value": value,
                "platforms": job_platforms,
                "checkpoint": {"platform_index": 0, "platform_status": {}},
                **values,
            })
        self._refresh_run_counts(run)
        if request.execute:
            self._execute(run)
        return self.repository.get_run(run.run_uid)

    def list_runs(self, offset: int, limit: int) -> dict[str, Any]:
        items, total = self.repository.list_runs(offset, limit)
        return {"items": items, "total": total, "offset": offset, "limit": limit}

    def get_run(self, run_uid: str):
        run = self.repository.get_run(run_uid)
        if run is None:
            raise NotFoundError(f"Creator discovery run {run_uid} was not found")
        return run

    def pause_run(self, run_uid: str):
        run = self.get_run(run_uid)
        if run.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            raise ConflictError(f"Run in {run.status} status cannot be paused")
        run.status = "PAUSED"
        self.session.flush()
        return run

    def resume_run(self, run_uid: str):
        run = self.get_run(run_uid)
        if run.status == "CANCELLED":
            raise ConflictError("Cancelled runs cannot be resumed")
        self._execute(run)
        return self.repository.get_run(run_uid)

    def retry_run(self, run_uid: str):
        run = self.get_run(run_uid)
        for job in run.jobs:
            if job.status == "FAILED":
                job.status = "PENDING"
                job.error = None
        run.completed_at = None
        self.session.flush()
        self._execute(run)
        return self.repository.get_run(run_uid)

    def cancel_run(self, run_uid: str):
        run = self.get_run(run_uid)
        if run.status == "COMPLETED":
            raise ConflictError("Completed runs cannot be cancelled")
        run.status = "CANCELLED"
        run.completed_at = utc_now()
        self.session.flush()
        return run

    def list_candidates(
        self,
        *,
        offset: int,
        limit: int,
        run_uid: str | None,
        platform: str | None,
        review_status: str | None,
        classification: str | None,
    ) -> dict[str, Any]:
        rows, total = self.repository.list_candidates(
            offset=offset, limit=limit, run_uid=run_uid, platform=platform,
            review_status=review_status, classification=classification,
        )
        return {"items": rows, "total": total, "offset": offset, "limit": limit}

    def confirm_candidate(self, candidate_uid: str, decision: CandidateDecisionRequest) -> dict[str, Any]:
        candidate = self._candidate(candidate_uid)
        if candidate.review_status in {"CONFIRMED", "MERGED", "KEPT_SEPARATE"} and candidate.creator_id:
            profile = self.repository.get_profile_by_creator(candidate.creator_id)
            return self.profile_detail(profile.profile_uid)  # type: ignore[union-attr]
        run = self.repository.get_run(candidate.run_id)
        options = (run.options if run else {}) or {}
        existing_account = self.repository.find_account(candidate.platform, candidate.profile_url)
        existing_core_creator = self._existing_core_creator(candidate)
        if decision.action == "MERGE":
            profile = self.repository.get_profile_by_creator_uid(decision.creator_uid or "")
            if profile is None:
                raise NotFoundError(f"Creator {decision.creator_uid} was not found")
            creator = self.session.get(Creator, profile.creator_id)
        elif existing_account is not None:
            if decision.action == "KEEP_SEPARATE":
                raise ConflictError("The exact platform profile URL already belongs to a creator")
            creator = self.session.get(Creator, existing_account.creator_id)
            profile = self.repository.get_profile_by_creator(existing_account.creator_id)
        elif existing_core_creator is not None:
            if decision.action == "KEEP_SEPARATE":
                raise ConflictError("The exact platform identity already belongs to a Creator Master record")
            creator = existing_core_creator
            profile = self.repository.get_profile_by_creator(creator.id)
        else:
            creator = self._new_creator(candidate)
            profile = None
        if creator is None:
            raise NotFoundError("The selected creator no longer exists")
        if profile is None:
            profile = self.repository.create_profile({
                "profile_uid": f"CDP_{uuid4().hex.upper()}",
                "creator_id": creator.id,
                "normalized_name": normalize_creator_name(creator.display_name),
                "match_confidence": candidate.confidence,
                "provenance": list(candidate.provenance),
                "history": [{"action": "CREATED_FROM_CANDIDATE", "candidate_uid": candidate.candidate_uid, "at": utc_now().isoformat()}],
            })
        account = self._upsert_discovery_account(
            creator, candidate, update_existing=bool(options.get("update_existing_profiles")),
        )
        self._mirror_core_account(
            creator, candidate, update_existing=bool(options.get("update_existing_profiles")),
        )
        setattr(profile, f"{candidate.platform}_url", candidate.profile_url)
        profile.match_confidence = max(profile.match_confidence, candidate.confidence)
        profile.provenance = [*profile.provenance, *candidate.provenance]
        profile.history = [*profile.history, {
            "action": decision.action,
            "candidate_uid": candidate.candidate_uid,
            "platform": candidate.platform,
            "at": utc_now().isoformat(),
        }]
        candidate.creator_id = creator.id
        candidate.review_status = {
            "THIS_IS_THE_ACCOUNT": "CONFIRMED", "MERGE": "MERGED", "KEEP_SEPARATE": "KEPT_SEPARATE",
        }[decision.action]
        candidate.classification = "CONFIRMED"
        self._record_candidate_sources(profile, candidate)
        if options.get("analyze_content", True):
            connector = self.connectors.get(candidate.platform)
            discovered = DiscoveredCandidate(
                platform=DiscoveryPlatform(candidate.platform), profile_url=candidate.profile_url,
                display_name=candidate.display_name, username=candidate.username,
                public_bio=candidate.public_bio, public_avatar_url=candidate.public_avatar_url,
                followers=candidate.followers, following=candidate.following,
                content_count=candidate.content_count, verified=candidate.verified,
                discovery_source=candidate.discovery_source, source_id=candidate.source_id,
                profile_data=candidate.profile_data, provenance=candidate.provenance,
            )
            try:
                samples = connector.collect_recent(discovered, int(options.get("content_sample_size", 10)))
            except Exception as exc:
                samples = []
                account.data_collection_status = "DATA_COLLECTION_REQUIRED"
                account.connector_requirement = exc.status if isinstance(exc, MetaApiError) else "API_ERROR"
                error = exc.safe_message if isinstance(exc, MetaApiError) else "Content sampling failed."
                profile.history = [*profile.history, {"action": "CONTENT_SAMPLE_FAILED", "platform": candidate.platform, "error": error, "at": utc_now().isoformat()}]
            for sample in samples:
                self._persist_sample(creator, account, sample)
        self._refresh_collection_state(profile)
        self._reanalyze(profile, execute=bool(options.get("analyze_content", True)))
        self.session.flush()
        return self.profile_detail(profile.profile_uid)

    def reject_candidate(self, candidate_uid: str) -> CreatorCandidate:
        candidate = self._candidate(candidate_uid)
        candidate.review_status = "REJECTED"
        candidate.classification = "REJECTED"
        self.session.flush()
        run = self.repository.get_run(candidate.run_id)
        if run:
            self._refresh_run_counts(run)
        return candidate

    def list_profiles(self, **filters: Any) -> dict[str, Any]:
        offset = int(filters.pop("offset"))
        limit = int(filters.pop("limit"))
        rows, total = self.repository.list_profiles(offset=offset, limit=limit, **filters)
        return {
            "items": [self._profile_summary(profile, creator) for profile, creator in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    def profile_detail(self, profile_uid: str) -> dict[str, Any]:
        profile = self.repository.get_profile(profile_uid)
        if profile is None:
            profile = self.repository.get_profile_by_creator_uid(profile_uid)
        if profile is None:
            raise NotFoundError(f"Creator profile {profile_uid} was not found")
        creator = self.session.get(Creator, profile.creator_id)
        if creator is None:
            raise NotFoundError("Creator Master record was not found")
        accounts = self.repository.accounts_for_creator(creator.id)
        samples = self.repository.samples_for_creator(creator.id)
        analyses = self.repository.analyses_for_profile(profile.id)
        sources = self.repository.sources_for_profile(profile.id)
        candidates = list(self.session.scalars(select(CreatorCandidate).where(CreatorCandidate.creator_id == creator.id).order_by(CreatorCandidate.id.desc())))
        meta_accounts = [item for item in accounts if item.platform in {"instagram", "facebook"}]
        last_meta_refresh = max(
            (item.last_seen_at for item in meta_accounts if item.source == "meta_api" and item.last_seen_at),
            default=None,
        )
        return {
            "unified_profile": self._profile_summary(profile, creator),
            "platform_accounts": [self._account_payload(item) for item in accounts],
            "content_samples": [self._sample_payload(item) for item in samples],
            "analysis": [self._analysis_payload(item) for item in analyses],
            "match_evidence": [self._candidate_payload(item) for item in candidates],
            "provenance": [self._source_payload(item) for item in sources],
            "history": profile.history,
            "meta_connector_status": self.meta_connection_status(),
            "identity_match": {
                "status": profile.identity_status,
                "confidence": profile.match_confidence,
            },
            "last_api_refresh": last_meta_refresh.isoformat() if last_meta_refresh else None,
            "api_requirement_problem": (
                profile.connector_requirement if profile.connector_requirement != "NONE" else None
            ),
        }

    def update_profile(self, profile_uid: str, update: CreatorProfileUpdate) -> dict[str, Any]:
        profile = self.repository.get_profile(profile_uid)
        if profile is None:
            raise NotFoundError(f"Creator profile {profile_uid} was not found")
        values = update.model_dump(exclude_unset=True, mode="json")
        for field in ("niche", "industry", "main_platform", "content_mechanism_style", "kpi_impact"):
            if field in values and values[field] is None:
                values[field] = "UNKNOWN"
        if "industry" in values and values["industry"] != "UNKNOWN":
            allowed = {item.name.casefold() for item in self.repository.list_industries()}
            if values["industry"].casefold() not in allowed:
                raise ValueError("Industry is not present in the Creator Discovery taxonomy")
        for field, value in values.items():
            setattr(profile, field, value)
            self.repository.add_source({
                "source_uid": f"CDSRC_{uuid4().hex.upper()}", "profile_id": profile.id,
                "field_name": field, "source": "operator_manual_correction",
                "value": {"value": value}, "confidence": 1.0,
            })
        profile.history = [*profile.history, {"action": "MANUAL_CORRECTION", "fields": sorted(values), "at": utc_now().isoformat()}]
        self.session.flush()
        return self.profile_detail(profile_uid)

    def refresh_profile(self, profile_uid: str, request: CreatorRefreshRequest) -> dict[str, Any]:
        profile = self.repository.get_profile(profile_uid)
        if profile is None:
            raise NotFoundError(f"Creator profile {profile_uid} was not found")
        creator = self.session.get(Creator, profile.creator_id)
        requested_platforms = {item.value for item in request.platforms} if request.platforms else {
            item.value for item in DiscoveryPlatform
        }
        statuses: dict[str, str] = {}
        accounts = self.repository.accounts_for_creator(profile.creator_id)
        for account in accounts:
            if account.platform not in requested_platforms:
                continue
            connector = self.connectors.get(account.platform)
            try:
                outcome = connector.discover(normalize_discovery_input(account.profile_url))
            except MetaApiError as exc:
                statuses[account.platform] = exc.status
                account.connector_requirement = exc.status
                continue
            statuses[account.platform] = outcome.status
            found = next((item for item in outcome.candidates if item.profile_url == account.profile_url), None)
            if found:
                for field in ("display_name", "username", "followers", "following", "content_count", "verified"):
                    value = getattr(found, field)
                    if value is not None:
                        setattr(account, field, value)
                if found.public_bio is not None:
                    account.bio = found.public_bio
                account.last_seen_at = utc_now()
                account.metadata_json = {**account.metadata_json, **found.profile_data}
                account.provenance = [*account.provenance, *found.provenance]
                account.connector_requirement = found.connector_requirement
                if request.analyze_content and creator:
                    try:
                        for sample in connector.collect_recent(found, request.content_sample_size):
                            self._persist_sample(creator, account, sample)
                    except MetaApiError as exc:
                        statuses[account.platform] = exc.status
                        account.connector_requirement = exc.status
                        profile.history = [*profile.history, {
                            "action": "CONTENT_SAMPLE_FAILED",
                            "platform": account.platform,
                            "error": exc.safe_message,
                            "at": utc_now().isoformat(),
                        }]
        missing_platforms = sorted(requested_platforms - {item.platform for item in accounts})
        discovery_run = None
        if missing_platforms and creator:
            discovery_run = self.create_run(CreatorDiscoveryRunRequest(
                inputs=[creator.display_name],
                platforms=[DiscoveryPlatform(item) for item in missing_platforms],
                analyze_content=request.analyze_content,
                resolve_cross_platform_identity=True,
                update_existing_profiles=True,
                content_sample_size=request.content_sample_size,
                execute=True,
            ))
            if discovery_run and discovery_run.jobs:
                statuses.update(discovery_run.jobs[0].checkpoint.get("platform_status") or {})
        self._refresh_collection_state(profile)
        if request.analyze_content:
            self._reanalyze(profile, execute=True)
        elif profile.analysis_status != "COMPLETED":
            self._reanalyze(profile, execute=False)
        profile.history = [*profile.history, {
            "action": "REFRESH",
            "platform_status": statuses,
            "discovery_run_uid": discovery_run.run_uid if discovery_run else None,
            "at": utc_now().isoformat(),
        }]
        self.session.flush()
        detail = self.profile_detail(profile_uid)
        detail["refresh_status"] = statuses
        return detail

    def export(self, request: CreatorExportRequest) -> tuple[bytes, str, str]:
        rows: list[dict[str, Any]] = []
        offset = 0
        batch_size = 5_000
        while True:
            page = self.list_profiles(
                offset=offset, limit=batch_size,
                query=None, platform=request.platform.value if request.platform else None,
                industry=request.industry, niche=request.niche,
                influence_min=request.influence_min, influence_max=request.influence_max,
                match_confidence_min=request.match_confidence_min,
                analysis_status=request.analysis_status, start_year=request.start_year,
                creator_uids=request.creator_uids or None,
            )
            rows.extend(page["items"])
            if len(page["items"]) < batch_size:
                break
            offset += len(page["items"])
        if request.format == "csv":
            return build_csv(rows, extended=request.extended), "text/csv; charset=utf-8", "creator_discovery.csv"
        return (
            build_xlsx(rows, extended=request.extended),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "creator_discovery.xlsx",
        )

    def industries(self) -> list[dict[str, Any]]:
        return [{"code": item.code, "name": item.name, "aliases": item.aliases} for item in self.repository.list_industries()]

    def _execute(self, run) -> None:
        if run.status == "CANCELLED":
            return
        run.status = "RUNNING"
        run.started_at = run.started_at or utc_now()
        run.completed_at = None
        self.session.flush()
        jobs = self.repository.pending_jobs(run.id, self.config.execution.max_inline_jobs)
        for job in jobs:
            if run.status == "PAUSED":
                break
            self._process_job(run, job)
        self._refresh_run_counts(run)
        remaining = self.repository.remaining_jobs(run.id)
        if remaining and run.status != "PAUSED":
            run.status = "PAUSED"
            warning = "Inline execution checkpoint reached; resume to process the next bounded batch."
            if warning not in run.warnings:
                run.warnings = [*run.warnings, warning]
        elif not remaining:
            statuses = {job.status for job in run.jobs}
            if statuses == {"FAILED"}:
                run.status = "FAILED"
            elif statuses & {"FAILED", "PARTIAL"}:
                run.status = "PARTIAL"
            else:
                run.status = "COMPLETED"
            run.completed_at = utc_now()
        self.session.flush()

    def _process_job(self, run, job) -> None:
        job.status = "RUNNING"
        job.attempt += 1
        job.started_at = utc_now()
        job.error = None
        self.session.flush()
        try:
            normalized = normalize_discovery_input(job.input_value)
            statuses = dict(job.checkpoint.get("platform_status") or {})
            resolved_name = job.checkpoint.get("resolved_name")
            start = int(job.checkpoint.get("platform_index", 0))
            for index, platform_name in enumerate(job.platforms[start:], start=start):
                connector = self.connectors.get(platform_name)
                direct = normalized.kind == "PROFILE_URL" and normalized.platform.value == platform_name
                query = normalized
                if normalized.kind == "PROFILE_URL" and not direct and resolved_name:
                    query = normalize_discovery_input(str(resolved_name))
                outcome = connector.discover(query)
                statuses[platform_name] = outcome.status
                requirements = {
                    raw.connector_requirement for raw in outcome.candidates
                    if raw.connector_requirement not in {"", "NONE"}
                }
                if outcome.status == "FOUND" and requirements:
                    statuses[platform_name] = sorted(requirements)[0]
                if outcome.errors:
                    run.errors = [*run.errors, {"job_uid": job.job_uid, "platform": platform_name, "errors": outcome.errors}]
                for raw in outcome.candidates:
                    if self.repository.existing_candidate(run.id, raw.platform.value, raw.profile_url):
                        continue
                    direct_candidate = direct and normalized.url == raw.profile_url
                    if direct_candidate and raw.display_name:
                        resolved_name = raw.display_name
                    match_payload = raw.as_match_payload()
                    if normalized.url and not direct_candidate:
                        match_payload["reference_social_urls"] = [normalized.url]
                    result = self.matcher.match(
                        str(resolved_name or job.input_value), match_payload, direct_url=direct_candidate,
                    )
                    candidate = self.repository.create_candidate({
                        "candidate_uid": f"CDC_{uuid4().hex.upper()}", "run_id": run.id, "job_id": job.id,
                        "platform": raw.platform.value, "display_name": raw.display_name,
                        "normalized_name": normalize_creator_name(raw.display_name or "") or None,
                        "username": raw.username, "profile_url": raw.profile_url,
                        "public_bio": raw.public_bio, "public_avatar_url": raw.public_avatar_url,
                        "followers": raw.followers, "following": raw.following, "content_count": raw.content_count,
                        "verified": raw.verified, "discovery_source": raw.discovery_source,
                        "source_id": raw.source_id, "confidence": result.confidence,
                        "classification": result.classification.value, "review_status": "PENDING",
                        "identity_status": raw.identity_status,
                        "data_collection_status": raw.data_collection_status,
                        "data_completeness": raw.data_completeness,
                        "connector_requirement": raw.connector_requirement,
                        "profile_data": raw.profile_data, "provenance": raw.provenance,
                    })
                    for signal in result.signals:
                        self.repository.add_match_evidence({
                            "evidence_uid": f"CDME_{uuid4().hex.upper()}", "candidate_id": candidate.id,
                            "signal": signal.signal, "score": signal.score, "weight": signal.weight,
                            "contribution": signal.contribution, "evidence": signal.evidence,
                        })
                    job.candidate_count += 1
                job.checkpoint = {
                    "platform_index": index + 1,
                    "platform_status": statuses,
                    "resolved_name": resolved_name,
                }
                self.session.flush()
            partial_states = {
                "IDENTITY_RESOLVED", "DATA_COLLECTION_REQUIRED", "API_REQUIRED",
                "MANUAL_URL_REQUIRED", "NOT_CONFIGURED", "NOT_AVAILABLE", "API_ERROR",
            }
            job.status = "PARTIAL" if any(value in partial_states for value in statuses.values()) else "COMPLETED"
        except Exception as exc:
            job.status = "FAILED"
            job.error = str(exc)[:500]
            run.errors = [*run.errors, {"job_uid": job.job_uid, "error": str(exc)[:500]}]
        finally:
            job.completed_at = utc_now()
            self.session.flush()

    def _refresh_run_counts(self, run) -> None:
        self.session.flush()
        jobs = list(run.jobs)
        run.processed = sum(job.status in {"COMPLETED", "PARTIAL", "FAILED"} for job in jobs)
        run.matched = sum(job.candidate_count for job in jobs)
        run.failed = sum(job.status == "FAILED" for job in jobs)
        run.review_required = int(self.session.scalar(
            select(func.count()).select_from(CreatorCandidate).where(
                CreatorCandidate.run_id == run.id, CreatorCandidate.review_status == "PENDING"
            )
        ) or 0)

    def _candidate(self, candidate_uid: str) -> CreatorCandidate:
        candidate = self.repository.get_candidate(candidate_uid)
        if candidate is None:
            raise NotFoundError(f"Creator candidate {candidate_uid} was not found")
        return candidate

    def _new_creator(self, candidate: CreatorCandidate) -> Creator:
        name = candidate.display_name or candidate.username or candidate.profile_url
        creator = self.creators.create({
            "display_name": name[:255], "category": None, "country": None,
            "primary_language": None, "notes": "Created by Creator Discovery Studio",
            "priority": 0, "active": True, "possible_duplicate": False,
        })
        matches = [item for item in self.creators.possible_name_matches(name, None) if item.id != creator.id]
        if matches:
            creator.possible_duplicate = True
            self.creators.mark_possible_duplicates({creator.id, *(item.id for item in matches)})
        return creator

    def _upsert_discovery_account(
        self,
        creator: Creator,
        candidate: CreatorCandidate,
        *,
        update_existing: bool,
    ):
        account = self.repository.find_account(candidate.platform, candidate.profile_url)
        if account is not None:
            if account.creator_id != creator.id:
                raise ConflictError("The exact platform profile is already attached to another creator")
            if update_existing:
                for field, candidate_field in (
                    ("display_name", "display_name"), ("username", "username"), ("followers", "followers"),
                    ("following", "following"), ("content_count", "content_count"),
                    ("bio", "public_bio"), ("verified", "verified"),
                    ("source_id", "source_id"),
                ):
                    value = getattr(candidate, candidate_field)
                    if value is not None:
                        setattr(account, field, value)
                account.source = candidate.discovery_source
                account.confidence = max(account.confidence, candidate.confidence)
                account.identity_status = candidate.identity_status
                account.data_collection_status = candidate.data_collection_status
                account.data_completeness = candidate.data_completeness
                account.connector_requirement = candidate.connector_requirement
                account.metadata_json = {**account.metadata_json, **candidate.profile_data}
                account.provenance = [*account.provenance, *candidate.provenance]
                account.last_seen_at = utc_now()
        else:
            account = self.repository.create_account({
                "account_uid": f"CDA_{uuid4().hex.upper()}", "creator_id": creator.id,
                "platform": candidate.platform, "display_name": candidate.display_name,
                "username": candidate.username,
                "profile_url": candidate.profile_url, "followers": candidate.followers,
                "following": candidate.following, "content_count": candidate.content_count,
                "bio": candidate.public_bio, "verified": candidate.verified,
                "source": candidate.discovery_source, "source_id": candidate.source_id,
                "confidence": candidate.confidence,
                "identity_status": candidate.identity_status,
                "data_collection_status": candidate.data_collection_status,
                "data_completeness": candidate.data_completeness,
                "connector_requirement": candidate.connector_requirement,
                "metadata_json": candidate.profile_data,
                "provenance": candidate.provenance,
            })
        return account

    def _mirror_core_account(
        self,
        creator: Creator,
        candidate: CreatorCandidate,
        *,
        update_existing: bool,
    ) -> None:
        supported = {
            "youtube": Platform.YOUTUBE, "facebook": Platform.FACEBOOK,
            "instagram": Platform.INSTAGRAM, "tiktok": Platform.TIKTOK, "x": Platform.X,
        }
        platform = supported.get(candidate.platform)
        if platform is None:
            return
        normalized = AccountNormalizer().normalize_account(
            platform=platform, username=candidate.username,
            profile_url=candidate.profile_url, platform_user_id=candidate.source_id,
        )
        matches = self.core_accounts.find_matches(
            platform=platform, username=normalized.username,
            profile_url=normalized.profile_url, platform_user_id=normalized.platform_user_id,
        )
        if matches:
            if any(item.creator_id != creator.id for item in matches):
                raise ConflictError("The normalized platform identity belongs to another Creator Master record")
            if update_existing:
                values = {
                    "display_name": candidate.display_name,
                    "bio": candidate.public_bio,
                    "followers_count": candidate.followers,
                    "following_count": candidate.following,
                    "content_count": candidate.content_count,
                    "verified": candidate.verified,
                }
                self.core_accounts.update(
                    matches[0], {field: value for field, value in values.items() if value is not None},
                )
            return
        self.core_accounts.create(creator.id, {
            "platform": platform, "username": normalized.username,
            "profile_url": normalized.profile_url, "platform_user_id": normalized.platform_user_id,
            "display_name": candidate.display_name, "bio": candidate.public_bio,
            "followers_count": candidate.followers, "following_count": candidate.following,
            "content_count": candidate.content_count, "verified": bool(candidate.verified),
        })

    def _persist_sample(self, creator: Creator, account, raw: DiscoveredContent) -> None:
        sample = self.repository.find_sample(raw.platform.value, raw.content_url)
        if sample is None:
            sample = self.repository.create_sample({
                "content_uid": f"CDS_{uuid4().hex.upper()}", "creator_id": creator.id,
                "account_id": account.id, "platform": raw.platform.value,
                "content_url": raw.content_url, "platform_content_id": raw.platform_content_id,
                "published_at": raw.published_at, "title": raw.title, "caption": raw.caption,
                "content_type": raw.content_type, "views": raw.views, "likes": raw.likes,
                "comments": raw.comments, "shares": raw.shares, "duration_seconds": raw.duration_seconds,
                "hashtags": raw.hashtags, "metadata_json": raw.metadata,
                "source": raw.source, "provenance": raw.provenance,
            })
        else:
            for field in ("published_at", "title", "caption", "views", "likes", "comments", "shares", "duration_seconds"):
                value = getattr(raw, field)
                if value is not None:
                    setattr(sample, field, value)
            sample.metadata_json = {**sample.metadata_json, **raw.metadata}
            sample.provenance = [*sample.provenance, *raw.provenance]
        self._mirror_core_content(creator, account, raw)

    def _existing_core_creator(self, candidate: CreatorCandidate) -> Creator | None:
        try:
            platform = Platform(candidate.platform)
        except ValueError:
            return None
        normalized = AccountNormalizer().normalize_account(
            platform=platform, username=candidate.username,
            profile_url=candidate.profile_url, platform_user_id=candidate.source_id,
        )
        matches = self.core_accounts.find_matches(
            platform=platform, username=normalized.username,
            profile_url=normalized.profile_url, platform_user_id=normalized.platform_user_id,
        )
        creator_ids = {item.creator_id for item in matches}
        if len(creator_ids) > 1:
            raise ConflictError("Platform identity resolves to multiple Creator Master records")
        return self.session.get(Creator, next(iter(creator_ids))) if creator_ids else None

    def _mirror_core_content(self, creator: Creator, discovery_account, raw: DiscoveredContent) -> None:
        try:
            platform = Platform(raw.platform.value)
        except ValueError:
            return
        core_accounts = self.core_accounts.find_matches(
            platform=platform, username=discovery_account.username,
            profile_url=discovery_account.profile_url, platform_user_id=discovery_account.source_id,
        )
        if not core_accounts:
            return
        content_type = ContentType.VIDEO if raw.content_type in {"VIDEO", "SHORT", "REEL"} else ContentType.POST
        normalized = NormalizedContent(
            platform=platform, platform_content_id=raw.platform_content_id,
            content_type=content_type, source_url=raw.content_url, canonical_url=raw.content_url,
            published_at=raw.published_at, title=raw.title, caption=raw.caption,
            hashtags=raw.hashtags, duration_ms=int(raw.duration_seconds * 1000) if raw.duration_seconds is not None else None,
            views=raw.views, likes=raw.likes, comments=raw.comments, shares=raw.shares,
            raw_metadata={"creator_discovery_source": raw.source, **raw.metadata},
        )
        result = self.content.upsert(
            normalized, creator_id=creator.id, platform_account_id=core_accounts[0].id,
            raw_storage_path=None,
        )
        try:
            UniversalContentAnalyzer(self.session).analyze_content(
                result.item.id, AnalysisOptions(mode=AnalysisMode.TEXT_ONLY)
            )
        except Exception:
            pass

    def _refresh_collection_state(self, profile: CreatorDiscoveryProfile) -> None:
        accounts = self.repository.accounts_for_creator(profile.creator_id)
        samples = self.repository.samples_for_creator(profile.creator_id)
        sample_account_ids = {item.account_id for item in samples}
        for account in accounts:
            account.data_completeness = data_completeness(
                account, has_content_samples=account.id in sample_account_ids,
            )
            account.data_collection_status = collection_status(account.data_completeness)
        profile.identity_status = "IDENTITY_RESOLVED" if accounts else "IDENTITY_PENDING"
        profile.data_completeness = max(
            (item.data_completeness for item in accounts), default=0.0,
        )
        profile.data_collection_status = (
            "DATA_COLLECTED"
            if accounts and all(item.data_collection_status == "DATA_COLLECTED" for item in accounts)
            else "DATA_COLLECTION_REQUIRED"
        )
        profile.connector_requirement = aggregate_connector_requirement(accounts)

    def _reanalyze(self, profile: CreatorDiscoveryProfile, *, execute: bool = True) -> None:
        accounts = self.repository.accounts_for_creator(profile.creator_id)
        samples = self.repository.samples_for_creator(profile.creator_id)
        if not analysis_is_ready(accounts, samples):
            connector_analysis_states = {
                "TOKEN_INVALID", "TOKEN_EXPIRED", "PERMISSION_MISSING", "RATE_LIMITED",
                "ACCOUNT_NOT_LINKED", "ACCOUNT_NOT_ACCESSIBLE", "API_UNAVAILABLE",
            }
            if profile.connector_requirement in connector_analysis_states:
                status = profile.connector_requirement
            elif profile.connector_requirement in {"API_REQUIRED", "API_ERROR", "NOT_CONFIGURED"}:
                meta_api_required = any(
                    item.platform in {"instagram", "facebook"}
                    and item.connector_requirement in {"API_REQUIRED", "NOT_CONFIGURED"}
                    for item in accounts
                )
                status = "API_REQUIRED" if meta_api_required else (
                    "COLLECTION_PENDING" if profile.connector_requirement == "API_ERROR" else "INSUFFICIENT_EVIDENCE"
                )
            elif not accounts:
                status = "COLLECTION_PENDING"
            elif profile.data_completeness <= 20:
                status = "IDENTITY_ONLY"
            elif profile.data_collection_status == "DATA_COLLECTION_REQUIRED":
                status = "COLLECTION_PENDING"
            else:
                status = "INSUFFICIENT_EVIDENCE"
            profile.analysis_status = status
            profile.history = [*profile.history, {
                "action": "ANALYSIS_SKIPPED",
                "reason": status,
                "data_completeness": profile.data_completeness,
                "content_samples": len(samples),
                "at": utc_now().isoformat(),
            }]
            return
        profile.analysis_status = "ANALYSIS_READY"
        if not execute:
            profile.history = [*profile.history, {
                "action": "ANALYSIS_READY", "at": utc_now().isoformat(),
            }]
            return
        output = self.analyzer.analyze(accounts=accounts, samples=samples)
        output["analysis_status"] = "COMPLETED"
        manual_fields = {
            field for event in profile.history if event.get("action") == "MANUAL_CORRECTION"
            for field in event.get("fields", [])
        }
        for field in (
            "niche", "industry", "main_platform", "main_platform_confidence",
            "content_mechanism_style", "influence_size", "influence_size_numeric",
            "kpi_impact", "start_year", "start_year_confidence", "start_year_source", "analysis_status",
        ):
            if field not in manual_fields:
                setattr(profile, field, output[field])
        self.repository.add_analysis({
            "analysis_uid": f"CDAI_{uuid4().hex.upper()}", "profile_id": profile.id,
            "status": output["analysis_status"], "provider": self.analyzer.provider_code,
            "model": self.analyzer.model_version, "output": output,
            "evidence_references": output["evidence_references"], "confidence": output["confidence"],
        })
        profile.history = [*profile.history, {"action": "ANALYZED", "provider": self.analyzer.provider_code, "model": self.analyzer.model_version, "at": utc_now().isoformat()}]

    def _record_candidate_sources(self, profile: CreatorDiscoveryProfile, candidate: CreatorCandidate) -> None:
        for field, value in (
            (f"{candidate.platform}_url", candidate.profile_url), ("name", candidate.display_name),
            ("followers", candidate.followers), ("bio", candidate.public_bio),
        ):
            if value is None:
                continue
            self.repository.add_source({
                "source_uid": f"CDSRC_{uuid4().hex.upper()}", "profile_id": profile.id,
                "field_name": field, "platform": candidate.platform,
                "source": candidate.discovery_source, "source_url": candidate.profile_url,
                "evidence_reference": candidate.candidate_uid, "value": {"value": value},
                "confidence": candidate.confidence / 100,
            })

    def _sync_industries(self) -> None:
        self.repository.sync_industries([
            {"code": item.code, "name": item.name, "aliases": item.keywords}
            for item in self.config.industry_taxonomy
        ])

    def _profile_summary(self, profile: CreatorDiscoveryProfile, creator: Creator) -> dict[str, Any]:
        accounts = self.repository.accounts_for_creator(creator.id)
        return {
            "profile_uid": profile.profile_uid, "creator_uid": creator.creator_uid,
            "name": creator.display_name, "normalized_name": profile.normalized_name,
            "niche": profile.niche, "industry": profile.industry,
            "main_platform": profile.main_platform, "main_platform_confidence": profile.main_platform_confidence,
            "platforms_found": [item.platform for item in accounts],
            "youtube_url": profile.youtube_url, "facebook_url": profile.facebook_url,
            "instagram_url": profile.instagram_url, "tiktok_url": profile.tiktok_url,
            "snapchat_url": profile.snapchat_url, "linkedin_url": profile.linkedin_url, "x_url": profile.x_url,
            "content_mechanism_style": profile.content_mechanism_style,
            "influence_size": profile.influence_size, "influence_size_numeric": profile.influence_size_numeric,
            "kpi_impact": profile.kpi_impact, "start_year": profile.start_year,
            "start_year_confidence": profile.start_year_confidence, "start_year_source": profile.start_year_source,
            "match_confidence": profile.match_confidence, "analysis_status": profile.analysis_status,
            "identity_status": profile.identity_status,
            "data_collection_status": profile.data_collection_status,
            "data_completeness": profile.data_completeness,
            "connector_requirement": profile.connector_requirement,
            "possible_duplicate": creator.possible_duplicate,
            "created_at": profile.created_at.isoformat(), "updated_at": profile.updated_at.isoformat(),
        }

    @staticmethod
    def _account_payload(item) -> dict[str, Any]:
        return {column.name: getattr(item, column.name) for column in item.__table__.columns}

    @staticmethod
    def _sample_payload(item) -> dict[str, Any]:
        return {column.name: getattr(item, column.name) for column in item.__table__.columns}

    @staticmethod
    def _analysis_payload(item) -> dict[str, Any]:
        return {column.name: getattr(item, column.name) for column in item.__table__.columns}

    @staticmethod
    def _source_payload(item) -> dict[str, Any]:
        return {column.name: getattr(item, column.name) for column in item.__table__.columns}

    def _candidate_payload(self, item: CreatorCandidate) -> dict[str, Any]:
        return {
            "candidate_uid": item.candidate_uid, "platform": item.platform,
            "profile_url": item.profile_url, "confidence": item.confidence,
            "classification": item.classification, "review_status": item.review_status,
            "identity_status": item.identity_status,
            "data_collection_status": item.data_collection_status,
            "data_completeness": item.data_completeness,
            "connector_requirement": item.connector_requirement,
            "signals": [{
                "signal": value.signal, "score": value.score, "weight": value.weight,
                "contribution": value.contribution, "evidence": value.evidence,
            } for value in item.match_evidence],
        }
