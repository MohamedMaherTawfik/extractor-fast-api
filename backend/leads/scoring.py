"""Deterministic config-driven lead fit scoring and classification."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.leads.config import LeadCatalog, get_lead_catalog


class LeadScorer:
    def __init__(self, catalog: LeadCatalog | None = None) -> None:
        self.catalog = catalog or get_lead_catalog()
        self.weights = {key: float(value) for key, value in self.catalog.scoring["weights"].items()}
        self.thresholds = {key: float(value) for key, value in self.catalog.scoring["classes"].items()}

    def score(self, lead: Any, *, source_count: int = 1) -> tuple[float, str, dict[str, Any]]:
        tier = getattr(lead, "segment_tier", None) if not isinstance(lead, dict) else lead.get("segment_tier")
        buyer_type = getattr(lead, "buyer_type", None) if not isinstance(lead, dict) else lead.get("buyer_type")
        get = (lambda key: lead.get(key)) if isinstance(lead, dict) else (lambda key: getattr(lead, key, None))
        professional = buyer_type in {"PROFESSIONAL_SERVICE", "CLINIC", "ACADEMY"}
        resale = buyer_type in {"IMPORTER", "DISTRIBUTOR", "WHOLESALER", "SUPPLIER", "RETAILER", "ONLINE_RETAILER"}
        contact_fields = sum(bool(get(key)) for key in ("phone_normalized", "email", "website")) + bool(get("social_links"))
        last_seen = get("source_last_seen_at") or datetime.now(UTC)
        age_days = max(0, (datetime.now(UTC) - self._aware(last_seen)).days)
        governorate = str(get("governorate") or "")
        density = self.catalog.governorate_by_id.get(governorate, {}).get("density", "LOW")
        components = {
            "category_fit": 100 if tier == 1 else 75 if tier == 2 else 25,
            "commercial_scale": 95 if buyer_type in {"IMPORTER", "DISTRIBUTOR", "WHOLESALER"} else 70 if resale else 50,
            "professional_consumption": 95 if professional else 60 if resale else 30,
            "resale_potential": 100 if resale else 35,
            "contactability": min(100, contact_fields * 25),
            "freshness": 100 if age_days <= 30 else 75 if age_days <= 180 else 45,
            "geographic_priority": {"HIGH": 90, "MEDIUM": 70, "LOW": 55}.get(str(density), 55),
            "verification": 100 if get("last_verified_at") else 70 if source_count > 1 else 40,
        }
        weighted = {key: round(value * self.weights[key], 3) for key, value in components.items()}
        total = round(sum(weighted.values()), 2)
        fit_class = next((name for name in ("A+", "A", "B", "C") if total >= self.thresholds[name]), "C")
        return total, fit_class, {"components": components, "weights": self.weights, "weighted": weighted, "source_count": source_count, "policy_version": self.catalog.version}

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

