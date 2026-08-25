"""Provider-neutral contracts for multimodal generation and QA."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.core.enums import (
    GeneratedAssetStatus, GenerationJobStatus, GenerationPriority, GenerationRetryType,
    GenerationType, ProviderAvailability, ProviderLocality, ProviderPreference,
    QACategory, QAResultStatus, ReferenceRole, ReproducibilityLevel,
)


class GenerationEngineConfig(BaseModel):
    version: str = "1.0.0"
    provider_preference: ProviderPreference = ProviderPreference.LOCAL_FIRST
    default_max_attempts: int = Field(default=3, ge=1, le=20)
    provider_timeout_seconds: int = Field(default=60, ge=1, le=3600)
    health_cache_seconds: int = Field(default=30, ge=1, le=3600)
    generation_cache_enabled: bool = True
    max_asset_size_bytes: int = Field(default=104857600, ge=1)
    allowed_mime_types: dict[str, str]
    providers: list[dict[str, Any]] = Field(default_factory=list)
    models: list[dict[str, Any]] = Field(default_factory=list)


class ModelCapabilities(BaseModel):
    supports_text_input: bool = True
    supports_image_input: bool = False
    supports_audio_input: bool = False
    supports_video_input: bool = False
    outputs: set[GenerationType] = Field(default_factory=set)
    supports_structured_output: bool = False
    supports_seed: bool = False
    supports_reference_images: bool = False
    supports_mask_editing: bool = False
    supports_image_to_video: bool = False
    supports_audio_conditioning: bool = False
    max_input_size: int | None = Field(default=None, ge=1)
    max_output_duration: float | None = Field(default=None, gt=0)
    supported_aspect_ratios: list[str] = Field(default_factory=list)
    supported_resolutions: list[str] = Field(default_factory=list)


class ProviderProfileCreate(BaseModel):
    provider_code: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,99}$")
    display_name: str = Field(min_length=1, max_length=255)
    locality: ProviderLocality
    enabled: bool = True
    availability: ProviderAvailability = ProviderAvailability.AVAILABLE
    timeout_seconds: int = Field(default=60, ge=1, le=3600)
    config: dict[str, Any] = Field(default_factory=dict)


class ModelProfileCreate(BaseModel):
    provider_code: str
    model_id: str = Field(min_length=1, max_length=255)
    model_version: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    availability: ProviderAvailability = ProviderAvailability.AVAILABLE
    capabilities: ModelCapabilities
    quality_score: float = Field(default=0.5, ge=0, le=1)
    privacy_score: float = Field(default=0.5, ge=0, le=1)
    cost_score: float = Field(default=0.5, ge=0, le=1)
    latency_score: float = Field(default=0.5, ge=0, le=1)
    cost_class: str = "test"
    license_notes: str | None = None


class ModelProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    provider_code: str
    model_id: str
    model_version: str
    locality: ProviderLocality
    enabled: bool
    availability: ProviderAvailability
    capabilities: ModelCapabilities
    quality_score: float
    privacy_score: float
    cost_score: float
    latency_score: float
    cost_class: str
    license_notes: str | None


class RequiredCapabilities(BaseModel):
    generation_type: GenerationType
    aspect_ratio: str | None = None
    resolution: str | None = None
    duration_seconds: float | None = Field(default=None, gt=0)
    needs_seed: bool = False
    needs_references: bool = False
    needs_mask_editing: bool = False
    needs_image_to_video: bool = False
    needs_audio_conditioning: bool = False


class ReferenceAssetSpec(BaseModel):
    asset_id: str = Field(min_length=1, max_length=255)
    reference_role: ReferenceRole
    reference_version: int = Field(default=1, ge=1)
    angle: str | None = None
    expression: str | None = None
    lighting: str | None = None
    priority: int = Field(default=0, ge=0, le=1000)
    rights_status: str = "UNKNOWN"
    approved: bool = False
    checksum: str | None = None
    relative_path: str | None = None
    identity_priority: int | None = Field(default=None, ge=0, le=100)
    composition_priority: int | None = Field(default=None, ge=0, le=100)
    pose_priority: int | None = Field(default=None, ge=0, le=100)
    product_priority: int | None = Field(default=None, ge=0, le=100)


class OutputSpecification(BaseModel):
    mime_type: str | None = None
    aspect_ratio: str | None = None
    resolution: str | None = None
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    duration_seconds: float | None = Field(default=None, gt=0)
    format: str | None = None
    color_profile: str | None = None
    frame_rate: float | None = Field(default=None, gt=0)
    sample_rate: int | None = Field(default=None, gt=0)


class PromptSection(BaseModel):
    id: str
    priority: int
    content: Any
    hardness: str
    source: str
    order: int


class PromptPackageData(BaseModel):
    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    task: str
    objective: str
    modality: str
    generation_type: GenerationType
    content_type: str | None = None
    platform: Any = None
    character: dict[str, Any] | None = None
    brand: dict[str, Any] | None = None
    product: dict[str, Any] | None = None
    scene: dict[str, Any] = Field(default_factory=dict)
    visual: dict[str, Any] = Field(default_factory=dict)
    camera: dict[str, Any] = Field(default_factory=dict)
    lighting: dict[str, Any] = Field(default_factory=dict)
    performance: dict[str, Any] = Field(default_factory=dict)
    copy_spec: dict[str, Any] = Field(default_factory=dict, alias="copy")
    audio: dict[str, Any] = Field(default_factory=dict)
    accessibility: dict[str, Any] = Field(default_factory=dict)
    positive_constraints: list[Any] = Field(default_factory=list)
    negative_constraints: list[Any] = Field(default_factory=list)
    forbidden_changes: list[Any] = Field(default_factory=list)
    required_evidence: list[Any] = Field(default_factory=list)
    reference_assets: list[ReferenceAssetSpec] = Field(default_factory=list)
    output_specification: OutputSpecification = Field(default_factory=OutputSpecification)
    qa_requirements: list[Any] = Field(default_factory=list)
    provenance_requirements: list[Any] = Field(default_factory=list)
    sections: list[PromptSection] = Field(default_factory=list)


class PromptPackageResponse(BaseModel):
    prompt_uid: str
    version: int
    prompt_hash: str
    data: PromptPackageData
    created_at: datetime | None = None


class GenerationRequest(BaseModel):
    generation_contract_id: int | str
    generation_contract_version: int | None = Field(default=None, ge=1)
    generation_type: GenerationType
    task_id: str | None = None
    priority: GenerationPriority = GenerationPriority.NORMAL
    provider_preference: ProviderPreference | None = None
    model_id: str | None = None
    max_attempts: int | None = Field(default=None, ge=1, le=20)
    max_cost: float | None = Field(default=None, ge=0)
    max_duration_seconds: float | None = Field(default=None, gt=0)
    seed: int | None = Field(default=None, ge=0)
    references: list[ReferenceAssetSpec] = Field(default_factory=list)
    output_specification: OutputSpecification = Field(default_factory=OutputSpecification)
    changed_variables: list[str] = Field(default_factory=list)
    fresh_variation: bool = False
    dry_run: bool = False
    execute: bool = True
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def variants_are_traceable(self):
        variants = int(self.options.get("variants", 1))
        if variants > 1 and not self.changed_variables:
            raise ValueError("Multiple variants require changed_variables")
        return self


class NormalizedGenerationResult(BaseModel):
    provider: str
    model_id: str
    model_version: str
    external_job_id: str | None = None
    status: str
    media_assets: list[dict[str, Any]] = Field(default_factory=list)
    text_outputs: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw_response_reference: str | None = None
    cost_metadata: dict[str, Any] = Field(default_factory=dict)
    timing: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class QAResultData(BaseModel):
    check_id: str
    category: QACategory
    result: QAResultStatus
    severity: str
    evidence: Any = None
    message: str
    suggested_action: str | None = None
    automatically_repairable: bool = False


class AssetVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    version: int
    relative_path: str
    checksum: str
    mime_type: str
    file_size: int
    width: int | None
    height: int | None
    duration_seconds: float | None
    metadata_payload: dict[str, Any] | None
    provenance: dict[str, Any]
    qa_status: str
    created_at: datetime


class GeneratedAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    asset_uid: str
    modality: str
    asset_type: str
    status: GeneratedAssetStatus
    current_version: int
    versions: list[AssetVersionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class GenerationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    job_uid: str
    task_id: str | None
    generation_contract_id: int
    generation_contract_version: int
    recipe_id: int
    recipe_version: int
    content_type: str
    modality: str
    generation_type: GenerationType
    provider: str | None
    model_id: str | None
    model_version: str | None
    status: GenerationJobStatus
    priority: GenerationPriority
    attempt_count: int
    max_attempts: int
    seed: int | None
    error_code: str | None
    error_message: str | None
    used_fallback: bool
    prompt_hash: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    assets: list[GeneratedAssetResponse] = Field(default_factory=list)


class GenerationPreviewResponse(BaseModel):
    contract_uid: str
    contract_version: int
    selected_provider: str
    selected_model: str
    fallback_models: list[str]
    prompt_summary: dict[str, Any]
    prompt_hash: str
    constraints: dict[str, Any]
    references: list[ReferenceAssetSpec]
    estimated_jobs: int
    estimated_cost: float
    warnings: list[str]


class StoryboardShotData(BaseModel):
    shot_id: str
    segment_id: str | None = None
    purpose: str
    shot_size: str | None = None
    camera_angle: str | None = None
    lens_fov: str | None = None
    camera_height: str | None = None
    camera_movement: str | None = None
    subject_position: str | None = None
    subject_movement: str | None = None
    pose: str | None = None
    expression: str | None = None
    gaze: str | None = None
    product_position: str | None = None
    background: str | None = None
    lighting: str | None = None
    duration: float | None = None
    dialogue: str | None = None
    sfx: list[dict[str, Any]] = Field(default_factory=list)
    transition: str | None = None
    dependency: dict[str, Any] = Field(default_factory=dict)


class CopyOutputData(BaseModel):
    copy_uid: str
    copy_type: str
    language: str | None = None
    dialect: str | None = None
    tone: str | None = None
    headline: str | None = None
    hook: str | None = None
    body: str | None = None
    cta: str | None = None
    claims: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    evidence_links: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    version: int = 1


class GenerationCancelRequest(BaseModel):
    cancelled_by: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=1, max_length=2000)


class AssetArchiveRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
