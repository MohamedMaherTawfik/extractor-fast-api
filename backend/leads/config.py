"""Validated, external control catalog for lead acquisition."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from backend.core.config import get_settings
from backend.core.exceptions import ConfigurationError
from backend.core.paths import paths


class LeadCatalog:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.version = str(data.get("version", "unknown"))
        self.country = data.get("country", {})
        self.execution = data.get("execution", {})
        self.workbook = data.get("workbook", {})
        self.sources = list(data.get("sources", []))
        self.scoring = data.get("scoring", {})
        self.category_mapping = {
            str(key).casefold(): str(value)
            for key, value in data.get("category_mapping", {}).items()
        }
        self.segments = list(data.get("segments", []))
        self.governorates = list(data.get("governorates", []))
        self.segment_by_id = {item["category_id"]: item for item in self.segments}
        self.governorate_by_id = {item["id"]: item for item in self.governorates}
        self.source_by_uid = {item["source_uid"]: item for item in self.sources}
        self._validate()

    def _validate(self) -> None:
        if len(self.governorates) != 27 or len(self.governorate_by_id) != 27:
            raise ConfigurationError("Lead acquisition config must define all 27 unique Egypt governorates")
        if len(self.segment_by_id) != len(self.segments):
            raise ConfigurationError("Lead segment category_id values must be unique")
        if not {"SRC_OVERTURE", "SRC_OSM_GEOFABRIK"}.issubset(self.source_by_uid):
            raise ConfigurationError("Both primary bulk lead sources must be configured")
        weights = self.scoring.get("weights", {})
        if abs(sum(float(value) for value in weights.values()) - 1.0) > 0.001:
            raise ConfigurationError("Lead scoring weights must sum to 1.0")

    @property
    def approved_keywords(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for segment in self.segments:
            for term in segment.get("terms", []):
                rows.append(
                    {
                        "keyword": str(term),
                        "category_id": segment["category_id"],
                        "approved": True,
                        "language": "ar" if any("\u0600" <= char <= "\u06ff" for char in str(term)) else "en",
                    }
                )
        return rows


@lru_cache(maxsize=1)
def get_lead_catalog() -> LeadCatalog:
    filename = get_settings().lead_acquisition_config_file
    config_path = paths.resolve_under(paths.configs, filename)
    if not config_path.exists():
        raise ConfigurationError(f"Lead acquisition config not found: configs/{filename}")
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError("Unable to read lead acquisition config") from exc
    if not isinstance(loaded, dict):
        raise ConfigurationError("Lead acquisition config must be a mapping")
    return LeadCatalog(loaded)

