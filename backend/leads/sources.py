"""Lead source capability and adapter registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.core.config import Settings, get_settings
from backend.leads.collectors import (
    BaseLeadCollector,
    FoursquarePlacesAdapter,
    GooglePlacesAdapter,
    OSMGeofabrikCollector,
    OfficialRegistryAdapter,
    OvertureCollector,
    WebsiteEnrichmentAdapter,
)
from backend.leads.config import LeadCatalog, get_lead_catalog


@dataclass(slots=True)
class SourceDescriptor:
    config: dict[str, Any]
    configured: bool
    status: str
    status_detail: str | None


class LeadSourceRegistry:
    def __init__(self, catalog: LeadCatalog | None = None, settings: Settings | None = None) -> None:
        self.catalog = catalog or get_lead_catalog()
        self.settings = settings or get_settings()

    def describe_all(self) -> list[SourceDescriptor]:
        return [self.describe(item["source_uid"]) for item in self.catalog.sources]

    def describe(self, source_uid: str) -> SourceDescriptor:
        config = self.catalog.source_by_uid.get(source_uid)
        if config is None:
            raise KeyError(source_uid)
        credential_name = config.get("credential_setting")
        configured = not config.get("credentials_required") or bool(getattr(self.settings, str(credential_name), None))
        if not config.get("enabled"):
            status = "NOT_CONFIGURED" if config.get("credentials_required") and not configured else "DISABLED"
        elif not configured:
            status = "NOT_CONFIGURED"
        else:
            status = "READY"
        detail = None
        if "PERMISSION_REQUIRED" in str(config.get("terms_status")):
            status, detail = "DISABLED", "Permission/license review required"
        return SourceDescriptor(config=config, configured=configured, status=status, status_detail=detail)

    def collector(self, source_uid: str) -> BaseLeadCollector:
        if source_uid == "SRC_OVERTURE":
            return OvertureCollector(self.catalog)
        if source_uid == "SRC_OSM_GEOFABRIK":
            return OSMGeofabrikCollector(self.catalog)
        if source_uid == "SRC_GOOGLE_PLACES":
            return GooglePlacesAdapter(source_uid, self.settings.google_places_api_key)
        if source_uid == "SRC_FOURSQUARE":
            return FoursquarePlacesAdapter(source_uid, self.settings.foursquare_api_key)
        if source_uid == "SRC_WEBSITE":
            return WebsiteEnrichmentAdapter(source_uid, "enabled" if self.catalog.source_by_uid[source_uid].get("enabled") else None)
        if source_uid == "SRC_OFFICIAL_REGISTRY":
            return OfficialRegistryAdapter(source_uid, None)
        raise RuntimeError(f"No collector is registered for {source_uid}")

