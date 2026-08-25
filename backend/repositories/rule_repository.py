"""Persistence boundary for versioned rule registry and decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.core.enums import RuleLifecycleStatus, RuleStage
from backend.db.models.rules import (
    GenerationContract, GenerationContractVersion, HumanReviewRequest, MasterControl,
    Rule, RuleDependency, RuleEvaluationResult, RuleEvaluationRun, RuleImportRun,
    RuleOverride, RuleSet, RuleSetMember, RuleVersion,
    RuleAuditLog,
)


class RuleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, **values) -> Rule:
        item = Rule(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def get(self, identifier: int | str) -> Rule | None:
        predicate = Rule.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else or_(Rule.rule_uid == str(identifier), Rule.rule_code == str(identifier))
        return self.session.scalar(self._rule_statement().where(predicate))

    def list(self, *, domain: str | None = None, status: str | None = None, limit: int = 1000) -> list[Rule]:
        statement = self._rule_statement()
        if domain:
            statement = statement.join(RuleVersion).where(RuleVersion.domain == domain, RuleVersion.version == Rule.current_version)
        if status:
            statement = statement.join(RuleVersion).where(RuleVersion.status == status, RuleVersion.version == Rule.current_version)
        return list(self.session.scalars(statement.order_by(Rule.rule_code).limit(limit)).unique())

    def add_version(self, rule: Rule, *, depends_on: list[str], **values) -> RuleVersion:
        version = RuleVersion(**values)
        rule.versions.append(version)
        self.session.flush()
        for code in dict.fromkeys(depends_on):
            dependency = self.get(code)
            if dependency is None:
                raise ValueError(f"Dependency rule does not exist: {code}")
            version.dependencies.append(RuleDependency(depends_on_rule_id=dependency.id))
        rule.current_version = max(rule.current_version, version.version)
        self.session.flush()
        return version

    def active_versions(self, *, at: datetime, stage: RuleStage, set_codes: list[str] | None = None) -> list[RuleVersion]:
        statement = self._version_statement().where(
            RuleVersion.status == RuleLifecycleStatus.ACTIVE,
            RuleVersion.enabled.is_(True),
            RuleVersion.stage == stage,
            or_(RuleVersion.effective_from.is_(None), RuleVersion.effective_from <= at),
            or_(RuleVersion.effective_to.is_(None), RuleVersion.effective_to > at),
        )
        if set_codes:
            statement = statement.join(RuleSetMember, RuleSetMember.rule_id == Rule.id).join(RuleSet, RuleSet.id == RuleSetMember.rule_set_id).where(
                RuleSet.set_code.in_(set_codes), RuleSet.status == RuleLifecycleStatus.ACTIVE
            )
        return list(self.session.scalars(statement.order_by(RuleVersion.priority.desc(), Rule.rule_code)).unique())

    def create_set(self, **values) -> RuleSet:
        rule_codes = values.pop("rule_codes")
        item = RuleSet(**values)
        self.session.add(item)
        self.session.flush()
        for code in dict.fromkeys(rule_codes):
            rule = self.get(code)
            if rule is None:
                raise ValueError(f"Rule does not exist: {code}")
            item.members.append(RuleSetMember(rule_id=rule.id))
        self.session.flush()
        return item

    def list_sets(self) -> list[RuleSet]:
        return list(self.session.scalars(select(RuleSet).options(selectinload(RuleSet.members).selectinload(RuleSetMember.rule)).order_by(RuleSet.set_code, RuleSet.version.desc())))

    def get_set(self, identifier: int | str) -> RuleSet | None:
        predicate = RuleSet.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else or_(RuleSet.set_uid == str(identifier), RuleSet.set_code == str(identifier))
        return self.session.scalar(select(RuleSet).options(selectinload(RuleSet.members).selectinload(RuleSetMember.rule)).where(predicate).order_by(RuleSet.version.desc()))

    def active_overrides(self, *, at: datetime) -> list[RuleOverride]:
        return list(self.session.scalars(select(RuleOverride).where(RuleOverride.effective_from <= at, RuleOverride.effective_to > at)))

    def create_override(self, **values) -> RuleOverride:
        item = RuleOverride(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def audit(self, *, action: str, entity_type: str, entity_id: str, actor: str, details: dict[str, Any]):
        from uuid import uuid4
        item = RuleAuditLog(
            audit_uid=f"AUDIT_{uuid4().hex}", action=action, entity_type=entity_type,
            entity_id=entity_id, actor=actor, details=details,
        )
        self.session.add(item)
        return item

    def create_evaluation(self, **values) -> RuleEvaluationRun:
        item = RuleEvaluationRun(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def add_evaluation_result(self, evaluation: RuleEvaluationRun, **values) -> RuleEvaluationResult:
        item = RuleEvaluationResult(evaluation_id=evaluation.id, **values)
        self.session.add(item)
        return item

    def get_evaluation(self, identifier: int | str) -> RuleEvaluationRun | None:
        predicate = RuleEvaluationRun.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else RuleEvaluationRun.evaluation_uid == str(identifier)
        return self.session.scalar(select(RuleEvaluationRun).options(selectinload(RuleEvaluationRun.results)).where(predicate))

    def create_review(self, **values) -> HumanReviewRequest:
        item = HumanReviewRequest(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def get_review(self, identifier: int | str) -> HumanReviewRequest | None:
        predicate = HumanReviewRequest.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else HumanReviewRequest.review_uid == str(identifier)
        return self.session.scalar(select(HumanReviewRequest).where(predicate))

    def find_import(self, source_hash: str, sheet_name: str) -> RuleImportRun | None:
        return self.session.scalar(select(RuleImportRun).where(RuleImportRun.source_file_hash == source_hash, RuleImportRun.sheet_name == sheet_name).order_by(RuleImportRun.id.desc()))

    def latest_control(self, control_id: str) -> MasterControl | None:
        return self.session.scalar(select(MasterControl).where(MasterControl.control_id == control_id).order_by(MasterControl.version.desc()))

    def create_import(self, **values) -> RuleImportRun:
        item = RuleImportRun(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def create_control(self, **values) -> MasterControl:
        item = MasterControl(**values)
        self.session.add(item)
        return item

    def create_contract(self, **values) -> GenerationContract:
        item = GenerationContract(**values)
        self.session.add(item)
        self.session.flush()
        return item

    def get_contract(self, identifier: int | str) -> GenerationContract | None:
        predicate = GenerationContract.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else GenerationContract.contract_uid == str(identifier)
        return self.session.scalar(select(GenerationContract).options(selectinload(GenerationContract.versions)).where(predicate))

    def add_contract_version(self, contract: GenerationContract, **values) -> GenerationContractVersion:
        item = GenerationContractVersion(contract_id=contract.id, **values)
        self.session.add(item)
        contract.current_version = item.version
        self.session.flush()
        return item

    @staticmethod
    def _rule_statement():
        return select(Rule).options(selectinload(Rule.versions).selectinload(RuleVersion.dependencies).selectinload(RuleDependency.depends_on_rule))

    @staticmethod
    def _version_statement():
        return select(RuleVersion).join(Rule).options(selectinload(RuleVersion.rule), selectinload(RuleVersion.dependencies).selectinload(RuleDependency.depends_on_rule))
