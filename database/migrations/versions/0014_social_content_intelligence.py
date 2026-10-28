"""Add Social Content Intelligence persistence, models, and export jobs."""

from collections.abc import Sequence
from alembic import op

revision: str = "0014_social_content_intelligence"
down_revision: str | None = "0013_social_inventory"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

TABLES = (
    "content_analysis_jobs",
    "content_transcripts",
    "content_transcript_segments",
    "content_hook_analyses",
    "content_copy_analyses",
    "content_narrative_analyses",
    "content_video_analyses",
    "content_video_scenes",
    "creator_intelligence",
    "creative_recommendations",
    "excel_export_jobs",
)


def upgrade() -> None:
    import backend.db.models  # noqa: F401
    from backend.db.base import Base
    bind = op.get_bind()
    for name in TABLES:
        Base.metadata.tables[name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    import backend.db.models  # noqa: F401
    from backend.db.base import Base
    bind = op.get_bind()
    for name in reversed(TABLES):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
