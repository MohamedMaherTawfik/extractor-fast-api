"""Creator import response contracts."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.core.enums import ImportStatus


class CreatorImportErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    row_number: int
    raw_data: dict[str, Any]
    error_type: str
    error_message: str
    created_at: datetime


class CreatorImportBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_uid: str
    source_file: str
    rows_total: int
    rows_success: int
    rows_failed: int
    started_at: datetime
    completed_at: datetime | None
    status: ImportStatus
    error_summary: str | None
    errors: list[CreatorImportErrorResponse] = Field(default_factory=list)
