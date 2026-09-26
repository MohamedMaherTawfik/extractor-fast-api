"""Configuration loader for ComfyUI-backed video generation."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from backend.core.config import get_settings
from backend.core.exceptions import ConfigurationError
from backend.core.paths import paths


class InjectionTarget(BaseModel):
    node_id: str
    input: str


class VideoModelConfig(BaseModel):
    model_id: str
    display_name: str
    workflow_file: str
    enabled: bool = True
    # A template is deliberately not a runnable model.  Only an operator who
    # has validated an exported API workflow on the target ComfyUI runtime may
    # set this to true.
    verified: bool = False
    fps: int = Field(default=16, ge=1, le=120)
    max_duration_seconds: float = Field(default=20, ge=1, le=120)
    aspect_ratios: list[str] = Field(default_factory=lambda: ["9:16", "16:9"])
    supports_image_reference: bool = True
    model_files: list[str] = Field(default_factory=list)
    required_custom_nodes: list[str] = Field(default_factory=list)
    injections: dict[str, InjectionTarget] = Field(default_factory=dict)
    output_node_ids: list[str] = Field(default_factory=list)


class PromptRecipeConfig(BaseModel):
    recipe_id: str
    name: str
    master_prompt: str
    camera_style: str
    lighting: str
    colors: str
    environment: str
    realism_level: str
    motion_style: str
    negative_prompt: list[str] = Field(default_factory=list)


class VideoEngineConfig(BaseModel):
    version: str = "1.0.0"
    default_model: str
    worker_concurrency: int = Field(default=1, ge=1, le=4)
    poll_interval_seconds: float = Field(default=1.0, ge=0.1, le=30)
    upload_timeout_seconds: int = Field(default=300, ge=30, le=3600)
    generation_timeout_seconds: int = Field(default=3600, ge=30, le=86400)
    max_reference_size_bytes: int = Field(default=25 * 1024 * 1024, ge=1024)
    max_reference_dimension: int = Field(default=12000, ge=128, le=50000)
    models: list[VideoModelConfig]
    recipes: list[PromptRecipeConfig]
    accepted_output_extensions: list[str] = Field(default_factory=lambda: [".mp4", ".webm", ".mov", ".gif"])

    @model_validator(mode="after")
    def references_are_valid(self):
        model_ids = {item.model_id for item in self.models}
        if self.default_model not in model_ids:
            raise ValueError("default_model must reference a configured video model")
        if len(model_ids) != len(self.models):
            raise ValueError("Video model IDs must be unique")
        recipe_ids = {item.recipe_id for item in self.recipes}
        if len(recipe_ids) != len(self.recipes):
            raise ValueError("Prompt recipe IDs must be unique")
        if not self.accepted_output_extensions or any(not value.startswith(".") for value in self.accepted_output_extensions):
            raise ValueError("accepted_output_extensions must contain file extensions beginning with '.'")
        return self

    def model(self, model_id: str) -> VideoModelConfig:
        model = next((item for item in self.models if item.model_id == model_id), None)
        if model is None:
            raise ConfigurationError(f"Unknown video model: {model_id}")
        return model

    def recipe(self, recipe_id: str) -> PromptRecipeConfig:
        recipe = next((item for item in self.recipes if item.recipe_id == recipe_id), None)
        if recipe is None:
            raise ConfigurationError(f"Unknown video recipe: {recipe_id}")
        return recipe


@lru_cache(maxsize=1)
def load_video_config() -> VideoEngineConfig:
    settings = get_settings()
    source = paths.resolve_under(paths.configs, settings.video_generation_config_file)
    try:
        payload: dict[str, Any] = yaml.safe_load(source.read_text(encoding="utf-8"))
        return VideoEngineConfig.model_validate(payload)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise ConfigurationError("Unable to load video generation configuration") from exc
