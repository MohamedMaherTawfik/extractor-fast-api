"""Route canonical content into one or more observable analysis modalities."""

from dataclasses import dataclass

from backend.core.enums import AnalysisModality, ContentType
from backend.db.models.content_item import ContentItem


@dataclass(frozen=True)
class AnalysisRoute:
    modalities: frozenset[AnalysisModality]
    engines: frozenset[str]


class ContentRouter:
    def route(self, content: ContentItem) -> AnalysisRoute:
        modalities = {AnalysisModality.METADATA}
        engines = {"metadata"}
        content_type = content.content_type

        if content_type in {
            ContentType.VIDEO,
            ContentType.REEL,
            ContentType.SHORT,
            ContentType.LIVE,
        }:
            modalities.update(
                {AnalysisModality.VIDEO, AnalysisModality.AUDIO, AnalysisModality.TEXT}
            )
            engines.update(
                {
                    "video_structure",
                    "vision",
                    "audio",
                    "speech",
                    "ocr",
                    "copy",
                    "behavior",
                    "seo",
                }
            )
        elif content_type is ContentType.IMAGE:
            modalities.update({AnalysisModality.IMAGE, AnalysisModality.TEXT})
            engines.update({"vision", "ocr", "copy", "behavior", "seo"})
        elif content_type is ContentType.CAROUSEL:
            modalities.update(
                {
                    AnalysisModality.CAROUSEL,
                    AnalysisModality.IMAGE,
                    AnalysisModality.TEXT,
                }
            )
            engines.update({"vision", "ocr", "copy", "behavior", "seo"})
        elif content_type is ContentType.AUDIO:
            modalities.update({AnalysisModality.AUDIO, AnalysisModality.TEXT})
            engines.update({"audio", "speech", "copy", "behavior", "seo"})
        elif content_type in {ContentType.POST, ContentType.ARTICLE}:
            modalities.add(AnalysisModality.TEXT)
            engines.update({"copy", "behavior", "seo"})
        elif any((content.title, content.caption, content.description)):
            modalities.add(AnalysisModality.TEXT)
            engines.update({"copy", "behavior", "seo"})

        return AnalysisRoute(frozenset(modalities), frozenset(engines))
