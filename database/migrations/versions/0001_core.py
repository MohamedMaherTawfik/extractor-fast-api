"""Baseline core system metadata table."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_core"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_meta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_meta_key", "system_meta", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_system_meta_key", table_name="system_meta")
    op.drop_table("system_meta")
