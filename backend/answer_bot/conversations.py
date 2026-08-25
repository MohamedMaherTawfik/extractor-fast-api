"""Contact resolution, normalized message ingestion, conversation state, and audit."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath

from sqlalchemy.orm import Session

from backend.answer_bot.config import get_answer_bot_config
from backend.answer_bot.intent import detect_language
from backend.core.exceptions import ConflictError, MessagingValidationError, NotFoundError
from backend.core.paths import paths
from backend.db.models.answer_bot import Contact, Conversation, ConversationEvent, ConversationState, Message, MessageAttachment, MessageEdit
from backend.repositories.answer_bot_repository import AnswerBotRepository
from backend.repositories.sales_repository import SalesRepository
from backend.sales.common import stable_hash, uid
from backend.schemas.answer_bot import InboundMessageRequest


def normalize_phone(value: str | None) -> str | None:
    if not value: return None
    plus = value.strip().startswith("+"); digits = "".join(re.findall(r"\d", value))
    return ("+" if plus else "") + digits if digits else None


class ConversationService:
    def __init__(self, session: Session) -> None:
        self.repository = AnswerBotRepository(session); self.sales = SalesRepository(session); self.config = get_answer_bot_config()

    def get(self, identifier: int | str) -> Conversation:
        item = self.repository.get_conversation(identifier)
        if item is None: raise NotFoundError(f"Conversation {identifier} was not found")
        return item

    def list(self, *, status: str | None = None, query: str | None = None, limit: int = 100) -> list[Conversation]: return self.repository.list_conversations(status=status, query=query, limit=limit)

    def assign(self, identifier: int | str, *, actor: str, assigned_to: str | None, assigned_queue: str | None) -> Conversation:
        conversation = self.get(identifier); conversation.assigned_to = assigned_to; conversation.assigned_queue = assigned_queue
        if assigned_to or assigned_queue: conversation.status = "WAITING_AGENT"
        self.event(conversation, actor, "CONVERSATION_ASSIGNED", {"assigned_to": assigned_to, "assigned_queue": assigned_queue})
        return conversation

    def resolve(self, identifier: int | str, *, actor: str, resolution: str | None = None) -> Conversation:
        conversation = self.get(identifier); conversation.status = "RESOLVED"; conversation.resolved_at = datetime.now(UTC)
        self.event(conversation, actor, "CONVERSATION_RESOLVED", {"resolution": resolution})
        return conversation

    def event(self, conversation: Conversation, actor: str, event_type: str, payload: dict | None = None) -> ConversationEvent:
        return self.repository.add(ConversationEvent(event_uid=uid("CEVT"), conversation_id=conversation.id, actor=actor, event_type=event_type, payload=payload or {}))


class ContactResolutionService:
    def __init__(self, session: Session) -> None: self.repository = AnswerBotRepository(session); self.sales = SalesRepository(session)

    def resolve(self, request: InboundMessageRequest) -> Contact:
        channel = request.channel.lower(); existing = self.repository.contact_by_external(channel, request.sender)
        if existing: return existing
        phone = normalize_phone(request.phone); email = request.email.strip().lower() if request.email else None
        customer = self.sales.get_customer(request.customer_code) if request.customer_code else None
        if customer is None:
            candidates = [item for item in self.sales.list_customers() if (phone and normalize_phone(item.phone) == phone) or (email and item.email and item.email.casefold() == email)]
            customer = candidates[0] if len(candidates) == 1 else None
        return self.repository.add(Contact(contact_uid=uid("CONTACT"), channel=channel, external_contact_id=request.sender.strip(), display_name=request.display_name, phone=phone, email=email, customer_id=customer.id if customer else None, lead_uid=request.lead_uid, preferred_language=None, communication_preferences={}, crm_memory={}, do_not_contact=False))


class MessageIngestionService:
    def __init__(self, session: Session) -> None:
        self.repository = AnswerBotRepository(session); self.conversations = ConversationService(session); self.config = get_answer_bot_config()

    def get_message(self, identifier: int | str) -> Message:
        item = self.repository.get_message(identifier)
        if item is None: raise NotFoundError(f"Message {identifier} was not found")
        return item

    def ingest(self, request: InboundMessageRequest) -> tuple[Message, bool]:
        channel = request.channel.lower()
        existing = self.repository.message_by_external(channel, request.external_message_id)
        if existing: return existing, True
        media = self._validated_media(request.media)
        contact = ContactResolutionService(self.repository.session).resolve(request)
        conversation = self.repository.conversation_by_thread(channel, request.external_thread_id)
        language, confidence = detect_language(request.text or "")
        now = request.timestamp
        if conversation is None:
            sla = self.config["sla_minutes"]
            conversation = self.repository.add(Conversation(conversation_uid=uid("CONV"), channel=channel, external_thread_id=request.external_thread_id, contact_id=contact.id, customer_id=contact.customer_id, lead_uid=contact.lead_uid, status="NEW", priority="NORMAL", language=language, language_confidence=confidence, automation_level=self.config["automation_level"], privacy_mode=self.config["privacy_mode"], started_at=now, last_message_at=now, last_inbound_at=now, first_response_due_at=now + timedelta(minutes=sla["first_response"]), resolution_due_at=now + timedelta(minutes=sla["resolution"])))
            self.repository.add(ConversationState(conversation_id=conversation.id, pricing_context={}, delivery_context={}, human_required=False, memory={}))
        elif conversation.contact_id != contact.id:
            raise ConflictError("External thread is already linked to a different contact")
        key = stable_hash({"channel": channel, "external_message_id": request.external_message_id})
        message = self.repository.add(Message(message_uid=uid("MSG"), conversation_id=conversation.id, channel=channel, external_message_id=request.external_message_id, external_thread_id=request.external_thread_id, direction="INBOUND", sender=request.sender, recipient=request.recipient, text=request.text, media=media, reply_to_message_uid=request.reply_to, language=language, language_confidence=confidence, timestamp=now, metadata_json=request.metadata, status="RECEIVED", idempotency_key=key, max_attempts=self.config["max_send_attempts"]))
        for item in media:
            if item.get("relative_path"):
                self.repository.add(MessageAttachment(attachment_uid=uid("ATT"), message_id=message.id, attachment_type=str(item.get("type", "file"))[:40], original_name=str(item.get("name") or PurePosixPath(item["relative_path"]).name)[:255], relative_path=item["relative_path"], mime_type=str(item.get("mime_type", "application/octet-stream"))[:100], checksum=str(item.get("checksum") or stable_hash(item)), size_bytes=max(0, int(item.get("size_bytes", 0))), derived_text=item.get("derived_text"), safety_status=str(item.get("safety_status", "PENDING_SCAN"))[:30]))
        conversation.last_message_at = now; conversation.last_inbound_at = now; conversation.language = language; conversation.language_confidence = confidence
        if conversation.status in {"NEW", "WAITING_CUSTOMER", "RESOLVED"}: conversation.status = "OPEN"
        self.conversations.event(conversation, "channel", "MESSAGE_RECEIVED", {"message_uid": message.message_uid, "channel": channel})
        return message, False

    @staticmethod
    def _validated_media(items: list[dict]) -> list[dict]:
        validated = []
        for raw in items:
            item = dict(raw)
            supplied_path = item.get("relative_path") or item.get("path")
            if supplied_path:
                try:
                    relative = paths.validate_storage_value(str(supplied_path))
                    resolved = paths.resolve_under(paths.media, relative)
                except ValueError as exc:
                    raise MessagingValidationError("Attachment path must remain inside managed media storage") from exc
                item.pop("path", None)
                item["relative_path"] = paths.relative(resolved).as_posix()
                item["name"] = PurePosixPath(str(item.get("name") or relative).replace("\\", "/")).name[:255]
            validated.append(item)
        return validated

    def create_outbound(self, conversation: Conversation, text: str, *, actor: str, status: str = "DRAFT", idempotency_key: str | None = None, provider: str | None = None) -> Message:
        key = idempotency_key or stable_hash({"conversation": conversation.conversation_uid, "text": text, "actor": actor})
        existing = self.repository.message_by_idempotency(key)
        if existing: return existing
        outbound_hash = stable_hash({"channel": conversation.channel, "thread": conversation.external_thread_id, "text": text, "key": key})
        duplicate = self.repository.message_by_outbound_hash(outbound_hash)
        if duplicate: return duplicate
        now = datetime.now(UTC)
        return self.repository.add(Message(message_uid=uid("MSG"), conversation_id=conversation.id, channel=conversation.channel, external_message_id=f"local_{uid('OUT')}", external_thread_id=conversation.external_thread_id, direction="AGENT" if actor != "answer_bot" else "OUTBOUND", sender=actor, recipient=None, text=text, media=[], timestamp=now, metadata_json={}, status=status, idempotency_key=key, outbound_hash=outbound_hash, max_attempts=self.config["max_send_attempts"], provider=provider))

    def edit(self, identifier: int | str, *, text: str, edited_by: str, feedback: str | None = None) -> Message:
        message = self.get_message(identifier)
        if message.direction == "INBOUND" or message.status in {"SENT", "DELIVERED", "READ", "CANCELLED"}: raise MessagingValidationError("Message cannot be edited in its current state")
        old = message.text; message.text = text; message.outbound_hash = stable_hash({"message_uid": message.message_uid, "text": text})
        self.repository.add(MessageEdit(edit_uid=uid("EDIT"), message_id=message.id, old_text=old, new_text=text, diff={"changed": old != text}, edited_by=edited_by, feedback=feedback))
        return message
