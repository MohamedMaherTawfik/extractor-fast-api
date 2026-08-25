"""Validated, project-relative configuration for decision-engine policy."""

from functools import lru_cache

from pydantic import BaseModel, Field, model_validator
import yaml

from backend.core.exceptions import ConfigurationError
from backend.core.paths import paths


class RuleEngineConfig(BaseModel):
    version: str = "1.0.0"
    priority_tiers: dict[str, int]
    default_confidence_threshold: float = Field(default=0.8, ge=0, le=1)
    stale_policy_days: int = Field(default=90, ge=1)
    same_priority_hard_conflict: str = "human_review"
    cache_enabled: bool = True
    cache_max_entries: int = Field(default=512, ge=0, le=100000)
    max_rules_per_evaluation: int = Field(default=10000, ge=1, le=100000)

    @model_validator(mode="after")
    def validate_tiers(self):
        if not self.priority_tiers or len(set(self.priority_tiers.values())) != len(self.priority_tiers):
            raise ValueError("Priority tiers must be non-empty and distinct")
        return self


@lru_cache(maxsize=1)
def load_rule_config(filename: str = "rules.yaml") -> RuleEngineConfig:
    source = paths.resolve_under(paths.configs, filename)
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
        return RuleEngineConfig.model_validate(payload)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise ConfigurationError("Unable to load rules engine configuration") from exc
