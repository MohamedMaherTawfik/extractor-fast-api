"""Add advanced social intelligence fields for multi-modal hooks, video metrics, and creator DNA V2.

Revision ID: 0015_advanced_social_intelligence
Revises: 0014_social_content_intelligence
Create Date: 2026-10-29
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0015_advanced_social_intelligence"
down_revision: str | None = "0014_social_content_intelligence"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    def col_exists(table: str, col: str) -> bool:
        cols = [c["name"] for c in insp.get_columns(table)]
        return col in cols

    # 1. content_hook_analyses
    if not col_exists("content_hook_analyses", "identified_hooks"):
        op.add_column("content_hook_analyses", sa.Column("identified_hooks", sa.JSON(), nullable=True))
    if not col_exists("content_hook_analyses", "opening_payoff_connection"):
        op.add_column("content_hook_analyses", sa.Column("opening_payoff_connection", sa.JSON(), nullable=True))

    # 2. content_video_analyses
    if not col_exists("content_video_analyses", "shot_distribution"):
        op.add_column("content_video_analyses", sa.Column("shot_distribution", sa.JSON(), nullable=True))
    if not col_exists("content_video_analyses", "audio_visual_alignment"):
        op.add_column("content_video_analyses", sa.Column("audio_visual_alignment", sa.JSON(), nullable=True))
    if not col_exists("content_video_analyses", "visual_analysis_level"):
        op.add_column("content_video_analyses", sa.Column("visual_analysis_level", sa.String(50), nullable=True))

    # 3. content_video_scenes
    if not col_exists("content_video_scenes", "sampled_metrics"):
        op.add_column("content_video_scenes", sa.Column("sampled_metrics", sa.JSON(), nullable=True))

    # 4. creator_intelligence
    if not col_exists("creator_intelligence", "topic_distribution"):
        op.add_column("creator_intelligence", sa.Column("topic_distribution", sa.JSON(), nullable=True))
    if not col_exists("creator_intelligence", "posting_frequency"):
        op.add_column("creator_intelligence", sa.Column("posting_frequency", sa.JSON(), nullable=True))
    if not col_exists("creator_intelligence", "visual_style_patterns"):
        op.add_column("creator_intelligence", sa.Column("visual_style_patterns", sa.JSON(), nullable=True))
    if not col_exists("creator_intelligence", "representative_posts"):
        op.add_column("creator_intelligence", sa.Column("representative_posts", sa.JSON(), nullable=True))
    if not col_exists("creator_intelligence", "sample_post_uuids"):
        op.add_column("creator_intelligence", sa.Column("sample_post_uuids", sa.JSON(), nullable=True))
    if not col_exists("creator_intelligence", "temporal_trends"):
        op.add_column("creator_intelligence", sa.Column("temporal_trends", sa.JSON(), nullable=True))


def downgrade() -> None:
    pass
