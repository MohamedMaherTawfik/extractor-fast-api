"""Lead acquisition HTTP contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


RunMode = Literal["FULL_SCAN", "INCREMENTAL", "REFRESH_STALE", "ENRICH_ONLY", "VERIFY_ONLY"]


class LeadRunRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    mode: RunMode = "FULL_SCAN"
    sources: list[str] = Field(default_factory=list)
    governorates: list[str] = Field(default_factory=list)
    segments: list[str] = Field(default_factory=list)
    keyword_set: Literal["approved", "custom"] = "approved"
    keywords: list[str] = Field(default_factory=list, max_length=1000)
    dry_run: bool = False
    execute: bool = True
    adaptive_tiling: bool = True
    max_records_per_job: int | None = Field(default=None, ge=1, le=10000)
    source_options: dict[str, Any] = Field(default_factory=dict)


class LeadRunPlan(BaseModel):
    dry_run: bool = True
    enabled_sources: list[str]
    governorates: list[str]
    segments: list[str]
    keyword_count: int
    planned_jobs: int
    missing_credentials: list[str]
    warnings: list[str]


class LeadJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    job_uid: str
    source_uid: str
    governorate: str | None
    tile: dict[str, Any] | None
    category: str | None
    status: str
    attempt: int
    checkpoint: dict[str, Any]
    processed: int
    found: int
    unique_count: int
    duplicates: int
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None


class LeadRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    run_uid: str
    name: str
    mode: str
    sources: list[str]
    geography: dict[str, Any]
    segments: list[str]
    keywords: list[str]
    status: str
    planned_jobs: int
    processed: int
    found: int
    unique_count: int
    duplicates: int
    errors: int
    current_source: str | None
    current_governorate: str | None
    current_category: str | None
    warnings: list[str]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    jobs: list[LeadJobResponse] = Field(default_factory=list)


class LeadExportRequest(BaseModel):
    format: Literal["csv", "xlsx", "parquet"]
    fit_class: str | None = None
    governorate: str | None = None
    category: str | None = None
    source: str | None = None
    verified_only: bool = False

