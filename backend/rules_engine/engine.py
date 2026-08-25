"""External rule document loader.

This module loads configuration only. It intentionally contains no product,
sales, extraction, or generation decisions.
"""

import json
from enum import StrEnum
from pathlib import Path
from typing import Any, TYPE_CHECKING

import yaml

from backend.core.exceptions import RuleLoadError
from backend.core.paths import paths
from backend.core.exceptions import RuleValidationError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class RuleType(StrEnum):
    TAXONOMY = "taxonomy"
    EXTRACTION = "extraction"
    GENERATION = "generation"
    SALES = "sales"


class RulesEngine:
    """Global rules facade while preserving the original document loader."""

    def __init__(self, session: "Session | None" = None) -> None:
        self._session = session
        self._roots = {
            RuleType.TAXONOMY: paths.taxonomy,
            RuleType.EXTRACTION: paths.rules,
            RuleType.GENERATION: paths.rules,
            RuleType.SALES: paths.rules,
        }

    def load(self, rule_type: RuleType, relative_file: str | Path) -> Any:
        try:
            source = paths.resolve_under(self._roots[rule_type], relative_file)
        except (KeyError, ValueError) as exc:
            raise RuleLoadError("Rule path is outside its configured directory") from exc

        if source.suffix.lower() not in {".yaml", ".yml", ".json"}:
            raise RuleLoadError("Rules must use YAML or JSON")
        if not source.is_file():
            raise RuleLoadError(f"Rule file does not exist: {relative_file}")

        try:
            text = source.read_text(encoding="utf-8")
            if source.suffix.lower() == ".json":
                return json.loads(text)
            return yaml.safe_load(text)
        except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
            raise RuleLoadError(f"Unable to load rule file: {relative_file}") from exc

    def evaluate(self, context: dict[str, Any], rule_sets: list[str] | None = None, **options):
        from backend.schemas.rules import RuleEvaluationRequest
        from backend.services.rule_evaluation_service import RuleEvaluationService
        return RuleEvaluationService(self._require_session()).evaluate(
            RuleEvaluationRequest(context=context, rule_sets=rule_sets, **options)
        )

    def validate_recipe(self, recipe: int | str, context: dict[str, Any], **options):
        from backend.schemas.rules import RecipeRuleRequest
        from backend.services.recipe_rule_validation_service import RecipeRuleValidationService
        return RecipeRuleValidationService(self._require_session()).validate(
            RecipeRuleRequest(recipe_id=recipe, context=context, **options)
        )

    def build_generation_contract(self, recipe: int | str, context: dict[str, Any], **options):
        from backend.schemas.rules import GenerationContractBuildRequest
        from backend.services.generation_contract_service import GenerationContractService
        return GenerationContractService(self._require_session()).build(
            GenerationContractBuildRequest(recipe_id=recipe, context=context, **options)
        )

    def explain(self, evaluation_id: int | str):
        from backend.services.rule_evaluation_service import RuleEvaluationService
        return RuleEvaluationService(self._require_session()).explain(evaluation_id)

    def _require_session(self):
        if self._session is None:
            raise RuleValidationError("A database session is required for rule evaluation")
        return self._session
