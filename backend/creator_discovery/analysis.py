"""Evidence-only unified creator analysis with replaceable provider boundary."""

from __future__ import annotations

import statistics
from abc import ABC, abstractmethod
from collections import Counter
from datetime import datetime
from typing import Any

from backend.creator_discovery.config import CreatorDiscoveryConfig, get_creator_discovery_config
from backend.db.models.creator_discovery import CreatorContentSample, CreatorDiscoveryAccount


class CreatorAnalysisProvider(ABC):
    provider_code: str
    model_version: str

    @abstractmethod
    def analyze(
        self,
        *,
        accounts: list[CreatorDiscoveryAccount],
        samples: list[CreatorContentSample],
    ) -> dict[str, Any]:
        raise NotImplementedError


class EvidenceOnlyCreatorAnalyzer(CreatorAnalysisProvider):
    """Local deterministic summary; every result points to collected fields."""

    provider_code = "emy_content_analyzer"
    model_version = "creator-evidence-rules-2.0.0"

    def __init__(self, config: CreatorDiscoveryConfig | None = None) -> None:
        self.config = config or get_creator_discovery_config()

    def analyze(
        self,
        *,
        accounts: list[CreatorDiscoveryAccount],
        samples: list[CreatorContentSample],
    ) -> dict[str, Any]:
        evidence = self._evidence_text(accounts, samples)
        industry, niche, taxonomy_evidence = self._taxonomy(evidence)
        mechanisms, mechanism_evidence = self._mechanisms(samples)
        main_platform, main_confidence, platform_evidence = self._main_platform(accounts)
        influence_numeric = max((item.followers for item in accounts if item.followers is not None), default=None)
        start_year, start_confidence, start_source = self._start_year(accounts, samples)
        kpi, kpi_evidence = self._kpi(accounts, samples)
        format_patterns = _format_patterns(samples)
        cta_patterns = _cta_patterns(samples)
        posting_patterns = _posting_patterns(samples)
        content_angle = _content_angle(mechanisms)
        content_style = ", ".join(mechanisms) if mechanisms else "UNKNOWN"
        engagement_pattern = _engagement_pattern(accounts, samples)
        audience_analysis = _audience_analysis(accounts, samples)
        trend_analysis = _trend_analysis(samples, posting_patterns)
        visual_style = _visual_style(samples)
        content_themes = _content_themes(samples)
        hook_style = _hook_style(samples)
        caption_style = _caption_style(samples)
        communication_style = _communication_style(mechanisms, caption_style)
        community_signals = _community_impact(samples)
        positioning = _positioning(niche, content_style, main_platform)
        success_formula = _success_formula(content_style, hook_style, cta_patterns)
        audience_type = _audience_type(niche, audience_analysis)
        confidence_parts = [value for value in (
            0.8 if taxonomy_evidence else None,
            0.75 if mechanism_evidence else None,
            main_confidence if main_platform != "UNKNOWN" else None,
            start_confidence if start_year else None,
        ) if value is not None]
        return {
            "niche": niche,
            "industry": industry,
            "main_platform": main_platform,
            "main_platform_confidence": main_confidence,
            "content_mechanism_style": ", ".join(mechanisms) if mechanisms else "UNKNOWN",
            "influence_size": format_influence_size(influence_numeric),
            "influence_size_numeric": influence_numeric,
            "kpi_impact": kpi,
            "content_category": niche,
            "content_type": _as_text(format_patterns),
            "content_angle": content_angle,
            "content_style": content_style,
            "visual_style": visual_style,
            "cta_analysis": _as_text(cta_patterns),
            "engagement_pattern": engagement_pattern,
            "audience_analysis": audience_analysis,
            "trend_analysis": trend_analysis,
            "ai_recommendation": _recommendation(main_platform, niche, content_style),
            "personalization": _personalization(main_platform, niche),
            "campaign_idea": _campaign_idea(niche, content_angle),
            "creative_strategy": _creative_strategy(content_style, posting_patterns),
            "community_impact": _community_impact(samples),
            "category": industry,
            "content_themes": content_themes,
            "hook_style": hook_style,
            "caption_style": caption_style,
            "communication_style": communication_style,
            "voice": communication_style,
            "tone": _tone(samples),
            "personality": _personality(mechanisms),
            "presentation_style": visual_style,
            "editing_style": visual_style,
            "storytelling_style": "Storytelling" if "Storytelling" in mechanisms else "UNKNOWN",
            "brand_identity": _brand_identity(niche, visual_style),
            "creative_pattern": _creative_pattern(content_style, format_patterns, hook_style),
            "audience_relationship": _audience_relationship(cta_patterns, samples),
            "success_formula": success_formula,
            "audience_type": audience_type,
            "audience_interests": ", ".join(content_themes) if content_themes else "UNKNOWN",
            "audience_needs": _audience_needs(niche),
            "audience_problem": _audience_problem(niche),
            "audience_motivation": _audience_motivation(niche),
            "audience_questions": _audience_questions(samples),
            "audience_trigger": hook_style,
            "engagement_behavior": engagement_pattern,
            "community_signals": community_signals,
            "brand_suitability": _brand_suitability(niche, content_style, engagement_pattern),
            "positioning": positioning,
            "usp": success_formula,
            "mission": _mission(niche, content_angle),
            "vision": "UNKNOWN",
            "benchmark": "UNKNOWN",
            "differentiation": _differentiation(content_style, visual_style),
            "collaboration_opportunities": _collaboration_opportunities(niche, content_style),
            "growth_opportunities": _growth_opportunities(trend_analysis, posting_patterns),
            "brand_partnership_suggestions": _brand_partnerships(niche),
            "posting_behavior": posting_patterns,
            "growth_signals": _growth_signals(accounts, samples),
            "platform_factors": _platform_factors(format_patterns, cta_patterns),
            "campaign_goal": _campaign_goal(cta_patterns),
            "cta_type": _cta_type(cta_patterns),
            "copy_framework": _copy_framework(samples),
            "persuasion_elements": _persuasion_elements(samples),
            "emotional_trigger": _emotional_trigger(samples),
            "value_promise": _value_promise(niche, content_angle),
            "recommendation_reasoning": _recommendation_reasoning(len(samples), content_style, engagement_pattern),
            "word_of_mouth": community_signals,
            "start_year": start_year,
            "start_year_confidence": start_confidence,
            "start_year_source": start_source,
            "analysis_status": "COMPLETED" if evidence else "INSUFFICIENT_EVIDENCE",
            "confidence": round(statistics.fmean(confidence_parts), 3) if confidence_parts else 0.0,
            "evidence_references": taxonomy_evidence + mechanism_evidence + platform_evidence + kpi_evidence,
            "details": {
                "format_patterns": format_patterns,
                "presentation_style": "UNKNOWN",
                "editing_style": "UNKNOWN",
                "storytelling_style": "Storytelling" if "Storytelling" in mechanisms else "UNKNOWN",
                "educational_entertainment_mix": _education_mix(samples),
                "commercial_behavior": _commercial_behavior(samples),
                "cta_patterns": cta_patterns,
                "posting_patterns": posting_patterns,
            },
        }

    @staticmethod
    def _evidence_text(accounts: list[CreatorDiscoveryAccount], samples: list[CreatorContentSample]) -> str:
        values = [item.bio or "" for item in accounts]
        values.extend(f"{item.title or ''} {item.caption or ''}" for item in samples)
        return " ".join(values).casefold().strip()

    def _taxonomy(self, evidence: str) -> tuple[str, str, list[str]]:
        if not evidence:
            return "UNKNOWN", "UNKNOWN", []
        scores: Counter[str] = Counter()
        matched: dict[str, list[str]] = {}
        names: dict[str, str] = {}
        for item in self.config.industry_taxonomy:
            names[item.code] = item.name
            hits = [keyword for keyword in item.keywords if keyword.casefold() in evidence]
            if hits:
                scores[item.code] = len(hits)
                matched[item.code] = hits
        if not scores:
            return "UNKNOWN", "UNKNOWN", []
        code, _ = scores.most_common(1)[0]
        niche_names = {
            "education": "Edutainment / Education", "technology": "Technology / Gadgets",
            "entertainment": "Entertainment", "food": "Food / Reviews", "gaming": "Gaming",
            "lifestyle": "Lifestyle", "sports": "Sports", "travel": "Travel",
            "cinema": "Cinema", "auto": "Auto / Reviews", "beauty": "Beauty / Skincare",
            "business": "Business / Marketing",
        }
        references = [f"taxonomy:{code}:{keyword}" for keyword in matched[code]]
        return names[code], niche_names.get(code, names[code]), references

    @staticmethod
    def _mechanisms(samples: list[CreatorContentSample]) -> tuple[list[str], list[str]]:
        text = " ".join(f"{item.title or ''} {item.caption or ''}" for item in samples).casefold()
        mechanisms: list[str] = []
        references: list[str] = []
        groups = (
            ("Reviews and comparisons", ("review", "unboxing", "comparison", "versus", "vs ")),
            ("Educational explainers", ("how to", "tutorial", "learn", "explained", "tips")),
            ("Storytelling", ("story", "what happened", "journey", "experience")),
            ("Commercial product features", ("shop", "buy", "discount", "offer", "sponsored")),
        )
        for label, terms in groups:
            hits = [term for term in terms if term in text]
            if hits:
                mechanisms.append(label)
                references.extend(f"mechanism:{label}:{term}" for term in hits)
        durations = [item.duration_seconds for item in samples if item.duration_seconds is not None]
        if durations and sum(value <= 60 for value in durations) / len(durations) >= 0.6:
            mechanisms.append("Short-form video")
            references.append(f"duration:short_form:{sum(value <= 60 for value in durations)}/{len(durations)}")
        return mechanisms, references

    @staticmethod
    def _main_platform(accounts: list[CreatorDiscoveryAccount]) -> tuple[str, float, list[str]]:
        followers = [item for item in accounts if item.followers is not None]
        if followers:
            ordered = sorted(followers, key=lambda item: (item.followers or 0, item.content_count or 0), reverse=True)
            leader = ordered[0]
            runner = ordered[1].followers if len(ordered) > 1 else 0
            confidence = 0.95 if not runner or (leader.followers or 0) >= runner * 1.25 else 0.7
            return leader.platform, confidence, [f"account:{leader.account_uid}:followers:{leader.followers}"]
        activity = [item for item in accounts if item.content_count is not None]
        if activity:
            leader = max(activity, key=lambda item: item.content_count or 0)
            return leader.platform, 0.6, [f"account:{leader.account_uid}:content_count:{leader.content_count}"]
        if len(accounts) == 1:
            return accounts[0].platform, 0.4, [f"account:{accounts[0].account_uid}:only_observed_platform"]
        return "UNKNOWN", 0.0, []

    @staticmethod
    def _start_year(accounts: list[CreatorDiscoveryAccount], samples: list[CreatorContentSample]) -> tuple[int | None, float, str | None]:
        official = []
        for account in accounts:
            published = account.metadata_json.get("published_at")
            if published:
                try:
                    official.append((datetime.fromisoformat(str(published).replace("Z", "+00:00")), account.profile_url))
                except ValueError:
                    pass
        if official:
            earliest = min(official, key=lambda item: item[0])
            return earliest[0].year, 1.0, earliest[1]
        dates = [item for item in samples if item.published_at]
        if dates:
            earliest = min(dates, key=lambda item: item.published_at)  # type: ignore[arg-type]
            return earliest.published_at.year, 0.5, earliest.content_url  # type: ignore[union-attr]
        return None, 0.0, None

    @staticmethod
    def _kpi(accounts: list[CreatorDiscoveryAccount], samples: list[CreatorContentSample]) -> tuple[str, list[str]]:
        followers = max((item.followers for item in accounts if item.followers), default=None)
        rates = []
        share_rates = []
        review_count = 0
        educational_count = 0
        for item in samples:
            engagement = sum(value or 0 for value in (item.likes, item.comments, item.shares))
            denominator = item.views or followers
            if denominator:
                rates.append(engagement / denominator)
            if item.views and item.shares is not None:
                share_rates.append(item.shares / item.views)
            text = f"{item.title or ''} {item.caption or ''}".casefold()
            review_count += int(any(term in text for term in ("review", "unboxing", "comparison")))
            educational_count += int(any(term in text for term in ("how to", "tutorial", "learn", "explained")))
        labels: list[str] = []
        references: list[str] = []
        if len(rates) >= 3 and statistics.fmean(rates) >= 0.05:
            labels.append("High engagement")
            references.append(f"kpi:mean_public_engagement_rate:{statistics.fmean(rates):.4f}")
        if len(share_rates) >= 3 and statistics.fmean(share_rates) >= 0.01:
            labels.append("High sharing tendency")
            references.append(f"kpi:mean_public_share_rate:{statistics.fmean(share_rates):.4f}")
        if review_count >= 3:
            labels.append("Strong product-review influence")
            references.append(f"kpi:review_samples:{review_count}")
        if educational_count >= 3 and followers and followers >= 100_000:
            labels.append("High educational authority")
            references.append(f"kpi:educational_samples:{educational_count}:followers:{followers}")
        return "; ".join(labels) if labels else "UNKNOWN", references


def format_influence_size(value: int | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value >= 1_000_000:
        amount = value / 1_000_000
        shown = f"{amount:.1f}".rstrip("0").rstrip(".")
        return f"+{shown} Million"
    if value >= 1_000:
        amount = value / 1_000
        shown = f"{amount:.0f}" if amount >= 10 else f"{amount:.1f}".rstrip("0").rstrip(".")
        return f"+{shown}K"
    return f"+{value}"


def _format_patterns(samples: list[CreatorContentSample]) -> list[str] | str:
    values = sorted({item.content_type for item in samples if item.content_type and item.content_type != "UNKNOWN"})
    return values or "UNKNOWN"


def _education_mix(samples: list[CreatorContentSample]) -> str:
    if not samples:
        return "UNKNOWN"
    education = sum(any(term in f"{item.title or ''} {item.caption or ''}".casefold() for term in ("how to", "tutorial", "learn", "explained")) for item in samples)
    entertainment = sum(any(term in f"{item.title or ''} {item.caption or ''}".casefold() for term in ("funny", "comedy", "challenge", "entertainment")) for item in samples)
    if not education and not entertainment:
        return "UNKNOWN"
    return f"observed educational={education}, entertainment={entertainment}, sample={len(samples)}"


def _commercial_behavior(samples: list[CreatorContentSample]) -> str:
    count = sum(any(term in f"{item.title or ''} {item.caption or ''}".casefold() for term in ("buy", "shop", "discount", "offer", "sponsored", "affiliate")) for item in samples)
    return f"commercial signals in {count}/{len(samples)} samples" if count else "UNKNOWN"


def _cta_patterns(samples: list[CreatorContentSample]) -> list[str] | str:
    text = " ".join(f"{item.title or ''} {item.caption or ''}" for item in samples).casefold()
    patterns = [label for label, terms in (
        ("subscribe", ("subscribe", "follow")), ("visit", ("link in bio", "visit")),
        ("buy", ("buy now", "shop now")), ("comment", ("comment below", "tell me")),
    ) if any(term in text for term in terms)]
    return patterns or "UNKNOWN"


def _posting_patterns(samples: list[CreatorContentSample]) -> str:
    dates = sorted(item.published_at for item in samples if item.published_at)
    if len(dates) < 3:
        return "UNKNOWN"
    gaps = [(right - left).total_seconds() / 86400 for left, right in zip(dates, dates[1:])]
    return f"median observed interval {statistics.median(gaps):.1f} days across {len(dates)} samples"


def _as_text(value: list[str] | str) -> str:
    return ", ".join(value) if isinstance(value, list) else value


def _content_angle(mechanisms: list[str]) -> str:
    for mechanism, angle in (
        ("Educational explainers", "Education and problem solving"),
        ("Reviews and comparisons", "Product evaluation and comparison"),
        ("Storytelling", "Personal story and experience"),
        ("Commercial product features", "Product discovery and conversion"),
    ):
        if mechanism in mechanisms:
            return angle
    return "UNKNOWN"


def _visual_style(samples: list[CreatorContentSample]) -> str:
    values = []
    media_formats = []
    for sample in samples:
        for key in ("visual_style", "editing_style", "presentation_style"):
            value = sample.metadata_json.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
        media_format = sample.metadata_json.get("media_product_type") or sample.metadata_json.get("media_type")
        if isinstance(media_format, str) and media_format.strip():
            media_formats.append(media_format.strip().upper())
    if values:
        return Counter(values).most_common(1)[0][0]
    if not media_formats:
        return "UNKNOWN"
    dominant = Counter(media_formats).most_common(1)[0][0]
    return {
        "IMAGE": "Static image-led",
        "CAROUSEL_ALBUM": "Carousel-led",
        "VIDEO": "Video-led",
        "REELS": "Short-form video-led",
    }.get(dominant, f"{dominant.replace('_', ' ').title()}-led")


def _engagement_pattern(
    accounts: list[CreatorDiscoveryAccount], samples: list[CreatorContentSample],
) -> str:
    followers = max((item.followers for item in accounts if item.followers), default=None)
    rates = []
    for sample in samples:
        denominator = sample.views or followers
        if denominator:
            interactions = sum(value or 0 for value in (sample.likes, sample.comments, sample.shares))
            rates.append(interactions / denominator)
    if not rates:
        return "UNKNOWN"
    return f"mean public engagement rate {statistics.fmean(rates):.2%} across {len(rates)} samples"


def _audience_analysis(
    accounts: list[CreatorDiscoveryAccount], samples: list[CreatorContentSample],
) -> str:
    provided = []
    for account in accounts:
        for key in ("audience", "audience_type", "audience_analysis"):
            value = account.metadata_json.get(key)
            if isinstance(value, str) and value.strip():
                provided.append(value.strip())
    if provided:
        return Counter(provided).most_common(1)[0][0]
    followers = max((item.followers for item in accounts if item.followers is not None), default=None)
    if followers is None:
        return "UNKNOWN"
    return f"public audience size {followers:,}; demographic data unavailable"


def _trend_analysis(samples: list[CreatorContentSample], posting_patterns: str) -> str:
    hashtags = Counter(
        str(tag).strip().casefold()
        for sample in samples for tag in sample.hashtags
        if str(tag).strip()
    )
    recurring = [tag for tag, count in hashtags.most_common(3) if count >= 2]
    parts = [] if posting_patterns == "UNKNOWN" else [posting_patterns]
    if recurring:
        parts.append("recurring topics: " + ", ".join(recurring))
    return "; ".join(parts) or "UNKNOWN"


def _recommendation(main_platform: str, niche: str, content_style: str) -> str:
    if main_platform == "UNKNOWN" or content_style == "UNKNOWN":
        return "INSUFFICIENT_EVIDENCE"
    topic = niche if niche != "UNKNOWN" else "the observed niche"
    return f"Prioritize {content_style.casefold()} for {topic} on {main_platform}."


def _personalization(main_platform: str, niche: str) -> str:
    if main_platform == "UNKNOWN" or niche == "UNKNOWN":
        return "INSUFFICIENT_EVIDENCE"
    return f"Tailor briefs to {niche} audience needs and {main_platform} publishing conventions."


def _campaign_idea(niche: str, content_angle: str) -> str:
    if niche == "UNKNOWN" or content_angle == "UNKNOWN":
        return "INSUFFICIENT_EVIDENCE"
    return f"A {niche} series built around {content_angle.casefold()}."


def _creative_strategy(content_style: str, posting_patterns: str) -> str:
    if content_style == "UNKNOWN":
        return "INSUFFICIENT_EVIDENCE"
    cadence = "Use the observed cadence" if posting_patterns != "UNKNOWN" else "Test a consistent cadence"
    return f"{cadence} with repeatable {content_style.casefold()} formats."


def _community_impact(samples: list[CreatorContentSample]) -> str:
    observed = [item for item in samples if item.comments is not None or item.shares is not None]
    if not observed:
        return "UNKNOWN"
    comments = sum(item.comments or 0 for item in observed)
    shares = sum(item.shares or 0 for item in observed)
    return f"{comments:,} comments and {shares:,} shares observed across {len(observed)} samples"


def _sample_text(samples: list[CreatorContentSample]) -> str:
    return " ".join(f"{item.title or ''} {item.caption or ''}" for item in samples).casefold()


def _content_themes(samples: list[CreatorContentSample]) -> list[str]:
    counts = Counter(
        str(tag).strip().casefold()
        for sample in samples for tag in sample.hashtags
        if str(tag).strip()
    )
    return [tag for tag, _ in counts.most_common(8)]


def _hook_style(samples: list[CreatorContentSample]) -> str:
    openings = [
        (item.caption or item.title or "").strip().splitlines()[0][:180]
        for item in samples if (item.caption or item.title or "").strip()
    ]
    if not openings:
        return "UNKNOWN"
    questions = sum("?" in item for item in openings)
    educational = sum(any(term in item.casefold() for term in ("how to", "tips", "guide", "learn")) for item in openings)
    if questions / len(openings) >= 0.4:
        return "Question-led hooks"
    if educational / len(openings) >= 0.4:
        return "Educational promise hooks"
    return "Statement-led hooks"


def _caption_style(samples: list[CreatorContentSample]) -> str:
    captions = [(item.caption or "").strip() for item in samples if (item.caption or "").strip()]
    if not captions:
        return "UNKNOWN"
    mean_words = statistics.fmean(len(item.split()) for item in captions)
    length = "short" if mean_words < 25 else "medium-length" if mean_words < 80 else "long-form"
    return f"{length} captions; mean {mean_words:.0f} words across {len(captions)} samples"


def _communication_style(mechanisms: list[str], caption_style: str) -> str:
    if mechanisms:
        return f"{', '.join(mechanisms)} delivered through {caption_style.casefold()}"
    return caption_style


def _tone(samples: list[CreatorContentSample]) -> str:
    text = _sample_text(samples)
    if not text:
        return "UNKNOWN"
    if any(term in text for term in ("how to", "tips", "learn", "explained", "tutorial")):
        return "Helpful and instructional"
    if any(term in text for term in ("funny", "comedy", "challenge")):
        return "Playful and entertaining"
    if any(term in text for term in ("buy", "shop", "offer", "discount")):
        return "Commercial and action-oriented"
    return "Informational"


def _personality(mechanisms: list[str]) -> str:
    if "Educational explainers" in mechanisms:
        return "Observed educator persona"
    if "Reviews and comparisons" in mechanisms:
        return "Observed evaluator persona"
    if "Storytelling" in mechanisms:
        return "Observed storyteller persona"
    return "UNKNOWN"


def _brand_identity(niche: str, visual_style: str) -> str:
    parts = [value for value in (niche, visual_style) if value != "UNKNOWN"]
    return " / ".join(parts) if parts else "UNKNOWN"


def _creative_pattern(content_style: str, formats: list[str] | str, hook_style: str) -> str:
    shown_formats = _as_text(formats)
    parts = [value for value in (hook_style, content_style, shown_formats) if value != "UNKNOWN"]
    return " → ".join(parts) if parts else "UNKNOWN"


def _audience_relationship(cta_patterns: list[str] | str, samples: list[CreatorContentSample]) -> str:
    cta = _as_text(cta_patterns)
    comments = sum(item.comments or 0 for item in samples if item.comments is not None)
    if cta != "UNKNOWN" and comments:
        return f"CTA-led relationship with {comments:,} observed comments"
    if comments:
        return f"Comment-driven relationship with {comments:,} observed comments"
    return "UNKNOWN"


def _positioning(niche: str, content_style: str, platform: str) -> str:
    if niche == "UNKNOWN" or content_style == "UNKNOWN":
        return "UNKNOWN"
    channel = f" on {platform}" if platform != "UNKNOWN" else ""
    return f"{niche} creator using {content_style.casefold()}{channel}"


def _success_formula(content_style: str, hook_style: str, cta_patterns: list[str] | str) -> str:
    cta = _as_text(cta_patterns)
    parts = [value for value in (hook_style, content_style, cta) if value != "UNKNOWN"]
    return " + ".join(parts) if parts else "UNKNOWN"


def _audience_type(niche: str, audience_analysis: str) -> str:
    if niche != "UNKNOWN":
        return f"People interested in {niche}"
    return audience_analysis


def _audience_needs(niche: str) -> str:
    return f"Useful, relevant {niche} content" if niche != "UNKNOWN" else "UNKNOWN"


def _audience_problem(niche: str) -> str:
    return f"Finding trusted guidance in {niche}" if niche != "UNKNOWN" else "UNKNOWN"


def _audience_motivation(niche: str) -> str:
    return f"Learn, evaluate, or engage with {niche}" if niche != "UNKNOWN" else "UNKNOWN"


def _audience_questions(samples: list[CreatorContentSample]) -> str:
    questions = []
    for item in samples:
        for sentence in (item.caption or "").replace("\n", " ").split("?")[:-1]:
            candidate = sentence.rsplit(".", 1)[-1].strip()
            if candidate:
                questions.append(candidate + "?")
    return " | ".join(questions[:5]) or "UNKNOWN"


def _brand_suitability(niche: str, content_style: str, engagement: str) -> str:
    if niche == "UNKNOWN" or content_style == "UNKNOWN":
        return "INSUFFICIENT_EVIDENCE"
    suffix = f"; {engagement}" if engagement != "UNKNOWN" else ""
    return f"Suitable for evidence-aligned {niche} partnerships using {content_style.casefold()}{suffix}"


def _mission(niche: str, angle: str) -> str:
    if niche == "UNKNOWN" or angle == "UNKNOWN":
        return "UNKNOWN"
    return f"Deliver {niche} content focused on {angle.casefold()}"


def _differentiation(content_style: str, visual_style: str) -> str:
    parts = [value for value in (content_style, visual_style) if value != "UNKNOWN"]
    return " combined with ".join(parts) if parts else "UNKNOWN"


def _collaboration_opportunities(niche: str, content_style: str) -> str:
    if niche == "UNKNOWN" or content_style == "UNKNOWN":
        return "INSUFFICIENT_EVIDENCE"
    return f"Brands in {niche}; briefs built around {content_style.casefold()}"


def _growth_opportunities(trend: str, posting: str) -> str:
    if trend == "UNKNOWN" and posting == "UNKNOWN":
        return "INSUFFICIENT_EVIDENCE"
    return f"Scale recurring observed themes; {posting.casefold() if posting != 'UNKNOWN' else 'test a consistent cadence'}"


def _brand_partnerships(niche: str) -> str:
    return f"Partnerships whose products and audience align with {niche}" if niche != "UNKNOWN" else "INSUFFICIENT_EVIDENCE"


def _growth_signals(accounts: list[CreatorDiscoveryAccount], samples: list[CreatorContentSample]) -> str:
    followers = max((item.followers for item in accounts if item.followers is not None), default=None)
    if followers is None:
        return "UNKNOWN"
    return f"Current public audience {followers:,}; historical growth unavailable; {len(samples)} recent samples observed"


def _platform_factors(formats: list[str] | str, cta_patterns: list[str] | str) -> str:
    parts = [value for value in (_as_text(formats), _as_text(cta_patterns)) if value != "UNKNOWN"]
    return "; ".join(parts) if parts else "UNKNOWN"


def _campaign_goal(cta_patterns: list[str] | str) -> str:
    cta = _as_text(cta_patterns)
    if cta == "UNKNOWN":
        return "Awareness"
    if "buy" in cta:
        return "Conversion"
    if "visit" in cta:
        return "Traffic"
    return "Engagement and audience growth"


def _cta_type(cta_patterns: list[str] | str) -> str:
    cta = _as_text(cta_patterns)
    return "UNKNOWN" if cta == "UNKNOWN" else f"Observed {cta} CTA"


def _copy_framework(samples: list[CreatorContentSample]) -> str:
    text = _sample_text(samples)
    if not text:
        return "UNKNOWN"
    if any(term in text for term in ("problem", "solution", "because")):
        return "Observed problem-solution structure"
    if any(term in text for term in ("before", "after", "result")):
        return "Observed before-after structure"
    return "UNKNOWN"


def _persuasion_elements(samples: list[CreatorContentSample]) -> str:
    text = _sample_text(samples)
    found = [label for label, terms in (
        ("social proof", ("review", "results", "tested")),
        ("scarcity", ("limited", "today only", "last chance")),
        ("value", ("tips", "how to", "guide")),
    ) if any(term in text for term in terms)]
    return ", ".join(found) or "UNKNOWN"


def _emotional_trigger(samples: list[CreatorContentSample]) -> str:
    text = _sample_text(samples)
    if any(term in text for term in ("secret", "surprise", "never")):
        return "Curiosity"
    if any(term in text for term in ("problem", "mistake", "avoid")):
        return "Problem avoidance"
    if any(term in text for term in ("result", "transform", "before", "after")):
        return "Transformation"
    return "UNKNOWN"


def _value_promise(niche: str, angle: str) -> str:
    if niche == "UNKNOWN" or angle == "UNKNOWN":
        return "UNKNOWN"
    return f"Help the audience with {niche} through {angle.casefold()}"


def _recommendation_reasoning(sample_count: int, content_style: str, engagement: str) -> str:
    if not sample_count or content_style == "UNKNOWN":
        return "INSUFFICIENT_EVIDENCE"
    evidence = f"{sample_count} stored samples support the observed {content_style.casefold()} pattern"
    return f"{evidence}; {engagement}" if engagement != "UNKNOWN" else evidence

