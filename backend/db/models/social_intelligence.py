"""Social Content Intelligence persistence models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin, utc_now


class ContentAnalysisJob(Base, TimestampMixin):
    __tablename__ = "content_analysis_jobs"
    __table_args__ = (
        Index("ix_analysis_job_item_status", "item_uuid", "status"),
        Index("ix_analysis_job_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[UUID] = mapped_column(default=uuid4, unique=True, nullable=False)
    item_uuid: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", nullable=False)
    stage: Mapped[str] = mapped_column(String(50), default="QUEUED", nullable=False)
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    options: Mapped[dict | None] = mapped_column(JSON)
    error_category: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    transcript: Mapped[ContentTranscript | None] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )
    hook_analysis: Mapped[ContentHookAnalysis | None] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )
    copy_analysis: Mapped[ContentCopyAnalysis | None] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )
    narrative_analysis: Mapped[ContentNarrativeAnalysis | None] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )
    video_analysis: Mapped[ContentVideoAnalysis | None] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )


class ContentTranscript(Base, TimestampMixin):
    __tablename__ = "content_transcripts"
    __table_args__ = (Index("ix_transcript_item", "item_uuid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("content_analysis_jobs.id", ondelete="CASCADE"), nullable=False
    )
    item_uuid: Mapped[UUID] = mapped_column(nullable=False)
    language: Mapped[str | None] = mapped_column(String(20))
    language_probability: Mapped[float | None] = mapped_column(Float)
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="completed", nullable=False)

    job: Mapped[ContentAnalysisJob] = relationship(back_populates="transcript")
    segments: Mapped[list[ContentTranscriptSegment]] = relationship(
        back_populates="transcript", cascade="all, delete-orphan"
    )


class ContentTranscriptSegment(Base):
    __tablename__ = "content_transcript_segments"
    __table_args__ = (Index("ix_transcript_seg_transcript", "transcript_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transcript_id: Mapped[int] = mapped_column(
        ForeignKey("content_transcripts.id", ondelete="CASCADE"), nullable=False
    )
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    speaker: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float | None] = mapped_column(Float)

    transcript: Mapped[ContentTranscript] = relationship(back_populates="segments")


class ContentHookAnalysis(Base, TimestampMixin):
    __tablename__ = "content_hook_analyses"
    __table_args__ = (Index("ix_hook_item", "item_uuid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("content_analysis_jobs.id", ondelete="CASCADE"), nullable=False
    )
    item_uuid: Mapped[UUID] = mapped_column(nullable=False)
    spoken_hook: Mapped[dict | None] = mapped_column(JSON)
    visual_hook: Mapped[dict | None] = mapped_column(JSON)
    text_hook: Mapped[dict | None] = mapped_column(JSON)
    hook_types: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    clarity: Mapped[str | None] = mapped_column(Text)
    specificity: Mapped[str | None] = mapped_column(Text)
    relevance: Mapped[str | None] = mapped_column(Text)
    curiosity_mechanism: Mapped[str | None] = mapped_column(Text)
    text_visual_alignment: Mapped[str | None] = mapped_column(Text)
    heuristic_score: Mapped[float | None] = mapped_column(Float)
    qualitative_strengths: Mapped[list | None] = mapped_column(JSON)
    qualitative_weaknesses: Mapped[list | None] = mapped_column(JSON)
    recommendations: Mapped[list | None] = mapped_column(JSON)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)

    job: Mapped[ContentAnalysisJob] = relationship(back_populates="hook_analysis")


class ContentCopyAnalysis(Base, TimestampMixin):
    __tablename__ = "content_copy_analyses"
    __table_args__ = (Index("ix_copy_item", "item_uuid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("content_analysis_jobs.id", ondelete="CASCADE"), nullable=False
    )
    item_uuid: Mapped[UUID] = mapped_column(nullable=False)
    original_caption: Mapped[str | None] = mapped_column(Text)
    opening_sentence: Mapped[str | None] = mapped_column(Text)
    primary_message: Mapped[str | None] = mapped_column(Text)
    main_topic: Mapped[str | None] = mapped_column(String(255))
    secondary_topics: Mapped[list | None] = mapped_column(JSON)
    tone_of_voice: Mapped[str | None] = mapped_column(String(100))
    writing_style: Mapped[str | None] = mapped_column(String(100))
    emotional_framing: Mapped[str | None] = mapped_column(String(100))
    persuasion_techniques: Mapped[list | None] = mapped_column(JSON)
    content_objective: Mapped[str | None] = mapped_column(String(100))
    audience_address: Mapped[str | None] = mapped_column(String(100))
    hashtag_strategy: Mapped[dict | None] = mapped_column(JSON)
    cta_type: Mapped[str | None] = mapped_column(String(50))
    cta_text: Mapped[str | None] = mapped_column(Text)
    is_explicit_cta: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    caption_structure: Mapped[str | None] = mapped_column(Text)
    sentence_characteristics: Mapped[str | None] = mapped_column(Text)
    readability_observations: Mapped[str | None] = mapped_column(Text)
    brand_voice_indicators: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)

    job: Mapped[ContentAnalysisJob] = relationship(back_populates="copy_analysis")


class ContentNarrativeAnalysis(Base, TimestampMixin):
    __tablename__ = "content_narrative_analyses"
    __table_args__ = (Index("ix_narrative_item", "item_uuid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("content_analysis_jobs.id", ondelete="CASCADE"), nullable=False
    )
    item_uuid: Mapped[UUID] = mapped_column(nullable=False)
    narrative_pattern: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    stages: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    job: Mapped[ContentAnalysisJob] = relationship(back_populates="narrative_analysis")


class ContentVideoAnalysis(Base, TimestampMixin):
    __tablename__ = "content_video_analyses"
    __table_args__ = (Index("ix_video_item", "item_uuid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("content_analysis_jobs.id", ondelete="CASCADE"), nullable=False
    )
    item_uuid: Mapped[UUID] = mapped_column(nullable=False)
    duration: Mapped[float | None] = mapped_column(Float)
    aspect_ratio: Mapped[str | None] = mapped_column(String(20))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    scene_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_scene_duration: Mapped[float | None] = mapped_column(Float)
    editing_pace: Mapped[str | None] = mapped_column(String(50))
    opening_style: Mapped[str | None] = mapped_column(String(100))
    visual_style: Mapped[str | None] = mapped_column(String(100))
    has_talking_head: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_broll: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_graphics: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_subtitles: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ending_style: Mapped[str | None] = mapped_column(String(100))
    production_characteristics: Mapped[str | None] = mapped_column(Text)

    job: Mapped[ContentAnalysisJob] = relationship(back_populates="video_analysis")
    scenes: Mapped[list[ContentVideoScene]] = relationship(
        back_populates="video_analysis", cascade="all, delete-orphan"
    )


class ContentVideoScene(Base):
    __tablename__ = "content_video_scenes"
    __table_args__ = (Index("ix_video_scene_video", "video_analysis_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_analysis_id: Mapped[int] = mapped_column(
        ForeignKey("content_video_analyses.id", ondelete="CASCADE"), nullable=False
    )
    scene_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    visual_description: Mapped[str | None] = mapped_column(Text)
    camera_framing: Mapped[str | None] = mapped_column(String(50))
    camera_movement: Mapped[str | None] = mapped_column(String(50))
    visible_text: Mapped[str | None] = mapped_column(Text)
    editing_notes: Mapped[str | None] = mapped_column(Text)
    scene_classification: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float | None] = mapped_column(Float)

    video_analysis: Mapped[ContentVideoAnalysis] = relationship(back_populates="scenes")


class CreatorIntelligence(Base, TimestampMixin):
    __tablename__ = "creator_intelligence"
    __table_args__ = (
        UniqueConstraint("platform", "creator_id", name="uq_creator_intel_platform_id"),
        Index("ix_creator_intel_username", "platform", "username"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    creator_id: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    sample_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    primary_topics: Mapped[list | None] = mapped_column(JSON)
    common_hook_types: Mapped[list | None] = mapped_column(JSON)
    typical_copy_style: Mapped[str | None] = mapped_column(Text)
    storytelling_patterns: Mapped[list | None] = mapped_column(JSON)
    typical_video_duration: Mapped[str | None] = mapped_column(String(50))
    editing_patterns: Mapped[list | None] = mapped_column(JSON)
    common_cta_types: Mapped[list | None] = mapped_column(JSON)
    engagement_observations: Mapped[dict | None] = mapped_column(JSON)
    creator_dna_summary: Mapped[str | None] = mapped_column(Text)
    hypotheses_vs_observed: Mapped[dict | None] = mapped_column(JSON)
    limitations_notice: Mapped[str | None] = mapped_column(Text)


class CreativeRecommendation(Base, TimestampMixin):
    __tablename__ = "creative_recommendations"
    __table_args__ = (Index("ix_creative_rec_item", "item_uuid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[UUID] = mapped_column(default=uuid4, unique=True, nullable=False)
    item_uuid: Mapped[UUID | None] = mapped_column(nullable=True)
    creator_username: Mapped[str | None] = mapped_column(String(255))
    output_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_platform: Mapped[str] = mapped_column(String(50), nullable=False)
    target_audience: Mapped[str | None] = mapped_column(String(100))
    target_duration: Mapped[str | None] = mapped_column(String(50))
    target_language: Mapped[str] = mapped_column(String(30), default="ar", nullable=False)
    suggested_hook: Mapped[str | None] = mapped_column(Text)
    suggested_caption: Mapped[str | None] = mapped_column(Text)
    suggested_cta: Mapped[str | None] = mapped_column(Text)
    script_outline: Mapped[str | None] = mapped_column(Text)
    creative_rationale: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ExcelExportJob(Base, TimestampMixin):
    __tablename__ = "excel_export_jobs"
    __table_args__ = (Index("ix_excel_job_status", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[UUID] = mapped_column(default=uuid4, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", nullable=False)
    scope: Mapped[str] = mapped_column(String(50), nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSON)
    file_path: Mapped[str | None] = mapped_column(String(1000))
    filename: Mapped[str | None] = mapped_column(String(255))
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
