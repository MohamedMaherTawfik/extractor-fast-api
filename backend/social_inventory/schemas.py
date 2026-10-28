"""Pydantic contracts shared by API, providers, normalizer, and worker."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator

Platform = Literal["instagram", "tiktok", "facebook", "youtube", "x", "linkedin"]
RunStatus = Literal["queued", "starting", "running", "importing", "succeeded", "partial", "failed", "cancelled"]


class InventoryMetrics(BaseModel):
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None


class InventoryMedia(BaseModel):
    type: str
    url: str
    thumbnail_url: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    url_status: Literal["permanent", "observed_temporary"] = "permanent"


class InventoryAuthor(BaseModel):
    external_id: str | None = None
    username: str | None = None
    display_name: str | None = None
    profile_url: str | None = None
    avatar_url: str | None = None
    followers_count: int | None = None
    verified: bool | None = None


class NormalizedSocialItem(BaseModel):
    platform: Platform
    external_id: str | None = None
    canonical_url: str
    content_type: str
    title: str | None = None
    caption: str | None = None
    language: str | None = None
    published_at: datetime | None = None
    author: InventoryAuthor = Field(default_factory=InventoryAuthor)
    media: list[InventoryMedia] = Field(default_factory=list)
    metrics: InventoryMetrics = Field(default_factory=InventoryMetrics)
    hashtags: list[str] = Field(default_factory=list)
    mentions: list[str] = Field(default_factory=list)
    location: dict[str, Any] | None = None
    comments: list[dict[str, Any]] = Field(default_factory=list)
    observed_at: datetime
    provider: str
    provider_response: dict[str, Any] = Field(default_factory=dict)


class StartProviderRunRequest(BaseModel):
    platform: Platform
    source_url: str
    max_items: int
    date_from: datetime | None = None
    date_to: datetime | None = None
    include_comments: bool = False
    max_comments_per_post: int = 0
    request_id: str


class ProviderCapabilities(BaseModel):
    provider: str
    enabled: bool
    platforms: dict[str, bool]
    comments: bool = True
    reason: str | None = None


class ProviderRun(BaseModel):
    id: str
    status: RunStatus
    dataset_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None


class ProviderItemsPage(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    offset: int
    limit: int
    has_more: bool


class SourceCreate(BaseModel):
    platform: Platform | None = None
    source_url: str
    provider: Literal["apify"] = "apify"
    max_items: int = Field(default=100, ge=1)
    date_from: datetime | None = None
    date_to: datetime | None = None
    include_comments: bool = False
    max_comments_per_post: int = Field(default=25, ge=0)

    @model_validator(mode="after")
    def valid_dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be before date_to")
        return self


class SourceUpdate(BaseModel):
    sync_enabled: bool | None = None
    sync_interval_minutes: int | None = Field(default=None, ge=15, le=525_600)


class SourceResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    uuid: UUID
    provider: str
    platform: str
    source_url: str
    canonical_url: str
    username: str | None
    display_name: str | None
    status: str
    settings: dict[str, Any] | None
    sync_enabled: bool
    sync_interval_minutes: int | None
    last_synced_at: datetime | None
    next_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RunResponse(BaseModel):
    model_config = {"from_attributes": True}
    uuid: UUID
    source_id: int
    provider: str
    status: str
    request_id: str
    max_items: int
    include_comments: bool
    items_seen: int
    items_created: int
    items_updated: int
    comments_created: int
    warnings: list[Any] | None
    error_code: str | None
    error_message: str | None
    attempts: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ItemResponse(BaseModel):
    model_config = {"from_attributes": True}
    uuid: UUID
    source_id: int
    platform: str
    external_id: str | None
    canonical_url: str
    content_type: str
    title: str | None
    caption: str | None
    language: str | None
    published_at: datetime | None
    author: dict[str, Any] | None
    media: list[Any] | None
    metrics: dict[str, Any] | None
    hashtags: list[Any] | None
    mentions: list[Any] | None
    location: dict[str, Any] | None
    provider: str
    first_observed_at: datetime
    last_observed_at: datetime


class PaginatedItems(BaseModel):
    items: list[ItemResponse]
    total: int
    offset: int
    limit: int


class ResearchRequest(BaseModel):
    source_uuid: UUID
    goal: str = Field(min_length=3, max_length=2000)
    target_count: int = Field(default=20, ge=1, le=100)
