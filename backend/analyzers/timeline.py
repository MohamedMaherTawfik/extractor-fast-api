"""Streaming-friendly timeline provider boundary with embedded-evidence default."""

from abc import ABC, abstractmethod
from typing import ClassVar

from backend.db.models.content_item import ContentItem
from backend.schemas.analysis import TimelineDraft


class TimelineProvider(ABC):
    name: ClassVar[str]
    version: ClassVar[str]

    @abstractmethod
    def extract(self, content: ContentItem) -> TimelineDraft:
        """Extract timeline entities without loading complete media into memory."""


class EmbeddedTimelineProvider(TimelineProvider):
    """Use verified intermediate timeline evidence already attached to content."""

    name = "embedded_timeline"
    version = "1"

    def extract(self, content: ContentItem) -> TimelineDraft:
        metadata = content.raw_metadata or {}
        timeline = metadata.get("analysis_timeline")
        if timeline is None:
            return TimelineDraft()
        return TimelineDraft.model_validate(timeline)
