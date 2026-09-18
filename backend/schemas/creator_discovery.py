"""HTTP and service contracts for Creator Discovery Studio."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DiscoveryPlatform(StrEnum):
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    SNAPCHAT = "snapchat"
    LINKEDIN = "linkedin"
    X = "x"


class DiscoveryRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MatchClassification(StrEnum):
    CONFIRMED = "CONFIRMED"
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    POSSIBLE = "POSSIBLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"


class CandidateReviewStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    MERGED = "MERGED"
    KEPT_SEPARATE = "KEPT_SEPARATE"


class IdentityStatus(StrEnum):
    IDENTITY_PENDING = "IDENTITY_PENDING"
    IDENTITY_RESOLVED = "IDENTITY_RESOLVED"


class DataCollectionStatus(StrEnum):
    DATA_COLLECTION_REQUIRED = "DATA_COLLECTION_REQUIRED"
    DATA_COLLECTED = "DATA_COLLECTED"


class CreatorAnalysisStatus(StrEnum):
    IDENTITY_ONLY = "IDENTITY_ONLY"
    COLLECTION_PENDING = "COLLECTION_PENDING"
    API_REQUIRED = "API_REQUIRED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    ANALYSIS_READY = "ANALYSIS_READY"
    COMPLETED = "COMPLETED"
    TOKEN_INVALID = "TOKEN_INVALID"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    PERMISSION_MISSING = "PERMISSION_MISSING"
    RATE_LIMITED = "RATE_LIMITED"


class CreatorDiscoveryRunRequest(BaseModel):
    inputs: list[str] = Field(min_length=1, max_length=10_000)
    platforms: list[DiscoveryPlatform] = Field(min_length=1, max_length=7)
    mode: Literal["single", "bulk"] = "single"
    auto_process: bool | None = None
    analyze_content: bool = True
    resolve_cross_platform_identity: bool = True
    update_existing_profiles: bool = False
    content_sample_size: int = Field(default=10, ge=1, le=30)
    execute: bool = True

    @field_validator("inputs")
    @classmethod
    def clean_inputs(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not cleaned:
            raise ValueError("At least one creator name or account URL is required")
        return cleaned

    @field_validator("platforms")
    @classmethod
    def unique_platforms(cls, values: list[DiscoveryPlatform]) -> list[DiscoveryPlatform]:
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def default_bulk_automation(self) -> "CreatorDiscoveryRunRequest":
        if self.auto_process is None:
            self.auto_process = self.mode == "bulk"
        return self


class CreatorDiscoveryJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_uid: str
    input_value: str
    normalized_input: str
    input_kind: str
    platforms: list[str]
    status: str
    attempt: int
    checkpoint: dict[str, Any]
    stage: str = "PENDING"
    progress_percent: float = 0
    candidate_count: int
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None


class CreatorDiscoveryRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_uid: str
    status: str
    input_count: int
    platforms: list[str]
    options: dict[str, Any]
    processed: int
    matched: int
    review_required: int
    failed: int
    stage: str = "PENDING"
    progress_percent: float = 0
    warnings: list[Any]
    errors: list[Any]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    jobs: list[CreatorDiscoveryJobResponse] = Field(default_factory=list)


class CreatorCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    candidate_uid: str
    run_id: int
    creator_id: int | None
    platform: str
    display_name: str | None
    normalized_name: str | None
    username: str | None
    profile_url: str
    public_bio: str | None
    public_avatar_url: str | None
    followers: int | None
    following: int | None
    content_count: int | None
    verified: bool | None
    discovery_source: str
    source_id: str | None
    confidence: float
    classification: str
    review_status: str
    identity_status: str
    data_collection_status: str
    data_completeness: float
    connector_requirement: str
    profile_data: dict[str, Any]
    provenance: list[Any]
    retrieved_at: datetime
    created_at: datetime
    updated_at: datetime


class CandidateDecisionRequest(BaseModel):
    action: Literal["THIS_IS_THE_ACCOUNT", "MERGE", "KEEP_SEPARATE"] = "THIS_IS_THE_ACCOUNT"
    creator_uid: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def merge_needs_creator(self) -> "CandidateDecisionRequest":
        if self.action == "MERGE" and not self.creator_uid:
            raise ValueError("creator_uid is required for MERGE")
        return self


class CreatorProfileUpdate(BaseModel):
    niche: str | None = Field(default=None, min_length=1, max_length=255)
    industry: str | None = Field(default=None, min_length=1, max_length=120)
    main_platform: DiscoveryPlatform | None = None
    content_mechanism_style: str | None = Field(default=None, min_length=1, max_length=1000)
    kpi_impact: str | None = Field(default=None, min_length=1, max_length=500)
    start_year: int | None = Field(default=None, ge=1900, le=2100)


class CreatorRefreshRequest(BaseModel):
    platforms: list[DiscoveryPlatform] = Field(default_factory=list)
    analyze_content: bool = True
    content_sample_size: int = Field(default=10, ge=1, le=30)


class CreatorExportRequest(BaseModel):
    format: Literal["csv", "xlsx"] = "xlsx"
    template: Literal["standard", "intelligence"] = "standard"
    extended: bool = False
    creator_uids: list[str] = Field(default_factory=list, max_length=10_000)
    run_uid: str | None = Field(default=None, max_length=64)
    platform: DiscoveryPlatform | None = None
    industry: str | None = None
    niche: str | None = None
    influence_min: int | None = Field(default=None, ge=0)
    influence_max: int | None = Field(default=None, ge=0)
    match_confidence_min: float | None = Field(default=None, ge=0, le=100)
    analysis_status: str | None = None
    start_year: int | None = Field(default=None, ge=1900, le=2100)


class ConnectorCapabilityResponse(BaseModel):
    platform: DiscoveryPlatform
    configured: bool
    name_discovery: str
    direct_url: str
    profile_enumeration: str
    content_sampling: str
    detail: str
    status: str | None = None
    last_validation: datetime | None = None
