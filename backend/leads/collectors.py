"""Streaming official-source collectors for business POI discovery."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx

from backend.core.paths import paths
from backend.leads.config import LeadCatalog, get_lead_catalog
from backend.leads.normalization import RawLeadRecord


EmitRecord = Callable[[RawLeadRecord, int], bool]


class SourceRateLimitError(RuntimeError):
    """Preserve provider rate evidence without triggering an aggressive retry."""

    def __init__(
        self,
        source_uid: str,
        provider_message: str,
        *,
        status_code: int = 429,
        retry_after: str | None = None,
        reset_time: str | None = None,
    ) -> None:
        super().__init__(provider_message)
        self.source_uid = source_uid
        self.status_code = status_code
        self.provider_message = provider_message[:1000]
        self.retry_after = retry_after
        self.reset_time = reset_time

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_uid,
            "http_code": self.status_code,
            "provider_message": self.provider_message,
            "retry_after": self.retry_after,
            "reset_time": self.reset_time or "RESET_TIME_UNKNOWN",
        }


def _raise_for_source_status(response: httpx.Response, source_uid: str) -> None:
    if response.status_code == 429:
        raise SourceRateLimitError(
            source_uid,
            response.text[:1000] or "Too many requests",
            retry_after=response.headers.get("Retry-After"),
            reset_time=response.headers.get("X-RateLimit-Reset") or response.headers.get("RateLimit-Reset"),
        )
    response.raise_for_status()


@dataclass(slots=True)
class CollectionContext:
    source_uid: str
    run_uid: str
    job_uid: str
    governorate: str | None
    tile: dict[str, Any] | None
    segment_ids: list[str]
    keywords: list[str]
    checkpoint: dict[str, Any] = field(default_factory=dict)
    max_records: int | None = None
    options: dict[str, Any] = field(default_factory=dict)


class BaseLeadCollector:
    collector_version = "1.0.0"

    def collect(self, context: CollectionContext, emit: EmitRecord) -> dict[str, Any]:
        raise NotImplementedError


class OvertureCollector(BaseLeadCollector):
    """BBox-filtered streaming access through Overture's official Python client."""

    catalog_url = "https://stac.overturemaps.org/catalog.json"

    def __init__(self, catalog: LeadCatalog | None = None) -> None:
        self.catalog = catalog or get_lead_catalog()

    def discover_latest_release(self) -> str:
        timeout = float(self.catalog.execution.get("overture_timeout_seconds", 90))
        response = httpx.get(self.catalog_url, timeout=timeout, follow_redirects=True)
        _raise_for_source_status(response, "SRC_OVERTURE")
        release = response.json().get("latest")
        if not release:
            raise RuntimeError("Overture STAC catalog did not advertise a latest release")
        return str(release)

    def collect(self, context: CollectionContext, emit: EmitRecord) -> dict[str, Any]:
        try:
            from overturemaps import record_batch_reader
            from shapely import from_wkb
        except ImportError as exc:  # pragma: no cover - installation contract
            raise RuntimeError("Overture dependencies are not installed in the project environment") from exc
        if not context.tile or not context.tile.get("bbox"):
            raise ValueError("Overture collection requires a bbox tile")
        release = self.discover_latest_release()
        timeout = float(self.catalog.execution.get("overture_timeout_seconds", 90))
        reader = record_batch_reader(
            "place",
            bbox=tuple(context.tile["bbox"]),
            release=release,
            connect_timeout=min(timeout, 30),
            request_timeout=timeout,
            stac=True,
        )
        if reader is None:
            raise RuntimeError("Overture returned no reader for the requested tile")
        skip = int(context.checkpoint.get("raw_position", 0))
        scanned = 0
        emitted = 0
        allowed = set(context.segment_ids)
        for batch in reader:
            for row in batch.to_pylist():
                scanned += 1
                if scanned <= skip:
                    continue
                raw = self._to_record(row, release, context.governorate, from_wkb)
                category = self._mapped_category(raw)
                if allowed and category not in allowed:
                    if not self._keyword_match(raw, context.keywords):
                        if not emit(None, scanned):  # type: ignore[arg-type]
                            return {"release": release, "scanned": scanned, "emitted": emitted}
                        continue
                if not raw.business_name:
                    if not emit(None, scanned):  # type: ignore[arg-type]
                        return {"release": release, "scanned": scanned, "emitted": emitted}
                    continue
                raw.keyword = self._matching_keyword(raw, context.keywords)
                emitted += 1
                if not emit(raw, scanned):
                    return {"release": release, "scanned": scanned, "emitted": emitted}
                if context.max_records and emitted >= context.max_records:
                    return {"release": release, "scanned": scanned, "emitted": emitted}
        return {"release": release, "scanned": scanned, "emitted": emitted}

    def _mapped_category(self, record: RawLeadRecord) -> str | None:
        key = str(record.category_raw or "").casefold().replace(" ", "_")
        return self.catalog.category_mapping.get(key)

    @staticmethod
    def _keyword_match(record: RawLeadRecord, keywords: list[str]) -> bool:
        haystack = f"{record.business_name} {record.category_raw or ''}".casefold()
        return any(keyword.casefold() in haystack for keyword in keywords)

    @staticmethod
    def _matching_keyword(record: RawLeadRecord, keywords: list[str]) -> str | None:
        haystack = f"{record.business_name} {record.category_raw or ''}".casefold()
        return next((keyword for keyword in keywords if keyword.casefold() in haystack), None)

    @staticmethod
    def _to_record(row: dict[str, Any], release: str, governorate: str | None, from_wkb: Any) -> RawLeadRecord:
        names = row.get("names") or {}
        name = names.get("primary") or ""
        if not name:
            common = names.get("common") or {}
            if isinstance(common, list):
                name = next((value for _, value in common if value), "")
            elif isinstance(common, dict):
                name = next((value for value in common.values() if value), "")
        categories = row.get("categories") or row.get("taxonomy") or {}
        category = categories.get("primary")
        addresses = row.get("addresses") or []
        address = addresses[0] if addresses else {}
        geometry = from_wkb(row["geometry"]) if row.get("geometry") else None
        longitude = float(geometry.x) if geometry is not None and geometry.geom_type == "Point" else None
        latitude = float(geometry.y) if geometry is not None and geometry.geom_type == "Point" else None
        sources = row.get("sources") or []
        source_record = sources[0] if sources else {}
        return RawLeadRecord(
            source_uid="SRC_OVERTURE",
            source_record_id=str(row.get("id")),
            business_name=str(name or ""),
            category_raw=str(category) if category else None,
            address=address.get("freeform"),
            city=address.get("locality"),
            governorate=address.get("region") or governorate,
            latitude=latitude,
            longitude=longitude,
            phone=(row.get("phones") or [None])[0],
            email=(row.get("emails") or [None])[0],
            website=(row.get("websites") or [None])[0],
            social_links=list(row.get("socials") or []),
            business_status=row.get("operating_status"),
            confidence=row.get("confidence"),
            source_version=release,
            raw={
                "overture_id": row.get("id"),
                "record_version": row.get("version"),
                "basic_category": row.get("basic_category"),
                "source_dataset": source_record.get("dataset"),
                "source_provider": source_record.get("provider"),
                "source_update_time": source_record.get("update_time"),
            },
        )


class _StopCollection(Exception):
    pass


class OSMGeofabrikCollector(BaseLeadCollector):
    """Streaming Egypt PBF reader with resumable HTTP download and tag filtering."""

    RELEVANT = {"shop", "amenity", "healthcare", "office", "craft", "beauty", "hairdresser", "pharmacy", "spa", "leisure"}

    def __init__(self, catalog: LeadCatalog | None = None) -> None:
        self.catalog = catalog or get_lead_catalog()
        self.extract_path = paths.lead_raw / "geofabrik" / "egypt-latest.osm.pbf"

    def ensure_egypt_extract(self) -> Path:
        url = str(self.catalog.execution["geofabrik_url"])
        self.extract_path.parent.mkdir(parents=True, exist_ok=True)
        if self.extract_path.exists() and self.extract_path.stat().st_size > 1_000_000:
            return self.extract_path
        partial = self.extract_path.with_suffix(self.extract_path.suffix + ".part")
        start = partial.stat().st_size if partial.exists() else 0
        headers = {"Range": f"bytes={start}-"} if start else {}
        with httpx.stream("GET", url, headers=headers, timeout=120, follow_redirects=True) as response:
            _raise_for_source_status(response, "SRC_OSM_GEOFABRIK")
            mode = "ab" if start and response.status_code == 206 else "wb"
            with partial.open(mode) as stream:
                for chunk in response.iter_bytes(1024 * 1024):
                    stream.write(chunk)
        partial.replace(self.extract_path)
        return self.extract_path

    def collect(self, context: CollectionContext, emit: EmitRecord) -> dict[str, Any]:
        if context.options.get("osm_mode") == "overpass":
            return self._collect_overpass(context, emit)
        try:
            import osmium
        except ImportError as exc:  # pragma: no cover - installation contract
            raise RuntimeError("osmium is not installed in the project environment") from exc
        extract = self.ensure_egypt_extract()
        skip = int(context.checkpoint.get("raw_position", 0))
        collector = self

        class Handler(osmium.SimpleHandler):
            def __init__(self) -> None:
                super().__init__()
                self.scanned = 0
                self.emitted = 0

            def node(self, node):
                self._process("node", node, node.location.lon if node.location.valid() else None, node.location.lat if node.location.valid() else None)

            def way(self, way):
                locations = [node.location for node in way.nodes if node.location.valid()]
                lon = sum(item.lon for item in locations) / len(locations) if locations else None
                lat = sum(item.lat for item in locations) / len(locations) if locations else None
                self._process("way", way, lon, lat)

            def area(self, area):
                # Ways are already handled; relations without an inexpensive centroid are skipped.
                return None

            def _process(self, object_type, obj, longitude, latitude):
                tags = {tag.k: tag.v for tag in obj.tags}
                if not collector.RELEVANT.intersection(tags) or not tags.get("name"):
                    return
                self.scanned += 1
                if self.scanned <= skip:
                    return
                category = collector._category(tags)
                if context.segment_ids and category not in context.segment_ids:
                    if not collector._keyword_match(tags, context.keywords):
                        if not emit(None, self.scanned):  # type: ignore[arg-type]
                            raise _StopCollection
                        return
                record = collector._to_record(object_type, obj.id, tags, longitude, latitude, context.governorate)
                self.emitted += 1
                if not emit(record, self.scanned):
                    raise _StopCollection
                if context.max_records and self.emitted >= context.max_records:
                    raise _StopCollection

        handler = Handler()
        try:
            handler.apply_file(str(extract), locations=True)
        except _StopCollection:
            pass
        return {"release": extract.name, "scanned": handler.scanned, "emitted": handler.emitted, "extract": paths.relative(extract).as_posix()}

    def _collect_overpass(self, context: CollectionContext, emit: EmitRecord) -> dict[str, Any]:
        if not context.tile or not context.tile.get("bbox"):
            raise ValueError("Bounded OSM live collection requires a bbox tile")
        west, south, east, north = (float(value) for value in context.tile["bbox"])
        bbox = f"{south},{west},{north},{east}"
        filters = self._overpass_filters(context.segment_ids)
        statements = "".join(f'nwr{item}({bbox});' for item in filters)
        query = f"[out:json][timeout:60];({statements});out center tags;"
        response = httpx.post(
            str(self.catalog.execution["overpass_url"]),
            data={"data": query},
            headers={"User-Agent": "EMY-Private-AI-OS/1.0 lead-audit"},
            timeout=90,
            follow_redirects=True,
        )
        _raise_for_source_status(response, "SRC_OSM_GEOFABRIK")
        payload = response.json()
        release = str((payload.get("osm3s") or {}).get("timestamp_osm_base") or "overpass-current")
        skip = int(context.checkpoint.get("raw_position", 0))
        scanned = 0
        emitted = 0
        allowed = set(context.segment_ids)
        for element in payload.get("elements", []):
            tags = dict(element.get("tags") or {})
            if not tags.get("name"):
                continue
            scanned += 1
            if scanned <= skip:
                continue
            category = self._category(tags)
            if allowed and category not in allowed and not self._keyword_match(tags, context.keywords):
                if not emit(None, scanned):  # type: ignore[arg-type]
                    break
                continue
            center = element.get("center") or element
            record = self._to_record(
                str(element.get("type", "object")),
                int(element.get("id", 0)),
                tags,
                center.get("lon"),
                center.get("lat"),
                context.governorate,
            )
            record.source_version = release
            emitted += 1
            if not emit(record, scanned):
                break
            if context.max_records and emitted >= context.max_records:
                break
        return {"release": release, "scanned": scanned, "emitted": emitted, "mode": "overpass_bbox"}

    @staticmethod
    def _overpass_filters(segment_ids: list[str]) -> list[str]:
        selected = set(segment_ids)
        filters: list[str] = []
        if "pharmacies" in selected:
            filters.extend(('["amenity"="pharmacy"]', '["shop"="chemist"]'))
        if selected.intersection({"ladies_salons", "men_barbers", "unisex_salons", "beauty_centers"}):
            filters.extend(('["shop"="hairdresser"]', '["shop"="beauty"]'))
        if selected.intersection({"spas", "medical_spas"}):
            filters.append('["leisure"="spa"]')
        if not filters:
            filters.extend(f'["{key}"]' for key in ("shop", "amenity", "healthcare", "office", "craft"))
        return list(dict.fromkeys(filters))

    def _category(self, tags: dict[str, str]) -> str | None:
        values = [tags.get(key, "") for key in self.RELEVANT]
        for value in values:
            mapped = self.catalog.category_mapping.get(value.casefold().replace(" ", "_"))
            if mapped:
                return mapped
        return None

    @staticmethod
    def _keyword_match(tags: dict[str, str], keywords: list[str]) -> bool:
        haystack = " ".join(tags.values()).casefold()
        return any(keyword.casefold() in haystack for keyword in keywords)

    @staticmethod
    def _to_record(object_type: str, object_id: int, tags: dict[str, str], longitude: float | None, latitude: float | None, governorate: str | None) -> RawLeadRecord:
        category = next((tags.get(key) for key in ("shop", "amenity", "healthcare", "office", "craft", "beauty") if tags.get(key)), None)
        address = " ".join(filter(None, (tags.get("addr:housenumber"), tags.get("addr:street")))) or None
        return RawLeadRecord(
            source_uid="SRC_OSM_GEOFABRIK",
            source_record_id=f"{object_type}/{object_id}",
            business_name=tags.get("name", ""),
            category_raw=category,
            address=address,
            city=tags.get("addr:city"),
            district=tags.get("addr:district") or tags.get("addr:suburb"),
            governorate=tags.get("addr:state") or governorate,
            latitude=latitude,
            longitude=longitude,
            phone=tags.get("contact:phone") or tags.get("phone"),
            email=tags.get("contact:email") or tags.get("email"),
            website=tags.get("contact:website") or tags.get("website"),
            social_links=[value for key, value in tags.items() if key.startswith("contact:") and key.split(":", 1)[-1] in {"facebook", "instagram", "twitter"}],
            business_status="OPEN" if tags.get("disused") != "yes" else "CLOSED",
            confidence=0.80,
            source_version="geofabrik-egypt-latest",
            raw={"osm_type": object_type, "osm_id": object_id, "tags": tags},
        )


class ConfigGatedAdapter(BaseLeadCollector):
    def __init__(self, source_uid: str, credential: str | None = None) -> None:
        self.source_uid = source_uid
        self.credential = credential

    def collect(self, context: CollectionContext, emit: EmitRecord) -> dict[str, Any]:
        if not self.credential:
            raise RuntimeError(f"{self.source_uid} is NOT_CONFIGURED")
        raise RuntimeError(f"{self.source_uid} live execution is disabled until its explicit live flag and terms review are enabled")


class GooglePlacesAdapter(ConfigGatedAdapter):
    pass


class FoursquarePlacesAdapter(ConfigGatedAdapter):
    pass


class WebsiteEnrichmentAdapter(ConfigGatedAdapter):
    """Public-page-only boundary; private/authenticated pages are never fetched."""


class OfficialRegistryAdapter(ConfigGatedAdapter):
    pass
