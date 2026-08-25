"""Content DNA, pattern mining, performance snapshots, and recipe plans."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_pattern_recipe_engine"
down_revision: str | None = "0004_content_analysis"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=False)


def upgrade() -> None:
    op.create_table(
        "content_dna",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dna_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_run_id", sa.Integer(), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dna_version", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("identity", sa.JSON(), nullable=False),
        sa.Column("structure", sa.JSON(), nullable=False),
        sa.Column("visual", sa.JSON(), nullable=False),
        sa.Column("copy", sa.JSON(), nullable=False),
        sa.Column("audio", sa.JSON(), nullable=False),
        sa.Column("editing", sa.JSON(), nullable=False),
        sa.Column("product", sa.JSON(), nullable=False),
        sa.Column("cta", sa.JSON(), nullable=False),
        sa.Column("behavioral", sa.JSON(), nullable=False),
        sa.Column("seo", sa.JSON(), nullable=False),
        sa.Column("performance", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("segment_sequence", sa.JSON(), nullable=False),
        sa.Column("feature_vector", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("analysis_version", sa.String(100), nullable=False),
        sa.Column("taxonomy_version", sa.String(100), nullable=False),
        sa.Column("pattern_engine_version", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("analysis_run_id", name="uq_content_dna_analysis_run"),
        sa.UniqueConstraint("content_id", "dna_version", name="uq_content_dna_version"),
    )
    op.create_index("ix_content_dna_content_id", "content_dna", ["content_id"])
    op.create_index("ix_content_dna_content_type", "content_dna", ["content_type"])
    op.create_index("ix_content_dna_created_at", "content_dna", ["created_at"])

    op.create_table(
        "performance_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("raw_value", sa.Float()),
        sa.Column("normalized_value", sa.Float()),
        sa.Column("availability", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("elapsed_minutes", sa.Integer()),
        sa.Column("traffic_type", _enum("performance_traffic_type", "organic", "paid", "mixed", "unknown"), nullable=False),
        sa.Column("metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("traffic_type IN ('organic', 'paid', 'mixed', 'unknown')", name="performance_traffic_type"),
        sa.UniqueConstraint("content_id", "metric_name", "collected_at", name="uq_performance_snapshot"),
    )
    op.create_index("ix_performance_snapshots_content_id", "performance_snapshots", ["content_id"])
    op.create_index("ix_performance_snapshots_metric", "performance_snapshots", ["metric_name"])
    op.create_index("ix_performance_snapshots_collected", "performance_snapshots", ["collected_at"])

    op.create_table(
        "pattern_mining_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("contents_processed", sa.Integer(), nullable=False),
        sa.Column("patterns_found", sa.Integer(), nullable=False),
        sa.Column("patterns_rejected_low_support", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON()),
        sa.Column("engine_version", sa.String(100), nullable=False),
    )
    op.create_index("ix_pattern_mining_runs_started", "pattern_mining_runs", ["started_at"])

    op.create_table(
        "patterns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pattern_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("mining_run_id", sa.Integer(), sa.ForeignKey("pattern_mining_runs.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("pattern_type", _enum("pattern_type", "structure_pattern", "hook_pattern", "visual_pattern", "editing_pattern", "audio_pattern", "copy_pattern", "cta_pattern", "product_pattern", "sequence_pattern", "timing_pattern", "performance_pattern", "cross_modal_pattern"), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("feature_definition", sa.JSON(), nullable=False),
        sa.Column("support_count", sa.Integer(), nullable=False),
        sa.Column("support_ratio", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("performance_summary", sa.JSON()),
        sa.Column("evidence_type", _enum("pattern_evidence_type", "observed", "correlated", "experimental", "inferred"), nullable=False),
        sa.Column("support_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("performance_score", sa.Float(), nullable=False),
        sa.Column("consistency_score", sa.Float(), nullable=False),
        sa.Column("recency_score", sa.Float(), nullable=False),
        sa.Column("pattern_score", sa.Float(), nullable=False),
        sa.Column("stability", _enum("pattern_stability", "new", "emerging", "stable", "declining", "insufficient_data"), nullable=False),
        sa.Column("status", _enum("pattern_status", "structural_pattern", "performance_associated", "low_confidence"), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True)),
        sa.Column("last_seen", sa.DateTime(timezone=True)),
        sa.Column("analysis_version", sa.String(100), nullable=False),
        sa.Column("taxonomy_version", sa.String(100), nullable=False),
        sa.Column("pattern_engine_version", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("pattern_type IN ('structure_pattern', 'hook_pattern', 'visual_pattern', 'editing_pattern', 'audio_pattern', 'copy_pattern', 'cta_pattern', 'product_pattern', 'sequence_pattern', 'timing_pattern', 'performance_pattern', 'cross_modal_pattern')", name="pattern_type"),
        sa.CheckConstraint("evidence_type IN ('observed', 'correlated', 'experimental', 'inferred')", name="pattern_evidence_type"),
        sa.CheckConstraint("status IN ('structural_pattern', 'performance_associated', 'low_confidence')", name="pattern_status"),
        sa.CheckConstraint("stability IN ('new', 'emerging', 'stable', 'declining', 'insufficient_data')", name="pattern_stability"),
        sa.UniqueConstraint("fingerprint", name="uq_patterns_fingerprint"),
    )
    op.create_index("ix_patterns_type", "patterns", ["pattern_type"])
    op.create_index("ix_patterns_score", "patterns", ["pattern_score"])
    op.create_index("ix_patterns_status", "patterns", ["status"])

    op.create_table(
        "pattern_features",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pattern_id", sa.Integer(), sa.ForeignKey("patterns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature_name", sa.String(150), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("modality", sa.String(50)),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", sa.JSON()),
    )
    op.create_index("ix_pattern_features_pattern", "pattern_features", ["pattern_id"])

    op.create_table(
        "pattern_content_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pattern_id", sa.Integer(), sa.ForeignKey("patterns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dna_id", sa.Integer(), sa.ForeignKey("content_dna.id", ondelete="CASCADE"), nullable=False),
        sa.Column("segment_id", sa.Integer(), sa.ForeignKey("content_segments.id", ondelete="SET NULL")),
        sa.Column("shot_id", sa.Integer(), sa.ForeignKey("content_shots.id", ondelete="SET NULL")),
        sa.Column("analysis_result_id", sa.Integer(), sa.ForeignKey("analysis_results.id", ondelete="SET NULL")),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", sa.JSON()),
        sa.UniqueConstraint("pattern_id", "content_id", name="uq_pattern_content_link"),
    )
    op.create_index("ix_pattern_content_links_content", "pattern_content_links", ["content_id"])

    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("recipe_type", _enum("recipe_type", "proven_pattern", "creator_style", "platform_native", "category_template", "experimental", "user_defined", "hybrid"), nullable=False),
        sa.Column("status", _enum("recipe_status", "proven", "experimental", "draft", "insufficient_data"), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("target_platform", sa.String(50)),
        sa.Column("target_duration_ms", sa.Integer()),
        sa.Column("target_category", sa.String(150)),
        sa.Column("language", sa.String(100)),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("recipe_engine_version", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("recipe_type IN ('proven_pattern', 'creator_style', 'platform_native', 'category_template', 'experimental', 'user_defined', 'hybrid')", name="recipe_type"),
        sa.CheckConstraint("status IN ('proven', 'experimental', 'draft', 'insufficient_data')", name="recipe_status"),
    )
    op.create_index("ix_recipes_type", "recipes", ["recipe_type"])
    op.create_index("ix_recipes_target", "recipes", ["target_platform", "content_type"])

    op.create_table(
        "recipe_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_type", _enum("recipe_evidence_type", "observed", "correlated", "experimental", "inferred"), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("change_summary", sa.Text()),
        sa.Column("created_by", _enum("recipe_created_by", "system", "user", "imported"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("evidence_type IN ('observed', 'correlated', 'experimental', 'inferred')", name="recipe_evidence_type"),
        sa.CheckConstraint("created_by IN ('system', 'user', 'imported')", name="recipe_created_by"),
        sa.UniqueConstraint("recipe_id", "version", name="uq_recipe_version"),
    )
    op.create_index("ix_recipe_versions_recipe", "recipe_versions", ["recipe_id"])

    op.create_table(
        "recipe_pattern_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_version_id", sa.Integer(), sa.ForeignKey("recipe_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pattern_id", sa.Integer(), sa.ForeignKey("patterns.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("recipe_version_id", "pattern_id", name="uq_recipe_pattern_link"),
    )
    op.create_table(
        "recipe_content_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipe_version_id", sa.Integer(), sa.ForeignKey("recipe_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("recipe_version_id", "content_id", name="uq_recipe_content_source"),
    )
    op.create_table(
        "recipe_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("variant_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("base_version_id", sa.Integer(), sa.ForeignKey("recipe_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("changed_variables", sa.JSON(), nullable=False),
        sa.Column("overrides", sa.JSON(), nullable=False),
        sa.Column("experiment_id", sa.String(100)),
        sa.Column("control_recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recipe_variants_recipe", "recipe_variants", ["recipe_id"])


def downgrade() -> None:
    op.drop_index("ix_recipe_variants_recipe", table_name="recipe_variants")
    op.drop_table("recipe_variants")
    op.drop_table("recipe_content_sources")
    op.drop_table("recipe_pattern_links")
    op.drop_index("ix_recipe_versions_recipe", table_name="recipe_versions")
    op.drop_table("recipe_versions")
    op.drop_index("ix_recipes_target", table_name="recipes")
    op.drop_index("ix_recipes_type", table_name="recipes")
    op.drop_table("recipes")
    op.drop_index("ix_pattern_content_links_content", table_name="pattern_content_links")
    op.drop_table("pattern_content_links")
    op.drop_index("ix_pattern_features_pattern", table_name="pattern_features")
    op.drop_table("pattern_features")
    op.drop_index("ix_patterns_status", table_name="patterns")
    op.drop_index("ix_patterns_score", table_name="patterns")
    op.drop_index("ix_patterns_type", table_name="patterns")
    op.drop_table("patterns")
    op.drop_index("ix_pattern_mining_runs_started", table_name="pattern_mining_runs")
    op.drop_table("pattern_mining_runs")
    op.drop_index("ix_performance_snapshots_collected", table_name="performance_snapshots")
    op.drop_index("ix_performance_snapshots_metric", table_name="performance_snapshots")
    op.drop_index("ix_performance_snapshots_content_id", table_name="performance_snapshots")
    op.drop_table("performance_snapshots")
    op.drop_index("ix_content_dna_created_at", table_name="content_dna")
    op.drop_index("ix_content_dna_content_type", table_name="content_dna")
    op.drop_index("ix_content_dna_content_id", table_name="content_dna")
    op.drop_table("content_dna")
