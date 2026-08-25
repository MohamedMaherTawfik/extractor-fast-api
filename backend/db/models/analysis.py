"""Normalized, versioned content-analysis persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.enums import (
    AnalysisLevel,
    AnalysisResultStatus,
    AnalysisRunStatus,
)
from backend.db.base import Base, utc_now
from backend.db.models.types import enum_check, enum_type

if TYPE_CHECKING:
    from backend.db.models.content_item import ContentItem


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        enum_check("status", AnalysisRunStatus, "analysis_run_status_type"),
        Index("ix_analysis_runs_content_id", "content_id"),
        Index("ix_analysis_runs_batch_uid", "batch_uid"),
        Index("ix_analysis_runs_status", "status"),
        Index("ix_analysis_runs_cache_key", "cache_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    batch_uid: Mapped[str | None] = mapped_column(String(64))
    content_id: Mapped[int] = mapped_column(
        ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[AnalysisRunStatus] = mapped_column(
        enum_type(AnalysisRunStatus, "analysis_run_status_type"),
        default=AnalysisRunStatus.QUEUED,
        nullable=False,
    )
    media_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False)
    analyzer_version: Mapped[str] = mapped_column(String(100), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(100), nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(1000), nullable=False)
    options: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    results_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    content: Mapped[ContentItem] = relationship(back_populates="analysis_runs")
    segments: Mapped[list[ContentSegment]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    shots: Mapped[list[ContentShot]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    results: Mapped[list[AnalysisResult]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    visual_events: Mapped[list[VisualEvent]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    audio_events: Mapped[list[AudioEvent]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    text_events: Mapped[list[TextEvent]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class ContentSegment(Base):
    __tablename__ = "content_segments"
    __table_args__ = (
        enum_check("level", AnalysisLevel, "segment_analysis_level_type"),
        Index("ix_content_segments_run_id", "run_id"),
        Index("ix_content_segments_content_id", "content_id"),
        Index("ix_content_segments_time", "start_ms", "end_ms"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    segment_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    content_id: Mapped[int] = mapped_column(
        ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False
    )
    parent_segment_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_segments.id", ondelete="CASCADE")
    )
    level: Mapped[AnalysisLevel] = mapped_column(
        enum_type(AnalysisLevel, "segment_analysis_level_type"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255))
    start_ms: Mapped[int | None] = mapped_column(Integer)
    end_ms: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_payload: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    run: Mapped[AnalysisRun] = relationship(back_populates="segments")
    parent: Mapped[ContentSegment | None] = relationship(remote_side=[id])

class ContentShot(Base):
    __tablename__ = "content_shots"
    __table_args__ = (
        Index("ix_content_shots_run_id", "run_id"),
        Index("ix_content_shots_content_id", "content_id"),
        Index("ix_content_shots_segment_id", "segment_id"),
        Index("ix_content_shots_time", "start_ms", "end_ms"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shot_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    content_id: Mapped[int] = mapped_column(
        ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False
    )
    segment_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_segments.id", ondelete="SET NULL")
    )
    start_ms: Mapped[int | None] = mapped_column(Integer)
    end_ms: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    shot_size: Mapped[str | None] = mapped_column(String(100))
    camera_angle: Mapped[str | None] = mapped_column(String(100))
    camera_movement: Mapped[str | None] = mapped_column(String(100))
    subject_position: Mapped[str | None] = mapped_column(String(100))
    cut_type: Mapped[str | None] = mapped_column(String(100))
    transition: Mapped[str | None] = mapped_column(String(100))
    metadata_payload: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    run: Mapped[AnalysisRun] = relationship(back_populates="shots")

class VisualEvent(Base):
    __tablename__ = "visual_events"
    __table_args__ = (
        Index("ix_visual_events_run_id", "run_id"),
        Index("ix_visual_events_content_id", "content_id"),
        Index("ix_visual_events_time", "start_ms", "end_ms"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[int | None] = mapped_column(ForeignKey("content_segments.id", ondelete="SET NULL"))
    shot_id: Mapped[int | None] = mapped_column(ForeignKey("content_shots.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(150), nullable=False)
    start_ms: Mapped[int | None] = mapped_column(Integer)
    end_ms: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[Any | None] = mapped_column(JSON)
    source: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped[AnalysisRun] = relationship(back_populates="visual_events")


class AudioEvent(Base):
    __tablename__ = "audio_events"
    __table_args__ = (
        Index("ix_audio_events_run_id", "run_id"),
        Index("ix_audio_events_content_id", "content_id"),
        Index("ix_audio_events_time", "start_ms", "end_ms"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[int | None] = mapped_column(ForeignKey("content_segments.id", ondelete="SET NULL"))
    shot_id: Mapped[int | None] = mapped_column(ForeignKey("content_shots.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(150), nullable=False)
    start_ms: Mapped[int | None] = mapped_column(Integer)
    end_ms: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[Any | None] = mapped_column(JSON)
    source: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped[AnalysisRun] = relationship(back_populates="audio_events")


class TextEvent(Base):
    __tablename__ = "text_events"
    __table_args__ = (
        Index("ix_text_events_run_id", "run_id"),
        Index("ix_text_events_content_id", "content_id"),
        Index("ix_text_events_time", "start_ms", "end_ms"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[int | None] = mapped_column(ForeignKey("content_segments.id", ondelete="SET NULL"))
    shot_id: Mapped[int | None] = mapped_column(ForeignKey("content_shots.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(150), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_ms: Mapped[int | None] = mapped_column(Integer)
    end_ms: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    bounding_box: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[Any | None] = mapped_column(JSON)
    source: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped[AnalysisRun] = relationship(back_populates="text_events")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        enum_check("level", AnalysisLevel, "result_analysis_level_type"),
        enum_check("status", AnalysisResultStatus, "analysis_result_status_type"),
        Index("ix_analysis_results_run_id", "run_id"),
        Index("ix_analysis_results_content_id", "content_id"),
        Index("ix_analysis_results_field", "field"),
        Index("ix_analysis_results_rule_id", "rule_id"),
        Index("ix_analysis_results_time", "start_ms", "end_ms"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[int | None] = mapped_column(ForeignKey("content_segments.id", ondelete="SET NULL"))
    shot_id: Mapped[int | None] = mapped_column(ForeignKey("content_shots.id", ondelete="SET NULL"))
    visual_event_id: Mapped[int | None] = mapped_column(ForeignKey("visual_events.id", ondelete="SET NULL"))
    audio_event_id: Mapped[int | None] = mapped_column(ForeignKey("audio_events.id", ondelete="SET NULL"))
    text_event_id: Mapped[int | None] = mapped_column(ForeignKey("text_events.id", ondelete="SET NULL"))
    field: Mapped[str] = mapped_column(String(150), nullable=False)
    level: Mapped[AnalysisLevel] = mapped_column(enum_type(AnalysisLevel, "result_analysis_level_type"), nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    start_ms: Mapped[int | None] = mapped_column(Integer)
    end_ms: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[Any | None] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    engine: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[AnalysisResultStatus] = mapped_column(enum_type(AnalysisResultStatus, "analysis_result_status_type"), nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    low_confidence: Mapped[bool] = mapped_column(Boolean, nullable=False)
    manual_review: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped[AnalysisRun] = relationship(back_populates="results")
