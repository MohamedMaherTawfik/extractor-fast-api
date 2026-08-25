"""Canonical analysis inputs, timeline drafts, results, and API responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.core.enums import (
    AnalysisLevel,
    AnalysisMode,
    AnalysisResultStatus,
    AnalysisRunStatus,
)


class TimeBound(BaseModel):
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def valid_time_range(self) -> "TimeBound":
        if (
            self.start_ms is not None
            and self.end_ms is not None
            and self.end_ms < self.start_ms
        ):
            raise ValueError("end_ms must be greater than or equal to start_ms")
        return self


class SegmentDraft(TimeBound):
    ref: str
    parent_ref: str | None = None
    level: AnalysisLevel
    kind: str
    label: str | None = None
    sequence_order: int = Field(ge=0)
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def segment_level_only(self) -> "SegmentDraft":
        if self.level not in {AnalysisLevel.SCENE, AnalysisLevel.SEGMENT}:
            raise ValueError("Segments must use scene or segment level")
        return self


class ShotDraft(TimeBound):
    ref: str
    segment_ref: str | None = None
    sequence_order: int = Field(ge=0)
    shot_size: str | None = None
    camera_angle: str | None = None
    camera_movement: str | None = None
    subject_position: str | None = None
    cut_type: str | None = None
    transition: str | None = None
    metadata: dict[str, Any] | None = None


class EventDraft(TimeBound):
    ref: str
    event_type: str
    segment_ref: str | None = None
    shot_ref: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: Any | None = None
    source: str | None = None
    payload: dict[str, Any] | None = None


class TextEventDraft(EventDraft):
    text: str
    position: dict[str, Any] | None = None
    bounding_box: dict[str, Any] | None = None


class TimelineDraft(BaseModel):
    segments: list[SegmentDraft] = Field(default_factory=list)
    shots: list[ShotDraft] = Field(default_factory=list)
    visual_events: list[EventDraft] = Field(default_factory=list)
    audio_events: list[EventDraft] = Field(default_factory=list)
    text_events: list[TextEventDraft] = Field(default_factory=list)

    @model_validator(mode="after")
    def references_are_valid(self) -> "TimelineDraft":
        segment_refs = _unique_refs(self.segments, "segment")
        shot_refs = _unique_refs(self.shots, "shot")
        _unique_refs(self.visual_events, "visual event")
        _unique_refs(self.audio_events, "audio event")
        _unique_refs(self.text_events, "text event")
        for segment in self.segments:
            if segment.parent_ref and segment.parent_ref not in segment_refs:
                raise ValueError("Segment parent_ref does not exist")
            if segment.parent_ref == segment.ref:
                raise ValueError("Segment cannot be its own parent")
        for shot in self.shots:
            if shot.segment_ref and shot.segment_ref not in segment_refs:
                raise ValueError("Shot segment_ref does not exist")
        for event in [
            *self.visual_events,
            *self.audio_events,
            *self.text_events,
        ]:
            if event.segment_ref and event.segment_ref not in segment_refs:
                raise ValueError("Event segment_ref does not exist")
            if event.shot_ref and event.shot_ref not in shot_refs:
                raise ValueError("Event shot_ref does not exist")
        return self


class EngineResultDraft(TimeBound):
    rule_id: str
    value: Any
    confidence: float = Field(ge=0, le=1)
    evidence: Any | None = None
    source: str
    target_ref: str | None = None


class NormalizedAnalysisResult(EngineResultDraft):
    content_id: int
    field: str
    level: AnalysisLevel
    engine: str
    status: AnalysisResultStatus
    accepted: bool
    low_confidence: bool
    manual_review: bool


class AnalysisOptions(BaseModel):
    mode: AnalysisMode = AnalysisMode.FULL
    rules_subset: list[str] | None = None
    force_reanalysis: bool = False

    @model_validator(mode="after")
    def unique_rules_subset(self) -> "AnalysisOptions":
        if self.rules_subset:
            self.rules_subset = list(dict.fromkeys(self.rules_subset))
        return self


class AnalysisBatchRequest(AnalysisOptions):
    content_ids: list[int | str] = Field(min_length=1, max_length=1000)


class AnalysisRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_uid: str
    batch_uid: str | None
    content_id: int
    status: AnalysisRunStatus
    media_hash: str
    cache_key: str
    analyzer_version: str
    rules_version: str
    taxonomy_version: str
    model_version: str
    options: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    results_count: int
    errors: list[dict[str, Any]] | None
    error_summary: str | None
    created_at: datetime


class SegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    segment_uid: str
    parent_segment_id: int | None
    level: AnalysisLevel
    kind: str
    label: str | None
    start_ms: int | None
    end_ms: int | None
    duration_ms: int | None
    sequence_order: int
    metadata: dict[str, Any] | None = Field(validation_alias="metadata_payload")


class ShotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shot_uid: str
    segment_id: int | None
    start_ms: int | None
    end_ms: int | None
    duration_ms: int | None
    sequence_order: int
    shot_size: str | None
    camera_angle: str | None
    camera_movement: str | None
    subject_position: str | None
    cut_type: str | None
    transition: str | None
    metadata: dict[str, Any] | None = Field(validation_alias="metadata_payload")


class AnalysisResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content_id: int
    segment_id: int | None
    shot_id: int | None
    visual_event_id: int | None
    audio_event_id: int | None
    text_event_id: int | None
    field: str
    level: AnalysisLevel
    value: Any
    start_ms: int | None
    end_ms: int | None
    confidence: float
    evidence: Any | None
    source: str
    engine: str
    rule_id: str
    status: AnalysisResultStatus
    accepted: bool
    low_confidence: bool
    manual_review: bool


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_uid: str
    segment_id: int | None
    shot_id: int | None
    event_type: str
    start_ms: int | None
    end_ms: int | None
    confidence: float | None
    evidence: Any | None
    source: str | None
    payload: dict[str, Any] | None


class TextEventResponse(EventResponse):
    text: str
    position: dict[str, Any] | None
    bounding_box: dict[str, Any] | None


class ContentAnalysisResponse(BaseModel):
    run: AnalysisRunResponse
    segments: list[SegmentResponse]
    shots: list[ShotResponse]
    results: list[AnalysisResultResponse]
    visual_events: list[EventResponse]
    audio_events: list[EventResponse]
    text_events: list[TextEventResponse]


def _unique_refs(items: list[Any], label: str) -> set[str]:
    refs = [item.ref for item in items]
    if len(refs) != len(set(refs)):
        raise ValueError(f"Duplicate {label} refs are not allowed")
    return set(refs)
