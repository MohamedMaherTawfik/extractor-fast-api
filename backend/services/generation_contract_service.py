"""Build immutable, versioned generation requirements without generating media."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.core.enums import RuleHardness, RuleStage
from backend.core.exceptions import NotFoundError
from backend.repositories.rule_repository import RuleRepository
from backend.schemas.rules import GenerationContractBuildRequest, GenerationContractResponse
from backend.services.recipe_rule_validation_service import RecipeRuleValidationService
from backend.schemas.rules import RuleEvaluationRequest
from backend.services.rule_evaluation_service import RuleEvaluationService


class GenerationContractService:
    DOMAIN_BUCKETS = {
        "accessibility": "accessibility_requirements", "rights": "rights_requirements",
        "technical": "technical_requirements", "copy": "copy_requirements",
        "visual": "visual_requirements", "audio": "audio_requirements",
        "seo": "copy_requirements",
        "qa": "qa_requirements", "brand": "visual_requirements",
        "character": "forbidden_changes", "factual": "required_evidence",
        "facts": "required_evidence", "ai_safety": "model_capability_requirements",
    }

    def __init__(self, session: Session) -> None:
        self.session = session
        self.rules = RuleRepository(session)
        self.recipes = RecipeRuleValidationService(session)

    def build(self, request: GenerationContractBuildRequest) -> GenerationContractResponse:
        recipe, version = self.recipes._resolve(request)
        normalized = self.recipes.normalize(request)
        generation_context = self.recipes._context(recipe, version, request.context)
        generation_context["recipe"] = normalized.normalized_payload | {
            "constraints": version.constraints, "id": recipe.id, "uid": recipe.recipe_uid,
            "version": version.version,
        }
        evaluation = RuleEvaluationService(self.session).evaluate(RuleEvaluationRequest(
            context=generation_context, rule_sets=request.rule_sets,
            stage=RuleStage.PRE_GENERATION, dry_run=request.dry_run,
        ))
        normalized.evaluation = evaluation
        payload = self._payload(recipe, version, request.context, normalized)
        if request.dry_run:
            return GenerationContractResponse(
                contract_uid=request.contract_uid or f"CONTRACT_DRY_{evaluation.context_hash[:16]}",
                version=1, status=evaluation.status, recipe_id=recipe.id,
                recipe_version=version.version, context_hash=evaluation.context_hash,
                rule_registry_version=evaluation.registry_version, payload=payload,
                evaluation_uid=evaluation.evaluation_uid, created_at=datetime.now(UTC),
            )
        run = self.rules.get_evaluation(evaluation.evaluation_uid)
        if run is None:
            raise RuntimeError("Persisted evaluation was not found")
        contract = self.rules.get_contract(request.contract_uid) if request.contract_uid else None
        if request.contract_uid and contract is None:
            raise NotFoundError(f"Generation contract {request.contract_uid} was not found")
        if contract is None:
            contract = self.rules.create_contract(
                contract_uid=f"GCON_{uuid4().hex}", recipe_id=recipe.id, current_version=1
            )
            next_version = 1
        else:
            if contract.recipe_id != recipe.id:
                raise ValueError("A generation contract cannot change its recipe identity")
            next_version = contract.current_version + 1
        stored = self.rules.add_contract_version(
            contract, version=next_version, recipe_version=version.version,
            context_hash=evaluation.context_hash, rule_registry_version=evaluation.registry_version,
            status=evaluation.status.value, payload=payload, evaluation_id=run.id,
        )
        return self._response(contract, stored, evaluation.evaluation_uid)

    def get(self, identifier: int | str, version_number: int | None = None):
        contract = self.rules.get_contract(identifier)
        if contract is None:
            raise NotFoundError(f"Generation contract {identifier} was not found")
        number = version_number or contract.current_version
        version = next((item for item in contract.versions if item.version == number), None)
        if version is None:
            raise NotFoundError(f"Generation contract version {number} was not found")
        run = self.rules.get_evaluation(version.evaluation_id)
        return self._response(contract, version, run.evaluation_uid if run else "")

    def _payload(self, recipe, version, context, normalized):
        buckets = {
            "required_controls": [], "hard_constraints": [], "soft_constraints": [],
            "forbidden_changes": [], "required_evidence": [], "accessibility_requirements": [],
            "rights_requirements": [], "technical_requirements": [], "copy_requirements": [],
            "visual_requirements": [], "audio_requirements": [], "qa_requirements": [],
            "model_capability_requirements": [], "human_approval_gates": [], "warnings": [],
        }
        for result in normalized.evaluation.results:
            item = {
                "rule_code": result.rule_code, "rule_version": result.rule_version,
                "action": result.action.value, "message": result.message,
                "affected_fields": result.affected_fields, "value": result.suggested_value,
                "source": result.source_reference,
            }
            if result.result.value in {"not_applicable", "pass"}:
                continue
            buckets["required_controls"].append(item)
            key = "hard_constraints" if result.hardness is RuleHardness.HARD else "soft_constraints"
            buckets[key].append(item)
            domain = self._rule_domain(result.rule_id)
            bucket = self.DOMAIN_BUCKETS.get(domain)
            if bucket:
                buckets[bucket].append(item)
            if result.human_review_required:
                buckets["human_approval_gates"].append(item)
            if result.result.value in {"warn", "unknown"}:
                buckets["warnings"].append(item)
        return {
            "task_id": context.get("task_id"), "recipe_id": recipe.id,
            "recipe_version": version.version, "brand_id": context.get("brand_id"),
            "brand_version": context.get("brand_version"), "character_id": context.get("character_id"),
            "character_version": context.get("character_version"),
            "character": context.get("character") or context.get("character_profile"),
            "brand": context.get("brand") or context.get("brand_profile"),
            "product": context.get("product") or context.get("product_context"),
            "product_version": context.get("product_version"),
            "platform_profile": context.get("platform_profile"), "content_type": recipe.content_type,
            "rule_evaluation_id": normalized.evaluation.evaluation_uid,
            "normalized_recipe": normalized.normalized_payload,
            "normalization": {"defaults": normalized.applied_defaults, "removed": normalized.removed_fields, "constraints": normalized.added_constraints},
            **buckets,
        }

    def _rule_domain(self, rule_id):
        rule = self.rules.get(rule_id)
        if not rule:
            return ""
        version = next(item for item in rule.versions if item.version == rule.current_version)
        return version.domain.lower()

    @staticmethod
    def _response(contract, version, evaluation_uid):
        from backend.core.enums import RuleEvaluationStatus
        return GenerationContractResponse(
            contract_uid=contract.contract_uid, version=version.version,
            status=RuleEvaluationStatus(version.status), recipe_id=contract.recipe_id,
            recipe_version=version.recipe_version, context_hash=version.context_hash,
            rule_registry_version=version.rule_registry_version, payload=version.payload,
            evaluation_uid=evaluation_uid, created_at=version.created_at,
        )
