"""Map normalized analysis output into versioned, comparable Content DNA."""

from collections import Counter
from statistics import mean, median
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.analyzers.engine import NOT_APPLICABLE, UNKNOWN
from backend.core.config import Settings, get_settings
from backend.core.enums import AnalysisLevel, AnalysisRunStatus
from backend.core.exceptions import AnalysisError, NotFoundError
from backend.db.models.analysis import AnalysisRun
from backend.db.models.content_item import ContentItem
from backend.repositories.analysis_repository import AnalysisRepository
from backend.repositories.content_dna_repository import ContentDNARepository
from backend.repositories.content_repository import ContentRepository
from backend.schemas.pattern_recipe import DNABatchResponse
from backend.services.performance_service import PerformanceService


FUNCTIONAL_ROLES = {
    "HOOK", "CONTEXT", "PROBLEM", "PAIN", "CURIOSITY", "VALUE", "BENEFIT",
    "DEMO", "PROOF", "COMPARISON", "PRODUCT_REVEAL", "OBJECTION", "OFFER",
    "CTA", "OUTRO", "OTHER",
}


class ContentDNAService:
    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self.settings = settings or get_settings()
        self.content = ContentRepository(session)
        self.analysis = AnalysisRepository(session)
        self.repository = ContentDNARepository(session)
        self.performance = PerformanceService(session)

    def generate(self, content_identifier: int | str):
        content = self._get_content(content_identifier)
        run = self.analysis.latest_for_content(content.id)
        if run is None or run.status not in {
            AnalysisRunStatus.COMPLETED,
            AnalysisRunStatus.PARTIAL,
        }:
            raise AnalysisError(f"Content {content_identifier} has no usable analysis")
        existing = self.repository.by_analysis_run(run.id)
        if existing is not None:
            return existing
        return self._map(content, run)

    def generate_batch(self, identifiers: list[int | str]) -> DNABatchResponse:
        items = []
        failed = []
        for identifier in dict.fromkeys(identifiers):
            try:
                with self._session.begin_nested():
                    item = self.generate(identifier)
                items.append(item)
            except Exception as exc:
                failed.append(
                    {
                        "content_id": str(identifier),
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
        return DNABatchResponse(items=items, failed_items=failed)

    def get(self, content_identifier: int | str):
        content = self._get_content(content_identifier)
        dna = self.repository.latest_for_content(content.id)
        if dna is None:
            raise NotFoundError(f"Content {content_identifier} has no Content DNA")
        return dna

    def _map(self, content: ContentItem, run: AnalysisRun):
        results = [result for result in run.results if not _is_sentinel(result.value)]
        fields = {result.field: result.value for result in results}
        evidence = [
            {
                "analysis_result_id": result.id,
                "segment_id": result.segment_id,
                "shot_id": result.shot_id,
                "start_ms": result.start_ms,
                "end_ms": result.end_ms,
                "source": result.source,
                "confidence": result.confidence,
                "evidence": result.evidence,
            }
            for result in results
        ]
        sequence = _segment_sequence(run, content.duration_ms)
        shot_lengths = [shot.duration_ms for shot in run.shots if shot.duration_ms is not None]
        first_product = min(
            (event.start_ms for event in run.visual_events if event.event_type.lower() == "product_reveal" and event.start_ms is not None),
            default=None,
        )
        cta_result = next((item for item in results if item.field == "cta_type"), None)
        duration = content.duration_ms
        visual = {
            "shot_count": len(run.shots),
            "camera_sizes": _counts(shot.shot_size for shot in run.shots),
            "camera_angles": _counts(shot.camera_angle for shot in run.shots),
            "movement": _counts(shot.camera_movement for shot in run.shots),
            "subject_position": _counts(shot.subject_position for shot in run.shots),
            "dominant_colors": fields.get("dominant_colors"),
            "visual_events": _event_summary(run.visual_events, duration),
        }
        editing = {
            "cuts": max(0, len(run.shots) - 1),
            "transitions": _counts(shot.transition or shot.cut_type for shot in run.shots),
            "average_shot_length_ms": mean(shot_lengths) if shot_lengths else None,
            "median_shot_length_ms": median(shot_lengths) if shot_lengths else None,
            "cuts_per_second": (
                max(0, len(run.shots) - 1) / (duration / 1000)
                if duration and duration > 0 else None
            ),
        }
        audio = {
            "audio_energy": fields.get("audio_energy"),
            "events": _event_summary(run.audio_events, duration),
            "speech": fields.get("spoken_text"),
        }
        copy = {
            "spoken_words": fields.get("spoken_text"),
            "hook_type": fields.get("hook_type"),
            "cta_type": fields.get("cta_type"),
            "text_events": len(run.text_events),
        }
        product = {
            "first_appearance_ms": first_product,
            "first_appearance_position": _position(first_product, duration),
            "events": [item for item in visual["visual_events"] if item["event_type"].lower().startswith("product")],
        }
        cta = {
            "type": fields.get("cta_type"),
            "start_ms": cta_result.start_ms if cta_result else None,
            "start_position": _position(cta_result.start_ms if cta_result else None, duration),
            "duration_ms": (
                cta_result.end_ms - cta_result.start_ms
                if cta_result and cta_result.start_ms is not None and cta_result.end_ms is not None
                else None
            ),
        }
        structure = {
            "hook": fields.get("hook_type"),
            "segments": sequence,
            "segment_count": len(sequence),
        }
        performance = self.performance.performance_object(content)
        confidence_values = [result.confidence for result in results]
        confidence = mean(confidence_values) if confidence_values else 0.0
        feature_vector = _feature_vector(
            content=content,
            structure=structure,
            visual=visual,
            editing=editing,
            audio=audio,
            copy=copy,
            product=product,
            cta=cta,
        )
        feature_vector["feature_confidence"] = {
            result.field: result.confidence for result in results
        }
        return self.repository.create(
            dna_uid=f"DNA_{uuid4().hex.upper()}",
            content_id=content.id,
            analysis_run_id=run.id,
            dna_version=self.repository.next_version(content.id),
            content_type=content.content_type.value,
            duration_ms=duration,
            identity={
                "content_uid": content.content_uid,
                "platform": content.platform.value,
                "creator_id": content.creator_id,
                "language": content.language,
                "category": content.creator.category,
                "country": content.creator.country,
                "creator_size_bucket": _creator_size_bucket(
                    content.platform_account.followers_count
                    if content.platform_account is not None else None
                ),
                "published_at": content.published_at.isoformat() if content.published_at else None,
                "publication_period": content.published_at.strftime("%Y-%m") if content.published_at else None,
                "traffic_type": (content.raw_metadata or {}).get("traffic_type", "unknown"),
            },
            structure=structure,
            visual=visual,
            copy=copy,
            audio=audio,
            editing=editing,
            product=product,
            cta=cta,
            behavioral={"need_state": fields.get("need_state")},
            seo={"main_topic": fields.get("main_topic")},
            performance=performance,
            provenance={
                "analysis_run_id": run.id,
                "extractor": run.model_version,
                "confidence": confidence,
                "evidence": evidence,
            },
            segment_sequence=sequence,
            feature_vector=feature_vector,
            confidence=confidence,
            analysis_version=run.analyzer_version,
            taxonomy_version=run.taxonomy_version,
            pattern_engine_version=self.settings.pattern_engine_version,
        )

    def _get_content(self, identifier: int | str) -> ContentItem:
        content = (
            self.content.get(int(identifier))
            if isinstance(identifier, int) or str(identifier).isdigit()
            else self.content.get_by_uid(str(identifier))
        )
        if content is None:
            raise NotFoundError(f"Content {identifier} was not found")
        return content


def _role(kind: str) -> str:
    normalized = kind.strip().upper().replace(" ", "_").replace("-", "_")
    aliases = {"CALL_TO_ACTION": "CTA", "PRODUCT": "PRODUCT_REVEAL", "INTRO": "CONTEXT"}
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in FUNCTIONAL_ROLES else "OTHER"


def _segment_sequence(run: AnalysisRun, duration_ms: int | None) -> list[dict[str, Any]]:
    functional = [segment for segment in run.segments if segment.level is AnalysisLevel.SEGMENT]
    return [
        {
            "segment_id": segment.id,
            "role": _role(segment.kind),
            "label": segment.label,
            "sequence_order": segment.sequence_order,
            "start_ms": segment.start_ms,
            "end_ms": segment.end_ms,
            "duration_ms": segment.duration_ms,
            "normalized_start_position": _position(segment.start_ms, duration_ms),
            "normalized_end_position": _position(segment.end_ms, duration_ms),
        }
        for segment in sorted(functional, key=lambda item: item.sequence_order)
    ]


def _position(value: int | None, duration: int | None) -> float | None:
    if value is None or not duration or duration <= 0:
        return None
    return round(min(1.0, max(0.0, value / duration)), 6)


def _counts(values) -> dict[str, int]:
    return dict(Counter(value for value in values if value))


def _event_summary(events, duration: int | None) -> list[dict[str, Any]]:
    return [
        {
            "event_id": event.id,
            "event_type": event.event_type,
            "start_ms": event.start_ms,
            "end_ms": event.end_ms,
            "normalized_start_position": _position(event.start_ms, duration),
            "confidence": event.confidence,
            "source": event.source,
        }
        for event in events
    ]


def _feature_vector(**sections) -> dict[str, Any]:
    content = sections.pop("content")
    structure = sections["structure"]
    return {
        "platform": content.platform.value,
        "content_type": content.content_type.value,
        "hook_type": structure.get("hook"),
        "segment_sequence": [item["role"] for item in structure["segments"]],
        "shot_count": sections["visual"]["shot_count"],
        "average_shot_length_ms": sections["editing"]["average_shot_length_ms"],
        "cuts_per_second": sections["editing"]["cuts_per_second"],
        "audio_energy": sections["audio"]["audio_energy"],
        "product_reveal_position": sections["product"]["first_appearance_position"],
        "cta_type": sections["cta"]["type"],
        "cta_start_position": sections["cta"]["start_position"],
    }


def _is_sentinel(value: Any) -> bool:
    return isinstance(value, str) and value in {UNKNOWN, NOT_APPLICABLE}


def _creator_size_bucket(followers: int | None) -> str | None:
    if followers is None:
        return None
    if followers < 10_000:
        return "under_10k"
    if followers < 100_000:
        return "10k_100k"
    if followers < 1_000_000:
        return "100k_1m"
    return "over_1m"
