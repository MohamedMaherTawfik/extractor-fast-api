"""Validated, cached Answer Bot policy configuration."""

from functools import lru_cache
from typing import Any

import yaml

from backend.core.config import get_settings
from backend.core.exceptions import ConfigurationError
from backend.core.paths import paths


@lru_cache(maxsize=1)
def get_answer_bot_config() -> dict[str, Any]:
    file = paths.resolve_under(paths.configs, get_settings().answer_bot_config_file)
    try: data = yaml.safe_load(file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc: raise ConfigurationError("Unable to load Answer Bot configuration") from exc
    if not isinstance(data, dict): raise ConfigurationError("Answer Bot configuration must be a mapping")
    return data
