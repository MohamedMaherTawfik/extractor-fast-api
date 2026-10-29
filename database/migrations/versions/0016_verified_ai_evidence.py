"""Add Phase 3 evidence, quality, and resource metadata.

Revision ID: 0016_verified_ai_evidence
Revises: 0015_advanced_social_intelligence
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0016_verified_ai_evidence"
down_revision: str | None = "0015_advanced_social_intelligence"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    def add_if_missing(table: str, column: sa.Column) -> None:
        if column.name not in {item["name"] for item in inspector.get_columns(table)}:
            op.add_column(table, column)

    add_if_missing("content_analysis_jobs", sa.Column("quality_summary", sa.JSON(), nullable=True))
    add_if_missing("content_analysis_jobs", sa.Column("completion_summary", sa.JSON(), nullable=True))
    add_if_missing("content_analysis_jobs", sa.Column("resource_usage", sa.JSON(), nullable=True))
    add_if_missing("content_transcripts", sa.Column("raw_text", sa.Text(), nullable=True))
    add_if_missing("content_transcripts", sa.Column("corrected_text", sa.Text(), nullable=True))
    add_if_missing("content_transcripts", sa.Column("correction_status", sa.String(30), nullable=False, server_default="not_corrected"))
    add_if_missing("content_transcripts", sa.Column("quality_indicators", sa.JSON(), nullable=True))
    op.execute("UPDATE content_transcripts SET raw_text = full_text WHERE raw_text IS NULL")
    if "analysis_evidence" not in inspector.get_table_names():
        op.create_table(
        "analysis_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", sa.Uuid(), nullable=False, unique=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("content_analysis_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_uuid", sa.Uuid(), nullable=False),
        sa.Column("claim_type", sa.String(80), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("evidence_type", sa.String(50), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=True),
        sa.Column("end_time", sa.Float(), nullable=True),
        sa.Column("evidence_quote", sa.Text(), nullable=True),
        sa.Column("analysis_provider", sa.String(120), nullable=False),
        sa.Column("model_version", sa.String(160), nullable=False),
        sa.Column("verification_status", sa.String(30), nullable=False),
        sa.Column("verification_reason", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_analysis_evidence_item", "analysis_evidence", ["item_uuid"])
        op.create_index("ix_analysis_evidence_job_status", "analysis_evidence", ["job_id", "verification_status"])


def downgrade() -> None:
    op.drop_table("analysis_evidence")
