"""Persistence boundary for conversations, messages, decisions, and CRM signals."""

from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.db.models.answer_bot import (
    AgentNote, BotDecision, ChannelAccount, Contact, Conversation,
    ConversationEvent, ConversationState, ConversationSummary, CRMSignal,
    EntityExtraction, FollowUp, HandoffRequest, IntentResult, KnowledgeItem,
    KnowledgeVersion, MarketingConsent, Message, MessageDeliveryEvent,
    MessageAttachment, MessageEdit, OrderDraft, QuoteDraft, ResponsePlan, ResponseTemplate,
    TelesalesTask, TemplateVersion, WebhookEvent,
)


T = TypeVar("T")


class AnswerBotRepository:
    def __init__(self, session: Session) -> None: self.session = session

    def add(self, item: T) -> T:
        self.session.add(item); self.session.flush(); return item

    def flush(self) -> None: self.session.flush()

    def get_contact(self, identifier: int | str) -> Contact | None:
        predicate = Contact.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else Contact.contact_uid == str(identifier)
        return self.session.scalar(select(Contact).where(predicate))

    def contact_by_external(self, channel: str, external_id: str) -> Contact | None:
        return self.session.scalar(select(Contact).where(Contact.channel == channel, Contact.external_contact_id == external_id))

    def contact_by_phone_email(self, phone: str | None, email: str | None) -> list[Contact]:
        predicates = []
        if phone: predicates.append(Contact.phone == phone)
        if email: predicates.append(Contact.email == email.lower())
        if not predicates: return []
        return list(self.session.scalars(select(Contact).where(or_(*predicates))))

    def get_conversation(self, identifier: int | str) -> Conversation | None:
        predicate = Conversation.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else Conversation.conversation_uid == str(identifier)
        return self.session.scalar(select(Conversation).where(predicate))

    def conversation_by_thread(self, channel: str, thread_id: str) -> Conversation | None:
        return self.session.scalar(select(Conversation).where(Conversation.channel == channel, Conversation.external_thread_id == thread_id))

    def list_conversations(self, *, status: str | None = None, query: str | None = None, limit: int = 100) -> list[Conversation]:
        statement = select(Conversation)
        if status: statement = statement.where(Conversation.status == status.upper())
        if query:
            message_conversations = select(Message.conversation_id).where(Message.text.ilike(f"%{query}%"))
            statement = statement.join(Contact, Contact.id == Conversation.contact_id).where(or_(Conversation.conversation_uid.ilike(f"%{query}%"), Contact.phone.ilike(f"%{query}%"), Contact.email.ilike(f"%{query}%"), Conversation.id.in_(message_conversations)))
        return list(self.session.scalars(statement.order_by(Conversation.last_message_at.desc()).limit(limit)))

    def get_message(self, identifier: int | str) -> Message | None:
        predicate = Message.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else Message.message_uid == str(identifier)
        return self.session.scalar(select(Message).where(predicate))

    def message_by_external(self, channel: str, external_id: str) -> Message | None:
        return self.session.scalar(select(Message).where(Message.channel == channel, Message.external_message_id == external_id))

    def message_by_idempotency(self, key: str) -> Message | None:
        return self.session.scalar(select(Message).where(Message.idempotency_key == key))

    def message_by_outbound_hash(self, value: str) -> Message | None:
        return self.session.scalar(select(Message).where(Message.outbound_hash == value))

    def conversation_messages(self, conversation_id: int, *, limit: int = 50) -> list[Message]:
        rows = list(self.session.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.timestamp.desc()).limit(limit)))
        return list(reversed(rows))

    def message_attachments(self, message_id: int) -> list[MessageAttachment]:
        return list(self.session.scalars(select(MessageAttachment).where(MessageAttachment.message_id == message_id).order_by(MessageAttachment.id)))

    def queued_messages(self, *, now: datetime, limit: int = 100) -> list[Message]:
        return list(self.session.scalars(select(Message).where(Message.status.in_(("QUEUED", "RETRYING")), or_(Message.next_attempt_at.is_(None), Message.next_attempt_at <= now)).order_by(Message.created_at).limit(limit)))

    def get_state(self, conversation_id: int) -> ConversationState | None:
        return self.session.scalar(select(ConversationState).where(ConversationState.conversation_id == conversation_id))

    def latest_intent(self, message_id: int) -> IntentResult | None:
        return self.session.scalar(select(IntentResult).where(IntentResult.message_id == message_id).order_by(IntentResult.id.desc()))

    def entities(self, message_id: int) -> list[EntityExtraction]:
        return list(self.session.scalars(select(EntityExtraction).where(EntityExtraction.message_id == message_id).order_by(EntityExtraction.id)))

    def latest_plan(self, message_id: int) -> ResponsePlan | None:
        return self.session.scalar(select(ResponsePlan).where(ResponsePlan.source_message_id == message_id).order_by(ResponsePlan.id.desc()))

    def latest_decision(self, message_id: int) -> BotDecision | None:
        return self.session.scalar(select(BotDecision).where(BotDecision.source_message_id == message_id).order_by(BotDecision.id.desc()))

    def open_handoff(self, conversation_id: int) -> HandoffRequest | None:
        return self.session.scalar(select(HandoffRequest).where(HandoffRequest.conversation_id == conversation_id, HandoffRequest.status == "OPEN"))

    def get_followup(self, identifier: int | str) -> FollowUp | None:
        predicate = FollowUp.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else FollowUp.followup_uid == str(identifier)
        return self.session.scalar(select(FollowUp).where(predicate))

    def list_followups(self, status: str | None = None) -> list[FollowUp]:
        statement = select(FollowUp)
        if status: statement = statement.where(FollowUp.status == status.upper())
        return list(self.session.scalars(statement.order_by(FollowUp.scheduled_at)))

    def due_followups(self, now: datetime) -> list[FollowUp]:
        return list(self.session.scalars(select(FollowUp).where(FollowUp.status == "SCHEDULED", FollowUp.scheduled_at <= now).order_by(FollowUp.scheduled_at)))

    def consent(self, contact_id: int, channel: str, purpose: str) -> MarketingConsent | None:
        return self.session.scalar(select(MarketingConsent).where(MarketingConsent.contact_id == contact_id, MarketingConsent.channel == channel, MarketingConsent.purpose == purpose))

    def get_knowledge(self, identifier: int | str) -> KnowledgeItem | None:
        predicate = KnowledgeItem.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else KnowledgeItem.knowledge_uid == str(identifier)
        return self.session.scalar(select(KnowledgeItem).where(predicate))

    def list_knowledge(self, domain: str | None = None) -> list[KnowledgeItem]:
        statement = select(KnowledgeItem)
        if domain: statement = statement.where(KnowledgeItem.domain == domain.upper())
        return list(self.session.scalars(statement.order_by(KnowledgeItem.title)))

    def knowledge_versions(self, knowledge_id: int) -> list[KnowledgeVersion]:
        return list(self.session.scalars(select(KnowledgeVersion).where(KnowledgeVersion.knowledge_id == knowledge_id).order_by(KnowledgeVersion.version)))

    def active_knowledge_versions(self, now: datetime) -> list[tuple[KnowledgeItem, KnowledgeVersion]]:
        statement = select(KnowledgeItem, KnowledgeVersion).join(KnowledgeVersion, KnowledgeVersion.knowledge_id == KnowledgeItem.id).where(KnowledgeItem.status == "ACTIVE", KnowledgeVersion.status == "ACTIVE", KnowledgeVersion.effective_from <= now, or_(KnowledgeVersion.effective_to.is_(None), KnowledgeVersion.effective_to >= now), KnowledgeVersion.version == KnowledgeItem.current_version)
        return list(self.session.execute(statement).all())

    def get_signal(self, identifier: int | str) -> CRMSignal | None:
        predicate = CRMSignal.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else CRMSignal.signal_uid == str(identifier)
        return self.session.scalar(select(CRMSignal).where(predicate))

    def list_signals(self, status: str | None = None) -> list[CRMSignal]:
        statement = select(CRMSignal)
        if status: statement = statement.where(CRMSignal.status == status.upper())
        return list(self.session.scalars(statement.order_by(CRMSignal.created_at.desc())))

    def summary_versions(self, conversation_id: int) -> list[ConversationSummary]:
        return list(self.session.scalars(select(ConversationSummary).where(ConversationSummary.conversation_id == conversation_id).order_by(ConversationSummary.version)))

    def events(self, conversation_id: int) -> list[ConversationEvent]:
        return list(self.session.scalars(select(ConversationEvent).where(ConversationEvent.conversation_id == conversation_id).order_by(ConversationEvent.occurred_at)))

    def webhook(self, channel: str, external_id: str) -> WebhookEvent | None:
        return self.session.scalar(select(WebhookEvent).where(WebhookEvent.channel == channel, WebhookEvent.external_event_id == external_id))

    def get_quote(self, identifier: int | str) -> QuoteDraft | None:
        predicate = QuoteDraft.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else QuoteDraft.quote_uid == str(identifier)
        return self.session.scalar(select(QuoteDraft).where(predicate))

    def get_order_draft(self, identifier: int | str) -> OrderDraft | None:
        predicate = OrderDraft.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else OrderDraft.order_draft_uid == str(identifier)
        return self.session.scalar(select(OrderDraft).where(predicate))
