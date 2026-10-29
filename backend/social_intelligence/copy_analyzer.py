"""Copywriting and caption analysis supporting Arabic nuances, dialects, and structured semantics."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from backend.social_intelligence.semantic_provider import (
    CTA_PATTERNS,
    StructuredCopyAnalysis,
    get_semantic_provider,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CopyAnalysisResult:
    original_caption: str | None
    opening_sentence: str | None
    primary_message: str
    main_topic: str
    secondary_topics: list[str]
    tone_of_voice: str
    writing_style: str
    emotional_framing: str
    persuasion_techniques: list[str]
    content_objective: str
    audience_address: str
    hashtag_strategy: dict[str, Any]
    cta_type: str
    cta_text: str | None
    is_explicit_cta: bool
    caption_structure: str
    sentence_characteristics: str
    readability_observations: str
    brand_voice_indicators: str
    summary: str
    evidence_citations: list[dict[str, Any]] = field(default_factory=list)


def extract_hashtags(text: str | None) -> list[str]:
    if not text:
        return []
    return re.findall(r"#([^\s#]+)", text)


def detect_cta(caption: str | None) -> tuple[str, str | None, bool]:
    """Detect CTA type and exact matched phrase in caption."""
    if not caption:
        return "none", None, False

    for pattern, cta_type in CTA_PATTERNS:
        match = re.search(pattern, caption, flags=re.IGNORECASE)
        if match:
            return cta_type, match.group(0).strip(), True

    if "شاهد" in caption or "watch" in caption.lower():
        return "watch_now", "شاهد", False

    return "none", None, False


def analyze_caption(
    caption: str | None,
    author_name: str | None = None,
    username: str | None = None,
) -> CopyAnalysisResult:
    """Analyze copywriting characteristics, persuasion techniques, and Arabic dialect using the semantic provider."""
    provider = get_semantic_provider()
    analysis: StructuredCopyAnalysis = provider.analyze_copy(
        caption=caption,
        author_name=author_name,
        username=username,
    )

    return CopyAnalysisResult(
        original_caption=analysis.original_caption,
        opening_sentence=analysis.opening_sentence,
        primary_message=analysis.primary_message,
        main_topic=analysis.main_topic,
        secondary_topics=analysis.secondary_topics,
        tone_of_voice=analysis.tone_of_voice,
        writing_style=analysis.writing_style,
        emotional_framing=analysis.emotional_framing,
        persuasion_techniques=analysis.persuasion_techniques,
        content_objective=analysis.content_objective,
        audience_address=analysis.audience_address,
        hashtag_strategy=analysis.hashtag_strategy,
        cta_type=analysis.cta_type,
        cta_text=analysis.cta_text,
        is_explicit_cta=analysis.is_explicit_cta,
        caption_structure=analysis.caption_structure,
        sentence_characteristics=analysis.sentence_characteristics,
        readability_observations=analysis.readability_observations,
        brand_voice_indicators=analysis.brand_voice_indicators,
        summary=analysis.summary,
        evidence_citations=[c.model_dump() for c in analysis.evidence_citations],
    )
