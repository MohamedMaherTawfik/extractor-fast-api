"""Global versioned rules, decisions, reviews, imports, and contracts."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006_rules_engine"
down_revision: str | None = "0005_pattern_recipe_engine"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=False)


RULE_KINDS = ("hard_constraint", "soft_constraint", "validation", "transformation", "recommendation", "warning", "qa_gate", "accessibility", "brand", "character", "platform", "rights", "factual", "ai_safety", "recipe", "generation", "technical", "policy")
HARDNESS = ("hard", "soft")
SEVERITY = ("info", "low", "medium", "high", "critical")
LIFECYCLE = ("draft", "active", "retired", "disabled_undefined", "non_executable")
SOURCES = ("master_sheet", "user", "system", "platform_profile", "brand_profile", "character_profile", "legal_policy", "accessibility_standard", "generated_draft")
STAGES = ("pre_analysis", "post_analysis", "pre_plan", "post_plan", "post_recipe", "pre_generation", "post_generation", "pre_publish", "post_performance")
REVIEWS = ("pending", "approved", "rejected", "cancelled")


def _check(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"{column} IN ({', '.join(repr(value) for value in values)})", name=name)


def upgrade() -> None:
    op.create_table(
        "rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("rule_code", sa.String(100), nullable=False, unique=True),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rules_code", "rules", ["rule_code"])
    op.create_table(
        "rule_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("domain", sa.String(100), nullable=False),
        sa.Column("subdomain", sa.String(100)),
        sa.Column("rule_type", _enum("rule_kind", *RULE_KINDS), nullable=False),
        sa.Column("hardness", _enum("rule_hardness", *HARDNESS), nullable=False),
        sa.Column("severity", _enum("rule_severity", *SEVERITY), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("condition", sa.JSON(), nullable=False),
        sa.Column("action", sa.JSON(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source_control_id", sa.String(255)),
        sa.Column("source_type", _enum("rule_source_type", *SOURCES), nullable=False),
        sa.Column("source_reference", sa.Text()),
        sa.Column("evidence_required", sa.Boolean(), nullable=False),
        sa.Column("minimum_confidence", sa.Float(), nullable=False),
        sa.Column("human_approval_required", sa.Boolean(), nullable=False),
        sa.Column("non_overridable", sa.Boolean(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True)),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.Column("supersedes", sa.Integer()),
        sa.Column("status", _enum("rule_lifecycle_status", *LIFECYCLE), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("stage", _enum("rule_stage", *STAGES), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("stale_policy_behavior", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _check("rule_type", RULE_KINDS, "rule_kind"),
        _check("hardness", HARDNESS, "rule_hardness"),
        _check("severity", SEVERITY, "rule_severity"),
        _check("status", LIFECYCLE, "rule_lifecycle_status"),
        _check("source_type", SOURCES, "rule_source_type"),
        _check("stage", STAGES, "rule_stage"),
        sa.UniqueConstraint("rule_id", "version", name="uq_rule_version"),
    )
    op.create_index("ix_rule_versions_status_effective", "rule_versions", ["status", "effective_from", "effective_to"])
    op.create_index("ix_rule_versions_domain", "rule_versions", ["domain", "subdomain"])
    op.create_table(
        "rule_dependencies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_version_id", sa.Integer(), sa.ForeignKey("rule_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("depends_on_rule_id", sa.Integer(), sa.ForeignKey("rules.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("rule_version_id", "depends_on_rule_id", name="uq_rule_dependency"),
    )
    op.create_table(
        "rule_sets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("set_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("set_code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("activation_criteria", sa.JSON(), nullable=False),
        sa.Column("status", _enum("rule_set_status", *LIFECYCLE), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _check("status", LIFECYCLE, "rule_set_status"),
        sa.UniqueConstraint("set_code", "version", name="uq_rule_set_version"),
    )
    op.create_table(
        "rule_set_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_set_id", sa.Integer(), sa.ForeignKey("rule_sets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("rules.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("rule_set_id", "rule_id", name="uq_rule_set_member"),
    )
    op.create_table(
        "rule_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("override_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(255), nullable=False),
        sa.Column("approved_by", sa.String(255), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "rule_import_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("import_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("source_file_hash", sa.String(64), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("sheet_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rule_import_runs_source_file_hash", "rule_import_runs", ["source_file_hash"])
    op.create_table(
        "master_controls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("control_id", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("classification", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("import_run_id", sa.Integer(), sa.ForeignKey("rule_import_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("control_id", "version", name="uq_master_control_version"),
    )
    op.create_index("ix_master_controls_control_id", "master_controls", ["control_id"])
    op.create_table(
        "rule_evaluation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("rules_considered", sa.Integer(), nullable=False),
        sa.Column("rules_applicable", sa.Integer(), nullable=False),
        sa.Column("rules_passed", sa.Integer(), nullable=False),
        sa.Column("rules_warned", sa.Integer(), nullable=False),
        sa.Column("rules_blocked", sa.Integer(), nullable=False),
        sa.Column("conflicts", sa.JSON(), nullable=False),
        sa.Column("human_reviews", sa.Integer(), nullable=False),
        sa.Column("registry_version", sa.String(64), nullable=False),
        sa.Column("result", sa.String(50), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
    )
    op.create_index("ix_rule_evaluation_context", "rule_evaluation_runs", ["context_hash", "registry_version"])
    op.create_table(
        "rule_evaluation_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("rule_evaluation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("result", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("affected_fields", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON()),
        sa.Column("details", sa.JSON(), nullable=False),
    )
    op.create_table(
        "human_review_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("review_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("rule_evaluation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("rules.id", ondelete="SET NULL")),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", _enum("human_review_status", *REVIEWS), nullable=False),
        sa.Column("decision", sa.Text()),
        sa.Column("decided_by", sa.String(255)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _check("status", REVIEWS, "human_review_status"),
    )
    op.create_table(
        "generation_contracts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "generation_contract_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("generation_contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("recipe_version", sa.Integer(), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("rule_registry_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("evaluation_id", sa.Integer(), sa.ForeignKey("rule_evaluation_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("contract_id", "version", name="uq_generation_contract_version"),
    )
    op.create_table(
        "rule_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("audit_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rule_audit_entity", "rule_audit_logs", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_rule_audit_entity", table_name="rule_audit_logs")
    op.drop_table("rule_audit_logs")
    op.drop_table("generation_contract_versions")
    op.drop_table("generation_contracts")
    op.drop_table("human_review_requests")
    op.drop_table("rule_evaluation_results")
    op.drop_index("ix_rule_evaluation_context", table_name="rule_evaluation_runs")
    op.drop_table("rule_evaluation_runs")
    op.drop_index("ix_master_controls_control_id", table_name="master_controls")
    op.drop_table("master_controls")
    op.drop_index("ix_rule_import_runs_source_file_hash", table_name="rule_import_runs")
    op.drop_table("rule_import_runs")
    op.drop_table("rule_overrides")
    op.drop_table("rule_set_members")
    op.drop_table("rule_sets")
    op.drop_table("rule_dependencies")
    op.drop_index("ix_rule_versions_domain", table_name="rule_versions")
    op.drop_index("ix_rule_versions_status_effective", table_name="rule_versions")
    op.drop_table("rule_versions")
    op.drop_index("ix_rules_code", table_name="rules")
    op.drop_table("rules")
