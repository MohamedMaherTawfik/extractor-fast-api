"""Answer Bot conversations, messaging, knowledge, follow-up, and CRM."""

from collections.abc import Sequence

from alembic import op

revision: str = "0009_answer_bot"
down_revision: str | None = "0008_product_sales"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

TABLES = (
    "messaging_contacts", "messaging_channel_accounts", "conversations",
    "messages", "message_attachments", "message_delivery_events",
    "conversation_states", "intent_results", "entity_extractions",
    "response_plans", "bot_decisions", "handoff_requests",
    "conversation_agent_notes", "message_edits", "followups",
    "marketing_consents", "crm_signals", "telesales_tasks", "quote_drafts",
    "order_drafts", "knowledge_items", "knowledge_versions",
    "response_templates", "template_versions", "conversation_summaries",
    "conversation_events", "messaging_webhook_events",
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
