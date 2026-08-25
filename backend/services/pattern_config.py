"""Validated, external configuration for pattern, similarity, and recipe logic."""

from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

from backend.core.config import get_settings
from backend.core.exceptions import ConfigurationError
from backend.core.paths import paths


class PatternThresholds(BaseModel):
    min_pattern_support_count: int = Field(ge=1)
    min_pattern_support_ratio: float = Field(ge=0, le=1)
    min_confidence: float = Field(ge=0, le=1)
    minimum_sample_size: int = Field(ge=1)
    minimum_source_contents: int = Field(ge=1)
    minimum_source_creators: int = Field(ge=1)
    early_position_max: float = Field(ge=0, le=1)
    short_hook_max_ratio: float = Field(ge=0, le=1)
    fast_cut_max_average_ms: int = Field(ge=1)


class PatternConfig(BaseModel):
    version: str
    thresholds: PatternThresholds
    score_weights: dict[str, float]
    similarity_weights: dict[str, float]
    performance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def positive_weight_groups(self) -> "PatternConfig":
        for label, values in (
            ("score_weights", self.score_weights),
            ("similarity_weights", self.similarity_weights),
        ):
            if not values or any(value < 0 for value in values.values()):
                raise ValueError(f"{label} must contain non-negative weights")
            if sum(values.values()) <= 0:
                raise ValueError(f"{label} must have a positive total")
        return self


@lru_cache(maxsize=4)
def load_pattern_config(filename: str | None = None) -> PatternConfig:
    selected = filename or get_settings().pattern_config_file
    path = paths.configs / selected
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return PatternConfig.model_validate(payload)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise ConfigurationError(f"Unable to load pattern config {selected}") from exc
