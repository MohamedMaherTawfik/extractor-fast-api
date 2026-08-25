"""Platform connector and universal content collector persistence."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_platform_collector"
down_revision: str | None = "0002_creator_master"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


collection_run_status_type = sa.Enum(
    "queued",
    "running",
    "completed",
    "partial",
    "failed",
    "retrying",
    name="collection_run_status_type",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    with op.batch_alter_table("platform_accounts") as batch_op:
        batch_op.add_column(sa.Column("last_cursor", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("last_collected_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "collection_completed",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )

    with op.batch_alter_table("content_items") as batch_op:
        batch_op.add_column(sa.Column("canonical_url", sa.String(1000)))
        batch_op.add_column(sa.Column("platform_updated_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("description", sa.Text()))
        batch_op.add_column(sa.Column("hashtags", sa.JSON()))
        batch_op.add_column(sa.Column("mentions", sa.JSON()))
        batch_op.add_column(sa.Column("width", sa.Integer()))
        batch_op.add_column(sa.Column("height", sa.Integer()))
        batch_op.add_column(sa.Column("aspect_ratio", sa.Float()))
        batch_op.add_column(sa.Column("thumbnail_url", sa.String(1000)))
        batch_op.add_column(sa.Column("media_url", sa.String(1000)))
        batch_op.add_column(sa.Column("views", sa.Integer()))
        batch_op.add_column(sa.Column("likes", sa.Integer()))
        batch_op.add_column(sa.Column("comments", sa.Integer()))
        batch_op.add_column(sa.Column("shares", sa.Integer()))
        batch_op.add_column(sa.Column("saves", sa.Integer()))
        batch_op.add_column(sa.Column("raw_metadata", sa.JSON()))
        batch_op.add_column(sa.Column("raw_storage_path", sa.String(1000)))
        batch_op.add_column(sa.Column("content_hash", sa.String(64)))
        batch_op.add_column(
            sa.Column(
                "collected_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            )
        )
        batch_op.create_index("ix_content_items_content_hash", ["content_hash"])

    op.create_table(
        "collection_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_uid", sa.String(64), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("platform_account_id", sa.Integer(), nullable=True),
        sa.Column("connector", sa.String(50), nullable=False),
        sa.Column("status", collection_run_status_type, nullable=False),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_found", sa.Integer(), nullable=False),
        sa.Column("items_created", sa.Integer(), nullable=False),
        sa.Column("items_updated", sa.Integer(), nullable=False),
        sa.Column("items_skipped", sa.Integer(), nullable=False),
        sa.Column("items_failed", sa.Integer(), nullable=False),
        sa.Column("cursor_state", sa.JSON(), nullable=True),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["platform_account_id"],
            ["platform_accounts.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_uid"),
    )
    op.create_index("ix_collection_runs_creator_id", "collection_runs", ["creator_id"])
    op.create_index(
        "ix_collection_runs_platform_account_id",
        "collection_runs",
        ["platform_account_id"],
    )
    op.create_index("ix_collection_runs_status", "collection_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_collection_runs_status", table_name="collection_runs")
    op.drop_index(
        "ix_collection_runs_platform_account_id", table_name="collection_runs"
    )
    op.drop_index("ix_collection_runs_creator_id", table_name="collection_runs")
    op.drop_table("collection_runs")

    with op.batch_alter_table("content_items") as batch_op:
        batch_op.drop_index("ix_content_items_content_hash")
        for column_name in (
            "collected_at",
            "content_hash",
            "raw_storage_path",
            "raw_metadata",
            "saves",
            "shares",
            "comments",
            "likes",
            "views",
            "media_url",
            "thumbnail_url",
            "aspect_ratio",
            "height",
            "width",
            "mentions",
            "hashtags",
            "description",
            "platform_updated_at",
            "canonical_url",
        ):
            batch_op.drop_column(column_name)

    with op.batch_alter_table("platform_accounts") as batch_op:
        batch_op.drop_column("collection_completed")
        batch_op.drop_column("last_collected_at")
        batch_op.drop_column("last_cursor")
