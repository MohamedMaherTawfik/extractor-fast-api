"""Add Social Media Inventory persistence and durable jobs."""

from collections.abc import Sequence
from alembic import op

revision: str = "0013_social_inventory"
down_revision: str | None = "0012_creator_collection_states"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

TABLES = (
    "social_inventory_sources", "social_inventory_runs", "social_inventory_items",
    "social_inventory_metric_snapshots", "social_inventory_comments",
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
