"""Evidence-preserving deterministic creator identity matching."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlsplit

from backend.creator_discovery.config import MatchingConfig, get_creator_discovery_config
from backend.creator_discovery.normalization import normalize_creator_name, normalize_username
from backend.schemas.creator_discovery import MatchClassification


@dataclass(frozen=True, slots=True)
class MatchSignal:
    signal: str
    score: float
    weight: float
    contribution: float
    evidence: dict[str, Any]


@dataclass(frozen=True, slots=True)
class MatchResult:
    confidence: float
    classification: MatchClassification
    signals: list[MatchSignal]


class IdentityMatcher:
    def __init__(self, config: MatchingConfig | None = None) -> None:
        self.config = config or get_creator_discovery_config().matching

    def match(self, input_value: str, candidate: dict[str, Any], *, direct_url: bool = False) -> MatchResult:
        signals: list[MatchSignal] = []
        if direct_url:
            self._add(signals, "direct_url", 1.0, {"operator_supplied": True})
        input_name = normalize_creator_name(input_value) if not direct_url else ""
        display_name = normalize_creator_name(candidate.get("display_name") or "")
        if input_name and display_name:
            ratio = SequenceMatcher(None, input_name, display_name).ratio()
            self._add(signals, "normalized_name", ratio, {"input": input_name, "candidate": display_name})
        username = normalize_username(candidate.get("username"))
        if input_name and username:
            ratio = SequenceMatcher(None, input_name.replace(" ", ""), username.replace("_", "").replace(".", "")).ratio()
            self._add(signals, "username_similarity", ratio, {"input": input_name, "username": username})
        bio = normalize_creator_name(candidate.get("public_bio") or "")
        if input_name and bio:
            tokens = set(input_name.split())
            score = len(tokens & set(bio.split())) / max(1, len(tokens))
            self._add(signals, "bio_similarity", score, {"matched_tokens": sorted(tokens & set(bio.split()))})
        if input_name and display_name and username:
            score = SequenceMatcher(None, display_name.replace(" ", ""), username.replace("_", "").replace(".", "")).ratio()
            self._add(signals, "profile_naming_consistency", score, {"display_name": display_name, "username": username})
        linked_urls = set(candidate.get("linked_social_urls") or [])
        reference_urls = set(candidate.get("reference_social_urls") or [])
        shared_urls = sorted(linked_urls & reference_urls)
        if shared_urls:
            self._add(signals, "linked_social_urls", 1.0, {"shared_urls": shared_urls})
        website = candidate.get("website")
        reference_website = candidate.get("reference_website")
        domain = urlsplit(website).hostname if website else None
        reference_domain = urlsplit(reference_website).hostname if reference_website else None
        if domain and reference_domain:
            self._add(signals, "website_domain", float(domain.casefold() == reference_domain.casefold()), {"domain": domain, "reference_domain": reference_domain})
        topics = {str(value).casefold() for value in candidate.get("content_topics") or []}
        reference_topics = {str(value).casefold() for value in candidate.get("reference_content_topics") or []}
        if topics and reference_topics:
            self._add(signals, "content_topic_similarity", len(topics & reference_topics) / len(topics | reference_topics), {"shared_topics": sorted(topics & reference_topics)})
        location = normalize_creator_name(candidate.get("location") or "")
        reference_location = normalize_creator_name(candidate.get("reference_location") or "")
        if location and reference_location:
            self._add(signals, "public_location", float(location == reference_location), {"location": location, "reference_location": reference_location})
        brands = {normalize_creator_name(str(value)) for value in candidate.get("brand_names") or []}
        reference_brands = {normalize_creator_name(str(value)) for value in candidate.get("reference_brand_names") or []}
        if brands and reference_brands:
            self._add(signals, "brand_names", len(brands & reference_brands) / len(brands | reference_brands), {"shared_brands": sorted(brands & reference_brands)})
        raw = sum(signal.contribution for signal in signals)
        if direct_url:
            available = float(self.config.weights["direct_url"])
        else:
            available = sum(float(self.config.weights[name]) for name in ("normalized_name", "username_similarity", "bio_similarity"))
            available += sum(signal.weight for signal in signals if signal.signal not in {"normalized_name", "username_similarity", "bio_similarity", "profile_naming_consistency"})
        confidence = round(min(100.0, (raw / max(available, 1.0)) * 100), 2)
        if direct_url:
            confidence = max(confidence, 95.0)
        return MatchResult(confidence, self.classify(confidence), signals)

    def classify(self, confidence: float) -> MatchClassification:
        thresholds = self.config.thresholds
        if confidence >= thresholds["confirmed"]:
            return MatchClassification.CONFIRMED
        if confidence >= thresholds["high_confidence"]:
            return MatchClassification.HIGH_CONFIDENCE
        if confidence >= thresholds["possible"]:
            return MatchClassification.POSSIBLE
        if confidence >= thresholds["review_required"]:
            return MatchClassification.REVIEW_REQUIRED
        return MatchClassification.REJECTED

    def _add(self, signals: list[MatchSignal], name: str, score: float, evidence: dict[str, Any]) -> None:
        weight = float(self.config.weights.get(name, 0))
        normalized = max(0.0, min(1.0, score))
        signals.append(MatchSignal(name, normalized, weight, normalized * weight, evidence))
