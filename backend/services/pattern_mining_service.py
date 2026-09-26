"""Deterministic multi-level pattern mining over comparable Content DNA cohorts."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import mean, median
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.core.config import Settings, get_settings
from backend.core.enums import (
    EvidenceType,
    PatternStability,
    PatternStatus,
    PatternType,
)
from backend.core.exceptions import NotFoundError
from backend.db.base import utc_now
from backend.db.models.pattern_recipe import ContentDNA, Pattern
from backend.repositories.content_dna_repository import ContentDNARepository
from backend.repositories.content_repository import ContentRepository
from backend.repositories.pattern_repository import PatternRepository
from backend.schemas.pattern_recipe import PatternFilters, PatternMineRequest
from backend.schemas.pattern_recipe import PatternResponse
from backend.services.content_dna_service import ContentDNAService
from backend.services.pattern_config import PatternConfig, load_pattern_config
from backend.services.pattern_scoring_service import PatternScoringService


@dataclass
class Candidate:
    name: str
    pattern_type: PatternType
    definition: dict[str, Any]
    features: list[dict[str, Any]]
    occurrences: list[ContentDNA]


class PatternMiningService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        config: PatternConfig | None = None,
    ) -> None:
        self._session = session
        self.settings = settings or get_settings()
        self.config = config or load_pattern_config()
        self.dna = ContentDNARepository(session)
        self.content = ContentRepository(session)
        self.patterns = PatternRepository(session)
        self.scoring = PatternScoringService(self.config)

    def mine(self, request: PatternMineRequest):
        started = utc_now()
        run = self.patterns.create_run(
            run_uid=f"PMR_{uuid4().hex.upper()}",
            filters=request.model_dump(mode="json", exclude_none=True),
            started_at=started,
            engine_version=self.settings.pattern_engine_version,
        )
        errors: list[dict[str, str]] = []
        content_ids = self._resolve_content_ids(request.content_ids, errors)
        filters = PatternFilters.model_validate(request.model_dump(exclude={"content_ids"}))
        dnas = self.dna.list_latest(filters, content_ids=content_ids)
        if request.content_ids:
            have = {dna.content_id for dna in dnas}
            for content_id in content_ids or []:
                if content_id not in have:
                    try:
                        ContentDNAService(self._session, settings=self.settings).generate(content_id)
                    except Exception as exc:
                        errors.append(_error(content_id, exc))
            dnas = self.dna.list_latest(filters, content_ids=content_ids)
        run.contents_processed = len(dnas)

        found: list[Pattern] = []
        rejected = 0
        for cohort_key, cohort in _cohorts(dnas).items():
            if len(cohort) < self.config.thresholds.minimum_sample_size:
                continue
            try:
                candidates = self._candidates(cohort)
                for candidate in candidates:
                    if not self._supported(candidate, len(cohort)):
                        rejected += 1
                        continue
                    try:
                        with self._session.begin_nested():
                            pattern = self._persist(
                                run.id,
                                cohort_key,
                                cohort,
                                candidate,
                                request.performance_metric,
                                filters,
                            )
                        found.append(pattern)
                    except Exception as exc:
                        errors.append(_error(candidate.name, exc))
            except Exception as exc:
                errors.append(_error(str(cohort_key), exc))

        run.patterns_found = len(found)
        run.patterns_rejected_low_support = rejected
        run.errors = errors or None
        run.finished_at = utc_now()
        self._session.flush()
        run.patterns = found
        return run

    def get(self, identifier: int | str) -> Pattern:
        pattern = self.patterns.get(identifier)
        if pattern is None:
            raise NotFoundError(f"Pattern {identifier} was not found")
        return pattern

    def list(self, **filters) -> list[Pattern]:
        return self.patterns.list(**filters)

    def explain(self, identifier: int | str) -> dict[str, Any]:
        pattern = self.get(identifier)
        evidence = [
            {
                "content_id": link.content_id,
                "dna_id": link.dna_id,
                "segment_id": link.segment_id,
                "shot_id": link.shot_id,
                "analysis_result_id": link.analysis_result_id,
                "confidence": link.confidence,
                "evidence": link.evidence,
            }
            for link in pattern.content_links
        ]
        association = pattern.performance_summary
        explanation = {
            "definition": pattern.feature_definition,
            "support": f"{pattern.support_count} / {pattern.feature_definition.get('cohort_size')} contents",
            "performance_association": association,
            "causality_warning": (
                "This is an observed association, not causation."
                if association else "No performance evidence is available; this is structural only."
            ),
            "confidence": pattern.confidence,
            "operational_ranking_score": pattern.pattern_score,
        }
        return {
            **PatternResponse.model_validate(pattern).model_dump(),
            "evidence": evidence,
            "explanation": explanation,
        }

    def _resolve_content_ids(self, identifiers, errors) -> list[int] | None:
        if identifiers is None:
            return None
        resolved = []
        for identifier in dict.fromkeys(identifiers):
            item = (
                self.content.get(int(identifier))
                if isinstance(identifier, int) or str(identifier).isdigit()
                else self.content.get_by_uid(str(identifier))
            )
            if item is None:
                errors.append({"content_id": str(identifier), "error_type": "NotFoundError", "message": "Content was not found"})
            else:
                resolved.append(item.id)
        return resolved

    def _candidates(self, cohort: list[ContentDNA]) -> list[Candidate]:
        buckets: dict[tuple, list[ContentDNA]] = defaultdict(list)
        definitions: dict[tuple, tuple[str, PatternType, dict, list[dict]]] = {}
        threshold = self.config.thresholds
        for dna in cohort:
            vector = dna.feature_vector
            hook = vector.get("hook_type")
            if hook:
                _add(buckets, definitions, ("hook", hook), dna, f"{hook} hook", PatternType.HOOK, {"feature": "hook_type", "operator": "equals", "value": hook}, [("hook_type", hook, "copy")])
            sequence = tuple(vector.get("segment_sequence") or [])
            if sequence:
                _add(buckets, definitions, ("sequence", sequence), dna, " → ".join(sequence), PatternType.SEQUENCE, {"feature": "segment_sequence", "operator": "equals", "value": list(sequence)}, [("segment_sequence", list(sequence), "structure")])
            reveal = vector.get("product_reveal_position")
            if reveal is not None and reveal <= threshold.early_position_max:
                definition = {"feature": "product_reveal_position", "operator": "lte", "value": threshold.early_position_max}
                _add(buckets, definitions, ("timing", "early_product"), dna, "Early product reveal", PatternType.TIMING, definition, [("product_reveal_position", reveal, "visual")])
            average_shot = vector.get("average_shot_length_ms")
            if average_shot is not None and average_shot <= threshold.fast_cut_max_average_ms:
                definition = {"feature": "average_shot_length_ms", "operator": "lte", "value": threshold.fast_cut_max_average_ms}
                _add(buckets, definitions, ("editing", "fast_cuts"), dna, "Fast editing pace", PatternType.EDITING, definition, [("average_shot_length_ms", average_shot, "editing")])
            cta = vector.get("cta_type")
            if cta:
                _add(buckets, definitions, ("cta", cta), dna, f"{cta} CTA", PatternType.CTA, {"feature": "cta_type", "operator": "equals", "value": cta}, [("cta_type", cta, "copy")])
            energy = vector.get("audio_energy")
            if average_shot is not None and average_shot <= threshold.fast_cut_max_average_ms and energy is not None and energy >= 0.65:
                definition = {"all": [{"feature": "average_shot_length_ms", "operator": "lte", "value": threshold.fast_cut_max_average_ms}, {"feature": "audio_energy", "operator": "gte", "value": 0.65}]}
                _add(buckets, definitions, ("cross_modal", "fast_high_energy"), dna, "Fast cuts with high-energy audio", PatternType.CROSS_MODAL, definition, [("average_shot_length_ms", average_shot, "editing"), ("audio_energy", energy, "audio")])
            if hook == "question" and reveal is not None and reveal <= threshold.early_position_max and average_shot is not None and average_shot <= threshold.fast_cut_max_average_ms:
                definition = {"all": [{"feature": "hook_type", "operator": "equals", "value": "question"}, {"feature": "product_reveal_position", "operator": "lte", "value": threshold.early_position_max}, {"feature": "average_shot_length_ms", "operator": "lte", "value": threshold.fast_cut_max_average_ms}]}
                _add(buckets, definitions, ("combination", "question_early_fast"), dna, "Question hook + early product + fast pace", PatternType.STRUCTURE, definition, [("hook_type", hook, "copy"), ("product_reveal_position", reveal, "visual"), ("average_shot_length_ms", average_shot, "editing")])
        return [
            Candidate(definitions[key][0], definitions[key][1], definitions[key][2], definitions[key][3], occurrences)
            for key, occurrences in buckets.items()
        ]

    def _supported(self, candidate: Candidate, cohort_size: int) -> bool:
        count = len(candidate.occurrences)
        return (
            count >= self.config.thresholds.min_pattern_support_count
            and count / cohort_size >= self.config.thresholds.min_pattern_support_ratio
        )

    def _persist(self, run_id, cohort_key, cohort, candidate, requested_metric, filters):
        support_count = len(candidate.occurrences)
        support_ratio = support_count / len(cohort)
        confidences = [_candidate_confidence(dna, candidate) for dna in candidate.occurrences]
        confidence = mean(confidences) if confidences else 0.0
        performance = _performance_association(cohort, candidate.occurrences, requested_metric)
        score = self.scoring.score(
            support_ratio=support_ratio,
            confidences=confidences,
            performance_association=(performance or {}).get("relative_lift"),
            recency_score=_recency(candidate.occurrences),
        )
        evidence_type = EvidenceType.CORRELATED if performance else EvidenceType.OBSERVED
        if confidence < self.config.thresholds.min_confidence:
            status = PatternStatus.LOW_CONFIDENCE
        elif performance:
            status = PatternStatus.PERFORMANCE_ASSOCIATED
        else:
            status = PatternStatus.STRUCTURAL
        definition = {**candidate.definition, "cohort_size": len(cohort)}
        scope = _scope(cohort_key)
        if filters.creator_id is not None:
            scope["creator_id"] = filters.creator_id
        fingerprint = hashlib.sha256(json.dumps({"scope": scope, "definition": definition}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        occurrences = candidate.occurrences
        dates = [_published(dna) for dna in occurrences if _published(dna) is not None]
        feature_rows = [
            {
                "feature_name": name,
                "value": value,
                "modality": modality,
                "confidence": confidence,
                "evidence": {"definition": definition},
            }
            for name, value, modality in candidate.features
        ]
        links = [
            {
                "content_id": dna.content_id,
                "dna_id": dna.id,
                "segment_id": _evidence_ref(dna, "segment_id"),
                "shot_id": _evidence_ref(dna, "shot_id"),
                "analysis_result_id": _evidence_ref(dna, "analysis_result_id"),
                "confidence": _candidate_confidence(dna, candidate),
                "evidence": {"matched_definition": definition, "dna_uid": dna.dna_uid},
            }
            for dna in occurrences
        ]
        return self.patterns.upsert(
            mining_run_id=run_id,
            pattern_uid=f"PAT_{uuid4().hex.upper()}",
            name=candidate.name,
            pattern_type=candidate.pattern_type,
            fingerprint=fingerprint,
            scope=scope,
            feature_definition=definition,
            support_count=support_count,
            support_ratio=support_ratio,
            confidence=confidence,
            performance_summary=performance,
            evidence_type=evidence_type,
            support_score=score.support_score,
            confidence_score=score.confidence_score,
            performance_score=score.performance_score,
            consistency_score=score.consistency_score,
            recency_score=score.recency_score,
            pattern_score=score.pattern_score,
            stability=_stability(occurrences, self.config.thresholds.minimum_sample_size),
            status=status,
            first_seen=min(dates) if dates else None,
            last_seen=max(dates) if dates else None,
            analysis_version=occurrences[0].analysis_version,
            taxonomy_version=occurrences[0].taxonomy_version,
            pattern_engine_version=self.settings.pattern_engine_version,
            features=feature_rows,
            links=links,
        )


def _add(buckets, definitions, key, dna, name, pattern_type, definition, features):
    buckets[key].append(dna)
    definitions[key] = (name, pattern_type, definition, features)


def _cohorts(dnas: list[ContentDNA]):
    result = defaultdict(list)
    for dna in dnas:
        identity = dna.identity
        duration_bucket = None if dna.duration_ms is None else f"{dna.duration_ms // 15000 * 15}-{dna.duration_ms // 15000 * 15 + 15}s"
        key = (
            identity.get("platform"), dna.content_type, identity.get("category"),
            identity.get("language"), identity.get("country"), duration_bucket,
            identity.get("traffic_type", "unknown"), identity.get("creator_size_bucket"),
            identity.get("publication_period"),
        )
        result[key].append(dna)
    return result


def _scope(key):
    labels = (
        "platform", "content_type", "category", "language", "country",
        "duration_bucket", "traffic_type", "creator_size_bucket", "publication_period",
    )
    return dict(zip(labels, key, strict=True))


def _metric(dna: ContentDNA, requested: str | None):
    metrics = dna.performance.get("normalized_metrics", {})
    if requested:
        return requested, metrics.get(requested)
    for name in ("completion_rate", "average_watch_time_ratio", "share_rate", "save_rate", "like_rate", "comment_rate"):
        if metrics.get(name) is not None:
            return name, metrics[name]
    return None, None


def _performance_association(cohort, occurrences, requested):
    selected = {dna.id for dna in occurrences}
    supported = []
    comparison = []
    metric_name = requested
    for dna in cohort:
        name, value = _metric(dna, requested)
        metric_name = metric_name or name
        if value is None:
            continue
        (supported if dna.id in selected else comparison).append(float(value))
    if not metric_name or not supported or not comparison:
        return None
    support_median = median(supported)
    cohort_median = median(comparison)
    lift = support_median - cohort_median
    relative = lift / abs(cohort_median) if cohort_median else lift
    return {
        "metric_name": metric_name,
        "support_median": support_median,
        "comparison_median": cohort_median,
        "absolute_difference": lift,
        "relative_lift": relative,
        "sample_with_metric": len(supported),
        "comparison_with_metric": len(comparison),
        "association_only": True,
    }


def _published(dna):
    value = dna.identity.get("published_at")
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _recency(dnas):
    dates = [_published(dna) for dna in dnas if _published(dna)]
    if not dates:
        return 0.5
    latest = max(dates)
    latest = latest if latest.tzinfo else latest.replace(tzinfo=UTC)
    age_days = max(0, (datetime.now(UTC) - latest).days)
    return max(0.0, 1.0 - age_days / 365)


def _stability(dnas, minimum):
    if len(dnas) < minimum * 2:
        return PatternStability.INSUFFICIENT_DATA
    dates = [_published(dna) for dna in dnas if _published(dna)]
    if len(dates) < minimum:
        return PatternStability.EMERGING
    return PatternStability.STABLE if (max(dates) - min(dates)).days >= 14 else PatternStability.EMERGING


def _evidence_ref(dna, key):
    for item in dna.provenance.get("evidence", []):
        if item.get(key) is not None:
            return item[key]
    return None


def _error(identifier, exc):
    return {"item": str(identifier), "error_type": type(exc).__name__, "message": "Item could not be processed safely"}


def _candidate_confidence(dna: ContentDNA, candidate: Candidate) -> float:
    field_confidence = dna.feature_vector.get("feature_confidence", {})
    values = [field_confidence[name] for name, _, _ in candidate.features if name in field_confidence]
    return mean(values) if values else dna.confidence
