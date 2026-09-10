"""Validated Creator Discovery Studio configuration."""

from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel, Field

from backend.core.config import get_settings
from backend.core.exceptions import ConfigurationError
from backend.core.paths import paths


class DiscoveryExecutionConfig(BaseModel):
    max_inputs_per_run: int = Field(default=10_000, ge=1, le=100_000)
    max_inline_jobs: int = Field(default=100, ge=1, le=1000)
    default_sample_size: int = Field(default=10, ge=1, le=30)
    max_sample_size: int = Field(default=30, ge=1, le=100)
    request_timeout_seconds: float = Field(default=15, gt=0, le=120)
    allow_public_page_fetch: bool = False


class MatchingConfig(BaseModel):
    thresholds: dict[str, float]
    weights: dict[str, float]


class IndustryConfig(BaseModel):
    code: str
    name: str
    keywords: list[str] = Field(default_factory=list)


class CreatorDiscoveryConfig(BaseModel):
    version: str = "1.0.0"
    execution: DiscoveryExecutionConfig = Field(default_factory=DiscoveryExecutionConfig)
    matching: MatchingConfig
    platforms: dict[str, dict[str, str]]
    industry_taxonomy: list[IndustryConfig] = Field(default_factory=list)


@lru_cache(maxsize=1)
def get_creator_discovery_config() -> CreatorDiscoveryConfig:
    filename = get_settings().creator_discovery_config_file
    source = paths.resolve_under(paths.configs, filename)
    try:
        payload: Any = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError("Unable to load Creator Discovery configuration") from exc
    if not isinstance(payload, dict):
        raise ConfigurationError("Creator Discovery configuration must be a mapping")
    return CreatorDiscoveryConfig.model_validate(payload)

