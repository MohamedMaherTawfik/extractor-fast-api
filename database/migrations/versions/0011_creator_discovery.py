"""Add the isolated multi-platform Creator Discovery Studio."""

from collections.abc import Sequence

from alembic import op

revision: str = "0011_creator_discovery"
down_revision: str | None = "0010_lead_acquisition"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

TABLES = (
    "creator_discovery_runs",
    "creator_discovery_jobs",
    "creator_candidates",
    "creator_profiles",
    "creator_discovery_accounts",
    "creator_content_samples",
    "creator_analysis",
    "creator_match_evidence",
    "creator_sources",
    "creator_industries",
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
