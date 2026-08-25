"""Collection API and persistent job schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.core.enums import CollectionRunStatus


class CollectionOptions(BaseModel):
    metadata_only: bool = True
    download_media: bool = False
    max_items: int | None = Field(default=None, ge=1, le=10000)
    since_date: datetime | None = None

    @model_validator(mode="after")
    def download_disables_metadata_only(self) -> "CollectionOptions":
        if self.download_media:
            self.metadata_only = False
        return self


class ManualURLCollectionRequest(CollectionOptions):
    url: str = Field(min_length=8, max_length=2000)


class CollectionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_uid: str
    creator_id: int | None
    platform_account_id: int | None
    connector: str
    status: CollectionRunStatus
    source_url: str | None
    started_at: datetime | None
    completed_at: datetime | None
    items_found: int
    items_created: int
    items_updated: int
    items_skipped: int
    items_failed: int
    cursor_state: dict[str, Any] | None
    options: dict[str, Any]
    errors: list[dict[str, Any]] | None
    error_summary: str | None
    created_at: datetime
