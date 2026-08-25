"""Handoff, queue/retry, follow-up/consent, CRM, and sales-draft workflows."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.answer_bot.channels import ChannelRegistry
from backend.answer_bot.config import get_answer_bot_config
from backend.answer_bot.conversations import ConversationService, MessageIngestionService
from backend.core.exceptions import MessagingProviderError, MessagingValidationError, NotFoundError
from backend.db.models.answer_bot import (
    CRMSignal, FollowUp, HandoffRequest, MarketingConsent, MessageDeliveryEvent,
    OrderDraft, QuoteDraft, TelesalesTask,
)
from backend.repositories.answer_bot_repository import AnswerBotRepository
from backend.repositories.sales_repository import SalesRepository
from backend.sales.common import json_safe, money, uid
from backend.sales.master_data import PricingService, ProductService
from backend.schemas.answer_bot import FollowUpCreate, OrderDraftCreate, QuoteDraftCreate, TelesalesTaskCreate


class HumanHandoffService:
    def __init__(self, session: Session) -> None: self.repository = AnswerBotRepository(session); self.conversations = ConversationService(session)

    def create(self, conversation_id: int | str, *, reason: str, priority: str, assigned_queue: str, actor: str, relevant_order_id: int | str | None = None) -> HandoffRequest:
        conversation = self.conversations.get(conversation_id); existing = self.repository.open_handoff(conversation.id)
        if existing: return existing
        order = SalesRepository(self.repository.session).get_order(relevant_order_id) if relevant_order_id is not None else None
        recent = self.repository.conversation_messages(conversation.id, limit=8)
        summary = f"Issue: {reason}. Customer wants assistance. Checked messages: " + " | ".join((item.text or "")[:120] for item in recent[-4:])
        handoff = self.repository.add(HandoffRequest(handoff_uid=uid("HANDOFF"), conversation_id=conversation.id, reason=reason, summary=summary[:2000], priority=priority.upper(), assigned_queue=assigned_queue.upper(), customer_id=conversation.customer_id, relevant_order_id=order.id if order else None, status="OPEN"))
        conversation.status = "HUMAN_HANDOFF"; conversation.priority = priority.upper(); conversation.assigned_queue = assigned_queue.upper()
        state = self.repository.get_state(conversation.id); state.human_required = True; state.pending_action = "HUMAN_HANDOFF"
        self.conversations.event(conversation, actor, "HANDOFF_CREATED", {"handoff_uid": handoff.handoff_uid, "queue": handoff.assigned_queue, "reason": reason})
        return handoff


class MessageQueueService:
    def __init__(self, session: Session) -> None:
        self.repository = AnswerBotRepository(session); self.channels = ChannelRegistry(); self.config = get_answer_bot_config(); self.conversations = ConversationService(session)

    def approve(self, message_id: int | str, approved_by: str) -> object:
        message = MessageIngestionService(self.repository.session).get_message(message_id)
        if message.status not in {"DRAFT", "PENDING_REVIEW"}: raise MessagingValidationError("Only a draft/review message can be approved")
        message.status = "APPROVED"; message.metadata_json = {**message.metadata_json, "approved_by": approved_by, "approved_at": datetime.now(UTC).isoformat()}
        return message

    def enqueue(self, message_id: int | str, actor: str) -> object:
        message = MessageIngestionService(self.repository.session).get_message(message_id)
        if message.status not in {"APPROVED", "QUEUED", "RETRYING"}: raise MessagingValidationError("Outbound message must be approved before queueing")
        message.status = "QUEUED"; message.next_attempt_at = datetime.now(UTC)
        conversation = self.conversations.get(message.conversation_id); self.conversations.event(conversation, actor, "MESSAGE_QUEUED", {"message_uid": message.message_uid})
        return message

    def process(self, *, limit: int = 100) -> list[object]:
        now = datetime.now(UTC); processed = []
        for message in self.repository.queued_messages(now=now, limit=limit):
            conversation = self.conversations.get(message.conversation_id)
            try:
                adapter = self.channels.get(message.channel); message.attempt_count += 1
                result = adapter.send_message({"message_uid": message.message_uid, "thread_id": message.external_thread_id, "text": message.text, "media": message.media})
                message.status = result["status"]; message.provider_message_id = result["provider_message_id"]; message.next_attempt_at = None
                conversation.last_outbound_at = now; conversation.last_bot_message_at = now if message.sender == "answer_bot" else conversation.last_bot_message_at; conversation.last_human_message_at = now if message.sender != "answer_bot" else conversation.last_human_message_at; conversation.last_message_at = now; conversation.status = "WAITING_CUSTOMER"
                self.conversations.event(conversation, "queue", "MESSAGE_SENT", {"message_uid": message.message_uid, "provider_message_id": message.provider_message_id})
            except MessagingProviderError as exc:
                message.failure_code = exc.code
                if message.attempt_count >= message.max_attempts:
                    message.status = "FAILED"; HumanHandoffService(self.repository.session).create(conversation.id, reason="OUTBOUND_DEAD_LETTER", priority="HIGH", assigned_queue="CUSTOMER_SERVICE", actor="queue")
                else:
                    delays = self.config["retry_backoff_seconds"]; delay = delays[min(message.attempt_count - 1, len(delays) - 1)]
                    message.status = "RETRYING"; message.next_attempt_at = now + timedelta(seconds=delay)
            processed.append(message)
        return processed

    def cancel(self, message_id: int | str, actor: str) -> object:
        message = MessageIngestionService(self.repository.session).get_message(message_id)
        if message.status in {"SENT", "DELIVERED", "READ"}: raise MessagingValidationError("Sent message cannot be cancelled")
        message.status = "CANCELLED"; self.conversations.event(self.conversations.get(message.conversation_id), actor, "MESSAGE_CANCELLED", {"message_uid": message.message_uid})
        return message

    def delivery_event(self, message_id: int | str, *, external_event_id: str, status: str, occurred_at: datetime, payload: dict) -> MessageDeliveryEvent:
        message = MessageIngestionService(self.repository.session).get_message(message_id); allowed = {"SENT", "DELIVERED", "READ", "FAILED"}; target = status.upper()
        if target not in allowed: raise MessagingValidationError("Unsupported delivery status")
        event = self.repository.add(MessageDeliveryEvent(delivery_event_uid=uid("MDE"), message_id=message.id, external_event_id=external_event_id, status=target, occurred_at=occurred_at, payload=payload)); message.status = target
        return event


class ConsentService:
    def __init__(self, session: Session) -> None: self.repository = AnswerBotRepository(session)

    def update(self, contact_id: int | str, *, purpose: str, status: str, basis: str | None, source_message_uid: str | None = None) -> MarketingConsent:
        contact = self.repository.get_contact(contact_id)
        if contact is None: raise NotFoundError(f"Contact {contact_id} was not found")
        purpose = purpose.upper(); status = status.upper(); existing = self.repository.consent(contact.id, contact.channel, purpose); now = datetime.now(UTC)
        if existing:
            existing.status = status; existing.basis = basis; existing.source_message_uid = source_message_uid; existing.effective_at = now; existing.revoked_at = now if status in {"REVOKED", "OPTED_OUT"} else None; consent = existing
        else: consent = self.repository.add(MarketingConsent(consent_uid=uid("CONSENT"), contact_id=contact.id, channel=contact.channel, purpose=purpose, status=status, basis=basis, source_message_uid=source_message_uid, effective_at=now, revoked_at=now if status in {"REVOKED", "OPTED_OUT"} else None))
        if purpose == "MARKETING" and status in {"REVOKED", "OPTED_OUT"}: contact.do_not_contact = True
        return consent

    def marketing_allowed(self, contact_id: int) -> bool:
        contact = self.repository.get_contact(contact_id)
        if not contact or contact.do_not_contact: return False
        consent = self.repository.consent(contact.id, contact.channel, "MARKETING")
        return bool(consent and consent.status == "GRANTED")


class FollowUpService:
    def __init__(self, session: Session) -> None: self.repository = AnswerBotRepository(session); self.config = get_answer_bot_config()

    def create(self, request: FollowUpCreate) -> FollowUp:
        conversation = ConversationService(self.repository.session).get(request.conversation_id); contact = self.repository.get_contact(conversation.contact_id)
        if contact.do_not_contact and request.message_type.upper() in {"MARKETING_MESSAGE", "FOLLOW_UP"}: raise MessagingValidationError("DO_NOT_CONTACT blocks this follow-up")
        if request.message_type.upper() == "MARKETING_MESSAGE" and not ConsentService(self.repository.session).marketing_allowed(contact.id): raise MessagingValidationError("Marketing follow-up requires consent")
        return self.repository.add(FollowUp(followup_uid=uid("FOLLOW"), conversation_id=conversation.id, contact_id=contact.id, reason=request.reason, message_type=request.message_type.upper(), channel=conversation.channel, scheduled_at=request.scheduled_at, max_attempts=request.max_attempts, cooldown_minutes=request.cooldown_minutes, status="SCHEDULED"))

    def cancel(self, identifier: int | str, actor: str, reason: str) -> FollowUp:
        item = self.repository.get_followup(identifier)
        if item is None: raise NotFoundError(f"Follow-up {identifier} was not found")
        item.status = "CANCELLED"; item.stopped_reason = f"{reason} ({actor})"; return item

    def run_due(self, now: datetime | None = None) -> list[FollowUp]:
        now = now or datetime.now(UTC); processed = []
        for item in self.repository.due_followups(now):
            contact = self.repository.get_contact(item.contact_id)
            if contact.do_not_contact and item.message_type in {"MARKETING_MESSAGE", "FOLLOW_UP"}: item.status = "STOPPED"; item.stopped_reason = "DO_NOT_CONTACT"; processed.append(item); continue
            quiet = self.config["quiet_hours"]; local = now.astimezone(timezone(timedelta(hours=int(quiet.get("utc_offset", 0))))); start = time.fromisoformat(quiet["start"]); end = time.fromisoformat(quiet["end"])
            in_quiet = local.time() >= start or local.time() < end if start > end else start <= local.time() < end
            if in_quiet:
                next_local = datetime.combine(local.date() + (timedelta(days=1) if local.time() >= start else timedelta()), end, tzinfo=local.tzinfo)
                item.scheduled_at = next_local.astimezone(UTC); processed.append(item); continue
            if item.attempt_count >= item.max_attempts: item.status = "STOPPED"; item.stopped_reason = "MAX_ATTEMPTS"; processed.append(item); continue
            item.attempt_count += 1; item.last_attempt_at = now
            if item.attempt_count >= item.max_attempts: item.status = "STOPPED"; item.stopped_reason = "MAX_ATTEMPTS"
            else: item.scheduled_at = now + timedelta(minutes=item.cooldown_minutes)
            processed.append(item)
        return processed


class CRMExtractionService:
    SIGNALS = {"PRICE_QUERY": "PRICE_REQUEST", "WHOLESALE_QUERY": "WHOLESALE_INTEREST", "ORDER_CREATE_INTENT": "ORDER_INTENT", "SALES_OBJECTION": "OBJECTION", "COMPLAINT": "COMPLAINT", "FOLLOW_UP": "FOLLOW_UP_REQUIRED"}
    def __init__(self, session: Session) -> None: self.repository = AnswerBotRepository(session)

    def create(self, *, conversation_id: int, message_id: int, intent: str, confidence: Decimal, entities: list[dict]) -> CRMSignal | None:
        signal_type = self.SIGNALS.get(intent)
        if not signal_type: return None
        conversation = ConversationService(self.repository.session).get(conversation_id)
        return self.repository.add(CRMSignal(signal_uid=uid("CRM"), conversation_id=conversation.id, customer_id=conversation.customer_id, lead_uid=conversation.lead_uid, signal_type=signal_type, value=json_safe({"entities": entities, "purchase_intent_score": str(min(Decimal("1"), confidence + (Decimal("0.1") if any(item["type"] == "QUANTITY" for item in entities) else Decimal("0"))))}), confidence=confidence, source_message_id=message_id, status="PENDING_REVIEW"))


class TelesalesService:
    def __init__(self, session: Session) -> None: self.repository = AnswerBotRepository(session); self.sales = SalesRepository(session)
    def create(self, request: TelesalesTaskCreate) -> TelesalesTask:
        conversation = ConversationService(self.repository.session).get(request.conversation_id) if request.conversation_id is not None else None
        customer = self.sales.get_customer(request.customer_id) if request.customer_id is not None else None
        script = {"opening": "Introduce yourself and confirm this is a good time.", "qualification": ["Business type", "Location", "Product interest"], "need": request.reason, "offer": "Use only approved Product/Sales facts.", "objection": "Use approved policies; do not invent discounts.", "cta": "Agree on one next step.", "next_step": "FOLLOW_UP"}
        return self.repository.add(TelesalesTask(call_task_uid=uid("CALL"), conversation_id=conversation.id if conversation else None, customer_id=customer.id if customer else None, lead_uid=request.lead_uid or (conversation.lead_uid if conversation else None), reason=request.reason, priority=request.priority.upper(), script=script, next_action="CALL_CUSTOMER", due_at=request.due_at, owner=request.owner, qualification_state="NEW", status="OPEN"))


class SalesDraftService:
    def __init__(self, session: Session) -> None: self.repository = AnswerBotRepository(session); self.sales = SalesRepository(session)

    def quote(self, request: QuoteDraftCreate) -> QuoteDraft:
        conversation = ConversationService(self.repository.session).get(request.conversation_id); product = ProductService(self.repository.session).get(request.product_id)
        customer = self.sales.get_customer(conversation.customer_id) if conversation.customer_id else None
        price = None; currency = "EGP"; approval = request.discount > 0
        if customer and customer.default_pricebook_id:
            try:
                line = PricingService(self.repository.session).get_price(customer.default_pricebook_id, product.id, request.quantity); price = line.net_price; currency = self.sales.get_pricebook(customer.default_pricebook_id).currency
            except Exception: pass
        subtotal = money(price * request.quantity) if price is not None else None; total = money(subtotal - request.discount + request.delivery) if subtotal is not None else None
        return self.repository.add(QuoteDraft(quote_uid=uid("QUOTE"), conversation_id=conversation.id, customer_id=conversation.customer_id, lines=[{"product_uid": product.product_uid, "sku": product.sku, "quantity": str(request.quantity), "unit_price": str(price) if price is not None else None}], currency=currency, subtotal=subtotal, discount=money(request.discount), tax=None, delivery=money(request.delivery), total=total, valid_until=datetime.now(UTC) + timedelta(days=request.validity_days), status="PENDING_REVIEW" if approval or price is None else "DRAFT", approval_required=approval or price is None))

    def order_draft(self, request: OrderDraftCreate) -> OrderDraft:
        conversation = ConversationService(self.repository.session).get(request.conversation_id); product = ProductService(self.repository.session).get(request.product_id)
        return self.repository.add(OrderDraft(order_draft_uid=uid("ODRAFT"), conversation_id=conversation.id, customer_id=conversation.customer_id, requested_lines=[{"product_uid": product.product_uid, "sku": product.sku, "quantity": str(request.quantity)}], address=request.address, delivery_option=request.delivery_option, status="DRAFT", customer_confirmed=False))

    def confirm_order_draft(self, identifier: int | str) -> OrderDraft:
        item = self.repository.get_order_draft(identifier)
        if item is None: raise NotFoundError(f"Order draft {identifier} was not found")
        item.customer_confirmed = True; item.status = "READY_FOR_SALES_REVIEW"
        return item
