"""Omnichannel conversation, decision, knowledge, follow-up, and CRM records."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin, utc_now


class Contact(Base, TimestampMixin):
    __tablename__ = "messaging_contacts"
    __table_args__ = (UniqueConstraint("channel", "external_contact_id", name="uq_messaging_contact_channel"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    external_contact_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50), index=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    lead_uid: Mapped[str | None] = mapped_column(String(100), index=True)
    preferred_language: Mapped[str | None] = mapped_column(String(20))
    communication_preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    crm_memory: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    do_not_contact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ChannelAccount(Base, TimestampMixin):
    __tablename__ = "messaging_channel_accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    availability: Mapped[str] = mapped_column(String(40), nullable=False)
    configured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("channel", "external_thread_id", name="uq_conversation_thread"),
        Index("ix_conversations_status_priority", "status", "priority"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    external_thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_id: Mapped[int] = mapped_column(ForeignKey("messaging_contacts.id", ondelete="RESTRICT"), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    lead_uid: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(40), default="NEW", nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(255))
    assigned_queue: Mapped[str | None] = mapped_column(String(50))
    priority: Mapped[str] = mapped_column(String(20), default="NORMAL", nullable=False)
    language: Mapped[str | None] = mapped_column(String(20))
    language_confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    automation_level: Mapped[str] = mapped_column(String(40), default="LEVEL_2_LOW_RISK_AUTO", nullable=False)
    privacy_mode: Mapped[str] = mapped_column(String(30), default="LOCAL_ONLY", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_human_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_bot_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    breached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(Base, TimestampMixin):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("channel", "external_message_id", name="uq_message_external"),
        UniqueConstraint("idempotency_key", name="uq_message_idempotency"),
        Index("ix_messages_conversation_time", "conversation_id", "timestamp"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    external_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str | None] = mapped_column(Text)
    media: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    reply_to_message_uid: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(20))
    language_confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="RECEIVED", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    outbound_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str | None] = mapped_column(String(100))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    failure_code: Mapped[str | None] = mapped_column(String(100))


class MessageAttachment(Base, TimestampMixin):
    __tablename__ = "message_attachments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attachment_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    attachment_type: Mapped[str] = mapped_column(String(40), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    derived_text: Mapped[str | None] = mapped_column(Text)
    safety_status: Mapped[str] = mapped_column(String(30), nullable=False)


class MessageDeliveryEvent(Base):
    __tablename__ = "message_delivery_events"
    __table_args__ = (UniqueConstraint("message_id", "external_event_id", name="uq_delivery_event"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delivery_event_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ConversationState(Base, TimestampMixin):
    __tablename__ = "conversation_states"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), unique=True, nullable=False)
    current_intent: Mapped[str | None] = mapped_column(String(60))
    requested_product: Mapped[str | None] = mapped_column(String(255))
    selected_product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    requested_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    pricing_context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    delivery_context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    pending_question: Mapped[str | None] = mapped_column(Text)
    pending_action: Mapped[str | None] = mapped_column(String(100))
    human_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    memory: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class IntentResult(Base):
    __tablename__ = "intent_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intent_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    primary_intent: Mapped[str] = mapped_column(String(60), nullable=False)
    secondary_intents: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(20), nullable=False)
    urgency: Mapped[str] = mapped_column(String(20), nullable=False)
    complaint_type: Mapped[str | None] = mapped_column(String(40))
    complaint_severity: Mapped[str | None] = mapped_column(String(20))
    classifier: Mapped[str] = mapped_column(String(100), nullable=False)
    classifier_version: Mapped[str] = mapped_column(String(50), nullable=False)


class EntityExtraction(Base):
    __tablename__ = "entity_extractions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False)
    source_span: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ResponsePlan(Base, TimestampMixin):
    __tablename__ = "response_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    source_message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    intent: Mapped[str] = mapped_column(String(60), nullable=False)
    required_facts: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    business_queries: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    response_tone: Mapped[str] = mapped_column(String(30), nullable=False)
    allowed_claims: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    cta: Mapped[str | None] = mapped_column(String(255))
    follow_up_needed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_send_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tools_allowed: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class BotDecision(Base, TimestampMixin):
    __tablename__ = "bot_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    source_message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    response_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))
    intent: Mapped[str] = mapped_column(String(60), nullable=False)
    auto_send: Mapped[bool] = mapped_column(Boolean, nullable=False)
    human_review: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    rule_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False)
    validation_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)


class HandoffRequest(Base, TimestampMixin):
    __tablename__ = "handoff_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    handoff_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    assigned_queue: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    relevant_order_id: Mapped[int | None] = mapped_column(ForeignKey("sales_orders.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(30), default="OPEN", nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(255))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentNote(Base, TimestampMixin):
    __tablename__ = "conversation_agent_notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    note_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    internal_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MessageEdit(Base):
    __tablename__ = "message_edits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    edit_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    old_text: Mapped[str | None] = mapped_column(Text)
    new_text: Mapped[str] = mapped_column(Text, nullable=False)
    diff: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    edited_by: Mapped[str] = mapped_column(String(255), nullable=False)
    feedback: Mapped[str | None] = mapped_column(String(30))
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class FollowUp(Base, TimestampMixin):
    __tablename__ = "followups"
    __table_args__ = (Index("ix_followups_due", "status", "scheduled_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    followup_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    contact_id: Mapped[int] = mapped_column(ForeignKey("messaging_contacts.id", ondelete="RESTRICT"), nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="SCHEDULED", nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stopped_reason: Mapped[str | None] = mapped_column(Text)


class MarketingConsent(Base, TimestampMixin):
    __tablename__ = "marketing_consents"
    __table_args__ = (UniqueConstraint("contact_id", "channel", "purpose", name="uq_marketing_consent"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    consent_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    contact_id: Mapped[int] = mapped_column(ForeignKey("messaging_contacts.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    basis: Mapped[str | None] = mapped_column(String(100))
    source_message_uid: Mapped[str | None] = mapped_column(String(64))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CRMSignal(Base, TimestampMixin):
    __tablename__ = "crm_signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    lead_uid: Mapped[str | None] = mapped_column(String(100))
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    source_message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING_REVIEW", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(255))


class TelesalesTask(Base, TimestampMixin):
    __tablename__ = "telesales_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_task_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    lead_uid: Mapped[str | None] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    script: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    next_action: Mapped[str] = mapped_column(String(100), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(255))
    qualification_state: Mapped[str] = mapped_column(String(30), default="NEW", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", nullable=False)


class QuoteDraft(Base, TimestampMixin):
    __tablename__ = "quote_drafts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    discount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    tax: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    delivery: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class OrderDraft(Base, TimestampMixin):
    __tablename__ = "order_drafts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_draft_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    requested_lines: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    delivery_option: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    customer_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sales_order_id: Mapped[int | None] = mapped_column(ForeignKey("sales_orders.id", ondelete="SET NULL"))


class KnowledgeItem(Base, TimestampMixin):
    __tablename__ = "knowledge_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    knowledge_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(40), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)


class KnowledgeVersion(Base):
    __tablename__ = "knowledge_versions"
    __table_args__ = (UniqueConstraint("knowledge_id", "version", name="uq_knowledge_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    knowledge_id: Mapped[int] = mapped_column(ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ResponseTemplate(Base, TimestampMixin):
    __tablename__ = "response_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)


class TemplateVersion(Base):
    __tablename__ = "template_versions"
    __table_args__ = (UniqueConstraint("template_id", "version", name="uq_template_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("response_templates.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"
    __table_args__ = (UniqueConstraint("conversation_id", "version", name="uq_conversation_summary"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    summary_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    critical_facts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ConversationEvent(Base):
    __tablename__ = "conversation_events"
    __table_args__ = (Index("ix_conversation_events_time", "conversation_id", "occurred_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class WebhookEvent(Base):
    __tablename__ = "messaging_webhook_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    webhook_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __table_args__ = (UniqueConstraint("channel", "external_event_id", name="uq_webhook_replay"),)
