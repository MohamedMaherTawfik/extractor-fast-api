"""Replaceable analysis-provider contracts and evidence-only local providers."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import date, datetime
from enum import Enum
from typing import Any, ClassVar

from backend.db.models.content_item import ContentItem
from backend.schemas.analysis import EngineResultDraft
from backend.schemas.analysis_rules import ExtractionRule


UNKNOWN = "UNKNOWN"
NOT_APPLICABLE = "NOT_APPLICABLE"


class AnalysisEngine(ABC):
    """Provider interface replaceable by local, external, or fine-tuned adapters."""

    name: ClassVar[str]
    version: ClassVar[str]

    @abstractmethod
    def analyze(
        self,
        content: ContentItem,
        rules: Iterable[ExtractionRule],
    ) -> list[EngineResultDraft]:
        """Return only observed results; providers must not invent missing values."""


class MetadataEngine(AnalysisEngine):
    name = "metadata"
    version = "local-metadata-1"

    def analyze(
        self,
        content: ContentItem,
        rules: Iterable[ExtractionRule],
    ) -> list[EngineResultDraft]:
        results = []
        for rule in rules:
            if rule.method != "content_field":
                results.append(_unknown(rule.rule_id, "canonical_metadata"))
                continue
            value = _read_path(content, rule.source)
            if value is None:
                results.append(_unknown(rule.rule_id, "canonical_metadata"))
                continue
            normalized = _json_value(value)
            results.append(
                EngineResultDraft(
                    rule_id=rule.rule_id,
                    value=normalized,
                    confidence=1,
                    evidence={"field": rule.source, "observed_value": normalized},
                    source="canonical_metadata",
                )
            )
        return results


class ObservationEngine(AnalysisEngine):
    """Consume precomputed observable evidence supplied by a replaceable provider."""

    def __init__(self, name: str, version: str = "embedded-evidence-1") -> None:
        self.name = name
        self.version = version

    def analyze(
        self,
        content: ContentItem,
        rules: Iterable[ExtractionRule],
    ) -> list[EngineResultDraft]:
        metadata = content.raw_metadata or {}
        observations = metadata.get("analysis_observations", {})
        if not isinstance(observations, dict):
            observations = {}
        results = []
        for rule in rules:
            if rule.method != "observation":
                results.append(_unknown(rule.rule_id, self.name))
                continue
            observation = _read_path(observations, rule.source)
            if not isinstance(observation, dict) or "value" not in observation:
                results.append(_unknown(rule.rule_id, self.name))
                continue
            results.append(
                EngineResultDraft(
                    rule_id=rule.rule_id,
                    value=_json_value(observation["value"]),
                    confidence=observation.get("confidence", 0),
                    evidence=observation.get("evidence"),
                    source=observation.get("source", self.name),
                    start_ms=observation.get("start_ms"),
                    end_ms=observation.get("end_ms"),
                    target_ref=observation.get("target_ref"),
                )
            )
        return results


def _unknown(rule_id: str, source: str) -> EngineResultDraft:
    return EngineResultDraft(
        rule_id=rule_id,
        value=UNKNOWN,
        confidence=0,
        evidence=None,
        source=source,
    )


def _read_path(value: Any, path: str) -> Any:
    current = value
    for component in path.split("."):
        if isinstance(current, dict):
            current = current.get(component)
        else:
            current = getattr(current, component, None)
        if current is None:
            return None
    return current


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, tuple):
        return list(value)
    return value
