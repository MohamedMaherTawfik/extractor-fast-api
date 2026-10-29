"""Hook extraction, multi-modality analysis, taxonomy classification, and creative assessment."""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from backend.social_intelligence.semantic_provider import (
    HookEntry,
    StructuredHookAnalysis,
    get_semantic_provider,
)
from backend.social_intelligence.transcriber import TranscriptionResult
from backend.social_intelligence.video_deconstructor import VideoDeconstructionResult

logger = logging.getLogger(__name__)

TAXONOMY_HOOK_TYPES = [
    "curiosity_gap",
    "question_hook",
    "surprising_fact",
    "contrarian_statement",
    "problem_solution",
    "story_opening",
    "emotional_hook",
    "authority_hook",
    "educational_hook",
    "challenge_hook",
    "direct_promise",
    "pattern_interruption",
    "statement_anchor",
    "humor",
    "suspense",
]

ARABIC_QUESTIONS = ["هل", "ليه", "إزاي", "ازاي", "كيف", "ما هو", "ما هي", "مين", "فين", "إمتى", "متى", "كم", "لماذا", "ماذا"]


@dataclass(slots=True)
class SpokenHookData:
    exact_text: str
    start_time: float
    end_time: float
    duration: float
    linguistic_structure: str
    opening_strategy: str
    key_attention_trigger: str
    evidence: str
    first_meaningful_sentence: str | None = None
    promise_or_curiosity_gap: str | None = None


@dataclass(slots=True)
class VisualHookData:
    first_frame_composition: str
    opening_visual_event: str
    camera_movement: str
    visible_subject: str
    visual_contrast: str
    scene_changes: int
    on_screen_text: str | None
    visual_attention_techniques: list[str]
    supporting_timestamps: list[float]
    first_visible_action: str | None = None


@dataclass(slots=True)
class TextHookData:
    opening_caption_sentence: str
    on_screen_headline: str | None
    opening_subtitle: str | None
    title_technique: str


@dataclass(slots=True)
class HookAnalysisResult:
    spoken_hook: SpokenHookData | None
    visual_hook: VisualHookData | None
    text_hook: TextHookData | None
    hook_types: list[str]
    clarity: str
    specificity: str
    relevance: str
    curiosity_mechanism: str
    text_visual_alignment: str
    heuristic_score: float
    qualitative_strengths: list[str]
    qualitative_weaknesses: list[str]
    recommendations: list[str]
    model_name: str = "deterministic-multilingual-nlp-v2"
    identified_hooks: list[dict[str, Any]] = field(default_factory=list)
    opening_payoff_connection: dict[str, Any] = field(default_factory=dict)
    suggested_alternative_hooks: list[str] = field(default_factory=list)


def extract_opening_caption_sentence(caption: str | None) -> str:
    if not caption:
        return ""
    sentences = re.split(r"[\n.!?؟]+", caption.strip())
    first = sentences[0].strip() if sentences else ""
    return first or caption[:100].strip()


def classify_hook_types(
    spoken_text: str,
    caption_text: str,
    has_question_visual: bool = False,
) -> list[str]:
    combined = f"{spoken_text} {caption_text}".strip().lower()
    categories: set[str] = set()

    if "?" in combined or "؟" in combined or any(re.search(rf"\b{re.escape(q)}\b", combined) for q in ARABIC_QUESTIONS):
        categories.add("question_hook")

    if any(w in combined for w in ["سر", "أسرار", "حقيقة", "السبب", "عارف", "بتعرف", "secret", "why", "curiosity", "المفاجأة", "صدمة"]):
        categories.add("curiosity_gap")

    if any(w in combined for w in ["في يوم", "مرة", "كان يا مكان", "قصة", "من زمان", "story", "once", "remember"]):
        categories.add("story_opening")

    if any(w in combined for w in ["مش كل", "أكبر غلطة", "إياك", "غلط", "خرافة", "never", "wrong", "myth"]):
        categories.add("contrarian_statement")

    if any(w in combined for w in ["في دقيقة", "هقولك", "طريقة", "حل", "how to", "step", "formula"]):
        categories.add("direct_promise")

    if any(w in combined for w in ["تخيل", "وقف", "إياك", "انتبه", "wait", "stop", "imagine"]):
        categories.add("pattern_interruption")

    if not categories:
        categories.add("statement_anchor" if len(combined) > 10 else "curiosity_gap")

    return sorted(list(categories))


def analyze_hooks(
    transcript: TranscriptionResult | None,
    video_decomp: VideoDeconstructionResult | None,
    caption: str | None,
    title: str | None,
) -> HookAnalysisResult:
    """Analyze spoken, visual, and text hooks using the semantic provider with evidence grounding."""
    provider = get_semantic_provider()

    # Normalize inputs for provider
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

    video_dict = None
    if video_decomp:
        video_dict = {
            "duration": video_decomp.duration,
            "scenes": [
                {
                    "scene_index": sc.scene_index,
                    "start_time": sc.start_time,
                    "end_time": sc.end_time,
                    "camera_framing": sc.camera_framing,
                    "scene_classification": sc.scene_classification,
                    "visible_text": sc.visible_text,
                    "sampled_metrics": sc.sampled_metrics,
                }
                for sc in video_decomp.scenes
            ],
        }

    duration = (video_decomp and video_decomp.duration) or (transcript and transcript.duration_seconds) or 60.0

    analysis: StructuredHookAnalysis = provider.analyze_hooks(
        transcript_segments=segments_payload,
        full_transcript=full_text,
        video_metadata=video_dict,
        caption=caption,
        title=title,
        source_duration=duration,
    )

    # Map spoken hook
    spoken_data = None
    if analysis.spoken_hook and analysis.spoken_hook.exact_text:
        sh = analysis.spoken_hook
        sentences = re.split(r"[.!?؟\n]+", sh.exact_text)
        first_meaningful = sentences[0].strip() if sentences else sh.exact_text

        spoken_data = SpokenHookData(
            exact_text=sh.exact_text,
            start_time=sh.start_time or 0.0,
            end_time=sh.end_time or 3.0,
            duration=sh.duration or round((sh.end_time or 3.0) - (sh.start_time or 0.0), 2),
            linguistic_structure=sh.mechanism,
            opening_strategy=sh.attention_strategy,
            key_attention_trigger=sh.category.replace("_", " ").title(),
            evidence=sh.evidence.verbatim_quote or f"Transcript 00:{int(sh.start_time or 0):02d}",
            first_meaningful_sentence=first_meaningful,
            promise_or_curiosity_gap=sh.promise_or_curiosity_gap,
        )

    # Map visual hook
    visual_data = None
    if analysis.visual_hook:
        vh = analysis.visual_hook
        first_scene = video_decomp.scenes[0] if (video_decomp and video_decomp.scenes) else None
        framing = (first_scene and first_scene.camera_framing) or "Not classified"
        sampled = (first_scene and first_scene.sampled_metrics) or {}
        contrast_str = f"Luminance {sampled.get('luminance', 0):.0f}, Contrast {sampled.get('contrast', 0):.0f} ({sampled.get('color_tone', 'unknown')} tone)"

        scene_changes = sum(1 for s in video_decomp.scenes if s.start_time < 5.0) if video_decomp else 1

        visual_data = VisualHookData(
            first_frame_composition=framing,
            opening_visual_event=vh.explanation,
            camera_movement=(first_scene and first_scene.camera_movement) or "Not classified",
            visible_subject="Not classified",
            visual_contrast=contrast_str,
            scene_changes=scene_changes,
            on_screen_text=(first_scene and first_scene.visible_text) or title,
            visual_attention_techniques=[
                f"Tone: {sampled.get('color_tone', 'balanced')}",
                "Frame statistics only",
            ],
            supporting_timestamps=[0.0, vh.end_time or 3.0],
            first_visible_action=vh.mechanism,
        )

    # Map text hook
    caption_sentence = extract_opening_caption_sentence(caption)
    text_data = None
    if analysis.text_hook and caption_sentence:
        text_data = TextHookData(
            opening_caption_sentence=caption_sentence,
            on_screen_headline=None,
            opening_subtitle=None,
            title_technique=analysis.text_hook.mechanism,
        )

    # Gather alternative hooks from identified hooks
    alternatives = []
    for h in analysis.all_hooks:
        alternatives.extend(h.suggested_alternatives)

    return HookAnalysisResult(
        spoken_hook=spoken_data,
        visual_hook=visual_data,
        text_hook=text_data,
        hook_types=analysis.hook_types,
        clarity=analysis.clarity,
        specificity=analysis.specificity,
        relevance=analysis.relevance,
        curiosity_mechanism=analysis.curiosity_mechanism,
        text_visual_alignment=analysis.text_visual_alignment,
        heuristic_score=analysis.heuristic_score,
        qualitative_strengths=analysis.qualitative_strengths,
        qualitative_weaknesses=analysis.qualitative_weaknesses,
        recommendations=analysis.recommendations,
        model_name=analysis.model_name,
        identified_hooks=[h.model_dump() for h in analysis.all_hooks],
        opening_payoff_connection=analysis.opening_payoff_connection,
        suggested_alternative_hooks=alternatives[:3],
    )
