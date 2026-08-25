"""Central settings loaded from environment, .env, and YAML."""

from functools import lru_cache
from typing import Any, Literal

import yaml
from pydantic import Field
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from backend.core.exceptions import ConfigurationError
from backend.core.paths import paths


class YamlSettingsSource(PydanticBaseSettingsSource):
    """Lowest-priority project configuration source."""

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        self._data = self._read_config()

    @staticmethod
    def _read_config() -> dict[str, Any]:
        if not paths.config_file.exists():
            return {}
        try:
            loaded = yaml.safe_load(paths.config_file.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigurationError("Unable to load the application YAML config") from exc
        if loaded is None:
            return {}
        if not isinstance(loaded, dict):
            raise ConfigurationError("Application YAML config must contain a mapping")
        return loaded

    def get_field_value(
        self,
        field: FieldInfo,
        field_name: str,
    ) -> tuple[Any, str, bool]:
        return self._data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._data


class Settings(BaseSettings):
    """Validated application settings with environment overrides."""

    model_config = SettingsConfigDict(
        env_prefix="EMY_",
        env_file=paths.env_file,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "EMY Private AI OS"
    environment: Literal["local", "remote"] = "local"
    version: str = "0.1.0"
    host: Literal["127.0.0.1", "localhost"] = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    database_echo: bool = False
    import_max_file_size_mb: int = Field(default=25, ge=1, le=500)
    creator_import_column_mapping: dict[str, str] = Field(default_factory=dict)
    analysis_rules_file: str = "analysis_extraction.yaml"
    analysis_taxonomy_file: str = "content_analysis.yaml"
    analyzer_version: str = "1.0.0"
    analysis_chunk_size_bytes: int = Field(
        default=1_048_576,
        ge=65_536,
        le=16_777_216,
    )
    frame_sampling_interval_ms: int = Field(default=1000, ge=100, le=60000)
    pattern_config_file: str = "pattern_mining.yaml"
    pattern_engine_version: str = "1.0.0"
    recipe_engine_version: str = "1.0.0"
    rules_config_file: str = "rules.yaml"
    rules_engine_version: str = "1.0.0"
    generation_config_file: str = "generation.yaml"
    generation_engine_version: str = "1.0.0"
    run_live_generation_tests: bool = False
    sales_engine_version: str = "1.0.0"
    sales_config_file: str = "sales.yaml"
    allow_negative_stock: bool = False
    sales_default_currency: str = "EGP"
    msc_high_confidence_threshold: float = Field(default=0.90, ge=0, le=1)
    msc_medium_confidence_threshold: float = Field(default=0.70, ge=0, le=1)
    sales_velocity_windows: list[int] = Field(default_factory=lambda: [7, 30, 90])
    sales_slow_mover_days: int = Field(default=90, ge=1)
    sales_reorder_cover_days: int = Field(default=30, ge=1)
    run_live_msc_extraction_tests: bool = False
    answer_bot_config_file: str = "answer_bot.yaml"
    answer_bot_version: str = "1.0.0"
    run_live_messaging_tests: bool = False
    messaging_privacy_mode: str = "LOCAL_ONLY"

    @property
    def database_url(self) -> str:
        return f"sqlite+pysqlite:///{paths.database_file.as_posix()}"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlSettingsSource(settings_cls),
            file_secret_settings,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
