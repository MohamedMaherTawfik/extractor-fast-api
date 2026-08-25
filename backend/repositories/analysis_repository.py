"""Persistence boundary for versioned analysis jobs and normalized output."""

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.core.enums import AnalysisRunStatus
from backend.db.models.analysis import (
    AnalysisResult,
    AnalysisRun,
    AudioEvent,
    ContentSegment,
    ContentShot,
    TextEvent,
    VisualEvent,
)
from backend.schemas.analysis import NormalizedAnalysisResult, TimelineDraft


@dataclass
class TimelineEntities:
    segments: dict[str, ContentSegment]
    shots: dict[str, ContentShot]
    visual_events: dict[str, VisualEvent]
    audio_events: dict[str, AudioEvent]
    text_events: dict[str, TextEvent]


class AnalysisRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_run(self, **values) -> AnalysisRun:
        run = AnalysisRun(job_uid=f"ANJ_{uuid4().hex.upper()}", **values)
        self._session.add(run)
        self._session.flush()
        return run

    def get_run(self, identifier: int | str) -> AnalysisRun | None:
        if isinstance(identifier, int) or str(identifier).isdigit():
            predicate = AnalysisRun.id == int(identifier)
        else:
            predicate = AnalysisRun.job_uid == str(identifier)
        return self._session.scalar(self._run_statement().where(predicate))

    def find_cached(self, content_id: int, cache_key: str) -> AnalysisRun | None:
        statement = (
            self._run_statement()
            .where(
                AnalysisRun.content_id == content_id,
                AnalysisRun.cache_key == cache_key,
                AnalysisRun.status == AnalysisRunStatus.COMPLETED,
            )
            .order_by(AnalysisRun.id.desc())
        )
        return self._session.scalar(statement)

    def latest_for_content(self, content_id: int) -> AnalysisRun | None:
        statement = (
            self._run_statement()
            .where(AnalysisRun.content_id == content_id)
            .order_by(AnalysisRun.id.desc())
        )
        return self._session.scalar(statement)

    def persist_timeline(
        self,
        run: AnalysisRun,
        timeline: TimelineDraft,
    ) -> TimelineEntities:
        segments: dict[str, ContentSegment] = {}
        for draft in timeline.segments:
            segment = ContentSegment(
                segment_uid=f"SEG_{uuid4().hex.upper()}",
                run_id=run.id,
                content_id=run.content_id,
                level=draft.level,
                kind=draft.kind,
                label=draft.label,
                start_ms=draft.start_ms,
                end_ms=draft.end_ms,
                duration_ms=_duration(draft.start_ms, draft.end_ms),
                sequence_order=draft.sequence_order,
                metadata_payload=draft.metadata,
            )
            self._session.add(segment)
            segments[draft.ref] = segment
        self._session.flush()
        for draft in timeline.segments:
            if draft.parent_ref:
                segments[draft.ref].parent_segment_id = segments[draft.parent_ref].id

        shots: dict[str, ContentShot] = {}
        for draft in timeline.shots:
            shot = ContentShot(
                shot_uid=f"SHOT_{uuid4().hex.upper()}",
                run_id=run.id,
                content_id=run.content_id,
                segment_id=(
                    segments[draft.segment_ref].id if draft.segment_ref else None
                ),
                start_ms=draft.start_ms,
                end_ms=draft.end_ms,
                duration_ms=_duration(draft.start_ms, draft.end_ms),
                sequence_order=draft.sequence_order,
                shot_size=draft.shot_size,
                camera_angle=draft.camera_angle,
                camera_movement=draft.camera_movement,
                subject_position=draft.subject_position,
                cut_type=draft.cut_type,
                transition=draft.transition,
                metadata_payload=draft.metadata,
            )
            self._session.add(shot)
            shots[draft.ref] = shot
        self._session.flush()

        visual_events = self._persist_events(
            run, timeline.visual_events, VisualEvent, "VEV", segments, shots
        )
        audio_events = self._persist_events(
            run, timeline.audio_events, AudioEvent, "AEV", segments, shots
        )
        text_events: dict[str, TextEvent] = {}
        for draft in timeline.text_events:
            event = TextEvent(
                event_uid=f"TEV_{uuid4().hex.upper()}",
                run_id=run.id,
                content_id=run.content_id,
                segment_id=(segments[draft.segment_ref].id if draft.segment_ref else None),
                shot_id=(shots[draft.shot_ref].id if draft.shot_ref else None),
                event_type=draft.event_type,
                text=draft.text,
                start_ms=draft.start_ms,
                end_ms=draft.end_ms,
                position=draft.position,
                bounding_box=draft.bounding_box,
                confidence=draft.confidence,
                evidence=draft.evidence,
                source=draft.source,
                payload=draft.payload,
            )
            self._session.add(event)
            text_events[draft.ref] = event
        self._session.flush()
        return TimelineEntities(
            segments,
            shots,
            visual_events,
            audio_events,
            text_events,
        )

    def add_result(
        self,
        run: AnalysisRun,
        result: NormalizedAnalysisResult,
        entities: TimelineEntities,
    ) -> AnalysisResult:
        target = _target_values(result.target_ref, entities)
        record = AnalysisResult(
            run_id=run.id,
            content_id=run.content_id,
            field=result.field,
            level=result.level,
            value=result.value,
            start_ms=result.start_ms,
            end_ms=result.end_ms,
            confidence=result.confidence,
            evidence=result.evidence,
            source=result.source,
            engine=result.engine,
            rule_id=result.rule_id,
            status=result.status,
            accepted=result.accepted,
            low_confidence=result.low_confidence,
            manual_review=result.manual_review,
            **target,
        )
        self._session.add(record)
        self._session.flush()
        return record

    def _persist_events(
        self,
        run,
        drafts,
        model,
        prefix,
        segments,
        shots,
    ):
        events = {}
        for draft in drafts:
            event = model(
                event_uid=f"{prefix}_{uuid4().hex.upper()}",
                run_id=run.id,
                content_id=run.content_id,
                segment_id=(segments[draft.segment_ref].id if draft.segment_ref else None),
                shot_id=(shots[draft.shot_ref].id if draft.shot_ref else None),
                event_type=draft.event_type,
                start_ms=draft.start_ms,
                end_ms=draft.end_ms,
                confidence=draft.confidence,
                evidence=draft.evidence,
                source=draft.source,
                payload=draft.payload,
            )
            self._session.add(event)
            events[draft.ref] = event
        self._session.flush()
        return events

    @staticmethod
    def _run_statement():
        return select(AnalysisRun).options(
            selectinload(AnalysisRun.segments),
            selectinload(AnalysisRun.shots),
            selectinload(AnalysisRun.results),
            selectinload(AnalysisRun.visual_events),
            selectinload(AnalysisRun.audio_events),
            selectinload(AnalysisRun.text_events),
        )


def _duration(start_ms: int | None, end_ms: int | None) -> int | None:
    if start_ms is None or end_ms is None:
        return None
    return end_ms - start_ms


def _target_values(
    target_ref: str | None,
    entities: TimelineEntities,
) -> dict[str, int | None]:
    values = {
        "segment_id": None,
        "shot_id": None,
        "visual_event_id": None,
        "audio_event_id": None,
        "text_event_id": None,
    }
    if not target_ref:
        return values
    for collection, field in (
        (entities.segments, "segment_id"),
        (entities.shots, "shot_id"),
        (entities.visual_events, "visual_event_id"),
        (entities.audio_events, "audio_event_id"),
        (entities.text_events, "text_event_id"),
    ):
        if target_ref in collection:
            values[field] = collection[target_ref].id
            return values
    return values
