"""Normalize provider output using rule thresholds, evidence, and value contracts."""

from typing import Any

from backend.analyzers.engine import NOT_APPLICABLE, UNKNOWN
from backend.core.enums import AnalysisResultStatus
from backend.schemas.analysis import EngineResultDraft, NormalizedAnalysisResult
from backend.schemas.analysis_rules import ExtractionRule


class AnalysisResultNormalizer:
    def normalize(
        self,
        *,
        content_id: int,
        rule: ExtractionRule,
        engine: str,
        draft: EngineResultDraft,
        engine_failed: bool = False,
    ) -> NormalizedAnalysisResult:
        value = draft.value
        valid_value = _matches_output_type(value, rule.output_type)
        is_sentinel = isinstance(value, str) and value in {
            UNKNOWN,
            NOT_APPLICABLE,
        }
        if rule.allowed_values is not None and not is_sentinel:
            valid_value = valid_value and value in rule.allowed_values
        if not valid_value:
            value = UNKNOWN

        is_unknown = value == UNKNOWN
        evidence_missing = rule.evidence_required and not draft.evidence
        low_confidence = draft.confidence < rule.confidence_threshold
        accepted = not (
            engine_failed or is_unknown or evidence_missing or low_confidence
        )
        manual_review = (
            not accepted
            and value != NOT_APPLICABLE
            and (
                engine_failed
                or is_unknown
                or evidence_missing
                or rule.manual_review_on_low_confidence
            )
        )

        if engine_failed:
            status = AnalysisResultStatus.FAILED
        elif accepted or value == NOT_APPLICABLE:
            status = AnalysisResultStatus.ACCEPTED
            accepted = True
            manual_review = False
            low_confidence = False
        elif low_confidence:
            status = AnalysisResultStatus.LOW_CONFIDENCE
        else:
            status = AnalysisResultStatus.MANUAL_REVIEW

        return NormalizedAnalysisResult(
            content_id=content_id,
            field=rule.field,
            level=rule.analysis_level,
            value=value,
            start_ms=draft.start_ms,
            end_ms=draft.end_ms,
            confidence=draft.confidence,
            evidence=draft.evidence,
            source=draft.source,
            engine=engine,
            rule_id=rule.rule_id,
            status=status,
            accepted=accepted,
            low_confidence=low_confidence,
            manual_review=manual_review,
            target_ref=draft.target_ref,
        )

    def not_applicable(
        self,
        *,
        content_id: int,
        rule: ExtractionRule,
    ) -> NormalizedAnalysisResult:
        return self.normalize(
            content_id=content_id,
            rule=rule,
            engine=rule.engine,
            draft=EngineResultDraft(
                rule_id=rule.rule_id,
                value=NOT_APPLICABLE,
                confidence=1,
                evidence={"reason": "rule_not_applicable_to_content_modality"},
                source="content_router",
            ),
        )


def _matches_output_type(value: Any, output_type: str) -> bool:
    if isinstance(value, str) and value in {UNKNOWN, NOT_APPLICABLE}:
        return True
    match output_type:
        case "string":
            return isinstance(value, str)
        case "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        case "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        case "boolean":
            return isinstance(value, bool)
        case "list":
            return isinstance(value, list)
        case "object":
            return isinstance(value, dict)
        case _:
            return True
