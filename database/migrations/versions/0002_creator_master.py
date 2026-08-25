"""Creator Master, platform accounts, imports, and content skeleton."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_creator_master"
down_revision: str | None = "0001_core"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


platform_type = sa.Enum(
    "instagram",
    "tiktok",
    "youtube",
    "facebook",
    "telegram",
    "x",
    "website",
    "other",
    name="platform_type",
    native_enum=False,
    create_constraint=True,
)
access_status_type = sa.Enum(
    "unknown",
    "accessible",
    "private",
    "not_found",
    "restricted",
    "error",
    name="access_status_type",
    native_enum=False,
    create_constraint=True,
)
import_status_type = sa.Enum(
    "running",
    "completed",
    "partial",
    "failed",
    name="import_status_type",
    native_enum=False,
    create_constraint=True,
)
content_platform_type = sa.Enum(
    "instagram",
    "tiktok",
    "youtube",
    "facebook",
    "telegram",
    "x",
    "website",
    "other",
    name="content_platform_type",
    native_enum=False,
    create_constraint=True,
)
content_type = sa.Enum(
    "video",
    "reel",
    "short",
    "image",
    "carousel",
    "post",
    "audio",
    "live",
    "article",
    "other",
    name="content_type",
    native_enum=False,
    create_constraint=True,
)
collection_status_type = sa.Enum(
    "pending",
    "collected",
    "failed",
    name="collection_status_type",
    native_enum=False,
    create_constraint=True,
)
analysis_status_type = sa.Enum(
    "pending",
    "running",
    "completed",
    "failed",
    name="analysis_status_type",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "creators",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creator_uid", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("primary_language", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=150), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("possible_duplicate", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creator_uid"),
    )
    op.create_index("ix_creators_display_name", "creators", ["display_name"])
    op.create_index("ix_creators_country", "creators", ["country"])
    op.create_index("ix_creators_category", "creators", ["category"])

    op.create_table(
        "creator_import_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_uid", sa.String(length=64), nullable=False),
        sa.Column("source_file", sa.String(length=1000), nullable=False),
        sa.Column("rows_total", sa.Integer(), nullable=False),
        sa.Column("rows_success", sa.Integer(), nullable=False),
        sa.Column("rows_failed", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", import_status_type, nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_uid"),
    )

    op.create_table(
        "platform_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("platform", platform_type, nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("platform_user_id", sa.String(length=255), nullable=True),
        sa.Column("profile_url", sa.String(length=1000), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("followers_count", sa.Integer(), nullable=True),
        sa.Column("following_count", sa.Integer(), nullable=True),
        sa.Column("content_count", sa.Integer(), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("access_status", access_status_type, nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "platform",
            "username",
            name="uq_platform_accounts_platform_username",
        ),
        sa.UniqueConstraint(
            "platform",
            "platform_user_id",
            name="uq_platform_accounts_platform_user_id",
        ),
        sa.UniqueConstraint(
            "profile_url",
            name="uq_platform_accounts_profile_url",
        ),
    )
    op.create_index(
        "ix_platform_accounts_creator_id",
        "platform_accounts",
        ["creator_id"],
    )
    op.create_index(
        "ix_platform_accounts_platform",
        "platform_accounts",
        ["platform"],
    )
    op.create_index(
        "ix_platform_accounts_username",
        "platform_accounts",
        ["username"],
    )

    op.create_table(
        "creator_import_errors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("error_type", sa.String(length=100), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["creator_import_batches.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_creator_import_errors_batch_id",
        "creator_import_errors",
        ["batch_id"],
    )

    op.create_table(
        "content_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_uid", sa.String(length=64), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("platform_account_id", sa.Integer(), nullable=True),
        sa.Column("platform", content_platform_type, nullable=False),
        sa.Column("platform_content_id", sa.String(length=255), nullable=True),
        sa.Column("content_type", content_type, nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(length=1000), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=100), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("local_media_path", sa.String(length=1000), nullable=True),
        sa.Column("collection_status", collection_status_type, nullable=False),
        sa.Column("analysis_status", analysis_status_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["creators.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["platform_account_id"],
            ["platform_accounts.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_uid"),
        sa.UniqueConstraint(
            "platform",
            "platform_content_id",
            name="uq_content_items_platform_content_id",
        ),
    )
    op.create_index("ix_content_items_creator_id", "content_items", ["creator_id"])
    op.create_index(
        "ix_content_items_platform_account_id",
        "content_items",
        ["platform_account_id"],
    )
    op.create_index(
        "ix_content_items_published_at",
        "content_items",
        ["published_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_content_items_published_at", table_name="content_items")
    op.drop_index(
        "ix_content_items_platform_account_id",
        table_name="content_items",
    )
    op.drop_index("ix_content_items_creator_id", table_name="content_items")
    op.drop_table("content_items")
    op.drop_index(
        "ix_creator_import_errors_batch_id",
        table_name="creator_import_errors",
    )
    op.drop_table("creator_import_errors")
    op.drop_index(
        "ix_platform_accounts_username",
        table_name="platform_accounts",
    )
    op.drop_index(
        "ix_platform_accounts_platform",
        table_name="platform_accounts",
    )
    op.drop_index(
        "ix_platform_accounts_creator_id",
        table_name="platform_accounts",
    )
    op.drop_table("platform_accounts")
    op.drop_table("creator_import_batches")
    op.drop_index("ix_creators_category", table_name="creators")
    op.drop_index("ix_creators_country", table_name="creators")
    op.drop_index("ix_creators_display_name", table_name="creators")
    op.drop_table("creators")
