"""Transport and domain schemas for DNA, pattern mining, and recipes."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.core.enums import (
    EvidenceType,
    PatternStability,
    PatternStatus,
    PatternType,
    RecipeCreatedBy,
    RecipeStatus,
    RecipeType,
    TrafficType,
)


class ContentDNAResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    dna_uid: str
    content_id: int
    analysis_run_id: int
    dna_version: int
    content_type: str
    duration_ms: int | None
    identity: dict[str, Any]
    structure: dict[str, Any]
    visual: dict[str, Any]
    copy_section: dict[str, Any] = Field(
        validation_alias="copy",
        serialization_alias="copy",
    )
    audio: dict[str, Any]
    editing: dict[str, Any]
    product: dict[str, Any]
    cta: dict[str, Any]
    behavioral: dict[str, Any]
    seo: dict[str, Any]
    performance: dict[str, Any]
    provenance: dict[str, Any]
    segment_sequence: list[dict[str, Any]]
    feature_vector: dict[str, Any]
    confidence: float
    analysis_version: str
    taxonomy_version: str
    pattern_engine_version: str
    created_at: datetime


class DNABatchRequest(BaseModel):
    content_ids: list[int | str] = Field(min_length=1, max_length=10000)


class DNABatchResponse(BaseModel):
    items: list[ContentDNAResponse]
    failed_items: list[dict[str, str]]


class PatternFilters(BaseModel):
    platform: str | None = None
    creator_id: int | None = None
    creator_ids: list[int] | None = None
    content_type: str | None = None
    category: str | None = None
    language: str | None = None
    country: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    duration_min_ms: int | None = Field(default=None, ge=0)
    duration_max_ms: int | None = Field(default=None, ge=0)
    performance_metric: str | None = None
    traffic_type: TrafficType | None = None

    @model_validator(mode="after")
    def valid_ranges(self) -> "PatternFilters":
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError("date_to must be greater than or equal to date_from")
        if (
            self.duration_min_ms is not None
            and self.duration_max_ms is not None
            and self.duration_max_ms < self.duration_min_ms
        ):
            raise ValueError("duration_max_ms must be >= duration_min_ms")
        return self


class PatternMineRequest(PatternFilters):
    content_ids: list[int | str] | None = Field(default=None, max_length=10000)


class PatternFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feature_name: str
    value: Any
    modality: str | None
    confidence: float
    evidence: Any | None


class PatternResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pattern_uid: str
    name: str
    pattern_type: PatternType
    scope: dict[str, Any]
    feature_definition: dict[str, Any]
    support_count: int
    support_ratio: float
    confidence: float
    performance_summary: dict[str, Any] | None
    evidence_type: EvidenceType
    support_score: float
    confidence_score: float
    performance_score: float
    consistency_score: float
    recency_score: float
    pattern_score: float
    stability: PatternStability
    status: PatternStatus
    first_seen: datetime | None
    last_seen: datetime | None
    analysis_version: str
    taxonomy_version: str
    pattern_engine_version: str
    features: list[PatternFeatureResponse]
    created_at: datetime
    updated_at: datetime


class PatternEvidenceItem(BaseModel):
    content_id: int
    dna_id: int
    segment_id: int | None = None
    shot_id: int | None = None
    analysis_result_id: int | None = None
    confidence: float
    evidence: Any | None = None


class PatternDetailResponse(PatternResponse):
    evidence: list[PatternEvidenceItem]
    explanation: dict[str, Any]


class PatternMiningRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_uid: str
    filters: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None
    contents_processed: int
    patterns_found: int
    patterns_rejected_low_support: int
    errors: list[dict[str, Any]] | None
    engine_version: str
    patterns: list[PatternResponse] = Field(default_factory=list)


class DNASimilarityResponse(BaseModel):
    content_id: int
    compared_content_id: int
    similarity_score: float
    shared_features: dict[str, Any]
    different_features: dict[str, Any]
    shared_sequence: list[str]
    timing_differences: dict[str, Any]
    performance_differences: dict[str, Any]
    weights: dict[str, float]


class SimilarContentItem(BaseModel):
    content_id: int
    content_uid: str
    similarity_score: float


class ContentClusterRequest(PatternFilters):
    similarity_threshold: float = Field(default=0.75, ge=0, le=1)


class ContentClusterResponse(BaseModel):
    cluster_id: str
    representative_content_id: int
    content_ids: list[int]
    minimum_similarity: float


class RecipeBuildRequest(PatternFilters):
    name: str = Field(min_length=1, max_length=255)
    build_mode: Literal["patterns", "top_performers", "creator"] = "patterns"
    pattern_ids: list[int | str] | None = None
    content_ids: list[int | str] | None = None
    creator_style_id: int | None = None
    recipe_type: RecipeType | None = None
    metric: str | None = None
    minimum_sample: int | None = Field(default=None, ge=1)
    target_duration_ms: int | None = Field(default=None, ge=0)
    created_by: RecipeCreatedBy = RecipeCreatedBy.SYSTEM


class RecipeVersionCreate(BaseModel):
    payload: dict[str, Any]
    constraints: dict[str, Any] = Field(default_factory=dict)
    change_summary: str | None = None
    created_by: RecipeCreatedBy = RecipeCreatedBy.USER


class RecipeVariantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_version: int | None = Field(default=None, ge=1)
    changed_variables: list[str] = Field(min_length=1)
    overrides: dict[str, Any]
    experiment_id: str | None = None


class RecipeVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    payload: dict[str, Any]
    constraints: dict[str, Any]
    confidence: float
    evidence_type: EvidenceType
    evidence: dict[str, Any]
    provenance: dict[str, Any]
    change_summary: str | None
    created_by: RecipeCreatedBy
    created_at: datetime


class RecipeVariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_uid: str
    base_version_id: int
    name: str
    changed_variables: list[str]
    overrides: dict[str, Any]
    experiment_id: str | None
    control_recipe_id: int | None
    status: str
    created_at: datetime


class RecipeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipe_uid: str
    name: str
    recipe_type: RecipeType
    status: RecipeStatus
    content_type: str
    target_platform: str | None
    target_duration_ms: int | None
    target_category: str | None
    language: str | None
    current_version: int
    recipe_engine_version: str
    versions: list[RecipeVersionResponse]
    variants: list[RecipeVariantResponse]
    created_at: datetime
    updated_at: datetime


class RecipeEvidenceResponse(BaseModel):
    recipe_id: int
    recipe_uid: str
    version: int
    why_this_recipe: dict[str, Any]
    provenance: dict[str, Any]
    evidence_type: EvidenceType
    confidence: float
