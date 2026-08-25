"""Machine contracts for the global constraint and decision engine."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.core.enums import (
    ControlClassification,
    ReviewStatus,
    RuleAction,
    RuleEvaluationStatus,
    RuleHardness,
    RuleKind,
    RuleLifecycleStatus,
    RuleResultStatus,
    RuleSeverity,
    RuleSourceType,
    RuleStage,
)


ALLOWED_CONDITION_OPERATORS = {
    "EQ", "NEQ", "GT", "GTE", "LT", "LTE", "IN", "NOT_IN",
    "EXISTS", "NOT_EXISTS", "CONTAINS", "MATCHES_ALLOWED_PATTERN",
}


def validate_condition_tree(node: Any, *, depth: int = 0) -> dict[str, Any]:
    if depth > 20 or not isinstance(node, dict):
        raise ValueError("Condition tree must be an object with at most 20 levels")
    logical = [key for key in ("all", "any", "not") if key in node]
    if logical:
        if len(logical) != 1 or len(node) != 1:
            raise ValueError("Logical condition nodes must contain exactly one of all, any, or not")
        key = logical[0]
        value = node[key]
        children = value if key != "not" else [value]
        if not isinstance(children, list) or not children:
            raise ValueError(f"{key} condition must contain one or more child conditions")
        if key == "not" and isinstance(value, list):
            if len(value) != 1:
                raise ValueError("not condition accepts exactly one child")
            children = value
        for child in children:
            validate_condition_tree(child, depth=depth + 1)
        return node
    allowed = {"field", "operator", "value"}
    if set(node) - allowed or not isinstance(node.get("field"), str):
        raise ValueError("Leaf conditions require a field and controlled operator")
    if node.get("operator") not in ALLOWED_CONDITION_OPERATORS:
        raise ValueError("Unsupported condition operator")
    if node["operator"] not in {"EXISTS", "NOT_EXISTS"} and "value" not in node:
        raise ValueError("This condition operator requires a value")
    return node


class RuleActionSpec(BaseModel):
    type: RuleAction
    target: str | None = None
    value: Any = None
    affected_fields: list[str] = Field(default_factory=list)
    suggestion: Any = None


class RuleDefinitionBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    domain: str = Field(min_length=1, max_length=100)
    subdomain: str | None = Field(default=None, max_length=100)
    rule_type: RuleKind
    hardness: RuleHardness
    severity: RuleSeverity
    priority: int = Field(default=0, ge=-100000, le=100000)
    scope: dict[str, Any] = Field(default_factory=dict)
    condition: dict[str, Any]
    action: RuleActionSpec
    message: str = Field(min_length=1, max_length=2000)
    source_control_id: str | None = None
    source_type: RuleSourceType = RuleSourceType.USER
    source_reference: str | None = None
    evidence_required: bool = False
    minimum_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    human_approval_required: bool = False
    non_overridable: bool = False
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    depends_on: list[str] = Field(default_factory=list)
    stage: RuleStage = RuleStage.PRE_GENERATION
    last_verified_at: datetime | None = None
    stale_policy_behavior: RuleAction | None = None

    @model_validator(mode="after")
    def validate_definition(self) -> "RuleDefinitionBase":
        validate_condition_tree(self.condition)
        if self.effective_from and self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be later than effective_from")
        if self.non_overridable and self.hardness is not RuleHardness.HARD:
            raise ValueError("Only hard rules can be non-overridable")
        return self


class RuleCreate(RuleDefinitionBase):
    rule_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,99}$")
    status: RuleLifecycleStatus = RuleLifecycleStatus.DRAFT


class RuleVersionCreate(RuleDefinitionBase):
    supersedes: int | None = Field(default=None, ge=1)


class RuleActivationRequest(BaseModel):
    explicit_approval: bool = False
    approved_by: str | None = None


class RuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_uid: str
    rule_code: str
    current_version: int
    created_at: datetime
    updated_at: datetime
    versions: list[RuleVersionResponse] = Field(default_factory=list)


class RuleVersionResponse(RuleDefinitionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    status: RuleLifecycleStatus
    supersedes: int | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class RuleSetCreate(BaseModel):
    set_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,99}$")
    name: str = Field(min_length=1, max_length=255)
    priority: int = 0
    activation_criteria: dict[str, Any] = Field(default_factory=dict)
    rule_codes: list[str] = Field(default_factory=list)
    status: RuleLifecycleStatus = RuleLifecycleStatus.DRAFT

    @model_validator(mode="after")
    def criteria_are_safe(self) -> "RuleSetCreate":
        if self.activation_criteria:
            validate_condition_tree(self.activation_criteria)
        return self


class RuleSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    set_uid: str
    set_code: str
    name: str
    version: int
    priority: int
    activation_criteria: dict[str, Any]
    status: RuleLifecycleStatus
    rule_codes: list[str] = Field(default_factory=list)
    created_at: datetime


class RuleEvaluationRequest(BaseModel):
    context: dict[str, Any]
    rule_sets: list[str] | None = None
    stage: RuleStage = RuleStage.PRE_GENERATION
    evaluation_time: datetime | None = None
    dry_run: bool = False


class RuleEvaluationItem(BaseModel):
    rule_id: int
    rule_uid: str
    rule_code: str
    rule_version: int
    result: RuleResultStatus
    action: RuleAction
    severity: RuleSeverity
    hardness: RuleHardness
    priority: int
    message: str
    reason: str
    affected_fields: list[str] = Field(default_factory=list)
    original_value: Any = None
    suggested_value: Any = None
    evidence: Any = None
    confidence: float | None = None
    human_review_required: bool = False
    source_reference: str | None = None


class RuleConflictResponse(BaseModel):
    winner_rule_code: str | None = None
    loser_rule_code: str | None = None
    rule_codes: list[str]
    target: str
    reason: str
    requires_human_review: bool = False


class RuleEvaluationResponse(BaseModel):
    evaluation_uid: str
    context_hash: str
    status: RuleEvaluationStatus
    registry_version: str
    rules_considered: int
    rules_applicable: int
    rules_passed: int
    rules_warned: int
    rules_blocked: int
    results: list[RuleEvaluationItem]
    conflicts: list[RuleConflictResponse]
    blockers: list[str]
    warnings: list[str]
    missing_fields: list[str]
    missing_evidence: list[str]
    human_reviews: int
    dry_run: bool = False


class RecipeRuleRequest(BaseModel):
    recipe_id: int | str
    recipe_version: int | None = Field(default=None, ge=1)
    context: dict[str, Any] = Field(default_factory=dict)
    rule_sets: list[str] | None = None
    dry_run: bool = False


class NormalizedRecipeResponse(BaseModel):
    recipe_id: int
    recipe_uid: str
    recipe_version: int
    original_payload: dict[str, Any]
    normalized_payload: dict[str, Any]
    applied_defaults: dict[str, Any]
    removed_fields: list[str]
    added_constraints: dict[str, Any]
    evaluation: RuleEvaluationResponse


class GenerationContractBuildRequest(RecipeRuleRequest):
    contract_uid: str | None = None


class GenerationContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contract_uid: str
    version: int
    status: RuleEvaluationStatus
    recipe_id: int
    recipe_version: int
    context_hash: str
    rule_registry_version: str
    payload: dict[str, Any]
    evaluation_uid: str
    created_at: datetime


class RuleOverrideCreate(BaseModel):
    rule_code: str
    scope: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=2000)
    requested_by: str = Field(min_length=1, max_length=255)
    approved_by: str = Field(min_length=1, max_length=255)
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class HumanReviewDecision(BaseModel):
    status: ReviewStatus
    decision: str
    decided_by: str


class MasterControlPreviewRequest(BaseModel):
    relative_path: str
    sheet_name: str | None = None
    dry_run: bool = True


class MasterControlPreviewResponse(BaseModel):
    source_file_hash: str | None
    status: str
    new_controls: int = 0
    modified_controls: int = 0
    unchanged_controls: int = 0
    disabled_controls: int = 0
    undefined_controls: int = 0
    executable_candidates: int = 0
    non_executable_controls: int = 0
    changes: list[dict[str, Any]] = Field(default_factory=list)


class CompilableControl(BaseModel):
    control_id: str
    name: str
    classification: ControlClassification
    status: str = "active"
    rule_code: str | None = None
    domain: str | None = None
    condition: dict[str, Any] | None = None
    action: dict[str, Any] | None = None
    priority: int = 0
    severity: RuleSeverity = RuleSeverity.MEDIUM
    hardness: RuleHardness = RuleHardness.SOFT
    source_reference: str | None = None


RuleResponse.model_rebuild()
