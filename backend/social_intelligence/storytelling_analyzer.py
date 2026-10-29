"""Storytelling and narrative structure analysis with timestamped stages grounded in evidence."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.social_intelligence.semantic_provider import (
    StructuredNarrativeAnalysis,
    get_semantic_provider,
)
from backend.social_intelligence.transcriber import TranscriptionResult
from backend.social_intelligence.video_deconstructor import VideoDeconstructionResult

logger = logging.getLogger(__name__)

NARRATIVE_PATTERNS = [
    "educational_explanation",
    "personal_storytelling",
    "documentary",
    "entertainment",
    "news_reporting",
    "tutorial_how_to",
    "challenge_and_attempt",
    "question_and_investigation",
    "problem_solution",
    "before_and_after",
]


@dataclass(slots=True)
class NarrativeStageData:
    stage_name: str
    start_time: float
    end_time: float
    description: str
    evidence: str
    confidence: float
    rhetorical_function: str = "Narrative Progression"


@dataclass(slots=True)
class StorytellingAnalysisResult:
    narrative_pattern: str
    summary: str
    stages: list[NarrativeStageData] = field(default_factory=list)
    opening_payoff_alignment: str | None = None


def analyze_storytelling(
    transcript: TranscriptionResult | None,
    video_decomp: VideoDeconstructionResult | None,
    caption: str | None,
) -> StorytellingAnalysisResult:
    """Extract narrative progression, timestamped stages, and narrative pattern using the semantic provider."""
    provider = get_semantic_provider()

    segments_payload = [
        {
            "segment_index": s.segment_index,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "text": s.text,
            "confidence": s.confidence,
        }
        for s in (transcript.segments if transcript else [])
    ]
    full_text = transcript.full_text if transcript else None
    duration = (video_decomp and video_decomp.duration) or (transcript and transcript.duration_seconds) or 30.0

    analysis: StructuredNarrativeAnalysis = provider.analyze_narrative(
        transcript_segments=segments_payload,
        full_transcript=full_text,
        caption=caption,
        source_duration=duration,
    )

    stage_items = [
        NarrativeStageData(
            stage_name=st.stage_name,
            start_time=st.start_time,
            end_time=st.end_time,
            description=st.description,
            evidence=st.evidence_quote,
            confidence=st.confidence,
            rhetorical_function=st.rhetorical_function,
        )
        for st in analysis.stages
    ]

    return StorytellingAnalysisResult(
        narrative_pattern=analysis.narrative_pattern,
        summary=analysis.summary,
        stages=stage_items,
        opening_payoff_alignment=analysis.opening_payoff_alignment,
    )
