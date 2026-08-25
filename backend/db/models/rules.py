"""Versioned rules, decisions, reviews, imports, and generation contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.enums import (
    RuleHardness, RuleKind, RuleLifecycleStatus, RuleSeverity, RuleSourceType,
    RuleStage, ReviewStatus,
)
from backend.db.base import Base, utc_now
from backend.db.models.types import enum_check, enum_type


class Rule(Base):
    __tablename__ = "rules"
    __table_args__ = (Index("ix_rules_code", "rule_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    rule_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    versions: Mapped[list[RuleVersion]] = relationship(back_populates="rule", cascade="all, delete-orphan")


class RuleVersion(Base):
    __tablename__ = "rule_versions"
    __table_args__ = (
        enum_check("rule_type", RuleKind, "rule_kind"),
        enum_check("hardness", RuleHardness, "rule_hardness"),
        enum_check("severity", RuleSeverity, "rule_severity"),
        enum_check("status", RuleLifecycleStatus, "rule_lifecycle_status"),
        enum_check("source_type", RuleSourceType, "rule_source_type"),
        enum_check("stage", RuleStage, "rule_stage"),
        UniqueConstraint("rule_id", "version", name="uq_rule_version"),
        Index("ix_rule_versions_status_effective", "status", "effective_from", "effective_to"),
        Index("ix_rule_versions_domain", "domain", "subdomain"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    subdomain: Mapped[str | None] = mapped_column(String(100))
    rule_type: Mapped[RuleKind] = mapped_column(enum_type(RuleKind, "rule_kind"), nullable=False)
    hardness: Mapped[RuleHardness] = mapped_column(enum_type(RuleHardness, "rule_hardness"), nullable=False)
    severity: Mapped[RuleSeverity] = mapped_column(enum_type(RuleSeverity, "rule_severity"), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    condition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    action: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source_control_id: Mapped[str | None] = mapped_column(String(255))
    source_type: Mapped[RuleSourceType] = mapped_column(enum_type(RuleSourceType, "rule_source_type"), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(Text)
    evidence_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    minimum_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    human_approval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    non_overridable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[RuleLifecycleStatus] = mapped_column(enum_type(RuleLifecycleStatus, "rule_lifecycle_status"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    stage: Mapped[RuleStage] = mapped_column(enum_type(RuleStage, "rule_stage"), nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stale_policy_behavior: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    rule: Mapped[Rule] = relationship(back_populates="versions")
    dependencies: Mapped[list[RuleDependency]] = relationship(back_populates="rule_version", cascade="all, delete-orphan", foreign_keys="RuleDependency.rule_version_id")


class RuleDependency(Base):
    __tablename__ = "rule_dependencies"
    __table_args__ = (UniqueConstraint("rule_version_id", "depends_on_rule_id", name="uq_rule_dependency"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_version_id: Mapped[int] = mapped_column(ForeignKey("rule_versions.id", ondelete="CASCADE"), nullable=False)
    depends_on_rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id", ondelete="CASCADE"), nullable=False)
    rule_version: Mapped[RuleVersion] = relationship(back_populates="dependencies", foreign_keys=[rule_version_id])
    depends_on_rule: Mapped[Rule] = relationship(foreign_keys=[depends_on_rule_id])


class RuleSet(Base):
    __tablename__ = "rule_sets"
    __table_args__ = (
        enum_check("status", RuleLifecycleStatus, "rule_set_status"),
        UniqueConstraint("set_code", "version", name="uq_rule_set_version"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    set_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    set_code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    activation_criteria: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[RuleLifecycleStatus] = mapped_column(enum_type(RuleLifecycleStatus, "rule_set_status"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    members: Mapped[list[RuleSetMember]] = relationship(back_populates="rule_set", cascade="all, delete-orphan")


class RuleSetMember(Base):
    __tablename__ = "rule_set_members"
    __table_args__ = (UniqueConstraint("rule_set_id", "rule_id", name="uq_rule_set_member"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_set_id: Mapped[int] = mapped_column(ForeignKey("rule_sets.id", ondelete="CASCADE"), nullable=False)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id", ondelete="CASCADE"), nullable=False)
    rule_set: Mapped[RuleSet] = relationship(back_populates="members")
    rule: Mapped[Rule] = relationship()


class RuleOverride(Base):
    __tablename__ = "rule_overrides"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    override_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(255), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class RuleImportRun(Base):
    __tablename__ = "rule_import_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class MasterControl(Base):
    __tablename__ = "master_controls"
    __table_args__ = (UniqueConstraint("control_id", "version", name="uq_master_control_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    control_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    classification: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("rule_import_runs.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class RuleEvaluationRun(Base):
    __tablename__ = "rule_evaluation_runs"
    __table_args__ = (Index("ix_rule_evaluation_context", "context_hash", "registry_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evaluation_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rules_considered: Mapped[int] = mapped_column(Integer, nullable=False)
    rules_applicable: Mapped[int] = mapped_column(Integer, nullable=False)
    rules_passed: Mapped[int] = mapped_column(Integer, nullable=False)
    rules_warned: Mapped[int] = mapped_column(Integer, nullable=False)
    rules_blocked: Mapped[int] = mapped_column(Integer, nullable=False)
    conflicts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    human_reviews: Mapped[int] = mapped_column(Integer, nullable=False)
    registry_version: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    results: Mapped[list[RuleEvaluationResult]] = relationship(back_populates="evaluation", cascade="all, delete-orphan")


class RuleEvaluationResult(Base):
    __tablename__ = "rule_evaluation_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("rule_evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id", ondelete="CASCADE"), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    result: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    affected_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evidence: Mapped[Any | None] = mapped_column(JSON)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evaluation: Mapped[RuleEvaluationRun] = relationship(back_populates="results")


class HumanReviewRequest(Base):
    __tablename__ = "human_review_requests"
    __table_args__ = (enum_check("status", ReviewStatus, "human_review_status"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("rule_evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("rules.id", ondelete="SET NULL"))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(enum_type(ReviewStatus, "human_review_status"), nullable=False)
    decision: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(String(255))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class GenerationContract(Base):
    __tablename__ = "generation_contracts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    versions: Mapped[list[GenerationContractVersion]] = relationship(back_populates="contract", cascade="all, delete-orphan")


class GenerationContractVersion(Base):
    __tablename__ = "generation_contract_versions"
    __table_args__ = (UniqueConstraint("contract_id", "version", name="uq_generation_contract_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("generation_contracts.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    recipe_version: Mapped[int] = mapped_column(Integer, nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_registry_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("rule_evaluation_runs.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    contract: Mapped[GenerationContract] = relationship(back_populates="versions")


class RuleAuditLog(Base):
    __tablename__ = "rule_audit_logs"
    __table_args__ = (Index("ix_rule_audit_entity", "entity_type", "entity_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
