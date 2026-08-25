from datetime import UTC, datetime, timedelta
import json

import pytest
from openpyxl import Workbook
from pydantic import ValidationError

from backend.core.enums import (
    EvidenceType, RecipeCreatedBy, RecipeStatus, RecipeType, RuleAction,
    RuleEvaluationStatus, RuleHardness, RuleKind, RuleLifecycleStatus,
    RuleSeverity, RuleSourceType, RuleStage, TruthValue,
)
from backend.core.exceptions import RuleDependencyCycleError, RuleValidationError
from backend.core.paths import paths
from backend.repositories.recipe_repository import RecipeRepository
from backend.rules_engine.conditions import RuleScopeMatcher, StructuredConditionEvaluator
from backend.schemas.rules import (
    GenerationContractBuildRequest, RecipeRuleRequest, RuleActionSpec,
    RuleActivationRequest, RuleCreate, RuleEvaluationRequest, RuleSetCreate,
    RuleVersionCreate, RuleOverrideCreate,
)
from backend.services.generation_contract_service import GenerationContractService
from backend.services.recipe_rule_validation_service import RecipeRuleValidationService
from backend.services.rule_evaluation_service import RuleEvaluationService
from backend.services.rule_import_service import MasterControlImportService, RuleCompiler
from backend.services.rule_registry_service import RuleRegistryService
from backend.db.session import session_scope


def rule_request(code: str, *, condition=None, action=RuleAction.BLOCK, target=None,
                 value=None, hardness=RuleHardness.HARD, priority=100,
                 domain="rights", stage=RuleStage.PRE_GENERATION,
                 status=RuleLifecycleStatus.DRAFT, evidence=False,
                 confidence=0.0, depends_on=None, non_overridable=False):
    return RuleCreate(
        rule_code=code, name=code.replace("_", " "), domain=domain,
        rule_type=RuleKind.HARD_CONSTRAINT if hardness is RuleHardness.HARD else RuleKind.SOFT_CONSTRAINT,
        hardness=hardness, severity=RuleSeverity.HIGH if hardness is RuleHardness.HARD else RuleSeverity.LOW,
        priority=priority, condition=condition or {"field": "rights.status", "operator": "EQ", "value": "PROHIBITED"},
        action=RuleActionSpec(type=action, target=target, value=value, affected_fields=[target] if target else []),
        message=f"{code} decision", source_type=RuleSourceType.SYSTEM,
        evidence_required=evidence, minimum_confidence=confidence,
        non_overridable=non_overridable, stage=stage, status=status,
        depends_on=depends_on or [],
    )


def activate(service, rule, version=1):
    return service.activate(rule.rule_code, version, RuleActivationRequest(explicit_approval=True, approved_by="test-admin"))


def test_safe_nested_conditions_three_valued_logic_and_scope() -> None:
    evaluator = StructuredConditionEvaluator()
    context = {"content_type": "video", "character": {"hair": {"color": "BLACK"}}}
    outcome = evaluator.evaluate({"all": [
        {"field": "content_type", "operator": "EQ", "value": "video"},
        {"any": [
            {"field": "character.hair.color", "operator": "EQ", "value": "BLACK"},
            {"field": "brand.palette", "operator": "EXISTS"},
        ]},
        {"not": {"field": "rights.status", "operator": "EQ", "value": "PROHIBITED"}},
    ]}, context)
    assert outcome.value is TruthValue.UNKNOWN
    assert "rights.status" in outcome.missing_fields
    assert evaluator.evaluate({"field": "brand.palette", "operator": "EQ", "value": "NAVY"}, context).value is TruthValue.UNKNOWN
    assert RuleScopeMatcher().match({"platform": "instagram"}, context).value == "partial_context"
    with pytest.raises(RuleValidationError):
        evaluator.evaluate({"field": "__class__.__mro__", "operator": "EXISTS"}, context)
    with pytest.raises(ValidationError):
        RuleCreate.model_validate({**rule_request("SAFE_RULE").model_dump(), "condition": '__import__("os").system("echo unsafe")'})


def test_rule_version_lifecycle_registry_and_rule_sets() -> None:
    with session_scope() as session:
        service = RuleRegistryService(session)
        created = service.create_rule(rule_request("VERSIONED_RIGHTS"))
        activate(service, created)
        v2 = service.add_version("VERSIONED_RIGHTS", RuleVersionCreate(**{
            **rule_request("IGNORED", priority=200).model_dump(exclude={"rule_code", "status"}),
            "supersedes": 1,
        }))
        assert v2.version == 2 and v2.status is RuleLifecycleStatus.DRAFT
        activate(service, created, 2)
        reloaded = service.get_rule("VERSIONED_RIGHTS")
        assert [item.version for item in reloaded.versions] == [1, 2]
        assert next(item for item in reloaded.versions if item.version == 1).status is RuleLifecycleStatus.RETIRED
        rule_set = service.create_rule_set(RuleSetCreate(
            set_code="GLOBAL_RIGHTS", name="Global rights", priority=500,
            rule_codes=["VERSIONED_RIGHTS"], status=RuleLifecycleStatus.ACTIVE,
        ))
        assert rule_set.version == 1 and rule_set.members[0].rule.rule_code == "VERSIONED_RIGHTS"
        service.retire("VERSIONED_RIGHTS", 2)
        assert service.get_rule("VERSIONED_RIGHTS").versions[-1].enabled is False


def test_evidence_confidence_fail_closed_and_idempotent_evaluation() -> None:
    with session_scope() as session:
        registry = RuleRegistryService(session)
        rights = registry.create_rule(rule_request("PROHIBITED_ASSET", non_overridable=True))
        activate(registry, rights)
        claim = registry.create_rule(rule_request(
            "CLAIM_EVIDENCE", domain="factual", evidence=True,
            condition={"field": "facts.claim", "operator": "EXISTS"},
            action=RuleAction.REQUIRE_EVIDENCE,
        ))
        activate(registry, claim)
        confidence = registry.create_rule(rule_request(
            "AI_FIELD_CONFIDENCE", domain="identity", confidence=0.8,
            condition={"field": "character.hair.color", "operator": "EQ", "value": "BLACK"},
            action=RuleAction.BLOCK,
        ))
        activate(registry, confidence)
        request = RuleEvaluationRequest(context={
            "rights": {"status": "PROHIBITED"}, "facts": {"claim": "Waterproof for 24 hours"},
            "character": {"hair": {"color": "BLACK"}},
            "_confidence": {"character.hair.color": 0.42},
        })
        first = RuleEvaluationService(session).evaluate(request)
        second = RuleEvaluationService(session).evaluate(request)
        assert first.evaluation_uid == second.evaluation_uid
        assert first.status is RuleEvaluationStatus.NOT_READY
        assert "PROHIBITED_ASSET" in first.blockers
        assert "CLAIM_EVIDENCE" in first.missing_evidence
        low = next(item for item in first.results if item.rule_code == "AI_FIELD_CONFIDENCE")
        assert low.result.value == "unknown" and low.human_review_required


def test_effective_dates_rule_set_activation_scope_staleness_and_overrides() -> None:
    now = datetime.now(UTC)
    with session_scope() as session:
        registry = RuleRegistryService(session)
        scoped = registry.create_rule(RuleCreate(
            **{
                **rule_request(
                    "SCOPED_WARNING", hardness=RuleHardness.SOFT, status=RuleLifecycleStatus.ACTIVE,
                    condition={"field": "copy.claim", "operator": "EXISTS"}, action=RuleAction.WARN,
                ).model_dump(exclude={"scope", "effective_from", "effective_to"}),
                "scope": {"brand_id": "MASA_TEST"}, "effective_from": now - timedelta(hours=1),
                "effective_to": now + timedelta(days=1),
            }
        ))
        registry.create_rule_set(RuleSetCreate(
            set_code="SCOPED_SET", name="Scoped set", priority=10,
            activation_criteria={"field": "platform", "operator": "EQ", "value": "instagram"},
            rule_codes=[scoped.rule_code], status=RuleLifecycleStatus.ACTIVE,
        ))
        excluded = RuleEvaluationService(session).evaluate(RuleEvaluationRequest(
            context={"brand_id": "OTHER", "platform": "instagram", "copy": {"claim": "x"}},
            rule_sets=["SCOPED_SET"], dry_run=True,
        ))
        assert excluded.results[0].result.value == "not_applicable"
        inactive_set = RuleEvaluationService(session).evaluate(RuleEvaluationRequest(
            context={"brand_id": "MASA_TEST", "platform": "tiktok", "copy": {"claim": "x"}},
            rule_sets=["SCOPED_SET"], dry_run=True,
        ))
        assert inactive_set.rules_considered == 0

        stale = registry.create_rule(RuleCreate(**{
            **rule_request(
                "STALE_PLATFORM_POLICY", hardness=RuleHardness.SOFT, domain="platform",
                status=RuleLifecycleStatus.ACTIVE,
                condition={"field": "platform", "operator": "EQ", "value": "instagram"},
                action=RuleAction.WARN,
            ).model_dump(exclude={"last_verified_at", "stale_policy_behavior"}),
            "last_verified_at": now - timedelta(days=365),
            "stale_policy_behavior": RuleAction.HUMAN_REVIEW,
        }))
        stale_result = RuleEvaluationService(session).evaluate(RuleEvaluationRequest(
            context={"platform": "instagram", "brand_id": "MASA_TEST", "copy": {"claim": "x"}}, dry_run=True,
        ))
        stale_item = next(item for item in stale_result.results if item.rule_code == stale.rule_code)
        assert stale_item.human_review_required and "stale" in stale_item.reason.lower()

        registry.create_override(RuleOverrideCreate(
            rule_code="SCOPED_WARNING", scope={"brand_id": "MASA_TEST"}, reason="Synthetic campaign test",
            requested_by="tester", approved_by="reviewer", effective_from=now - timedelta(minutes=1),
            effective_to=now + timedelta(days=1),
        ))
        overridden = RuleEvaluationService(session).evaluate(RuleEvaluationRequest(
            context={"brand_id": "MASA_TEST", "platform": "instagram", "copy": {"claim": "x"}}, dry_run=True,
        ))
        override_item = next(item for item in overridden.results if item.rule_code == "SCOPED_WARNING")
        assert override_item.result.value == "pass" and "override" in override_item.reason.lower()

        locked = registry.create_rule(rule_request("LOCKED_RIGHTS", non_overridable=True))
        activate(registry, locked)
        with pytest.raises(RuleValidationError, match="NON_OVERRIDABLE"):
            registry.create_override(RuleOverrideCreate(
                rule_code="LOCKED_RIGHTS", reason="Must fail", requested_by="tester",
                approved_by="reviewer", effective_to=now + timedelta(days=1),
            ))


def test_priority_conflicts_dependencies_and_cycle_detection() -> None:
    with session_scope() as session:
        registry = RuleRegistryService(session)
        for code, value, priority, hardness in (
            ("BRAND_NAVY", "NAVY", 100, RuleHardness.HARD),
            ("RECIPE_GREEN", "NEON_GREEN", 20, RuleHardness.SOFT),
        ):
            item = registry.create_rule(rule_request(
                code, domain="brand", priority=priority, hardness=hardness,
                condition={"field": "content_type", "operator": "EQ", "value": "video"},
                action=RuleAction.SET_CONSTRAINT, target="visual.background", value=value,
                status=RuleLifecycleStatus.ACTIVE if hardness is RuleHardness.SOFT else RuleLifecycleStatus.DRAFT,
            ))
            if hardness is RuleHardness.HARD:
                activate(registry, item)
        result = RuleEvaluationService(session).evaluate(RuleEvaluationRequest(context={"content_type": "video"}, dry_run=True))
        conflict = next(item for item in result.conflicts if item.target == "visual.background")
        assert conflict.winner_rule_code == "BRAND_NAVY"

        for code, value in (("HARD_EQUAL_A", "A"), ("HARD_EQUAL_B", "B")):
            item = registry.create_rule(rule_request(
                code, domain="brand", priority=300,
                condition={"field": "content_type", "operator": "EQ", "value": "video"},
                action=RuleAction.SET_CONSTRAINT, target="visual.logo", value=value,
            ))
            activate(registry, item)
        result = RuleEvaluationService(session).evaluate(RuleEvaluationRequest(context={"content_type": "video"}, dry_run=True))
        equal = next(item for item in result.conflicts if item.target == "visual.logo")
        assert equal.requires_human_review and equal.winner_rule_code is None

        base = registry.create_rule(rule_request("DEPENDENCY_BASE", hardness=RuleHardness.SOFT, status=RuleLifecycleStatus.ACTIVE))
        child = registry.create_rule(rule_request("DEPENDENCY_CHILD", hardness=RuleHardness.SOFT, status=RuleLifecycleStatus.ACTIVE, depends_on=["DEPENDENCY_BASE"]))
        registry.add_version("DEPENDENCY_BASE", RuleVersionCreate(**{
            **rule_request("IGNORED", hardness=RuleHardness.SOFT, depends_on=["DEPENDENCY_CHILD"]).model_dump(exclude={"rule_code", "status"})
        }))
        registry.activate("DEPENDENCY_BASE", 2, RuleActivationRequest())
        with pytest.raises(RuleDependencyCycleError, match="RULE_DEPENDENCY_CYCLE"):
            RuleEvaluationService(session).evaluate(RuleEvaluationRequest(context={"rights": {"status": "CLEAR"}}, dry_run=True))


def _create_recipe(session):
    repo = RecipeRepository(session)
    recipe = repo.create(
        recipe_uid="RECIPE_RULE_TEST", name="Synthetic vertical video",
        recipe_type=RecipeType.EXPERIMENTAL, status=RecipeStatus.EXPERIMENTAL,
        content_type="video", target_platform="instagram", target_duration_ms=30000,
        target_category="beauty", language="ar", current_version=1,
        recipe_engine_version="1.0.0",
    )
    repo.add_version(
        recipe, version=1, payload={"visual": {"background": "NEON_GREEN"}, "content_has_speech": True},
        constraints={}, confidence=0.9, evidence_type=EvidenceType.OBSERVED,
        evidence={}, provenance={"fixture": "fictional"}, change_summary="initial",
        created_by=RecipeCreatedBy.SYSTEM, pattern_ids=[], content_ids=[],
    )
    return recipe


def test_recipe_normalization_readiness_and_immutable_contract_versions() -> None:
    with session_scope() as session:
        recipe = _create_recipe(session)
        registry = RuleRegistryService(session)
        default = registry.create_rule(rule_request(
            "CAPTION_DEFAULT", domain="accessibility", hardness=RuleHardness.SOFT,
            stage=RuleStage.POST_RECIPE, status=RuleLifecycleStatus.ACTIVE,
            condition={"field": "recipe.captions", "operator": "NOT_EXISTS"},
            action=RuleAction.SET_DEFAULT, target="recipe.captions", value=True,
        ))
        required = registry.create_rule(rule_request(
            "CAPTIONS_REQUIRED", domain="accessibility",
            condition={"all": [
                {"field": "recipe.content_has_speech", "operator": "EQ", "value": True},
                {"field": "recipe.captions", "operator": "NEQ", "value": True},
            ]}, action=RuleAction.REQUIRE_FIELD, target="recipe.captions", value=True,
        ))
        activate(registry, required)
        request = RecipeRuleRequest(recipe_id=recipe.id, context={"accessibility_profile": {"captions_required": True}})
        normalized = RecipeRuleValidationService(session).normalize(request)
        assert normalized.original_payload.get("captions") is None
        assert normalized.normalized_payload["captions"] is True

        contracts = GenerationContractService(session)
        first = contracts.build(GenerationContractBuildRequest(recipe_id=recipe.id, context=request.context))
        second = contracts.build(GenerationContractBuildRequest(recipe_id=recipe.id, context=request.context, contract_uid=first.contract_uid))
        assert first.version == 1 and second.version == 2
        assert contracts.get(first.contract_uid, 1).payload == first.payload
        assert first.payload["normalized_recipe"]["captions"] is True


def test_master_control_preview_import_classification_and_idempotency() -> None:
    source = paths.imports / "synthetic_master_controls.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Controls"
    sheet.append(["control_id", "name", "classification", "status", "rule_code", "domain", "condition", "action", "hardness", "severity"])
    sheet.append(["C-1", "Allowed background", "brand_rule", "active", "IMPORTED_BRAND", "brand", json.dumps({"field": "content_type", "operator": "EQ", "value": "video"}), json.dumps({"type": "warn"}), "soft", "low"])
    sheet.append(["K-ROLL", "K-ROLL", "undefined", "NEEDS_DEFINITION", None, None, None, None, None, None])
    sheet.append(["SALES-1", "Inventory", "integration_only", "active", None, None, None, None, None, None])
    workbook.save(source)
    with session_scope() as session:
        service = MasterControlImportService(session)
        preview = service.preview("data/imports/synthetic_master_controls.xlsx", sheet_name="Controls")
        assert preview.executable_candidates == 1 and preview.undefined_controls == 1
        imported = service.import_controls("data/imports/synthetic_master_controls.xlsx", sheet_name="Controls", dry_run=False)
        assert imported.status == "IMPORTED"
        assert RuleRegistryService(session).get_rule("IMPORTED_BRAND").versions[0].status is RuleLifecycleStatus.DRAFT
        again = service.import_controls("data/imports/synthetic_master_controls.xlsx", sheet_name="Controls", dry_run=False)
        assert again.status == "IDEMPOTENT"
        sheet["B2"] = "Allowed navy background"
        workbook.save(source)
        changed = service.import_controls("data/imports/synthetic_master_controls.xlsx", sheet_name="Controls", dry_run=False)
        assert changed.modified_controls == 1
        assert RuleRegistryService(session).get_rule("IMPORTED_BRAND").current_version == 2
        missing = service.preview("data/imports/not-present.xlsx")
        assert missing.status == "MASTER_CONTROL_FILE_NOT_FOUND"


def test_rule_api_create_evaluate_explain_and_security(api_request) -> None:
    body = rule_request(
        "API_WARNING", hardness=RuleHardness.SOFT, status=RuleLifecycleStatus.ACTIVE,
        condition={"field": "copy.claim", "operator": "EXISTS"}, action=RuleAction.WARN,
    ).model_dump(mode="json")
    created = api_request("POST", "/rules", json=body)
    assert created.status_code == 201, created.text
    evaluated = api_request("POST", "/rules/evaluate", json={"context": {"copy": {"claim": "Best ever"}}})
    assert evaluated.status_code == 200, evaluated.text
    payload = evaluated.json()
    assert payload["rules_warned"] == 1
    explained = api_request("GET", f"/rules/evaluations/{payload['evaluation_uid']}/explain")
    assert explained.status_code == 200
    assert "not a legal compliance certification" in explained.json()["compliance_claim"]
    malicious = api_request("POST", "/rules", json={**body, "rule_code": "API_ATTACK", "condition": "eval('__import__(os)')"})
    assert malicious.status_code == 422
