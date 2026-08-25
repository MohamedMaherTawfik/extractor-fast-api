"""Canonical content schema shared by every connector."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.core.enums import (
    AnalysisStatus,
    CollectionStatus,
    ContentType,
    Platform,
)


class ContentAccountIdentity(BaseModel):
    username: str | None = None
    platform_user_id: str | None = None
    profile_url: str | None = None


class NormalizedContent(BaseModel):
    content_uid: str = Field(
        default_factory=lambda: f"CNT_{uuid4().hex.upper()}",
        max_length=64,
    )
    creator_id: int | None = None
    platform_account_id: int | None = None
    platform: Platform
    platform_content_id: str | None = Field(default=None, max_length=255)
    content_type: ContentType
    source_url: str | None = Field(default=None, max_length=1000)
    canonical_url: str | None = Field(default=None, max_length=1000)
    published_at: datetime | None = None
    platform_updated_at: datetime | None = None
    title: str | None = Field(default=None, max_length=1000)
    caption: str | None = None
    description: str | None = None
    hashtags: list[str] | None = None
    mentions: list[str] | None = None
    language: str | None = Field(default=None, max_length=100)
    duration_ms: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    aspect_ratio: float | None = Field(default=None, gt=0)
    thumbnail_url: str | None = Field(default=None, max_length=1000)
    media_url: str | None = Field(default=None, max_length=1000)
    views: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)
    raw_metadata: dict[str, Any] | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str | None = Field(default=None, max_length=64)
    account_identity: ContentAccountIdentity | None = Field(
        default=None,
        exclude=True,
    )

    @model_validator(mode="after")
    def stable_identity_is_required(self) -> "NormalizedContent":
        if not (
            self.platform_content_id
            or self.canonical_url
            or self.source_url
            or self.content_hash
        ):
            raise ValueError("Normalized content requires a stable identifier")
        return self


class ContentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content_uid: str
    creator_id: int
    platform_account_id: int | None
    platform: Platform
    platform_content_id: str | None
    content_type: ContentType
    source_url: str | None
    canonical_url: str | None
    published_at: datetime | None
    platform_updated_at: datetime | None
    title: str | None
    caption: str | None
    description: str | None
    hashtags: list[str] | None
    mentions: list[str] | None
    language: str | None
    duration_ms: int | None
    width: int | None
    height: int | None
    aspect_ratio: float | None
    thumbnail_url: str | None
    media_url: str | None
    views: int | None
    likes: int | None
    comments: int | None
    shares: int | None
    saves: int | None
    raw_metadata: dict[str, Any] | None
    raw_storage_path: str | None
    local_media_path: str | None
    content_hash: str | None
    collected_at: datetime
    collection_status: CollectionStatus
    analysis_status: AnalysisStatus
    created_at: datetime
    updated_at: datetime
