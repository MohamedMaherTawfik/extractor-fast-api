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
    model_version = "creator-evidence-rules-1.0.0"

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
            "start_year": start_year,
            "start_year_confidence": start_confidence,
            "start_year_source": start_source,
            "analysis_status": "COMPLETED" if evidence else "INSUFFICIENT_EVIDENCE",
            "confidence": round(statistics.fmean(confidence_parts), 3) if confidence_parts else 0.0,
            "evidence_references": taxonomy_evidence + mechanism_evidence + platform_evidence + kpi_evidence,
            "details": {
                "format_patterns": _format_patterns(samples),
                "presentation_style": "UNKNOWN",
                "editing_style": "UNKNOWN",
                "storytelling_style": "Storytelling" if "Storytelling" in mechanisms else "UNKNOWN",
                "educational_entertainment_mix": _education_mix(samples),
                "commercial_behavior": _commercial_behavior(samples),
                "cta_patterns": _cta_patterns(samples),
                "posting_patterns": _posting_patterns(samples),
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

