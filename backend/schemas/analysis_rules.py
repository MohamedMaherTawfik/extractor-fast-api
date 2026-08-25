"""Validated, data-driven taxonomy and extraction-rule documents."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from backend.core.enums import AnalysisLevel, AnalysisModality


class TaxonomyField(BaseModel):
    description: str | None = None
    allowed_values: list[Any] | None = None


class TaxonomyDocument(BaseModel):
    version: str = Field(min_length=1, max_length=100)
    fields: dict[str, TaxonomyField]
    prohibited_analysis_fields: set[str] = Field(default_factory=set)
    collector_only_fields: set[str] = Field(default_factory=set)


class ExtractionRule(BaseModel):
    rule_id: str = Field(min_length=1, max_length=100)
    field: str = Field(min_length=1, max_length=150)
    applies_to: set[AnalysisModality | str]
    analysis_level: AnalysisLevel = AnalysisLevel.CONTENT
    source: str = Field(min_length=1, max_length=250)
    method: str = Field(min_length=1, max_length=100)
    engine: str = Field(min_length=1, max_length=100)
    allowed_values: list[Any] | None = None
    output_type: str = Field(default="string", min_length=1, max_length=50)
    required: bool = False
    confidence_threshold: float = Field(default=0.7, ge=0, le=1)
    evidence_required: bool = True
    manual_review_on_low_confidence: bool = True

    @field_validator("applies_to")
    @classmethod
    def applies_to_cannot_be_empty(
        cls,
        value: set[AnalysisModality | str],
    ) -> set[AnalysisModality | str]:
        if not value:
            raise ValueError("applies_to cannot be empty")
        return value

    def applies_to_modalities(self, modalities: set[AnalysisModality]) -> bool:
        values = {
            item.value if isinstance(item, AnalysisModality) else str(item)
            for item in self.applies_to
        }
        return "all" in values or bool(values & {item.value for item in modalities})


class ExtractionRulesDocument(BaseModel):
    version: str = Field(min_length=1, max_length=100)
    rules: list[ExtractionRule]

    @field_validator("rules")
    @classmethod
    def rule_ids_are_unique(cls, rules: list[ExtractionRule]) -> list[ExtractionRule]:
        ids = [rule.rule_id for rule in rules]
        if len(ids) != len(set(ids)):
            raise ValueError("Extraction rule IDs must be unique")
        return rules
