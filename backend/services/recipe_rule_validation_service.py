"""Validate and normalize immutable Recipe versions through active rules."""

from copy import deepcopy

from sqlalchemy.orm import Session

from backend.core.enums import RuleAction, RuleStage
from backend.core.exceptions import NotFoundError
from backend.repositories.recipe_repository import RecipeRepository
from backend.schemas.rules import NormalizedRecipeResponse, RecipeRuleRequest, RuleEvaluationRequest
from backend.services.rule_evaluation_service import RuleEvaluationService


class RecipeRuleValidationService:
    def __init__(self, session: Session) -> None:
        self.recipes = RecipeRepository(session)
        self.evaluator = RuleEvaluationService(session)

    def validate(self, request: RecipeRuleRequest):
        recipe, version = self._resolve(request)
        context = self._context(recipe, version, request.context)
        return self.evaluator.evaluate(RuleEvaluationRequest(
            context=context, rule_sets=request.rule_sets, stage=RuleStage.POST_RECIPE,
            dry_run=request.dry_run,
        ))

    def normalize(self, request: RecipeRuleRequest) -> NormalizedRecipeResponse:
        recipe, version = self._resolve(request)
        original = deepcopy(version.payload)
        normalized = deepcopy(version.payload)
        evaluation = self.validate(request)
        defaults: dict = {}
        constraints: dict = {}
        removed: list[str] = []
        for result in evaluation.results:
            if not result.affected_fields:
                continue
            target = result.affected_fields[0]
            relative = target.removeprefix("recipe.").removeprefix("payload.")
            if result.action is RuleAction.SET_DEFAULT and self._get(normalized, relative) is None:
                self._set(normalized, relative, result.suggested_value)
                defaults[relative] = result.suggested_value
            elif result.action is RuleAction.SET_CONSTRAINT:
                constraints[relative] = result.suggested_value
            elif result.action is RuleAction.OMIT_FIELD and self._delete(normalized, relative):
                removed.append(relative)
        return NormalizedRecipeResponse(
            recipe_id=recipe.id, recipe_uid=recipe.recipe_uid, recipe_version=version.version,
            original_payload=original, normalized_payload=normalized, applied_defaults=defaults,
            removed_fields=removed, added_constraints=constraints, evaluation=evaluation,
        )

    def _resolve(self, request):
        recipe = self.recipes.get(request.recipe_id)
        if recipe is None:
            raise NotFoundError(f"Recipe {request.recipe_id} was not found")
        number = request.recipe_version or recipe.current_version
        version = next((item for item in recipe.versions if item.version == number), None)
        if version is None:
            raise NotFoundError(f"Recipe version {number} was not found")
        return recipe, version

    @staticmethod
    def _context(recipe, version, supplied):
        context = deepcopy(supplied)
        recipe_context = deepcopy(version.payload)
        recipe_context["constraints"] = deepcopy(version.constraints)
        recipe_context.update({
            "id": recipe.id, "uid": recipe.recipe_uid, "version": version.version,
            "content_type": recipe.content_type, "platform": recipe.target_platform,
            "language": recipe.language,
        })
        context["recipe"] = recipe_context
        context.setdefault("recipe_id", recipe.id)
        context.setdefault("recipe_version", version.version)
        context.setdefault("content_type", recipe.content_type)
        if recipe.target_platform:
            context.setdefault("platform", recipe.target_platform)
        if recipe.language:
            context.setdefault("language", recipe.language)
        return context

    @staticmethod
    def _get(payload, path):
        current = payload
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    @staticmethod
    def _set(payload, path, value):
        current = payload
        parts = path.split(".")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value

    @staticmethod
    def _delete(payload, path):
        current = payload
        parts = path.split(".")
        for part in parts[:-1]:
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]
        return isinstance(current, dict) and current.pop(parts[-1], None) is not None
