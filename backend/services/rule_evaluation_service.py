"""Auditable evaluation orchestration for active, composed rule versions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.core.enums import (
    RuleAction, RuleEvaluationStatus, RuleHardness, RuleResultStatus,
    RuleScopeStatus, RuleSeverity, ReviewStatus, TruthValue,
)
from backend.db.base import utc_now
from backend.repositories.rule_repository import RuleRepository
from backend.rules_engine.conditions import MISSING, RuleScopeMatcher, SafeFieldResolver, StructuredConditionEvaluator
from backend.rules_engine.conflicts import RuleConflictResolver
from backend.rules_engine.dependencies import RuleDependencyGraph
from backend.schemas.rules import RuleEvaluationItem, RuleEvaluationRequest, RuleEvaluationResponse
from backend.services.rule_registry_service import RuleRegistryService, stable_hash
from backend.services.rule_config import load_rule_config


class RuleEvaluationService:
    HIGH_RISK_DOMAINS = {"rights", "facts", "factual", "identity", "safety", "accessibility"}

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = RuleRepository(session)
        self.registry = RuleRegistryService(session)
        self.resolver = SafeFieldResolver()
        self.conditions = StructuredConditionEvaluator(self.resolver)
        self.scopes = RuleScopeMatcher(self.resolver)
        self.conflicts = RuleConflictResolver()
        self.dependencies = RuleDependencyGraph()
        self.config = load_rule_config()

    def evaluate(self, request: RuleEvaluationRequest) -> RuleEvaluationResponse:
        self._evaluation_context = request.context
        now = request.evaluation_time or datetime.now(UTC)
        versions = self.repository.active_versions(at=now, stage=request.stage, set_codes=request.rule_sets)
        versions = self._filter_rule_sets(versions, request.rule_sets, request.context)
        versions = self.dependencies.order(versions)
        if len(versions) > self.config.max_rules_per_evaluation:
            from backend.core.exceptions import RuleValidationError
            raise RuleValidationError("Evaluation exceeds configured rule limit")
        registry_version = self.registry.registry_version(versions)
        context_hash = stable_hash({
            "context": request.context, "rule_sets": request.rule_sets or [],
            "stage": request.stage.value, "registry": registry_version,
        })
        evaluation_uid = f"EVAL_{context_hash[:32]}"
        existing = self.repository.get_evaluation(evaluation_uid) if not request.dry_run else None
        if existing is not None:
            return RuleEvaluationResponse.model_validate(existing.summary)

        overrides = self.repository.active_overrides(at=now)
        results: list[RuleEvaluationItem] = []
        missing_fields: list[str] = []
        missing_evidence: list[str] = []
        applicable_count = 0
        for version in versions:
            scope_status = self.scopes.match(version.scope, request.context)
            if scope_status is RuleScopeStatus.NOT_APPLICABLE:
                results.append(self._item(version, RuleResultStatus.NOT_APPLICABLE, RuleAction.PASS, "Rule scope does not match", False))
                continue
            applicable_count += 1
            if self._is_overridden(version, overrides, request.context):
                results.append(self._item(version, RuleResultStatus.PASS, RuleAction.PASS, "Authorized, scoped override applied", False))
                continue
            if scope_status is RuleScopeStatus.PARTIAL_CONTEXT:
                results.append(self._item(version, RuleResultStatus.UNKNOWN, RuleAction.HUMAN_REVIEW, "Rule scope cannot be determined from partial context", True))
                continue
            outcome = self.conditions.evaluate(version.condition, request.context)
            missing_fields.extend(outcome.missing_fields)
            confidence = self._minimum_context_confidence(outcome.fields, request.context)
            if confidence is not None and confidence < version.minimum_confidence:
                results.append(self._item(version, RuleResultStatus.UNKNOWN, RuleAction.HUMAN_REVIEW, f"Context confidence {confidence:.2f} is below required {version.minimum_confidence:.2f}", True, confidence=confidence))
                continue
            if outcome.value is TruthValue.UNKNOWN:
                high_risk = version.hardness is RuleHardness.HARD or version.domain.lower() in self.HIGH_RISK_DOMAINS or version.severity in {RuleSeverity.HIGH, RuleSeverity.CRITICAL}
                action = RuleAction.HUMAN_REVIEW if high_risk else RuleAction.WARN
                results.append(self._item(version, RuleResultStatus.UNKNOWN, action, "Required context is unknown; no silent pass", high_risk, confidence=confidence))
                continue
            if outcome.value is TruthValue.FALSE:
                results.append(self._item(version, RuleResultStatus.PASS, RuleAction.PASS, "Trigger condition is false", False, confidence=confidence))
                continue
            if version.last_verified_at and version.domain.lower() in {"policy", "platform"}:
                verified = version.last_verified_at
                if verified.tzinfo is None:
                    verified = verified.replace(tzinfo=UTC)
                if (now - verified).days > self.config.stale_policy_days:
                    action = RuleAction(version.stale_policy_behavior or RuleAction.HUMAN_REVIEW.value)
                    results.append(self._item(version, RuleResultStatus.UNKNOWN, action, "Policy source is stale and requires verification", True, confidence=confidence))
                    continue
            evidence = self._evidence_for(version, request.context)
            if version.evidence_required and evidence is None:
                missing_evidence.append(version.rule.rule_code)
                status = RuleResultStatus.BLOCK if version.hardness is RuleHardness.HARD else RuleResultStatus.WARN
                results.append(self._item(version, status, RuleAction.REQUIRE_EVIDENCE, "Required evidence is missing", version.human_approval_required, confidence=confidence))
                continue
            action = RuleAction(version.action["type"])
            status = self._result_for_action(action, version.hardness)
            review = version.human_approval_required or action is RuleAction.HUMAN_REVIEW
            results.append(self._item(version, status, action, "Trigger condition matched", review, confidence=confidence, evidence=evidence))

        conflicts = self.conflicts.resolve(results)
        response = self._summarize(evaluation_uid, context_hash, registry_version, versions, applicable_count, results, conflicts, missing_fields, missing_evidence, request.dry_run)
        if not request.dry_run:
            self._persist(response, request.context)
        return response

    def explain(self, identifier: int | str) -> dict[str, Any]:
        run = self.repository.get_evaluation(identifier)
        if run is None:
            from backend.core.exceptions import NotFoundError
            raise NotFoundError(f"Rule evaluation {identifier} was not found")
        return {
            **run.summary,
            "explanation": [result.details for result in run.results],
            "compliance_claim": "Checks passed only under the recorded rule set, version, and context; this is not a legal compliance certification.",
        }

    def _filter_rule_sets(self, versions, set_codes, context):
        if not set_codes:
            return versions
        allowed: set[int] = set()
        for rule_set in self.repository.list_sets():
            if rule_set.set_code not in set_codes or rule_set.status.value != "active":
                continue
            if rule_set.activation_criteria:
                outcome = self.conditions.evaluate(rule_set.activation_criteria, context)
                if outcome.value is not TruthValue.TRUE:
                    continue
            allowed.update(member.rule_id for member in rule_set.members)
        return [version for version in versions if version.rule_id in allowed]

    def _is_overridden(self, version, overrides, context):
        if version.non_overridable:
            return False
        return any(item.rule_id == version.rule_id and self.scopes.match(item.scope, context) is RuleScopeStatus.APPLICABLE for item in overrides)

    @staticmethod
    def _minimum_context_confidence(fields, context):
        confidence_map = context.get("_confidence", {})
        values = [confidence_map[field] for field in fields if field in confidence_map and isinstance(confidence_map[field], (int, float))]
        return min(values) if values else None

    @staticmethod
    def _evidence_for(version, context):
        evidence = context.get("evidence")
        if not evidence:
            return None
        if isinstance(evidence, dict):
            return evidence.get(version.rule.rule_code) or evidence.get(version.source_control_id or "")
        return evidence

    @staticmethod
    def _result_for_action(action, hardness):
        if action is RuleAction.PASS: return RuleResultStatus.PASS
        if action is RuleAction.BLOCK: return RuleResultStatus.BLOCK
        if action is RuleAction.HUMAN_REVIEW: return RuleResultStatus.UNKNOWN
        if action in {RuleAction.WARN, RuleAction.RECOMMEND, RuleAction.SET_DEFAULT, RuleAction.REWRITE, RuleAction.RETRY, RuleAction.REGENERATE, RuleAction.USE_FALLBACK, RuleAction.DOWNGRADE_CLAIM}: return RuleResultStatus.WARN
        if action in {RuleAction.REQUIRE_FIELD, RuleAction.REQUIRE_EVIDENCE, RuleAction.SET_CONSTRAINT, RuleAction.OMIT_FIELD, RuleAction.DISABLE_FEATURE}:
            return RuleResultStatus.BLOCK if hardness is RuleHardness.HARD else RuleResultStatus.WARN
        return RuleResultStatus.FAIL

    def _item(self, version, result, action, reason, review, *, confidence=None, evidence=None):
        affected = version.action.get("affected_fields") or ([version.action["target"]] if version.action.get("target") else [])
        original = self.resolver.resolve(self._evaluation_context, affected[0]) if affected else None
        if original is MISSING:
            original = None
        return RuleEvaluationItem(
            rule_id=version.rule_id, rule_uid=version.rule.rule_uid, rule_code=version.rule.rule_code,
            rule_version=version.version, result=result, action=action, severity=version.severity,
            hardness=version.hardness, priority=version.priority, message=version.message,
            reason=reason, affected_fields=affected, original_value=original,
            suggested_value=(version.action.get("suggestion") if version.action.get("suggestion") is not None else version.action.get("value")),
            evidence=evidence, confidence=confidence, human_review_required=review,
            source_reference=version.source_reference,
        )

    @staticmethod
    def _summarize(uid, context_hash, registry, versions, applicable, results, conflicts, missing_fields, missing_evidence, dry_run):
        blocked = [item for item in results if item.result in {RuleResultStatus.BLOCK, RuleResultStatus.CONFLICT_REQUIRES_RESOLUTION}]
        reviews = [item for item in results if item.human_review_required]
        warned = [item for item in results if item.result in {RuleResultStatus.WARN, RuleResultStatus.UNKNOWN}]
        status = RuleEvaluationStatus.NOT_READY if blocked else (RuleEvaluationStatus.HUMAN_REVIEW if reviews else RuleEvaluationStatus.READY)
        return RuleEvaluationResponse(
            evaluation_uid=uid, context_hash=context_hash, status=status, registry_version=registry,
            rules_considered=len(versions), rules_applicable=applicable,
            rules_passed=sum(item.result is RuleResultStatus.PASS for item in results),
            rules_warned=len(warned), rules_blocked=len(blocked), results=results, conflicts=conflicts,
            blockers=[item.rule_code for item in blocked], warnings=[item.rule_code for item in warned],
            missing_fields=list(dict.fromkeys(missing_fields)), missing_evidence=list(dict.fromkeys(missing_evidence)),
            human_reviews=len(reviews) + sum(conflict.requires_human_review for conflict in conflicts), dry_run=dry_run,
        )

    def _persist(self, response, context):
        now = utc_now()
        run = self.repository.create_evaluation(
            evaluation_uid=response.evaluation_uid, context_hash=response.context_hash, context_snapshot=context,
            started_at=now, finished_at=now, rules_considered=response.rules_considered,
            rules_applicable=response.rules_applicable, rules_passed=response.rules_passed,
            rules_warned=response.rules_warned, rules_blocked=response.rules_blocked,
            conflicts=[item.model_dump(mode="json") for item in response.conflicts],
            human_reviews=response.human_reviews, registry_version=response.registry_version,
            result=response.status.value, summary=response.model_dump(mode="json"),
        )
        for item in response.results:
            self.repository.add_evaluation_result(
                run, rule_id=item.rule_id, rule_version=item.rule_version, result=item.result.value,
                action=item.action.value, message=item.message, affected_fields=item.affected_fields,
                evidence=item.evidence, details=item.model_dump(mode="json"),
            )
            if item.human_review_required:
                self.repository.create_review(
                    review_uid=f"REVIEW_{uuid4().hex}", evaluation_id=run.id, rule_id=item.rule_id,
                    reason=item.reason, severity=item.severity.value, context_snapshot=context,
                    status=ReviewStatus.PENDING,
                )
            if item.result is RuleResultStatus.BLOCK:
                self.repository.audit(
                    action="BLOCK", entity_type="rule_evaluation", entity_id=response.evaluation_uid,
                    actor="rules_engine", details={"rule_code": item.rule_code, "rule_version": item.rule_version, "reason": item.reason},
                )
        self.session.flush()
