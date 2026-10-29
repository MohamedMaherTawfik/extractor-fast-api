"""AI Creative Generation Engine for original hooks, captions, scripts, and production recipes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.db.models.social_intelligence import CreativeRecommendation, CreatorIntelligence
from backend.social_intelligence.semantic_provider import (
    StructuredCreativeVariation,
    get_semantic_provider,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GenerationRequest:
    item_uuid: UUID | None
    creator_username: str | None
    output_type: str  # hook_variations, caption_variations, video_script, storytelling_outline, cta_ideas
    target_platform: str = "instagram_reels"
    target_audience: str = "General Social Audience"
    target_duration: str = "45-60 seconds"
    target_language: str = "ar"
    objective: str = "Maximize watch time and engagement"
    topic_context: str | None = None


def generate_creative_recommendations(
    session: Session,
    request: GenerationRequest,
) -> list[CreativeRecommendation]:
    """Generate original creative variations grounded in analyzed creator patterns using the semantic provider."""
    provider = get_semantic_provider()

    # Look up creator intelligence if username provided
    creator_dna_dict = None
    if request.creator_username:
        intel = (
            session.query(CreatorIntelligence)
            .filter_by(username=request.creator_username)
            .first()
        )
        if intel:
            creator_dna_dict = {
                "primary_topics": intel.primary_topics,
                "common_hook_types": intel.common_hook_types,
                "typical_copy_style": intel.typical_copy_style,
                "storytelling_patterns": intel.storytelling_patterns,
            }

    variations: list[StructuredCreativeVariation] = provider.generate_creative(
        output_type=request.output_type,
        topic_context=request.topic_context,
        creator_dna=creator_dna_dict,
        target_audience=request.target_audience,
        target_platform=request.target_platform,
        target_duration=request.target_duration,
        target_language=request.target_language,
    )

    outputs: list[CreativeRecommendation] = []
    for var in variations:
        rec = CreativeRecommendation(
            item_uuid=request.item_uuid,
            creator_username=request.creator_username,
            output_type=request.output_type,
            target_platform=request.target_platform,
            target_audience=request.target_audience,
            target_duration=request.target_duration,
            target_language=request.target_language,
            suggested_hook=var.suggested_hook,
            suggested_caption=var.suggested_caption,
            suggested_cta=var.suggested_cta,
            script_outline=var.script_outline,
            creative_rationale=var.creative_rationale,
            model_name=var.model_name,
            is_ai_generated=var.is_ai_generated,
        )
        session.add(rec)
        outputs.append(rec)

    session.flush()
    return outputs
