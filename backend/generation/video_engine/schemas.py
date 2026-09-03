"""Contracts for the dedicated AI Video Studio."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


AspectRatio = Literal["1:1", "4:5", "9:16", "16:9"]


class CharacterProfile(BaseModel):
    character_id: str
    name: str
    version: int = 1
    reference_image: str
    reference_checksum: str
    identity_data: dict[str, Any] = Field(default_factory=dict)
    style_profile: dict[str, Any] = Field(default_factory=dict)
    recurring_attributes: list[str] = Field(default_factory=list)
    negative_constraints: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class VideoGenerationRequest(BaseModel):
    character_id: str = Field(min_length=1, max_length=150)
    recipe_id: str = Field(default="EMY_CHARACTER_V1", min_length=1, max_length=150)
    creative_idea: str = Field(min_length=2, max_length=4000)
    master_prompt: str | None = Field(default=None, max_length=12000)
    video_duration: float = Field(default=5.0, ge=1.0, le=120.0)
    style: str = Field(default="recipe_default", min_length=1, max_length=200)
    camera_motion: str = Field(default="gentle cinematic push-in", min_length=1, max_length=500)
    aspect_ratio: AspectRatio = "9:16"
    model_id: str | None = Field(default=None, max_length=150)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    execute: bool = True
    calendar_item_id: str | None = Field(default=None, max_length=255)
    publish_at: datetime | None = None

    @field_validator("creative_idea", "camera_motion", "style", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class ContentCalendarItem(BaseModel):
    idea: str = Field(min_length=2, max_length=4000)
    title: str | None = Field(default=None, max_length=300)
    calendar_item_id: str | None = Field(default=None, max_length=255)
    publish_at: datetime | None = None
    video_duration: float | None = Field(default=None, ge=1.0, le=120.0)
    style: str | None = Field(default=None, max_length=200)
    camera_motion: str | None = Field(default=None, max_length=500)
    aspect_ratio: AspectRatio | None = None
    model_id: str | None = Field(default=None, max_length=150)


class BatchGenerationRequest(BaseModel):
    character_id: str = Field(min_length=1, max_length=150)
    recipe_id: str = Field(default="EMY_CHARACTER_V1", min_length=1, max_length=150)
    items: list[ContentCalendarItem] = Field(min_length=1, max_length=120)
    video_duration: float = Field(default=5.0, ge=1.0, le=120.0)
    style: str = Field(default="recipe_default", max_length=200)
    camera_motion: str = Field(default="gentle cinematic push-in", max_length=500)
    aspect_ratio: AspectRatio = "9:16"
    model_id: str | None = Field(default=None, max_length=150)
    execute: bool = True


class PromptPackage(BaseModel):
    recipe_id: str
    master_prompt: str
    positive_prompt: str
    negative_prompt: str
    script: dict[str, Any]
    identity_constraints: dict[str, Any]


class VideoJob(BaseModel):
    job_id: str
    batch_id: str | None = None
    status: str
    progress: int = Field(ge=0, le=100)
    stage: str
    request: dict[str, Any]
    prompt_package: dict[str, Any] | None = None
    model: dict[str, Any] | None = None
    comfyui_prompt_id: str | None = None
    final_video: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class BatchRecord(BaseModel):
    batch_id: str
    status: str
    job_ids: list[str]
    total: int
    created_at: datetime
