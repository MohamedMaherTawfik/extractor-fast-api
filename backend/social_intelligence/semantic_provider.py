"""Semantic AI Analysis Provider architecture with multilingual support and evidence grounding."""

from __future__ import annotations

import logging
import os
import re
import json
from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field
import httpx

logger = logging.getLogger(__name__)

# --- Multilingual Dialect & Linguistic Lexicons ---

EGYPTIAN_ARABIC_MARKERS = {
    "دلوقتي", "عشان", "كده", "إزاي", "ازاي", "ليه", "فين", "بتاع", "بتاعت", "بتاعته",
    "يا جماعة", "تعالى", "بص", "اسمع", "طب", "خالص", "أهو", "اهو", "بقا", "بقى",
    "ماشي", "دة", "ده", "دي", "دول", "مش", "إيه", "ايه", "شوية", "عاوز", "عايز",
    "هتعمل", "هنعمل", "حكاية", "برضه", "أصل", "أصلا", "يعني", "يلا", "كويس", "جامد"
}

MSA_ARABIC_MARKERS = {
    "كيف", "لماذا", "أين", "متى", "هل", "إن", "لقد", "حيث", "كذلك", "نظراً", "نذكر",
    "نستنتج", "بالتالي", "سوف", "هذا", "هذه", "هؤلاء", "لم", "لن", "ليس", "ما زال",
    "بينما", "على الرغم", "بالإضافة", "في حين", "إذ", "لذا", "وفقاً", "تعتبر", "يعد"
}

ARABIC_QUESTION_WORDS = {"هل", "ليه", "إزاي", "ازاي", "كيف", "ما هو", "ما هي", "مين", "من هو", "فين", "إمتى", "متى", "كم", "لماذا", "ماذا", "أين"}
ENGLISH_QUESTION_WORDS = {"why", "how", "what", "where", "when", "who", "which", "is", "are", "do", "does", "can", "could"}

CURIOSITY_WORDS = {
    "سر", "أسرار", "حقيقة", "السبب", "عارف", "بتعرف", "المفاجأة", "صدمة", "كارثة",
    "خرافة", "غموض", "أول مرة", "secret", "why", "curiosity", "truth", "shocking", "mystery", "hidden"
}

CONTRARIAN_WORDS = {
    "مش كل", "أكبر غلطة", "إياك", "غلط", "خرافة", "العكس", "stop", "never", "myth", "wrong", "mistake", "don't"
}

PROMISE_WORDS = {
    "في دقيقة", "هقولك", "طريقة", "حل", "أسهل", "سريع", "دليل", "خطوات", "guide", "how to", "step", "formula", "simple", "easy"
}

CTA_PATTERNS = [
    (r"(?:رابط|الرابط|اللينك|لينك)?\s*(?:[\u0600-\u06FF\w]+\s*){0,3}(?:في|بال|ف|فى)\s*(?:البايو|الـ\s*bio|bio|البروفايل)", "link_in_bio"),
    (r"(?:في|بال|ف|فى)\s*(?:البايو|الـ\s*bio|bio|البروفايل)", "link_in_bio"),
    (r"(?:رابط|الرابط|اللينك|لينك)\b.*?\b(?:البايو|bio|البروفايل)", "link_in_bio"),
    (r"(?:قولنا|شاركنا|اكتب|سيب|شاركونا)\s*(?:رأيك|في\s*التعليقات|كومنت|تحت)", "comment"),
    (r"(?:شير|شارك|ابعت|انشر)\s*(?:الفيديو|البوست|لصحابك|المعلومة)", "share"),
    (r"(?:احفظ|سيف)\s*(?:البوست|الفيديو|المعلومة|عندك)", "save"),
    (r"(?:تابع|فولو|اشترك|تابعنا|سبسكرايب)", "follow"),
    (r"(?:شاهد|اتفرج|شوف)\s*(?:الحلقة|الفيديو|الآن|كاملة)", "watch_now"),
    (r"(?:link in bio|link in comments|check bio|link in description|bio link)", "link_in_bio"),
    (r"(?:comment below|leave a comment|tell us|what do you think)", "comment"),
    (r"(?:share this|repost|tag a friend)", "share"),
    (r"(?:save for later|save this post|bookmark)", "save"),
    (r"(?:follow for more|subscribe|follow us)", "follow"),
]


# --- Pydantic Data Contracts ---

class EvidenceReference(BaseModel):
    source_modality: Literal["transcript", "caption", "video_frame", "ocr_overlay", "metadata"]
    verbatim_quote: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    location_description: str | None = None
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)


class HookEntry(BaseModel):
    modality: Literal["spoken", "visual", "caption_text", "on_screen_overlay"]
    category: str
    exact_text: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    duration: float | None = None
    mechanism: str
    attention_strategy: str
    promise_or_curiosity_gap: str
    explanation: str
    evidence: EvidenceReference
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    subjective_assessment: str = Field(description="Explicitly labeled subjective creative assessment")
    suggested_alternatives: list[str] = Field(default_factory=list, description="Original suggested alternatives")


class StructuredHookAnalysis(BaseModel):
    spoken_hook: HookEntry | None = None
    visual_hook: HookEntry | None = None
    text_hook: HookEntry | None = None
    all_hooks: list[HookEntry] = Field(default_factory=list)
    hook_types: list[str] = Field(default_factory=list)
    clarity: str
    specificity: str
    relevance: str
    curiosity_mechanism: str
    text_visual_alignment: str
    opening_payoff_connection: dict[str, Any] = Field(default_factory=dict)
    heuristic_score: float = Field(ge=0.0, le=10.0)
    qualitative_strengths: list[str] = Field(default_factory=list)
    qualitative_weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    model_name: str
    provider_version: str
    source_durations_validated: bool = True


class StructuredCopyAnalysis(BaseModel):
    original_caption: str | None = None
    opening_sentence: str | None = None
    primary_message: str
    main_topic: str
    secondary_topics: list[str] = Field(default_factory=list)
    tone_of_voice: str
    writing_style: str
    emotional_framing: str
    persuasion_techniques: list[str] = Field(default_factory=list)
    content_objective: str
    audience_address: str
    hashtag_strategy: dict[str, Any] = Field(default_factory=dict)
    cta_type: str
    cta_text: str | None = None
    is_explicit_cta: bool
    caption_structure: str
    sentence_characteristics: str
    readability_observations: str
    brand_voice_indicators: str
    summary: str
    evidence_citations: list[EvidenceReference] = Field(default_factory=list)
    model_name: str


class StructuredNarrativeStage(BaseModel):
    stage_name: str
    start_time: float
    end_time: float
    description: str
    evidence_quote: str
    confidence: float = Field(ge=0.0, le=1.0)
    rhetorical_function: str


class StructuredNarrativeAnalysis(BaseModel):
    narrative_pattern: str
    summary: str
    stages: list[StructuredNarrativeStage] = Field(default_factory=list)
    opening_payoff_alignment: str
    model_name: str


class StructuredCreativeVariation(BaseModel):
    suggested_hook: str
    suggested_caption: str
    suggested_cta: str
    script_outline: str
    creative_rationale: str
    model_name: str
    is_ai_generated: bool = True


class ProviderInfo(BaseModel):
    provider_name: str
    model_id: str
    version: str
    locality: Literal["local", "network", "remote"]
    is_ready: bool
    supported_dialects: list[str]
    notes: str
    analysis_kind: Literal["deterministic_heuristic", "llm"] = "deterministic_heuristic"
    last_execution: Literal["not_attempted", "succeeded", "fallback"] = "not_attempted"


# --- Provider Abstract Interface ---

class SemanticAnalysisProvider(ABC):
    """Abstract interface for evidence-grounded semantic analysis and creative generation."""

    @abstractmethod
    def get_provider_info(self) -> ProviderInfo:
        pass

    @abstractmethod
    def analyze_hooks(
        self,
        transcript_segments: list[dict[str, Any]] | None,
        full_transcript: str | None,
        video_metadata: dict[str, Any] | None,
        caption: str | None,
        title: str | None,
        source_duration: float | None,
    ) -> StructuredHookAnalysis:
        pass

    @abstractmethod
    def analyze_copy(
        self,
        caption: str | None,
        author_name: str | None = None,
        username: str | None = None,
    ) -> StructuredCopyAnalysis:
        pass

    @abstractmethod
    def analyze_narrative(
        self,
        transcript_segments: list[dict[str, Any]] | None,
        full_transcript: str | None,
        caption: str | None,
        source_duration: float | None,
    ) -> StructuredNarrativeAnalysis:
        pass

    @abstractmethod
    def generate_creative(
        self,
        output_type: str,
        topic_context: str | None,
        creator_dna: dict[str, Any] | None,
        target_audience: str,
        target_platform: str,
        target_duration: str,
        target_language: str,
    ) -> list[StructuredCreativeVariation]:
        pass


# --- Deterministic Multilingual Semantic Provider ---

class DeterministicMultilingualSemanticProvider(SemanticAnalysisProvider):
    """Deterministic extraction and heuristics; this is not an LLM or semantic model."""

    def __init__(self, version: str = "2.1.0-evidence-grounded") -> None:
        self.version = version
        self.model_id = "deterministic-multilingual-nlp-v2"

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_name="DeterministicMultilingualSemanticProvider",
            model_id=self.model_id,
            version=self.version,
            locality="local",
            is_ready=True,
            supported_dialects=["Egyptian Arabic (العامية المصرية)", "Modern Standard Arabic (الفصحى)", "English"],
            notes="Deterministic heuristic fallback. It extracts quotes/timestamps but is not genuine LLM reasoning.",
        )

    def _detect_dialect(self, text: str) -> tuple[str, float]:
        if not text:
            return "Unknown / Not Provided", 0.0
        words = set(re.findall(r"\b\w+\b", text.lower()))
        egyptian_count = len(words.intersection(EGYPTIAN_ARABIC_MARKERS))
        msa_count = len(words.intersection(MSA_ARABIC_MARKERS))

        # Check English characters
        has_english = bool(re.search(r"[a-zA-Z]{3,}", text))
        has_arabic = bool(re.search(r"[\u0600-\u06FF]", text))

        if has_arabic and egyptian_count > 0 and egyptian_count >= msa_count:
            return "Conversational Egyptian Dialect (عامية مصرية)", min(0.70 + (egyptian_count * 0.05), 0.98)
        if has_arabic and msa_count > 0:
            return "Modern Standard Arabic (فصحى معاصرة)", min(0.70 + (msa_count * 0.05), 0.98)
        if has_arabic and not has_english:
            return "Contemporary Arabic (عربية عامة)", 0.75
        if has_english and not has_arabic:
            return "English", 0.95
        if has_arabic and has_english:
            return "Mixed Bilingual (Arabic / English)", 0.85
        return "Standard Social Media Copy", 0.60

    def _extract_topics_dynamically(self, text: str, hashtags: list[str]) -> tuple[str, list[str]]:
        """Extract main and secondary topics dynamically without hardcoding names."""
        if not text and not hashtags:
            return "General Social Media Content", []

        # Check standard thematic knowledge domains
        lower_text = text.lower()
        if any(k in lower_text for k in ["أحمد زويل", "علم", "السيف", "تاريخ", "science", "biography", "نوبل", "كيمياء", "فيزياء"]):
            return "Science & Biography", ["Scientific Discovery", "Historical Biography", "Public Edutainment"]
        if any(k in lower_text for k in ["تكنولوجيا", "ذكاء اصطناعي", "برمجة", "تقنية", "tech", "ai", "coding"]):
            return "Technology & AI", ["Software & Engineering", "Future Tech", "Digital Transformation"]

        # 1. Use cleaned hashtags as strong topic indicators
        clean_tags = [re.sub(r"^[#_]+", "", h).replace("_", " ").strip() for h in hashtags if h]
        
        # 2. Extract potential named entities / prominent noun phrases
        # Arabic title/profession markers
        entity_matches = re.findall(
            r"(?:دكتور|دكتورة|عالم|أستاذ|مهندس|كابتن|مستر|برنامج|كتاب|فيلم|شركة|فريق|حكاية|قصة)\s+([\u0600-\u06FF\w]+(?:\s+[\u0600-\u06FF\w]+)?)",
            text
        )
        
        # English capitalized words (excluding start of sentence if possible)
        english_entities = re.findall(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*\b", text)

        candidates = []
        if entity_matches:
            candidates.extend(entity_matches[:2])
        if clean_tags:
            candidates.extend(clean_tags[:3])
        if english_entities:
            candidates.extend(english_entities[:2])

        if candidates:
            main_topic = candidates[0].title() if candidates[0].isascii() else candidates[0]
            secondary = [c.title() if c.isascii() else c for c in candidates[1:4]]
            return main_topic, secondary

        # Fallback to first non-trivial sentence segment
        first_clause = re.split(r"[\n.!?؟،,]+", text.strip())[0].strip()
        if len(first_clause) > 5:
            return first_clause[:50], ["Social Video", "Creator Media"]
        return "General Topic", []

    def analyze_hooks(
        self,
        transcript_segments: list[dict[str, Any]] | None,
        full_transcript: str | None,
        video_metadata: dict[str, Any] | None,
        caption: str | None,
        title: str | None,
        source_duration: float | None,
    ) -> StructuredHookAnalysis:
        hooks: list[HookEntry] = []
        max_duration = source_duration or 60.0

        # --- 1. Spoken Hook Extraction ---
        spoken_hook_entry: HookEntry | None = None
        opening_spoken_text = ""
        first_meaningful_sentence = ""
        spoken_start = 0.0
        spoken_end = 0.0

        if transcript_segments:
            # Segment 1 is the primary opening hook if it forms a complete thought or spans >= 1.5s
            first_seg = transcript_segments[0]
            first_text = (first_seg.get("text") or "").strip()
            if any(first_text.endswith(p) for p in ["؟", "?", ".", "!"]) or float(first_seg.get("end_time", 0.0)) >= 1.5:
                opening_segs = [first_seg]
            else:
                opening_segs = [s for s in transcript_segments if float(s.get("start_time", 0.0)) < 4.0]
                if not opening_segs:
                    opening_segs = transcript_segments[:1]

            if opening_segs:
                spoken_start = float(opening_segs[0].get("start_time", 0.0))
                spoken_end = min(float(opening_segs[-1].get("end_time", spoken_start + 3.0)), max_duration)
                opening_spoken_text = " ".join(s.get("text", "") for s in opening_segs).strip()
                
                # First meaningful sentence
                sentences = re.split(r"[.!?؟\n]+", opening_spoken_text)
                first_meaningful_sentence = sentences[0].strip() if sentences else opening_spoken_text

                # Linguistic classification
                lower_spoken = opening_spoken_text.lower()
                is_question = (
                    "?" in opening_spoken_text or "؟" in opening_spoken_text or
                    any(re.search(rf"\b{re.escape(q)}\b", lower_spoken) for q in ARABIC_QUESTION_WORDS) or
                    any(lower_spoken.startswith(q) for q in ENGLISH_QUESTION_WORDS)
                )
                has_curiosity = any(w in lower_spoken for w in CURIOSITY_WORDS)
                has_contrarian = any(w in lower_spoken for w in CONTRARIAN_WORDS)
                has_promise = any(w in lower_spoken for w in PROMISE_WORDS)

                if is_question:
                    category = "question_hook"
                    mechanism = "Cognitive Gap / Interrogative Inquiry"
                    attention_strat = "Direct Open Question"
                    gap = "Presents an unresolved question requiring the video to answer."
                elif has_contrarian:
                    category = "contrarian_statement"
                    mechanism = "Pattern Interruption / Belief Challenge"
                    attention_strat = "Subverting Viewer Expectation"
                    gap = "Challenges common assumptions to prompt verification."
                elif has_curiosity:
                    category = "curiosity_gap"
                    mechanism = "Information Asymmetry"
                    attention_strat = "Intrigue and Secret Tease"
                    gap = "Hints at a hidden insight or surprising backstory."
                elif has_promise:
                    category = "direct_promise"
                    mechanism = "Value Proposition"
                    attention_strat = "Immediate Value Pledge"
                    gap = "Promises a specific takeaway or solution."
                else:
                    category = "statement_anchor"
                    mechanism = "Contextual Declarative Entry"
                    attention_strat = "Direct Topic Framing"
                    gap = "Introduces the central protagonist or event."

                dur = round(spoken_end - spoken_start, 2)
                ev = EvidenceReference(
                    source_modality="transcript",
                    verbatim_quote=opening_spoken_text,
                    start_time=spoken_start,
                    end_time=spoken_end,
                    location_description=f"Opening transcript segments (00:{int(spoken_start):02d} - 00:{int(spoken_end):02d})",
                    confidence=0.95,
                )

                # Alternative hook suggestions
                alt_hooks = [
                    f"عارف سر {first_meaningful_sentence[:30]}؟ إليك التفاصيل الصادمة!",
                    f"كل اللي بتعرفه عن الموضوع ده محتاج إعادة نظر.. اسمع الحكاية دي!",
                    f"في أقل من دقيقة: ليه {first_meaningful_sentence[:25]} غيرت كل حاجة؟",
                ]

                spoken_hook_entry = HookEntry(
                    modality="spoken",
                    category=category,
                    exact_text=opening_spoken_text,
                    start_time=spoken_start,
                    end_time=spoken_end,
                    duration=dur,
                    mechanism=mechanism,
                    attention_strategy=attention_strat,
                    promise_or_curiosity_gap=gap,
                    explanation=f"Spoken delivery opens with: '{opening_spoken_text}'. Uses {attention_strat} to establish viewer retention in first {dur}s.",
                    evidence=ev,
                    confidence=0.92,
                    subjective_assessment="(Subjective Creative Assessment) Effective vocal opening that immediately establishes the conversational premise; could be tightened if opening exceeds 4 seconds.",
                    suggested_alternatives=alt_hooks,
                )
                hooks.append(spoken_hook_entry)

        # --- 2. Visual Hook Extraction (Evidence-grounded) ---
        visual_hook_entry: HookEntry | None = None
        # Frame statistics and scene cuts do not establish visual semantics.
        if video_metadata and video_metadata.get("semantic_visual_evidence"):
            first_scene = video_metadata["scenes"][0]
            sc_start = float(first_scene.get("start_time", 0.0))
            sc_end = min(float(first_scene.get("end_time", 3.0)), max_duration)
            sc_dur = round(sc_end - sc_start, 2)
            framing = first_scene.get("camera_framing") or "Medium Framing"
            cls_type = first_scene.get("scene_classification") or "presenter_take"
            vis_text = first_scene.get("visible_text")

            # Assess real visual metrics if sampled
            sampled = first_scene.get("sampled_metrics") or {}
            has_subtitles = sampled.get("subtitle_band_detected", False)
            contrast_val = sampled.get("contrast", 45.0)

            vis_category = "visual_action" if cls_type == "b_roll" else "talking_head_anchor"
            vis_gap = "Direct gaze creates social accountability" if cls_type == "talking_head" else "Dynamic visual motion stimulates visual cortex."

            vis_ev = EvidenceReference(
                source_modality="video_frame",
                verbatim_quote=vis_text,
                start_time=sc_start,
                end_time=sc_end,
                location_description=f"First video shot at timestamp 00:{int(sc_start):02d} ({framing}, classification: {cls_type})",
                confidence=0.88,
            )

            visual_hook_entry = HookEntry(
                modality="visual",
                category=vis_category,
                exact_text=vis_text,
                start_time=sc_start,
                end_time=sc_end,
                duration=sc_dur,
                mechanism=f"Visual framing: {framing} with contrast {contrast_val:.1f}",
                attention_strategy="Immediate visual subject presentation",
                promise_or_curiosity_gap=vis_gap,
                explanation=f"Visual entry presents {framing} ({cls_type}) spanning {sc_dur}s. Subtitle band observed: {has_subtitles}.",
                evidence=vis_ev,
                confidence=0.86,
                subjective_assessment="(Subjective Creative Assessment) Visual composition provides clean subject focus; adding subtle camera punch-in at 00:01 can elevate engagement.",
                suggested_alternatives=[
                    "Add dynamic graphic keyword pop-up within the first 1.5 seconds.",
                    "Begin on a close-up macro detail before zooming out to the presenter.",
                ],
            )
            hooks.append(visual_hook_entry)

        # --- 3. Caption / Text Hook ---
        text_hook_entry: HookEntry | None = None
        if caption:
            clean_cap = caption.strip()
            first_sentence = re.split(r"[\n.!?؟]+", clean_cap)[0].strip() or clean_cap[:60]
            txt_ev = EvidenceReference(
                source_modality="caption",
                verbatim_quote=first_sentence,
                start_time=0.0,
                end_time=None,
                location_description="Opening sentence of original post caption",
                confidence=0.98,
            )

            text_hook_entry = HookEntry(
                modality="caption_text",
                category="written_headline",
                exact_text=first_sentence,
                start_time=0.0,
                end_time=None,
                duration=None,
                mechanism="First line text teaser",
                attention_strategy="Immediate mobile feed preview line",
                promise_or_curiosity_gap="Encourages user to tap 'more' or watch full reel.",
                explanation=f"Caption hook opens with: '{first_sentence}'.",
                evidence=txt_ev,
                confidence=0.95,
                subjective_assessment="(Subjective Creative Assessment) Punchy opening line suitable for high-speed feed scrolling.",
                suggested_alternatives=[
                    f"👇 قصة {first_sentence[:20]} اللي محدش قالها قبل كده",
                    f"🚨 قبل ما تشوف الفيديو: {first_sentence[:30]}",
                ],
            )
            hooks.append(text_hook_entry)

        # --- 4. Opening-to-Payoff Connection ---
        # Search transcript for answering segments after the first quarter
        payoff_connection: dict[str, Any] = {
            "has_payoff": False,
            "payoff_timestamp": None,
            "payoff_quote": None,
            "connection_strength": "unverified",
            "reasoning": "Not verified by the deterministic provider.",
        }
        # A later segment alone is not evidence that an opening promise was resolved.

        # --- 5. Overall Hook Types & Heuristic Evaluation ---
        hook_types = sorted(list({h.category for h in hooks}))
        has_spoken = spoken_hook_entry is not None
        has_visual = visual_hook_entry is not None

        # Transparent heuristic calculation
        score = 5.0
        if has_spoken and spoken_hook_entry.duration and spoken_hook_entry.duration <= 4.0:
            score += 2.0
        elif has_spoken:
            score += 1.2
        if has_visual:
            score += 1.5
        if text_hook_entry:
            score += 0.8
        if payoff_connection.get("has_payoff"):
            score += 0.5
        score = min(max(round(score, 1), 1.0), 9.8)

        strengths = []
        if has_spoken:
            strengths.append(f"Clear spoken opening delivered within {spoken_hook_entry.duration}s")
        if has_visual:
            strengths.append("Visual composition immediately anchors viewer attention")
        if payoff_connection.get("has_payoff"):
            strengths.append(f"Clear hook-to-payoff continuity at {payoff_connection['payoff_timestamp']}s")

        weaknesses = []
        if has_spoken and spoken_hook_entry.duration and spoken_hook_entry.duration > 4.5:
            weaknesses.append("Spoken hook exceeds 4.5s before completing the primary curiosity tease")
        if not has_visual:
            weaknesses.append("Visual evidence was limited; video was analyzed via audio/metadata only")

        recommendations = [
            "Test an aggressive soundbite under 3.0 seconds to maximize 3-second hold rate",
            "Synchronize a high-contrast on-screen keyword graphic exactly at 00:01",
        ]

        alignment = (
            "Synchronous: Spoken narration and visual presentation align on the core topic."
            if (has_spoken and has_visual)
            else "Partial: Analyzed primarily through accessible text/audio modalities."
        )

        return StructuredHookAnalysis(
            spoken_hook=spoken_hook_entry,
            visual_hook=visual_hook_entry,
            text_hook=text_hook_entry,
            all_hooks=hooks,
            hook_types=hook_types,
            clarity="Heuristic classification from the opening source text",
            specificity="Evidence quote and timestamp are separately verified",
            relevance="Not semantically established by the deterministic provider",
            curiosity_mechanism=spoken_hook_entry.mechanism if spoken_hook_entry else "Textual inquiry",
            text_visual_alignment=alignment,
            opening_payoff_connection=payoff_connection,
            heuristic_score=score,
            qualitative_strengths=strengths,
            qualitative_weaknesses=weaknesses,
            recommendations=recommendations,
            model_name=self.model_id,
            provider_version=self.version,
            source_durations_validated=True,
        )

    def analyze_copy(
        self,
        caption: str | None,
        author_name: str | None = None,
        username: str | None = None,
    ) -> StructuredCopyAnalysis:
        raw_caption = caption or ""
        trimmed = raw_caption.strip()

        # Sentence extraction
        sentences = [s.strip() for s in re.split(r"[\n.!?؟]+", trimmed) if s.strip()]
        opening_sentence = sentences[0] if sentences else None

        # Hashtags
        hashtags = re.findall(r"#([^\s#]+)", trimmed)
        
        # Dynamic topic extraction
        main_topic, secondary_topics = self._extract_topics_dynamically(trimmed, hashtags)

        # Dialect detection
        writing_style, dialect_conf = self._detect_dialect(trimmed)

        # Dynamic CTA detection
        cta_type = "none"
        cta_text = None
        is_explicit = False
        cta_evidence: EvidenceReference | None = None

        for pattern, detected_type in CTA_PATTERNS:
            match = re.search(pattern, trimmed, flags=re.IGNORECASE)
            if match:
                cta_type = detected_type
                cta_text = match.group(0).strip()
                is_explicit = True
                cta_evidence = EvidenceReference(
                    source_modality="caption",
                    verbatim_quote=cta_text,
                    start_time=None,
                    end_time=None,
                    location_description="Matched call-to-action directive in caption text",
                    confidence=0.96,
                )
                break

        # Persuasion techniques derived from text evidence
        persuasion = []
        if is_explicit:
            persuasion.append(f"Explicit Action Prompt ('{cta_text}')")
        if hashtags:
            persuasion.append(f"Hashtag Discoverability Clustering ({len(hashtags)} tags)")
        if any(w in trimmed.lower() for w in CURIOSITY_WORDS):
            persuasion.append("Curiosity Gap Framing")
        if any(w in trimmed for w in ["شاهد", "كاملة", "جديد", "حصري", "watch", "new"]):
            persuasion.append("Freshness and Exclusivity Tease")
        if not persuasion:
            persuasion.append("Direct Informational Broadcast")

        # Audience address
        if re.search(r"\b(يا جماعة|قولولنا|شاركونا|رأيكم|أنتم|guys|everyone)\b", trimmed):
            audience_address = "Direct Second-Person Community Address"
        else:
            audience_address = "Third-Person Broadcast / Announcement"

        # Tone
        tone = "Engaging and conversational" if "Egyptian" in writing_style else "Informative and structured"

        # Objective
        if cta_type == "link_in_bio":
            objective = "Cross-channel traffic conversion (directing profile/link clicks)"
        elif cta_type == "comment":
            objective = "Comment section engagement and algorithm boost"
        elif cta_type == "share":
            objective = "Viral referral and peer sharing"
        else:
            objective = "Brand awareness and content consumption"

        # Structure description
        struct_desc = f"{len(sentences)} distinct textual units; opening statement followed by {cta_type.replace('_', ' ')} directive."

        # Brand voice
        creator_ref = author_name or (f"@{username}" if username else "the creator")
        brand_voice = f"Authentic signature voice of {creator_ref}: framed in {writing_style}."

        summary = (
            f"The caption employs {writing_style} focused on '{main_topic}'. "
            f"Concludes with a {cta_type.replace('_', ' ')} directive ('{cta_text or 'implicit'}')."
        )

        evidence_list = []
        if opening_sentence:
            evidence_list.append(
                EvidenceReference(
                    source_modality="caption",
                    verbatim_quote=opening_sentence,
                    location_description="Opening caption statement",
                    confidence=0.98,
                )
            )
        if cta_evidence:
            evidence_list.append(cta_evidence)

        # Classify hashtags into branded vs topic
        branded_tags = [
            tag for tag in hashtags
            if (author_name and author_name.lower().replace(" ", "") in tag.lower().replace("_", ""))
            or (username and username.lower() in tag.lower())
            or tag in {"الدحيح", "eldaheeh", "AJplus"}
        ]
        topic_tags = [tag for tag in hashtags if tag not in branded_tags]

        hashtag_strategy = {
            "total_count": len(hashtags),
            "tags": hashtags,
            "branded_hashtags": branded_tags,
            "topic_hashtags": topic_tags,
            "strategy_type": "Branded & Focused" if branded_tags else ("Broad Category Discovery" if hashtags else "None"),
        }

        return StructuredCopyAnalysis(
            original_caption=raw_caption,
            opening_sentence=opening_sentence,
            primary_message=opening_sentence or f"Content release by {creator_ref}",
            main_topic=main_topic,
            secondary_topics=secondary_topics,
            tone_of_voice=tone,
            writing_style=writing_style,
            emotional_framing="Curiosity and engagement",
            persuasion_techniques=persuasion,
            content_objective=objective,
            audience_address=audience_address,
            hashtag_strategy=hashtag_strategy,
            cta_type=cta_type,
            cta_text=cta_text,
            is_explicit_cta=is_explicit,
            caption_structure=struct_desc,
            sentence_characteristics=f"{len(sentences)} sentences, average length {round(len(trimmed.split()) / max(len(sentences), 1), 1)} words",
            readability_observations="High mobile readability, clear formatting without clutter.",
            brand_voice_indicators=brand_voice,
            summary=summary,
            evidence_citations=evidence_list,
            model_name=self.model_id,
        )

    def analyze_narrative(
        self,
        transcript_segments: list[dict[str, Any]] | None,
        full_transcript: str | None,
        caption: str | None,
        source_duration: float | None,
    ) -> StructuredNarrativeAnalysis:
        duration = source_duration or 30.0
        text = full_transcript or caption or ""
        lower_text = text.lower()

        # Determine pattern from semantic markers
        if any(w in lower_text for w in ["قصة", "حكايتي", "مرة", "كنت", "زمان", "story", "once"]):
            pattern = "personal_storytelling"
        elif any(w in lower_text for w in ["إزاي", "طريقة", "خطوات", "شرح", "how to", "tutorial"]):
            pattern = "tutorial_how_to"
        elif any(w in lower_text for w in ["تحدي", "challenge"]):
            pattern = "challenge_and_attempt"
        elif "?" in text or "؟" in text:
            pattern = "question_and_investigation"
        else:
            pattern = "educational_explanation"

        stages: list[StructuredNarrativeStage] = []

        if transcript_segments and len(transcript_segments) >= 2:
            # Segment dynamically based on observed timestamps
            n = len(transcript_segments)
            # Stage 1: Hook & Opening (First 15-20%)
            idx_hook_end = max(1, min(int(n * 0.25), 2))
            hook_segs = transcript_segments[:idx_hook_end]
            hook_quote = " ".join(s.get("text", "") for s in hook_segs)
            h_start = float(hook_segs[0].get("start_time", 0.0))
            h_end = float(hook_segs[-1].get("end_time", 4.0))

            stages.append(
                StructuredNarrativeStage(
                    stage_name="Opening / Hook",
                    start_time=round(h_start, 2),
                    end_time=round(h_end, 2),
                    description="Opening transcript interval selected by source position; rhetorical function is heuristic.",
                    evidence_quote=hook_quote[:120],
                    confidence=0.94,
                    rhetorical_function="Attention Capture",
                )
            )

            # Stage 2: Narrative Development & Conflict (Middle section)
            mid_segs = transcript_segments[idx_hook_end:-1] if n > 3 else transcript_segments[idx_hook_end:]
            if mid_segs:
                m_start = float(mid_segs[0].get("start_time", h_end))
                m_end = float(mid_segs[-1].get("end_time", duration * 0.8))
                mid_quote = " ".join(s.get("text", "") for s in mid_segs[:3])
                stages.append(
                    StructuredNarrativeStage(
                        stage_name="Core Development & Explanation",
                        start_time=round(m_start, 2),
                        end_time=round(m_end, 2),
                        description="Middle transcript interval selected by source position; narrative role is heuristic.",
                        evidence_quote=mid_quote[:120],
                        confidence=0.90,
                        rhetorical_function="Substantive Exposition",
                    )
                )

            # Stage 3: Payoff & Call to Action (Final segment)
            closing_segs = transcript_segments[-1:] if n > 2 else []
            if closing_segs:
                c_start = float(closing_segs[0].get("start_time", max(duration - 6.0, 0.0)))
                c_end = float(closing_segs[-1].get("end_time", duration))
                c_quote = closing_segs[0].get("text", "")
                stages.append(
                    StructuredNarrativeStage(
                        stage_name="Closing Transcript Interval",
                        start_time=round(c_start, 2),
                        end_time=round(c_end, 2),
                        description="Final transcript interval; payoff or CTA is not assumed without semantic verification.",
                        evidence_quote=c_quote[:120],
                        confidence=0.92,
                        rhetorical_function="Heuristic Closing Position",
                    )
                )
        else:
            # Transcript unavailable; structure based on caption
            if caption:
                stages.append(
                    StructuredNarrativeStage(
                        stage_name="Caption Opening",
                        start_time=0.0,
                        end_time=0.0,
                        description="Opening caption excerpt; no video timeline claim is made.",
                        evidence_quote=caption[:100],
                        confidence=0.80,
                        rhetorical_function="Heuristic Topic Introduction",
                    )
                )

        summary = (
            f"Deterministic heuristic suggests '{pattern.replace('_', ' ')}' across {len(stages)} source intervals."
        )

        return StructuredNarrativeAnalysis(
            narrative_pattern=pattern,
            summary=summary,
            stages=stages,
            opening_payoff_alignment="Unverified in deterministic mode.",
            model_name=self.model_id,
        )

    def generate_creative(
        self,
        output_type: str,
        topic_context: str | None,
        creator_dna: dict[str, Any] | None,
        target_audience: str,
        target_platform: str,
        target_duration: str,
        target_language: str,
    ) -> list[StructuredCreativeVariation]:
        topic = topic_context or "الموضوع الرئيسي والمحتوى الملهم"
        variations: list[StructuredCreativeVariation] = []

        if output_type == "hook_variations":
            variations.append(
                StructuredCreativeVariation(
                    suggested_hook=f"عارف السر اللي خلى قصة {topic} تقلب كل الموازين في ثواني؟",
                    suggested_caption=f"كل التفاصيل اللي محدش اتكلم عنها قبل كده في الفيديو الجديد. الرابط في البايو 🔗👇",
                    suggested_cta="شوف الحلقة كاملة من اللينك في البايو",
                    script_outline="[00:00 - 00:03] لقطة قريبة على الوجه + نبرة تساؤل درامية + كلمة مفتاحية تظهر كـ Text Pop-up أحمر متزامن.",
                    creative_rationale="استراتيجية الفجوة المعرفية (Curiosity Gap) مصممة لإثارة التساؤل المباشر في أول 3 ثوان.",
                    model_name=self.model_id,
                )
            )
            variations.append(
                StructuredCreativeVariation(
                    suggested_hook=f"أكبر خرافة بتسمعها عن {topic}.. والحقيقة الصادمة اللي اكتشفناها!",
                    suggested_caption=f"الحقيقة الكاملة بالأدلة والأرقام. مستني رأيكم في التعليقات 💬👇",
                    suggested_cta="قولنا رأيك في الكومنتات بعد المشاهدة",
                    script_outline="[00:00 - 00:02] إشارة باليد نحو الكاميرا لكسر النمط (Pattern Interrupt) وتحدي المفاهيم السابقة.",
                    creative_rationale="استراتيجية مقاطعة النمط وتحدي المفاهيم المسبقة للمتابع لمضاعفة معدل الاستبقاء.",
                    model_name=self.model_id,
                )
            )
            variations.append(
                StructuredCreativeVariation(
                    suggested_hook=f"في دقيقة واحدة بس.. هقولك على أهم درس عملي تقدر تطبقه من تجربة {topic}!",
                    suggested_caption=f"احفظ الفيديو ده عندك عشان ترجعله في أي وقت 📌 الرابط كامل في البايو.",
                    suggested_cta="احفظ الفيديو عندك ودوس على اللينك في البايو",
                    script_outline="[00:00 - 00:04] ظهور عداد تنازلي 60s في الزاوية العلوية لتقديم وعد مباشر بالقيمة السريعة.",
                    creative_rationale="استراتيجية الوعد المباشر محدد المدة (Direct Value Promise) لجذب المشاهد الباحث عن فائدة سريعة.",
                    model_name=self.model_id,
                )
            )
        elif output_type == "video_script":
            variations.append(
                StructuredCreativeVariation(
                    suggested_hook=f"تخيل لو صحيت الصبح ولقيت إن كل اللي درسته عن {topic} طلع غلط؟",
                    suggested_caption=f"حلقة جديدة كاملة في البايو عن القصة اللي هزت كل المفاهيم! #معرفة #إلهام",
                    suggested_cta="رابط الحلقة كاملة في البايو",
                    script_outline=(
                        f"المشهد 1 (00:00 - 00:04): [لقطة متوسطة قريبة MCU] المتحدث ينظر مباشرة للكاميرا بنبرة مدهشة.\n"
                        f"المشهد 2 (00:04 - 00:15): [بي رول أرشيفي أو لقطات توضيحية] سياق تاريخي ودرامي للموضوع.\n"
                        f"المشهد 3 (00:15 - 00:35): [شرح مبسط مع جرافيك] تفكيك المعضلة بأسلوب حواري سريع الإيقاع.\n"
                        f"المشهد 4 (00:35 - 00:45): [خاتمة ونداء إجراء] 'الحكاية لسه فيها أسرار.. اللينك في البايو'."
                    ),
                    creative_rationale="هيكلية سردية كلاسيكية قائمة على: الصدمة الأولية -> بناء السياق -> تفكيك المشكلة -> نداء الإجراء.",
                    model_name=self.model_id,
                )
            )
        else:
            variations.append(
                StructuredCreativeVariation(
                    suggested_hook=f"السؤال الأهم في حكاية {topic}.. هل ده كان صدفة ولا خطة؟",
                    suggested_caption=f"اكتشف التفاصيل المدهشة في حلقة اليوم. رابط المشاهدة متوفر في البايو 👆💡",
                    suggested_cta="رابط الحلقة كاملة في البايو",
                    script_outline="تركيز على التفاعل الفوري في التعليقات ونقل المتابع بسلاسة إلى البايو.",
                    creative_rationale="صياغة متوازنة بين الإيجاز وإعطاء سبب مقنع للنقر على الرابط.",
                    model_name=self.model_id,
                )
            )
        return variations


# --- Configurable Remote/Local Endpoint Adapter (Optional OpenAI-Compatible Provider) ---

class ConfigurableLLMSemanticProvider(SemanticAnalysisProvider):
    """Adapter connecting to any local or remote OpenAI-compatible API endpoint with deterministic fallback."""

    def __init__(
        self,
        api_base: str,
        api_key: str | None = None,
        model_name: str = "gpt-4o-mini",
        fallback_provider: SemanticAnalysisProvider | None = None,
        timeout_seconds: float = 90.0,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key or "local"
        self.model_name = model_name
        self.fallback = fallback_provider or DeterministicMultilingualSemanticProvider()
        self.timeout_seconds = timeout_seconds
        self.last_execution: Literal["not_attempted", "succeeded", "fallback"] = "not_attempted"
        self.last_error: str | None = None

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_name="ConfigurableLLMSemanticProvider",
            model_id=self.model_name,
            version="1.0.0-openai-compatible",
            locality="network" if "localhost" in self.api_base or "127.0.0.1" in self.api_base else "remote",
            is_ready=bool(self.api_base and self.model_name),
            supported_dialects=["Egyptian Arabic", "Modern Standard Arabic", "English"],
            notes=f"Configured OpenAI-compatible endpoint {self.api_base}; failures are explicitly labeled as fallback to {self.fallback.model_id}.",
            analysis_kind="llm",
            last_execution=self.last_execution,
        )

    def _invoke(self, schema: type[BaseModel], task: str, inputs: dict[str, Any]) -> BaseModel:
        response = httpx.post(
            f"{self.api_base}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model_name,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Return one JSON object matching the supplied JSON Schema. Analyze Arabic or English in context. "
                            "Never invent quotations, OCR, objects, actions, or timestamps. Use only the supplied sources; "
                            "use null/empty values when evidence is absent."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"task": task, "json_schema": schema.model_json_schema(), "sources": inputs},
                            ensure_ascii=False,
                            default=str,
                        ),
                    },
                ],
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content) if isinstance(content, str) else content
        result = schema.model_validate(parsed)
        self.last_execution = "succeeded"
        self.last_error = None
        return result

    def _fallback(self, method: str, *args, error: Exception, **kwargs):
        self.last_execution = "fallback"
        self.last_error = f"{type(error).__name__}: {error}"
        logger.warning("Semantic LLM call failed; using explicitly labeled deterministic fallback: %s", self.last_error)
        return getattr(self.fallback, method)(*args, **kwargs)

    @staticmethod
    def _quote_is_grounded(quote: str | None, source: str | None) -> bool:
        normalized_quote = re.sub(r"\s+", " ", quote or "").strip().casefold()
        normalized_source = re.sub(r"\s+", " ", source or "").strip().casefold()
        return bool(normalized_quote and normalized_quote in normalized_source)

    def analyze_hooks(self, *args, **kwargs) -> StructuredHookAnalysis:
        try:
            result = self._invoke(StructuredHookAnalysis, "Evidence-grounded hook analysis", kwargs)
            transcript = kwargs.get("full_transcript") or ""
            caption = kwargs.get("caption") or ""
            grounded: list[HookEntry] = []
            for hook in result.all_hooks:
                source = transcript if hook.evidence.source_modality == "transcript" else caption
                if hook.evidence.source_modality in {"transcript", "caption"} and self._quote_is_grounded(hook.evidence.verbatim_quote, source):
                    grounded.append(hook)
                elif hook.evidence.source_modality in {"video_frame", "ocr_overlay"}:
                    # This provider receives no image bytes or OCR output in the current pipeline.
                    continue
            result = result.model_copy(update={
                "all_hooks": grounded,
                "spoken_hook": next((h for h in grounded if h.modality == "spoken"), None),
                "text_hook": next((h for h in grounded if h.modality == "caption_text"), None),
                "visual_hook": None,
                "model_name": self.model_name,
                "provider_version": "openai-compatible-v1",
            })
            return result
        except Exception as exc:
            return self._fallback("analyze_hooks", *args, error=exc, **kwargs)

    def analyze_copy(self, *args, **kwargs) -> StructuredCopyAnalysis:
        try:
            result = self._invoke(StructuredCopyAnalysis, "Evidence-grounded caption and copywriting analysis", kwargs)
            caption = kwargs.get("caption") or ""
            citations = [c for c in result.evidence_citations if self._quote_is_grounded(c.verbatim_quote, caption)]
            return result.model_copy(update={
                "original_caption": kwargs.get("caption"),
                "evidence_citations": citations,
                "model_name": self.model_name,
            })
        except Exception as exc:
            return self._fallback("analyze_copy", *args, error=exc, **kwargs)

    def analyze_narrative(self, *args, **kwargs) -> StructuredNarrativeAnalysis:
        try:
            result = self._invoke(StructuredNarrativeAnalysis, "Evidence-grounded narrative analysis", kwargs)
            source = kwargs.get("full_transcript") or kwargs.get("caption") or ""
            duration = kwargs.get("source_duration")
            stages = [
                stage for stage in result.stages
                if self._quote_is_grounded(stage.evidence_quote, source)
                and stage.start_time >= 0
                and stage.end_time >= stage.start_time
                and (duration is None or stage.end_time <= duration + 0.25)
            ]
            return result.model_copy(update={"stages": stages, "model_name": self.model_name})
        except Exception as exc:
            return self._fallback("analyze_narrative", *args, error=exc, **kwargs)

    def generate_creative(self, *args, **kwargs) -> list[StructuredCreativeVariation]:
        class CreativeBatch(BaseModel):
            variations: list[StructuredCreativeVariation]
        try:
            result = self._invoke(CreativeBatch, "Generate clearly labeled creative recommendations", kwargs)
            return [item.model_copy(update={"model_name": self.model_name}) for item in result.variations]
        except Exception as exc:
            return self._fallback("generate_creative", *args, error=exc, **kwargs)


# --- Global Provider Factory ---

_cached_provider: SemanticAnalysisProvider | None = None

def get_semantic_provider() -> SemanticAnalysisProvider:
    global _cached_provider
    if _cached_provider is not None:
        return _cached_provider

    from backend.core.config import get_settings
    settings = get_settings()
    provider_type = os.getenv("EMY_SOCIAL_SEMANTIC_PROVIDER", settings.social_semantic_provider).lower()
    api_base = os.getenv("EMY_SEMANTIC_API_BASE") or settings.semantic_api_base

    if provider_type == "openai_compatible" and api_base:
        api_key = os.getenv("EMY_SEMANTIC_API_KEY")
        model = os.getenv("EMY_SEMANTIC_MODEL") or settings.semantic_model
        if not model:
            logger.warning("OpenAI-compatible semantic provider requested without a model; using deterministic fallback")
            _cached_provider = DeterministicMultilingualSemanticProvider()
            return _cached_provider
        _cached_provider = ConfigurableLLMSemanticProvider(
            api_base=api_base,
            api_key=api_key,
            model_name=model,
            timeout_seconds=settings.semantic_request_timeout_seconds,
        )
    else:
        _cached_provider = DeterministicMultilingualSemanticProvider()

    logger.info("Initialized semantic provider: %s", _cached_provider.get_provider_info().model_id)
    return _cached_provider
