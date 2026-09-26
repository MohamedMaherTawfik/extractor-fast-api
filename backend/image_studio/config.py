"""Configuration loading for validated image-studio integrations."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from backend.core.config import get_settings
from backend.core.exceptions import ConfigurationError
from backend.core.paths import paths
from backend.image_studio.schemas import ImageStudioConfig


@lru_cache(maxsize=1)
def load_image_studio_config() -> ImageStudioConfig:
    source = paths.resolve_under(paths.configs, get_settings().image_studio_config_file)
    try:
        payload: dict[str, Any] = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
        settings = get_settings()
        local_overrides = {
            "comfyui_install_path": settings.image_studio_comfyui_install_path,
            "custom_nodes_path": settings.image_studio_custom_nodes_path,
            "models_path": settings.image_studio_models_path,
        }
        payload.update({key: value for key, value in local_overrides.items() if value})
        return ImageStudioConfig.model_validate(payload)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ConfigurationError("Unable to load Image Studio configuration") from exc
