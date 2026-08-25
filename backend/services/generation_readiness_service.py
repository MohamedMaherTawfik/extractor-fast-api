"""Small facade for READY / NOT_READY / HUMAN_REVIEW decisions."""

from sqlalchemy.orm import Session

from backend.schemas.rules import RecipeRuleRequest
from backend.services.recipe_rule_validation_service import RecipeRuleValidationService


class GenerationReadinessService:
    def __init__(self, session: Session) -> None:
        self.validation = RecipeRuleValidationService(session)

    def check_generation_readiness(self, request: RecipeRuleRequest):
        evaluation = self.validation.validate(request)
        return {
            "status": evaluation.status,
            "blockers": evaluation.blockers,
            "warnings": evaluation.warnings,
            "missing_fields": evaluation.missing_fields,
            "missing_evidence": evaluation.missing_evidence,
            "conflicts": evaluation.conflicts,
        }
