"""Load and validate extraction rules against the taxonomy dictionary."""

from dataclasses import dataclass

from backend.core.exceptions import AnalysisRuleError, RuleLoadError
from backend.rules_engine.engine import RuleType, RulesEngine
from backend.schemas.analysis_rules import (
    ExtractionRule,
    ExtractionRulesDocument,
    TaxonomyDocument,
)


@dataclass(frozen=True)
class AnalysisRuleSet:
    rules_version: str
    taxonomy_version: str
    rules: tuple[ExtractionRule, ...]

    def select(self, rule_ids: list[str] | None = None) -> tuple[ExtractionRule, ...]:
        if not rule_ids:
            return self.rules
        requested = set(rule_ids)
        selected = tuple(rule for rule in self.rules if rule.rule_id in requested)
        missing = requested - {rule.rule_id for rule in selected}
        if missing:
            raise AnalysisRuleError(
                f"Unknown analysis rule IDs: {', '.join(sorted(missing))}"
            )
        return selected


class AnalysisRuleCatalog:
    def __init__(self, loader: RulesEngine | None = None) -> None:
        self._loader = loader or RulesEngine()

    def load(self, rules_file: str, taxonomy_file: str) -> AnalysisRuleSet:
        try:
            rules_document = ExtractionRulesDocument.model_validate(
                self._loader.load(RuleType.EXTRACTION, rules_file)
            )
            taxonomy = TaxonomyDocument.model_validate(
                self._loader.load(RuleType.TAXONOMY, taxonomy_file)
            )
        except (RuleLoadError, ValueError) as exc:
            raise AnalysisRuleError("Analysis rule documents are invalid") from exc

        resolved: list[ExtractionRule] = []
        for rule in rules_document.rules:
            if rule.field in taxonomy.prohibited_analysis_fields:
                raise AnalysisRuleError(
                    f"Rule {rule.rule_id} requests a prohibited analysis field"
                )
            if rule.field in taxonomy.collector_only_fields:
                raise AnalysisRuleError(
                    f"Rule {rule.rule_id} requests a collector-only metric"
                )
            taxonomy_field = taxonomy.fields.get(rule.field)
            if taxonomy_field is None:
                raise AnalysisRuleError(
                    f"Rule {rule.rule_id} references unknown field {rule.field}"
                )
            if rule.allowed_values is None and taxonomy_field.allowed_values is not None:
                rule = rule.model_copy(
                    update={"allowed_values": taxonomy_field.allowed_values}
                )
            resolved.append(rule)
        return AnalysisRuleSet(
            rules_version=rules_document.version,
            taxonomy_version=taxonomy.version,
            rules=tuple(resolved),
        )
