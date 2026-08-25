"""Credential-free per-platform connector configuration."""

from typing import Any

import yaml
from pydantic import BaseModel, Field

from backend.core.enums import ConnectorAvailability, Platform
from backend.core.exceptions import ConfigurationError
from backend.core.paths import paths


SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "cookies",
    "credential",
    "credentials",
    "password",
    "secret",
    "session",
    "token",
    "api_key",
}


def is_sensitive_key(key: object) -> bool:
    normalized = str(key).casefold().replace("-", "_")
    return normalized in SENSITIVE_KEYS or any(
        normalized.endswith(f"_{suffix}")
        for suffix in ("token", "secret", "password", "cookie", "api_key")
    )


class ConnectorConfig(BaseModel):
    enabled: bool = False
    availability: ConnectorAvailability = ConnectorAvailability.NOT_CONFIGURED
    rate_limit_per_minute: float = Field(default=30, gt=0)
    timeout_seconds: float = Field(default=20, gt=0)
    max_retries: int = Field(default=3, ge=0, le=10)
    backoff_initial_seconds: float = Field(default=1, ge=0)
    backoff_max_seconds: float = Field(default=30, ge=0)
    download_media: bool = False
    max_items_per_run: int = Field(default=500, ge=1, le=10000)
    preserve_raw: bool = True


class ConnectorConfigLoader:
    def load(self, platform: Platform) -> ConnectorConfig:
        if platform is Platform.OTHER:
            return ConnectorConfig(
                enabled=False,
                availability=ConnectorAvailability.UNSUPPORTED,
            )
        source = paths.resolve_under(
            paths.connector_configs,
            f"{platform.value}.yaml",
        )
        if not source.is_file():
            return ConnectorConfig()
        try:
            data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigurationError(
                f"Unable to load connector config for {platform.value}"
            ) from exc
        if not isinstance(data, dict):
            raise ConfigurationError("Connector config must contain a mapping")
        self._reject_sensitive_keys(data)
        return ConnectorConfig.model_validate(data)

    @classmethod
    def _reject_sensitive_keys(cls, value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if is_sensitive_key(key):
                    raise ConfigurationError(
                        "Credentials are not allowed in connector YAML"
                    )
                cls._reject_sensitive_keys(child)
        elif isinstance(value, list):
            for child in value:
                cls._reject_sensitive_keys(child)
