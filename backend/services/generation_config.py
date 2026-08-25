"""Validated generation configuration loaded from a project-relative YAML file."""

from functools import lru_cache

import yaml

from backend.core.config import get_settings
from backend.core.exceptions import ConfigurationError
from backend.core.paths import paths
from backend.schemas.generation import GenerationEngineConfig


@lru_cache(maxsize=1)
def load_generation_config() -> GenerationEngineConfig:
    source = paths.resolve_under(paths.configs, get_settings().generation_config_file)
    try:
        return GenerationEngineConfig.model_validate(yaml.safe_load(source.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise ConfigurationError("Unable to load generation configuration") from exc
