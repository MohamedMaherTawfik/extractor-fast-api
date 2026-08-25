"""Nationwide Egypt lead data acquisition engine."""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_lead_acquisition"
down_revision: str | None = "0009_answer_bot"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

TABLES = (
    "lead_sources",
    "lead_runs",
    "lead_jobs",
    "leads",
    "lead_source_records",
    "lead_dedupe_events",
    "lead_control_imports",
    "opt_in_leads",
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

