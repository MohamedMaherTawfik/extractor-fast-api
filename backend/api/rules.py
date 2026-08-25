"""Local API for rule administration, evaluation, explanation, and contracts."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.core.exceptions import NotFoundError
from backend.db.session import get_db
from backend.repositories.rule_repository import RuleRepository
from backend.schemas.rules import (
    GenerationContractBuildRequest, GenerationContractResponse, HumanReviewDecision,
    MasterControlPreviewRequest, MasterControlPreviewResponse, NormalizedRecipeResponse,
    RecipeRuleRequest, RuleActivationRequest, RuleCreate, RuleEvaluationRequest,
    RuleEvaluationResponse, RuleOverrideCreate, RuleResponse, RuleSetCreate,
    RuleSetResponse, RuleVersionCreate, RuleVersionResponse,
)
from backend.services.generation_contract_service import GenerationContractService
from backend.services.generation_readiness_service import GenerationReadinessService
from backend.services.recipe_rule_validation_service import RecipeRuleValidationService
from backend.services.rule_evaluation_service import RuleEvaluationService
from backend.services.rule_import_service import MasterControlImportService
from backend.services.rule_registry_service import RuleRegistryService


router = APIRouter(tags=["rules"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post("/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(request: RuleCreate, session: DatabaseSession):
    return RuleRegistryService(session).create_rule(request)


@router.get("/rules", response_model=list[RuleResponse])
def list_rules(session: DatabaseSession, domain: str | None = None, rule_status: str | None = Query(None, alias="status"), limit: int = Query(1000, ge=1, le=5000)):
    return RuleRegistryService(session).list_rules(domain=domain, status=rule_status, limit=limit)


@router.get("/rules/{rule_id}", response_model=RuleResponse)
def get_rule(rule_id: str, session: DatabaseSession):
    return RuleRegistryService(session).get_rule(rule_id)


@router.post("/rules/{rule_id}/versions", response_model=RuleVersionResponse, status_code=status.HTTP_201_CREATED)
def create_rule_version(rule_id: str, request: RuleVersionCreate, session: DatabaseSession):
    return RuleRegistryService(session).add_version(rule_id, request)


@router.post("/rules/{rule_id}/versions/{version}/activate", response_model=RuleVersionResponse)
def activate_rule(rule_id: str, version: int, request: RuleActivationRequest, session: DatabaseSession):
    return RuleRegistryService(session).activate(rule_id, version, request)


@router.post("/rules/{rule_id}/versions/{version}/retire", response_model=RuleVersionResponse)
def retire_rule(rule_id: str, version: int, session: DatabaseSession):
    return RuleRegistryService(session).retire(rule_id, version)


def _set_response(item) -> RuleSetResponse:
    return RuleSetResponse.model_validate({
        **{key: getattr(item, key) for key in ("id", "set_uid", "set_code", "name", "version", "priority", "activation_criteria", "status", "created_at")},
        "rule_codes": [member.rule.rule_code for member in item.members],
    })


@router.post("/rule-sets", response_model=RuleSetResponse, status_code=status.HTTP_201_CREATED)
def create_rule_set(request: RuleSetCreate, session: DatabaseSession):
    return _set_response(RuleRegistryService(session).create_rule_set(request))


@router.get("/rule-sets", response_model=list[RuleSetResponse])
def list_rule_sets(session: DatabaseSession):
    return [_set_response(item) for item in RuleRepository(session).list_sets()]


@router.get("/rule-sets/{set_id}", response_model=RuleSetResponse)
def get_rule_set(set_id: str, session: DatabaseSession):
    item = RuleRepository(session).get_set(set_id)
    if item is None:
        raise NotFoundError(f"Rule set {set_id} was not found")
    return _set_response(item)


@router.post("/rules/evaluate", response_model=RuleEvaluationResponse)
def evaluate_rules(request: RuleEvaluationRequest, session: DatabaseSession):
    return RuleEvaluationService(session).evaluate(request)


@router.post("/rules/validate-recipe", response_model=RuleEvaluationResponse)
def validate_recipe(request: RecipeRuleRequest, session: DatabaseSession):
    return RecipeRuleValidationService(session).validate(request)


@router.post("/rules/normalize-recipe", response_model=NormalizedRecipeResponse)
def normalize_recipe(request: RecipeRuleRequest, session: DatabaseSession):
    return RecipeRuleValidationService(session).normalize(request)


@router.get("/rules/evaluations/{evaluation_id}")
def get_evaluation(evaluation_id: str, session: DatabaseSession):
    return RuleEvaluationService(session).explain(evaluation_id)


@router.get("/rules/evaluations/{evaluation_id}/explain")
def explain_evaluation(evaluation_id: str, session: DatabaseSession):
    return RuleEvaluationService(session).explain(evaluation_id)


@router.post("/generation-contracts/build", response_model=GenerationContractResponse, status_code=status.HTTP_201_CREATED)
def build_generation_contract(request: GenerationContractBuildRequest, session: DatabaseSession):
    return GenerationContractService(session).build(request)


@router.post("/generation-readiness/check")
def check_generation_readiness(request: RecipeRuleRequest, session: DatabaseSession):
    return GenerationReadinessService(session).check_generation_readiness(request)


@router.get("/generation-contracts/{contract_id}", response_model=GenerationContractResponse)
def get_generation_contract(contract_id: str, session: DatabaseSession, version: int | None = Query(None, ge=1)):
    return GenerationContractService(session).get(contract_id, version)


@router.post("/rule-overrides", status_code=status.HTTP_201_CREATED)
def create_override(request: RuleOverrideCreate, session: DatabaseSession):
    item = RuleRegistryService(session).create_override(request)
    return {"override_uid": item.override_uid, "rule_id": item.rule_id, "scope": item.scope, "reason": item.reason, "effective_from": item.effective_from, "effective_to": item.effective_to}


@router.post("/human-reviews/{review_id}/decision")
def decide_review(review_id: str, request: HumanReviewDecision, session: DatabaseSession):
    item = RuleRepository(session).get_review(review_id)
    if item is None:
        raise NotFoundError(f"Human review {review_id} was not found")
    item.status = request.status
    item.decision = request.decision
    item.decided_by = request.decided_by
    item.decided_at = datetime.now(UTC)
    RuleRepository(session).audit(action="HUMAN_APPROVAL", entity_type="human_review", entity_id=item.review_uid, actor=request.decided_by, details={"status": request.status.value, "decision": request.decision})
    return {"review_uid": item.review_uid, "status": item.status, "decision": item.decision, "decided_by": item.decided_by}


@router.post("/rule-imports/master-controls", response_model=MasterControlPreviewResponse)
def import_master_controls(request: MasterControlPreviewRequest, session: DatabaseSession):
    return MasterControlImportService(session).import_controls(
        request.relative_path, sheet_name=request.sheet_name, dry_run=request.dry_run,
    )
