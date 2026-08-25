"""Multimodal generation jobs, prompts, assets, QA, and provenance."""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "0007_generation_engine"
down_revision: str | None = "0006_rules_engine"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _enum(name, *values): return sa.Enum(*values, name=name, native_enum=False, create_constraint=False)
def _check(column, values, name): return sa.CheckConstraint(f"{column} IN ({', '.join(repr(v) for v in values)})", name=name)

LOCALITY = ("local", "remote")
AVAILABILITY = ("available", "unavailable", "degraded")
JOB_STATUS = ("queued", "validating", "planning", "generating", "processing", "qa_pending", "qa_failed", "retry_pending", "human_review", "approved", "failed", "cancelled", "completed", "completed_with_fallback")
GEN_TYPES = ("text", "copy", "script", "storyboard", "image", "image_variation", "image_edit", "video", "video_shot", "video_sequence", "audio", "voice", "sfx", "music_brief", "captions", "transcript", "audio_description_draft", "multimodal_package")
PRIORITIES = ("low", "normal", "high", "urgent")
RETRY_TYPES = ("same_model_retry", "prompt_repair", "reference_adjustment", "parameter_change", "fallback_model", "human_review")
REPRO = ("full", "partial", "best_effort", "non_deterministic")
ASSET_STATUS = ("draft", "qa_failed", "human_review", "approved", "archived")
REFERENCE_ROLES = ("identity", "pose", "expression", "wardrobe", "hair", "product", "background", "lighting", "composition", "color", "material", "camera", "style_reference")
QA_CATEGORIES = ("technical_qa", "schema_qa", "character_qa", "product_qa", "brand_qa", "visual_qa", "copy_qa", "audio_qa", "accessibility_qa", "rights_qa", "provenance_qa", "continuity_qa")
QA_RESULTS = ("pass", "warn", "fail", "unknown")


def upgrade() -> None:
    op.create_table("provider_profiles",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("provider_code", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False), sa.Column("locality", _enum("provider_locality", *LOCALITY), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("availability", _enum("provider_availability", *AVAILABILITY), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False), sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _check("locality", LOCALITY, "provider_locality"), _check("availability", AVAILABILITY, "provider_availability"))
    op.create_table("model_profiles",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("provider_id", sa.Integer(), sa.ForeignKey("provider_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_code", sa.String(100), nullable=False), sa.Column("locality", _enum("model_locality", *LOCALITY), nullable=False),
        sa.Column("model_id", sa.String(255), nullable=False), sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("availability", _enum("model_availability", *AVAILABILITY), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False), sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("privacy_score", sa.Float(), nullable=False), sa.Column("cost_score", sa.Float(), nullable=False),
        sa.Column("latency_score", sa.Float(), nullable=False), sa.Column("cost_class", sa.String(50), nullable=False),
        sa.Column("license_notes", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _check("locality", LOCALITY, "model_locality"), _check("availability", AVAILABILITY, "model_availability"),
        sa.UniqueConstraint("provider_code", "model_id", "model_version", name="uq_model_profile"))
    op.create_index("ix_model_profiles_available", "model_profiles", ["enabled", "availability"])
    op.create_table("generation_jobs",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("job_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("task_id", sa.String(100)), sa.Column("generation_contract_id", sa.Integer(), sa.ForeignKey("generation_contracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("generation_contract_version", sa.Integer(), nullable=False), sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recipe_version", sa.Integer(), nullable=False), sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("modality", sa.String(50), nullable=False), sa.Column("generation_type", _enum("generation_type", *GEN_TYPES), nullable=False),
        sa.Column("provider", sa.String(100)), sa.Column("model_id", sa.String(255)), sa.Column("model_version", sa.String(100)),
        sa.Column("status", _enum("generation_job_status", *JOB_STATUS), nullable=False),
        sa.Column("priority", _enum("generation_priority", *PRIORITIES), nullable=False), sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False), sa.Column("seed", sa.Integer()), sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("prompt_hash", sa.String(64)), sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("max_cost", sa.Float()), sa.Column("max_duration_seconds", sa.Float()), sa.Column("used_fallback", sa.Boolean(), nullable=False),
        sa.Column("reproducibility_level", _enum("generation_reproducibility", *REPRO), nullable=False),
        sa.Column("error_code", sa.String(100)), sa.Column("error_message", sa.Text()), sa.Column("cancelled_by", sa.String(255)),
        sa.Column("cancel_reason", sa.Text()), sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _check("status", JOB_STATUS, "generation_job_status"), _check("generation_type", GEN_TYPES, "generation_type"),
        _check("priority", PRIORITIES, "generation_priority"))
    op.create_index("ix_generation_jobs_status_priority", "generation_jobs", ["status", "priority"])
    op.create_index("ix_generation_jobs_cache", "generation_jobs", ["idempotency_key", "status"])
    op.create_table("generation_attempts",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False), sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model_id", sa.String(255), nullable=False), sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("retry_type", _enum("generation_retry_type", *RETRY_TYPES), nullable=False), sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("failed_checks", sa.JSON(), nullable=False), sa.Column("changes_applied", sa.JSON(), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False), sa.Column("status", sa.String(50), nullable=False),
        sa.Column("response_reference", sa.Text()), sa.Column("error_code", sa.String(100)), sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True)),
        _check("retry_type", RETRY_TYPES, "generation_retry_type"), sa.UniqueConstraint("job_id", "attempt_number", name="uq_generation_attempt"))
    op.create_table("generation_events",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("event_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False), sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(50), nullable=False), sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("payload_reference", sa.Text()), sa.Column("payload", sa.JSON()))
    op.create_index("ix_generation_events_job_time", "generation_events", ["job_id", "timestamp"])
    op.create_table("prompt_packages",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("prompt_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("prompt_package_versions",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("prompt_package_id", sa.Integer(), sa.ForeignKey("prompt_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False), sa.Column("sections", sa.JSON(), nullable=False),
        sa.Column("change_reason", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("prompt_package_id", "version", name="uq_prompt_package_version"))
    op.create_table("generated_assets",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("asset_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("modality", sa.String(50), nullable=False), sa.Column("asset_type", sa.String(50), nullable=False),
        sa.Column("status", _enum("generated_asset_status", *ASSET_STATUS), nullable=False), sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)), sa.Column("archive_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _check("status", ASSET_STATUS, "generated_asset_status"))
    op.create_index("ix_generated_assets_job", "generated_assets", ["job_id"])
    op.create_table("asset_versions",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("asset_id", sa.Integer(), sa.ForeignKey("generated_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("parent_asset_version_id", sa.Integer(), sa.ForeignKey("asset_versions.id", ondelete="SET NULL")),
        sa.Column("relative_path", sa.Text(), nullable=False), sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False), sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer()), sa.Column("height", sa.Integer()), sa.Column("duration_seconds", sa.Float()),
        sa.Column("aspect_ratio", sa.String(30)), sa.Column("format", sa.String(30)), sa.Column("color_profile", sa.String(100)),
        sa.Column("provider", sa.String(100), nullable=False), sa.Column("model_id", sa.String(255), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False), sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("seed", sa.Integer()), sa.Column("metadata", sa.JSON()), sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("qa_status", sa.String(50), nullable=False), sa.Column("change_reason", sa.Text()), sa.Column("repair_type", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("asset_id", "version", name="uq_asset_version"))
    op.create_index("ix_asset_versions_checksum", "asset_versions", ["checksum"])
    op.create_table("asset_references",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reference_asset_id", sa.String(255), nullable=False), sa.Column("reference_version", sa.Integer(), nullable=False),
        sa.Column("reference_role", _enum("reference_role", *REFERENCE_ROLES), nullable=False),
        sa.Column("rights_status", sa.String(50), nullable=False), sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("checksum", sa.String(64)), sa.Column("metadata", sa.JSON(), nullable=False),
        _check("reference_role", REFERENCE_ROLES, "reference_role"))
    op.create_table("generation_qa_runs",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("qa_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_version_id", sa.Integer(), sa.ForeignKey("asset_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_table("generation_qa_results",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("qa_run_id", sa.Integer(), sa.ForeignKey("generation_qa_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("check_id", sa.String(100), nullable=False), sa.Column("category", _enum("generation_qa_category", *QA_CATEGORIES), nullable=False),
        sa.Column("result", _enum("generation_qa_result", *QA_RESULTS), nullable=False), sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("evidence", sa.JSON()), sa.Column("message", sa.Text(), nullable=False), sa.Column("suggested_action", sa.String(100)),
        sa.Column("automatically_repairable", sa.Boolean(), nullable=False),
        _check("category", QA_CATEGORIES, "generation_qa_category"), _check("result", QA_RESULTS, "generation_qa_result"))
    op.create_table("generation_costs",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("generation_attempts.id", ondelete="SET NULL")),
        sa.Column("provider_cost", sa.Float(), nullable=False), sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("input_units", sa.Float(), nullable=False), sa.Column("output_units", sa.Float(), nullable=False),
        sa.Column("gpu_seconds", sa.Float(), nullable=False), sa.Column("generation_seconds", sa.Float(), nullable=False),
        sa.Column("estimated_cost", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("continuity_states",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shot_id", sa.String(100), nullable=False), sa.Column("previous_shot_id", sa.String(100)),
        sa.Column("state", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "shot_id", name="uq_continuity_state"))
    op.create_table("storyboards",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("storyboard_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("storyboard_shots",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("storyboard_id", sa.Integer(), sa.ForeignKey("storyboards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shot_id", sa.String(100), nullable=False), sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("segment_id", sa.String(100)), sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("storyboard_id", "shot_id", name="uq_storyboard_shot"))
    op.create_table("provenance_records",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("provenance_uid", sa.String(64), nullable=False, unique=True),
        sa.Column("asset_version_id", sa.Integer(), sa.ForeignKey("asset_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("generation_contracts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False), sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recipe_version", sa.Integer(), nullable=False), sa.Column("prompt_package_version_id", sa.Integer(), sa.ForeignKey("prompt_package_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False), sa.Column("model_id", sa.String(255), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False), sa.Column("seed", sa.Integer()),
        sa.Column("reference_asset_ids", sa.JSON(), nullable=False), sa.Column("character_version", sa.String(100)),
        sa.Column("brand_version", sa.String(100)), sa.Column("product_version", sa.String(100)),
        sa.Column("transformations", sa.JSON(), nullable=False), sa.Column("c2pa_status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    op.drop_table("provenance_records")
    op.drop_table("storyboard_shots")
    op.drop_table("storyboards")
    op.drop_table("continuity_states")
    op.drop_table("generation_costs")
    op.drop_table("generation_qa_results")
    op.drop_table("generation_qa_runs")
    op.drop_table("asset_references")
    op.drop_index("ix_asset_versions_checksum", table_name="asset_versions")
    op.drop_table("asset_versions")
    op.drop_index("ix_generated_assets_job", table_name="generated_assets")
    op.drop_table("generated_assets")
    op.drop_table("prompt_package_versions")
    op.drop_table("prompt_packages")
    op.drop_index("ix_generation_events_job_time", table_name="generation_events")
    op.drop_table("generation_events")
    op.drop_table("generation_attempts")
    op.drop_index("ix_generation_jobs_cache", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_status_priority", table_name="generation_jobs")
    op.drop_table("generation_jobs")
    op.drop_index("ix_model_profiles_available", table_name="model_profiles")
    op.drop_table("model_profiles")
    op.drop_table("provider_profiles")
