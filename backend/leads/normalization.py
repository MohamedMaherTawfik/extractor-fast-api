"""Conservative Arabic/English business lead normalization."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse

from backend.leads.config import LeadCatalog, get_lead_catalog
from backend.leads.geography import GeographyService


ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
NON_NAME = re.compile(r"[^\w\u0600-\u06ff]+", re.UNICODE)


@dataclass(slots=True)
class RawLeadRecord:
    source_uid: str
    source_record_id: str
    business_name: str
    category_raw: str | None = None
    address: str | None = None
    city: str | None = None
    district: str | None = None
    governorate: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    social_links: list[str] = field(default_factory=list)
    business_status: str | None = None
    confidence: float | None = None
    source_version: str | None = None
    keyword: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class LeadNormalizer:
    def __init__(self, catalog: LeadCatalog | None = None, geography: GeographyService | None = None) -> None:
        self.catalog = catalog or get_lead_catalog()
        self.geography = geography or GeographyService(self.catalog)
        self._governorate_aliases: dict[str, str] = {}
        for item in self.catalog.governorates:
            for value in (item["id"], item["name"], item["name_ar"], str(item["id"]).replace("_", " ")):
                self._governorate_aliases[self.normalize_text(str(value))] = item["id"]

    @staticmethod
    def normalize_text(value: str | None) -> str:
        if not value:
            return ""
        text = unicodedata.normalize("NFKC", value).translate(ARABIC_DIGITS).casefold()
        text = ARABIC_DIACRITICS.sub("", text).replace("ـ", "")
        text = text.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي"}))
        return " ".join(NON_NAME.sub(" ", text).split())

    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if not value:
            return None
        digits = re.sub(r"\D", "", value.translate(ARABIC_DIGITS))
        if digits.startswith("0020"):
            digits = digits[2:]
        if digits.startswith("20") and 11 <= len(digits) <= 12:
            return f"+{digits}"
        if digits.startswith("0") and 10 <= len(digits) <= 11:
            return f"+20{digits[1:]}"
        return None

    @staticmethod
    def normalize_domain(value: str | None) -> str | None:
        if not value:
            return None
        candidate = value.strip()
        parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
        host = (parsed.hostname or "").strip(".").casefold()
        if host.startswith("www."):
            host = host[4:]
        try:
            return host.encode("idna").decode("ascii") or None
        except UnicodeError:
            return None

    def normalize_category(self, category_raw: str | None, business_name: str) -> str | None:
        candidates = [self.normalize_text(category_raw), self.normalize_text(business_name)]
        raw_key = str(category_raw or "").casefold().replace(" ", "_")
        if raw_key in self.catalog.category_mapping:
            return self.catalog.category_mapping[raw_key]
        for segment in self.catalog.segments:
            for term in segment.get("terms", []):
                normalized_term = self.normalize_text(str(term))
                if normalized_term and any(normalized_term in candidate for candidate in candidates):
                    return str(segment["category_id"])
        return None

    def normalize_governorate(self, value: str | None, longitude: float | None, latitude: float | None) -> str | None:
        normalized = self.normalize_text(value)
        if normalized in self._governorate_aliases:
            return self._governorate_aliases[normalized]
        return self.geography.governorate_for_point(longitude, latitude)

    def normalize(self, record: RawLeadRecord) -> dict[str, Any]:
        latitude = float(record.latitude) if record.latitude is not None else None
        longitude = float(record.longitude) if record.longitude is not None else None
        if latitude is not None and not (-90 <= latitude <= 90):
            latitude = None
        if longitude is not None and not (-180 <= longitude <= 180):
            longitude = None
        category_id = self.normalize_category(record.category_raw, record.business_name)
        segment = self.catalog.segment_by_id.get(category_id or "", {})
        website = record.website.strip() if record.website else None
        return {
            "business_name_raw": record.business_name.strip(),
            "business_name_normalized": self.normalize_text(record.business_name),
            "category_id": category_id,
            "segment_tier": segment.get("tier"),
            "buyer_type": segment.get("buyer_type"),
            "governorate": self.normalize_governorate(record.governorate, longitude, latitude),
            "city": record.city.strip() if record.city else None,
            "district": record.district.strip() if record.district else None,
            "address_raw": record.address.strip() if record.address else None,
            "address_normalized": self.normalize_text(record.address) or None,
            "latitude": latitude,
            "longitude": longitude,
            "phone_raw": record.phone,
            "phone_normalized": self.normalize_phone(record.phone),
            "email": record.email.strip().casefold() if record.email and "@" in record.email else None,
            "website": website,
            "domain_normalized": self.normalize_domain(website),
            "social_links": list(dict.fromkeys(record.social_links)),
            "business_status": record.business_status,
            "source_confidence": record.confidence,
            "chain_key": self.normalize_text(record.business_name),
        }

