"""API contracts for normalized messaging and Answer Bot workflows."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BotSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class InboundMessageRequest(BotSchema):
    channel: str = "mock"
    external_message_id: str
    external_thread_id: str
    sender: str
    recipient: str | None = None
    text: str | None = None
    timestamp: datetime
    phone: str | None = None
    email: str | None = None
    customer_code: str | None = None
    lead_uid: str | None = None
    display_name: str | None = None
    reply_to: str | None = None
    media: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    auto_process: bool = True
    dry_run: bool = False


class BotProcessRequest(BotSchema):
    message_id: int | str
    dry_run: bool = False
    force_human_review: bool = False


class BotDraftRequest(BotSchema):
    message_id: int | str


class BotValidateRequest(BotSchema):
    message_id: int | str
    draft_text: str


class ConversationReplyRequest(BotSchema):
    text: str
    actor: str
    auto_send: bool = False
    idempotency_key: str | None = None


class ConversationAssignRequest(BotSchema):
    assigned_to: str | None = None
    assigned_queue: str | None = None
    actor: str


class ConversationResolveRequest(BotSchema):
    actor: str
    resolution: str | None = None


class HandoffCreate(BotSchema):
    reason: str
    priority: str = "HIGH"
    assigned_queue: str = "CUSTOMER_SERVICE"
    relevant_order_id: int | str | None = None
    actor: str = "system"


class MessageApprovalRequest(BotSchema):
    approved_by: str


class MessageEditRequest(BotSchema):
    text: str
    edited_by: str
    feedback: str | None = None


class MessageSendRequest(BotSchema):
    actor: str


class FollowUpCreate(BotSchema):
    conversation_id: int | str
    reason: str
    message_type: str = "FOLLOW_UP"
    scheduled_at: datetime
    max_attempts: int = Field(default=2, ge=1, le=10)
    cooldown_minutes: int = Field(default=1440, ge=1)


class FollowUpCancel(BotSchema):
    actor: str
    reason: str


class KnowledgeCreate(BotSchema):
    title: str
    content: str
    domain: str
    language: str = "en"
    keywords: list[str] = Field(default_factory=list)
    effective_from: datetime
    effective_to: datetime | None = None
    approved_by: str | None = None
    status: str = "DRAFT"
    source_reference: str | None = None


class KnowledgeUpdate(BotSchema):
    content: str
    language: str = "en"
    keywords: list[str] = Field(default_factory=list)
    effective_from: datetime
    effective_to: datetime | None = None
    approved_by: str | None = None
    status: str = "DRAFT"
    source_reference: str | None = None


class CRMReview(BotSchema):
    reviewed_by: str
    status: str


class ConsentUpdate(BotSchema):
    purpose: str = "MARKETING"
    status: str
    basis: str | None = None
    actor: str


class TelesalesTaskCreate(BotSchema):
    conversation_id: int | str | None = None
    customer_id: int | str | None = None
    lead_uid: str | None = None
    reason: str
    priority: str = "NORMAL"
    due_at: datetime
    owner: str | None = None


class QuoteDraftCreate(BotSchema):
    conversation_id: int | str
    product_id: int | str
    quantity: Decimal = Field(gt=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    delivery: Decimal = Field(default=Decimal("0"), ge=0)
    validity_days: int = Field(default=7, ge=1, le=90)


class OrderDraftCreate(BotSchema):
    conversation_id: int | str
    product_id: int | str
    quantity: Decimal = Field(gt=0)
    address: str | None = None
    delivery_option: str | None = None


class OrderDraftConfirm(BotSchema):
    confirmed_by: str


class DeliveryEventRequest(BotSchema):
    external_event_id: str
    status: str
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
