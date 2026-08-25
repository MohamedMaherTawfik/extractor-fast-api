"""Universal content analysis runs, timelines, events, and results."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004_content_analysis"
down_revision: str | None = "0003_platform_collector"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


analysis_run_status_type = sa.Enum(
    "queued",
    "preprocessing",
    "analyzing",
    "normalizing",
    "completed",
    "partial",
    "failed",
    name="analysis_run_status_type",
    native_enum=False,
    create_constraint=True,
)
segment_analysis_level_type = sa.Enum(
    "content",
    "scene",
    "segment",
    "shot",
    "frame",
    "audio_event",
    "text_event",
    "visual_event",
    name="segment_analysis_level_type",
    native_enum=False,
    create_constraint=True,
)
result_analysis_level_type = sa.Enum(
    "content",
    "scene",
    "segment",
    "shot",
    "frame",
    "audio_event",
    "text_event",
    "visual_event",
    name="result_analysis_level_type",
    native_enum=False,
    create_constraint=True,
)
analysis_result_status_type = sa.Enum(
    "accepted",
    "low_confidence",
    "manual_review",
    "failed",
    name="analysis_result_status_type",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    with op.batch_alter_table("content_items") as batch_op:
        batch_op.drop_constraint("analysis_status_type", type_="check")
        batch_op.create_check_constraint(
            "analysis_status_type",
            "analysis_status IN ('pending', 'running', 'completed', 'partial', 'failed')",
        )

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_uid", sa.String(64), nullable=False),
        sa.Column("batch_uid", sa.String(64), nullable=True),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("status", analysis_run_status_type, nullable=False),
        sa.Column("media_hash", sa.String(64), nullable=False),
        sa.Column("cache_key", sa.String(64), nullable=False),
        sa.Column("analyzer_version", sa.String(100), nullable=False),
        sa.Column("rules_version", sa.String(100), nullable=False),
        sa.Column("taxonomy_version", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(1000), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("results_count", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_uid"),
    )
    for name, columns in (
        ("ix_analysis_runs_content_id", ["content_id"]),
        ("ix_analysis_runs_batch_uid", ["batch_uid"]),
        ("ix_analysis_runs_status", ["status"]),
        ("ix_analysis_runs_cache_key", ["cache_key"]),
    ):
        op.create_index(name, "analysis_runs", columns)

    op.create_table(
        "content_segments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("segment_uid", sa.String(64), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("parent_segment_id", sa.Integer(), nullable=True),
        sa.Column("level", segment_analysis_level_type, nullable=False),
        sa.Column("kind", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("start_ms", sa.Integer(), nullable=True),
        sa.Column("end_ms", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_segment_id"], ["content_segments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("segment_uid"),
    )
    for name, columns in (
        ("ix_content_segments_run_id", ["run_id"]),
        ("ix_content_segments_content_id", ["content_id"]),
        ("ix_content_segments_time", ["start_ms", "end_ms"]),
    ):
        op.create_index(name, "content_segments", columns)

    op.create_table(
        "content_shots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shot_uid", sa.String(64), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("segment_id", sa.Integer(), nullable=True),
        sa.Column("start_ms", sa.Integer(), nullable=True),
        sa.Column("end_ms", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("shot_size", sa.String(100), nullable=True),
        sa.Column("camera_angle", sa.String(100), nullable=True),
        sa.Column("camera_movement", sa.String(100), nullable=True),
        sa.Column("subject_position", sa.String(100), nullable=True),
        sa.Column("cut_type", sa.String(100), nullable=True),
        sa.Column("transition", sa.String(100), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["segment_id"], ["content_segments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shot_uid"),
    )
    for name, columns in (
        ("ix_content_shots_run_id", ["run_id"]),
        ("ix_content_shots_content_id", ["content_id"]),
        ("ix_content_shots_segment_id", ["segment_id"]),
        ("ix_content_shots_time", ["start_ms", "end_ms"]),
    ):
        op.create_index(name, "content_shots", columns)

    _create_event_table("visual_events", include_text=False)
    _create_event_table("audio_events", include_text=False)
    _create_event_table("text_events", include_text=True)

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("segment_id", sa.Integer(), nullable=True),
        sa.Column("shot_id", sa.Integer(), nullable=True),
        sa.Column("visual_event_id", sa.Integer(), nullable=True),
        sa.Column("audio_event_id", sa.Integer(), nullable=True),
        sa.Column("text_event_id", sa.Integer(), nullable=True),
        sa.Column("field", sa.String(150), nullable=False),
        sa.Column("level", result_analysis_level_type, nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=True),
        sa.Column("end_ms", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("engine", sa.String(100), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("status", analysis_result_status_type, nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("low_confidence", sa.Boolean(), nullable=False),
        sa.Column("manual_review", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["segment_id"], ["content_segments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shot_id"], ["content_shots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["visual_event_id"], ["visual_events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["audio_event_id"], ["audio_events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["text_event_id"], ["text_events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("ix_analysis_results_run_id", ["run_id"]),
        ("ix_analysis_results_content_id", ["content_id"]),
        ("ix_analysis_results_field", ["field"]),
        ("ix_analysis_results_rule_id", ["rule_id"]),
        ("ix_analysis_results_time", ["start_ms", "end_ms"]),
    ):
        op.create_index(name, "analysis_results", columns)


def _create_event_table(table_name: str, *, include_text: bool) -> None:
    columns = [
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_uid", sa.String(64), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("segment_id", sa.Integer(), nullable=True),
        sa.Column("shot_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(150), nullable=False),
    ]
    if include_text:
        columns.extend(
            [
                sa.Column("text", sa.Text(), nullable=False),
            ]
        )
    columns.extend(
        [
            sa.Column("start_ms", sa.Integer(), nullable=True),
            sa.Column("end_ms", sa.Integer(), nullable=True),
        ]
    )
    if include_text:
        columns.extend(
            [
                sa.Column("position", sa.JSON(), nullable=True),
                sa.Column("bounding_box", sa.JSON(), nullable=True),
            ]
        )
    columns.extend(
        [
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("evidence", sa.JSON(), nullable=True),
            sa.Column("source", sa.String(255), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["content_id"], ["content_items.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["segment_id"], ["content_segments.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["shot_id"], ["content_shots.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_uid"),
        ]
    )
    op.create_table(table_name, *columns)
    prefix = table_name
    op.create_index(f"ix_{prefix}_run_id", table_name, ["run_id"])
    op.create_index(f"ix_{prefix}_content_id", table_name, ["content_id"])
    op.create_index(f"ix_{prefix}_time", table_name, ["start_ms", "end_ms"])


def downgrade() -> None:
    for table_name, indexes in (
        (
            "analysis_results",
            ("run_id", "content_id", "field", "rule_id", "time"),
        ),
        ("text_events", ("run_id", "content_id", "time")),
        ("audio_events", ("run_id", "content_id", "time")),
        ("visual_events", ("run_id", "content_id", "time")),
        (
            "content_shots",
            ("run_id", "content_id", "segment_id", "time"),
        ),
        ("content_segments", ("run_id", "content_id", "time")),
        (
            "analysis_runs",
            ("content_id", "batch_uid", "status", "cache_key"),
        ),
    ):
        for suffix in reversed(indexes):
            op.drop_index(f"ix_{table_name}_{suffix}", table_name=table_name)
        op.drop_table(table_name)

    with op.batch_alter_table("content_items") as batch_op:
        batch_op.drop_constraint("analysis_status_type", type_="check")
        batch_op.create_check_constraint(
            "analysis_status_type",
            "analysis_status IN ('pending', 'running', 'completed', 'failed')",
        )
