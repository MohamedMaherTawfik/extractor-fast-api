"""Separate creator identity, data collection, and analysis states."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_creator_collection_states"
down_revision: str | None = "0011_creator_discovery"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    _add_missing("creator_candidates", [
        sa.Column("identity_status", sa.String(40), nullable=False, server_default="IDENTITY_RESOLVED"),
        sa.Column("data_collection_status", sa.String(50), nullable=False, server_default="DATA_COLLECTION_REQUIRED"),
        sa.Column("data_completeness", sa.Float(), nullable=False, server_default="0"),
        sa.Column("connector_requirement", sa.String(50), nullable=False, server_default="API_REQUIRED"),
    ])
    _add_missing("creator_profiles", [
        sa.Column("identity_status", sa.String(40), nullable=False, server_default="IDENTITY_RESOLVED"),
        sa.Column("data_collection_status", sa.String(50), nullable=False, server_default="DATA_COLLECTION_REQUIRED"),
        sa.Column("data_completeness", sa.Float(), nullable=False, server_default="0"),
        sa.Column("connector_requirement", sa.String(50), nullable=False, server_default="API_REQUIRED"),
    ])
    _add_missing("creator_discovery_accounts", [
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("identity_status", sa.String(40), nullable=False, server_default="IDENTITY_RESOLVED"),
        sa.Column("data_collection_status", sa.String(50), nullable=False, server_default="DATA_COLLECTION_REQUIRED"),
        sa.Column("data_completeness", sa.Float(), nullable=False, server_default="0"),
        sa.Column("connector_requirement", sa.String(50), nullable=False, server_default="API_REQUIRED"),
    ])
    op.execute("UPDATE creator_profiles SET analysis_status = 'API_REQUIRED' WHERE analysis_status = 'COMPLETED' AND NOT EXISTS (SELECT 1 FROM creator_content_samples WHERE creator_content_samples.creator_id = creator_profiles.creator_id)")


def downgrade() -> None:
    _drop_existing("creator_discovery_accounts", ["connector_requirement", "data_completeness", "data_collection_status", "identity_status", "display_name"])
    _drop_existing("creator_profiles", ["connector_requirement", "data_completeness", "data_collection_status", "identity_status"])
    _drop_existing("creator_candidates", ["connector_requirement", "data_completeness", "data_collection_status", "identity_status"])


def _add_missing(table: str, columns: list[sa.Column]) -> None:
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
    missing = [column for column in columns if column.name not in existing]
    if missing:
        with op.batch_alter_table(table) as batch:
            for column in missing:
                batch.add_column(column)


def _drop_existing(table: str, columns: list[str]) -> None:
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
    selected = [column for column in columns if column in existing]
    if selected:
        with op.batch_alter_table(table) as batch:
            for column in selected:
                batch.drop_column(column)
