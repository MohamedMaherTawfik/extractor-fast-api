"""Typed Pydantic schemas for Social Content Intelligence API requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalysisJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: UUID
    item_uuid: UUID
    status: str
    stage: str
    progress_percent: float
    options: dict[str, Any] | None = None
    error_category: str | None = None
    error_message: str | None = None
    retry_count: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None


class BatchAnalysisRequest(BaseModel):
    item_uuids: list[UUID]
    force_reprocess: bool = False


class TranscriptSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    segment_index: int
    start_time: float
    end_time: float
    text: str
    speaker: str | None = None
    confidence: float | None = None


class TranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    language: str | None
    language_probability: float | None
    full_text: str
    duration_seconds: float | None
    model_name: str
    status: str
    segments: list[TranscriptSegmentResponse] = []


class HookAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    spoken_hook: dict[str, Any] | None = None
    visual_hook: dict[str, Any] | None = None
    text_hook: dict[str, Any] | None = None
    hook_types: list[str] = []
    clarity: str | None = None
    specificity: str | None = None
    relevance: str | None = None
    curiosity_mechanism: str | None = None
    text_visual_alignment: str | None = None
    heuristic_score: float | None = None
    qualitative_strengths: list[str] | None = None
    qualitative_weaknesses: list[str] | None = None
    recommendations: list[str] | None = None
    model_name: str


class CopyAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    original_caption: str | None = None
    opening_sentence: str | None = None
    primary_message: str | None = None
    main_topic: str | None = None
    secondary_topics: list[str] | None = None
    tone_of_voice: str | None = None
    writing_style: str | None = None
    emotional_framing: str | None = None
    persuasion_techniques: list[str] | None = None
    content_objective: str | None = None
    audience_address: str | None = None
    hashtag_strategy: dict[str, Any] | None = None
    cta_type: str | None = None
    cta_text: str | None = None
    is_explicit_cta: bool = False
    caption_structure: str | None = None
    sentence_characteristics: str | None = None
    readability_observations: str | None = None
    brand_voice_indicators: str | None = None
    summary: str | None = None


class NarrativeStageResponse(BaseModel):
    stage_name: str
    start_time: float
    end_time: float
    description: str
    evidence: str
    confidence: float = 0.90


class NarrativeAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    narrative_pattern: str
    summary: str | None = None
    stages: list[NarrativeStageResponse] = []


class VideoSceneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scene_index: int
    start_time: float
    end_time: float
    duration: float
    visual_description: str | None = None
    camera_framing: str | None = None
    camera_movement: str | None = None
    visible_text: str | None = None
    editing_notes: str | None = None
    scene_classification: str | None = None
    confidence: float | None = None


class VideoAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    duration: float | None = None
    aspect_ratio: str | None = None
    width: int | None = None
    height: int | None = None
    scene_count: int
    avg_scene_duration: float | None = None
    editing_pace: str | None = None
    opening_style: str | None = None
    visual_style: str | None = None
    has_talking_head: bool = False
    has_broll: bool = False
    has_graphics: bool = False
    has_subtitles: bool = False
    ending_style: str | None = None
    production_characteristics: str | None = None
    scenes: list[VideoSceneResponse] = []


class CompleteContentAnalysisResponse(BaseModel):
    model_config = {"populate_by_name": True}

    item_uuid: UUID
    job: AnalysisJobResponse | None = None
    transcript: TranscriptResponse | None = None
    hooks: HookAnalysisResponse | None = None
    copy_analysis: CopyAnalysisResponse | None = Field(default=None, alias="copy", serialization_alias="copy")
    storytelling: NarrativeAnalysisResponse | None = None
    video: VideoAnalysisResponse | None = None


class CreatorIntelligenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    platform: str
    creator_id: str
    username: str
    display_name: str | None = None
    sample_size: int
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    primary_topics: list[str] | None = None
    common_hook_types: list[str] | None = None
    typical_copy_style: str | None = None
    storytelling_patterns: list[str] | None = None
    typical_video_duration: str | None = None
    editing_patterns: list[str] | None = None
    common_cta_types: list[str] | None = None
    engagement_observations: dict[str, Any] | None = None
    creator_dna_summary: str | None = None
    hypotheses_vs_observed: dict[str, Any] | None = None
    limitations_notice: str | None = None


class CreativeGenerateRequest(BaseModel):
    item_uuid: UUID | None = None
    creator_username: str | None = None
    output_type: str = Field(default="hook_variations", description="hook_variations, caption_variations, video_script, etc.")
    target_platform: str = "instagram_reels"
    target_audience: str = "Broad mobile audience"
    target_duration: str = "45-60 seconds"
    target_language: str = "ar"
    objective: str = "Drive high engagement and link clicks"
    topic_context: str | None = None


class CreativeRecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: UUID
    item_uuid: UUID | None = None
    creator_username: str | None = None
    output_type: str
    target_platform: str
    target_audience: str | None = None
    target_duration: str | None = None
    target_language: str
    suggested_hook: str | None = None
    suggested_caption: str | None = None
    suggested_cta: str | None = None
    script_outline: str | None = None
    creative_rationale: str | None = None
    model_name: str
    is_ai_generated: bool
    created_at: datetime


class ExcelExportRequest(BaseModel):
    scope: str = Field(default="all_completed", description="current_post, selected_posts, filtered, all_completed, creator")
    item_uuids: list[UUID] | None = None
    creator_username: str | None = None
    filters: dict[str, Any] | None = None


class ExcelExportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    status: str
    scope: str
    filename: str | None = None
    total_rows: int = 0
    file_size_bytes: int = 0
    created_at: datetime
    completed_at: datetime | None = None
