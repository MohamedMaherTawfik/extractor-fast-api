"""Normalize only available platform metrics and retain time-series provenance."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.core.enums import TrafficType
from backend.db.models.content_item import ContentItem
from backend.repositories.performance_repository import PerformanceRepository


_RAW_FIELDS = ("views", "likes", "comments", "shares", "saves")
_RATE_FIELDS = {
    "like_rate": "likes",
    "comment_rate": "comments",
    "share_rate": "shares",
    "save_rate": "saves",
}


class PerformanceService:
    def __init__(self, session: Session) -> None:
        self.repository = PerformanceRepository(session)

    def snapshot_content(self, content: ContentItem) -> list:
        collected_at = _aware(content.collected_at)
        traffic = _traffic_type(content.raw_metadata)
        snapshots = []
        views = content.views
        for name in _RAW_FIELDS:
            raw_value = getattr(content, name)
            snapshots.append(
                self._upsert(
                    content_id=content.id,
                    metric_name=name,
                    raw_value=raw_value,
                    normalized_value=None,
                    availability=raw_value is not None,
                    source="content_master",
                    collected_at=collected_at,
                    elapsed_minutes=_elapsed_minutes(content.published_at, collected_at),
                    traffic_type=traffic,
                )
            )
        for rate_name, numerator_field in _RATE_FIELDS.items():
            numerator = getattr(content, numerator_field)
            available = numerator is not None and views is not None and views > 0
            snapshots.append(
                self._upsert(
                    content_id=content.id,
                    metric_name=rate_name,
                    raw_value=float(numerator) if numerator is not None else None,
                    normalized_value=(float(numerator) / views if available else None),
                    availability=available,
                    source="derived_from_content_master",
                    collected_at=collected_at,
                    elapsed_minutes=_elapsed_minutes(content.published_at, collected_at),
                    traffic_type=traffic,
                )
            )
        return snapshots

    def performance_object(self, content: ContentItem) -> dict[str, Any]:
        snapshots = self.snapshot_content(content)
        return {
            "available_metrics": [
                snapshot.metric_name for snapshot in snapshots if snapshot.availability
            ],
            "normalized_metrics": {
                snapshot.metric_name: snapshot.normalized_value
                for snapshot in snapshots
                if snapshot.availability and snapshot.normalized_value is not None
            },
            "metrics": [
                {
                    "metric_name": snapshot.metric_name,
                    "raw_value": snapshot.raw_value,
                    "normalized_value": snapshot.normalized_value,
                    "availability": snapshot.availability,
                    "source": snapshot.source,
                    "collected_at": snapshot.collected_at.isoformat(),
                    "traffic_type": snapshot.traffic_type.value,
                }
                for snapshot in snapshots
            ],
        }

    def _upsert(self, **values):
        existing = self.repository.find_exact(
            values["content_id"], values["metric_name"], values["collected_at"]
        )
        if existing is not None:
            for key, value in values.items():
                setattr(existing, key, value)
            return existing
        return self.repository.add(**values)


def _traffic_type(metadata: dict[str, Any] | None) -> TrafficType:
    value = (metadata or {}).get("traffic_type", TrafficType.UNKNOWN.value)
    try:
        return TrafficType(str(value).lower())
    except ValueError:
        return TrafficType.UNKNOWN


def _elapsed_minutes(published_at: datetime | None, collected_at: datetime) -> int | None:
    if published_at is None:
        return None
    return max(0, int((_aware(collected_at) - _aware(published_at)).total_seconds() // 60))


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

