"""Rule lifecycle, version selection, sets, overrides, and registry fingerprints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.core.enums import RuleHardness, RuleLifecycleStatus, RuleSeverity, RuleSourceType
from backend.core.exceptions import ConflictError, NotFoundError, RuleValidationError
from backend.repositories.rule_repository import RuleRepository
from backend.schemas.rules import RuleActivationRequest, RuleCreate, RuleOverrideCreate, RuleSetCreate, RuleVersionCreate
from backend.services.rule_config import load_rule_config


def stable_hash(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


class RuleRegistryService:
    def __init__(self, session: Session) -> None:
        self.repository = RuleRepository(session)
        self.session = session
        self.config = load_rule_config()

    def create_rule(self, request: RuleCreate):
        if self.repository.get(request.rule_code):
            raise ConflictError(f"Rule code already exists: {request.rule_code}")
        if request.status is RuleLifecycleStatus.ACTIVE and self._high_impact(request):
            raise RuleValidationError("High-impact rules must be activated with explicit approval")
        rule = self.repository.create(rule_uid=f"RULE_{uuid4().hex}", rule_code=request.rule_code, current_version=1)
        values = self._version_values(request)
        self.repository.add_version(rule, version=1, supersedes=None, depends_on=request.depends_on, **values)
        return self.get_rule(rule.id)

    def add_version(self, identifier: int | str, request: RuleVersionCreate):
        rule = self._require_rule(identifier)
        next_version = rule.current_version + 1
        supersedes = request.supersedes or rule.current_version
        values = self._version_values(request)
        values.update(status=RuleLifecycleStatus.DRAFT, enabled=True)
        version = self.repository.add_version(rule, version=next_version, supersedes=supersedes, depends_on=request.depends_on, **values)
        return version

    def activate(self, identifier: int | str, version_number: int, approval: RuleActivationRequest):
        rule = self._require_rule(identifier)
        version = next((item for item in rule.versions if item.version == version_number), None)
        if version is None:
            raise NotFoundError(f"Rule version {version_number} was not found")
        if self._high_impact(version) and (not approval.explicit_approval or not approval.approved_by):
            raise RuleValidationError("High-impact activation requires explicit approval and approved_by")
        for item in rule.versions:
            if item.status is RuleLifecycleStatus.ACTIVE:
                item.status = RuleLifecycleStatus.RETIRED
        version.status = RuleLifecycleStatus.ACTIVE
        version.enabled = True
        rule.current_version = version.version
        self.repository.audit(action="ACTIVATE", entity_type="rule", entity_id=rule.rule_uid, actor=approval.approved_by or "system", details={"version": version.version})
        self.session.flush()
        return version

    def retire(self, identifier: int | str, version_number: int):
        rule = self._require_rule(identifier)
        version = next((item for item in rule.versions if item.version == version_number), None)
        if version is None:
            raise NotFoundError(f"Rule version {version_number} was not found")
        version.status = RuleLifecycleStatus.RETIRED
        version.enabled = False
        self.repository.audit(action="RETIRE", entity_type="rule", entity_id=rule.rule_uid, actor="system", details={"version": version.version})
        self.session.flush()
        return version

    def create_rule_set(self, request: RuleSetCreate):
        prior = self.repository.get_set(request.set_code)
        version = prior.version + 1 if prior else 1
        if request.status is RuleLifecycleStatus.ACTIVE and not request.rule_codes:
            raise RuleValidationError("An active rule set cannot be empty")
        if prior and request.status is RuleLifecycleStatus.ACTIVE:
            prior.status = RuleLifecycleStatus.RETIRED
        return self.repository.create_set(
            set_uid=f"RSET_{uuid4().hex}", version=version, **request.model_dump()
        )

    def create_override(self, request: RuleOverrideCreate):
        rule = self._require_rule(request.rule_code)
        version = next(item for item in rule.versions if item.version == rule.current_version)
        if version.non_overridable:
            raise RuleValidationError("NON_OVERRIDABLE rule cannot be overridden")
        start = request.effective_from or datetime.now(UTC)
        end = request.effective_to or (start + timedelta(days=30))
        if end <= start:
            raise RuleValidationError("Override expiry must be later than its start")
        override = self.repository.create_override(
            override_uid=f"OVR_{uuid4().hex}", rule_id=rule.id,
            **request.model_dump(exclude={"rule_code", "effective_from", "effective_to"}),
            effective_from=start, effective_to=end,
        )
        self.repository.audit(action="OVERRIDE", entity_type="rule", entity_id=rule.rule_uid, actor=request.approved_by, details={"reason": request.reason, "scope": request.scope, "expires": end.isoformat()})
        return override

    def get_rule(self, identifier: int | str):
        return self._require_rule(identifier)

    def list_rules(self, **filters):
        return self.repository.list(**filters)

    def registry_version(self, versions: list) -> str:
        return stable_hash({"engine": self.config.version, "rules": [(v.rule.rule_code, v.version) for v in versions]})

    def _require_rule(self, identifier):
        rule = self.repository.get(identifier)
        if rule is None:
            raise NotFoundError(f"Rule {identifier} was not found")
        return rule

    @staticmethod
    def _high_impact(value) -> bool:
        return (
            value.hardness is RuleHardness.HARD
            or value.severity in {RuleSeverity.HIGH, RuleSeverity.CRITICAL}
            or value.source_type is RuleSourceType.GENERATED_DRAFT
        )

    @staticmethod
    def _version_values(request):
        values = request.model_dump(exclude={"rule_code", "depends_on", "supersedes"})
        values["action"] = request.action.model_dump(mode="json")
        values["stale_policy_behavior"] = request.stale_policy_behavior.value if request.stale_policy_behavior else None
        values.setdefault("status", RuleLifecycleStatus.DRAFT)
        values.setdefault("enabled", True)
        return values
