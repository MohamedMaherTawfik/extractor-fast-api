"""Egypt governorate coverage and adaptive bbox tile planning."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any

from backend.leads.config import LeadCatalog, get_lead_catalog


@dataclass(frozen=True, slots=True)
class GeographicTile:
    tile_id: str
    governorate_id: str
    bbox: tuple[float, float, float, float]
    polygon: tuple[tuple[float, float], ...]

    def as_dict(self) -> dict[str, Any]:
        return {"tile_id": self.tile_id, "bbox": list(self.bbox), "polygon": [list(point) for point in self.polygon]}


class GeographyService:
    TILE_DEGREES = {"HIGH": 0.20, "MEDIUM": 0.50, "LOW": 1.50}

    def __init__(self, catalog: LeadCatalog | None = None) -> None:
        self.catalog = catalog or get_lead_catalog()

    def list_governorates(self) -> list[dict[str, Any]]:
        result = []
        for item in self.catalog.governorates:
            bbox = tuple(float(value) for value in item["bbox"])
            result.append({**item, "polygon": [list(point) for point in self._bbox_polygon(bbox)]})
        return result

    def country_boundary(self) -> dict[str, Any]:
        return dict(self.catalog.country)

    def adaptive_tiles(self, governorate_ids: list[str] | None = None) -> list[GeographicTile]:
        selected = governorate_ids or list(self.catalog.governorate_by_id)
        unknown = sorted(set(selected) - set(self.catalog.governorate_by_id))
        if unknown:
            raise ValueError(f"Unknown governorates: {', '.join(unknown)}")
        tiles: list[GeographicTile] = []
        for governorate_id in selected:
            item = self.catalog.governorate_by_id[governorate_id]
            west, south, east, north = (float(value) for value in item["bbox"])
            step = self.TILE_DEGREES.get(str(item.get("density", "MEDIUM")), 0.50)
            columns = max(1, ceil((east - west) / step))
            rows = max(1, ceil((north - south) / step))
            for row in range(rows):
                for column in range(columns):
                    bbox = (
                        west + column * step,
                        south + row * step,
                        min(east, west + (column + 1) * step),
                        min(north, south + (row + 1) * step),
                    )
                    tiles.append(
                        GeographicTile(
                            tile_id=f"{governorate_id}:{row}:{column}",
                            governorate_id=governorate_id,
                            bbox=bbox,
                            polygon=self._bbox_polygon(bbox),
                        )
                    )
        return tiles

    def governorate_for_point(self, longitude: float | None, latitude: float | None) -> str | None:
        if longitude is None or latitude is None:
            return None
        candidates: list[tuple[float, str]] = []
        for item in self.catalog.governorates:
            west, south, east, north = (float(value) for value in item["bbox"])
            if west <= longitude <= east and south <= latitude <= north:
                candidates.append(((east - west) * (north - south), str(item["id"])))
        return min(candidates)[1] if candidates else None

    @staticmethod
    def _bbox_polygon(bbox: tuple[float, float, float, float]) -> tuple[tuple[float, float], ...]:
        west, south, east, north = bbox
        return ((west, south), (east, south), (east, north), (west, north), (west, south))

