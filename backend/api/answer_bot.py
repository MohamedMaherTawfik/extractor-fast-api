"""Local-first conversation, Answer Bot, queue, knowledge, and CRM APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.answer_bot.channels import ChannelRegistry
from backend.answer_bot.conversations import ConversationService, MessageIngestionService
from backend.answer_bot.engine import AnswerBotEngine
from backend.answer_bot.knowledge import KnowledgeBaseService
from backend.answer_bot.workflows import (
    ConsentService, FollowUpService, HumanHandoffService, MessageQueueService,
    SalesDraftService, TelesalesService,
)
from backend.core.exceptions import NotFoundError
from backend.db.session import get_db
from backend.repositories.answer_bot_repository import AnswerBotRepository
from backend.sales.common import model_dict
from backend.schemas.answer_bot import (
    BotDraftRequest, BotProcessRequest, BotValidateRequest, ConsentUpdate,
    ConversationAssignRequest, ConversationReplyRequest,
    ConversationResolveRequest, CRMReview, DeliveryEventRequest,
    FollowUpCancel, FollowUpCreate, HandoffCreate, InboundMessageRequest,
    KnowledgeCreate, KnowledgeUpdate, MessageApprovalRequest,
    MessageEditRequest, MessageSendRequest, OrderDraftConfirm, OrderDraftCreate,
    QuoteDraftCreate, TelesalesTaskCreate,
)


router = APIRouter(tags=["answer-bot"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _rows(items): return [model_dict(item) for item in items]


@router.get("/messaging/channels")
def messaging_channels(): return ChannelRegistry().status()


@router.post("/messages/inbound/mock", status_code=status.HTTP_201_CREATED)
def inbound_mock(request: InboundMessageRequest, session: DatabaseSession):
    # This development endpoint must never be used as an implicit live-channel
    # connector. Website and future provider webhooks get their own adapters.
    request.channel = "mock"
    message, duplicate = MessageIngestionService(session).ingest(request)
    result = AnswerBotEngine(session).process(message.id, dry_run=request.dry_run) if request.auto_process else None
    return {"message": model_dict(message), "duplicate": duplicate, "bot": result}


@router.get("/conversations")
def list_conversations(session: DatabaseSession, conversation_status: str | None = Query(None, alias="status"), q: str | None = None, limit: int = Query(100, ge=1, le=1000)):
    return _rows(ConversationService(session).list(status=conversation_status, query=q, limit=limit))


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, session: DatabaseSession):
    service = ConversationService(session); conversation = service.get(conversation_id); repository = AnswerBotRepository(session)
    messages = repository.conversation_messages(conversation.id)
    return {**model_dict(conversation), "contact": model_dict(repository.get_contact(conversation.contact_id)), "state": model_dict(repository.get_state(conversation.id)), "messages": [{**model_dict(item), "attachments": _rows(repository.message_attachments(item.id))} for item in messages], "events": _rows(repository.events(conversation.id)), "handoff": model_dict(repository.open_handoff(conversation.id)) if repository.open_handoff(conversation.id) else None}


@router.post("/conversations/{conversation_id}/reply")
def conversation_reply(conversation_id: str, request: ConversationReplyRequest, session: DatabaseSession):
    conversation = ConversationService(session).get(conversation_id); ingestion = MessageIngestionService(session)
    message = ingestion.create_outbound(conversation, request.text, actor=request.actor, status="APPROVED" if request.auto_send else "DRAFT", idempotency_key=request.idempotency_key)
    if request.auto_send: MessageQueueService(session).enqueue(message.id, request.actor); MessageQueueService(session).process(limit=1)
    return model_dict(message)


@router.post("/conversations/{conversation_id}/assign")
def assign_conversation(conversation_id: str, request: ConversationAssignRequest, session: DatabaseSession): return model_dict(ConversationService(session).assign(conversation_id, **request.model_dump()))


@router.post("/conversations/{conversation_id}/resolve")
def resolve_conversation(conversation_id: str, request: ConversationResolveRequest, session: DatabaseSession): return model_dict(ConversationService(session).resolve(conversation_id, **request.model_dump()))


@router.post("/conversations/{conversation_id}/handoff")
def handoff_conversation(conversation_id: str, request: HandoffCreate, session: DatabaseSession): return model_dict(HumanHandoffService(session).create(conversation_id, **request.model_dump()))


@router.post("/answer-bot/process")
def process_message(request: BotProcessRequest, session: DatabaseSession): return AnswerBotEngine(session).process(request.message_id, dry_run=request.dry_run, force_human_review=request.force_human_review)


@router.post("/answer-bot/draft")
def draft_message(request: BotDraftRequest, session: DatabaseSession): return AnswerBotEngine(session).process(request.message_id, dry_run=True)


@router.post("/answer-bot/validate")
def validate_message(request: BotValidateRequest, session: DatabaseSession): return AnswerBotEngine(session).validate_draft(request.message_id, request.draft_text)


@router.post("/messages/{message_id}/approve")
def approve_message(message_id: str, request: MessageApprovalRequest, session: DatabaseSession): return model_dict(MessageQueueService(session).approve(message_id, request.approved_by))


@router.patch("/messages/{message_id}")
def edit_message(message_id: str, request: MessageEditRequest, session: DatabaseSession): return model_dict(MessageIngestionService(session).edit(message_id, **request.model_dump()))


@router.post("/messages/{message_id}/send")
def send_message(message_id: str, request: MessageSendRequest, session: DatabaseSession):
    queue = MessageQueueService(session); message = MessageIngestionService(session).get_message(message_id)
    if message.status == "DRAFT": queue.approve(message.id, request.actor)
    queue.enqueue(message.id, request.actor); queue.process(limit=1); return model_dict(message)


@router.post("/messages/{message_id}/cancel")
def cancel_message(message_id: str, request: MessageSendRequest, session: DatabaseSession): return model_dict(MessageQueueService(session).cancel(message_id, request.actor))


@router.post("/messages/{message_id}/delivery-events")
def message_delivery(message_id: str, request: DeliveryEventRequest, session: DatabaseSession): return model_dict(MessageQueueService(session).delivery_event(message_id, **request.model_dump()))


@router.post("/outbound-queue/run")
def run_outbound_queue(session: DatabaseSession): return _rows(MessageQueueService(session).process())


@router.post("/followups", status_code=status.HTTP_201_CREATED)
def create_followup(request: FollowUpCreate, session: DatabaseSession): return model_dict(FollowUpService(session).create(request))


@router.get("/followups")
def list_followups(session: DatabaseSession, followup_status: str | None = Query(None, alias="status")): return _rows(AnswerBotRepository(session).list_followups(followup_status))


@router.post("/followups/{followup_id}/cancel")
def cancel_followup(followup_id: str, request: FollowUpCancel, session: DatabaseSession): return model_dict(FollowUpService(session).cancel(followup_id, request.actor, request.reason))


@router.post("/followups/run")
def run_followups(session: DatabaseSession): return _rows(FollowUpService(session).run_due())


@router.post("/contacts/{contact_id}/consent")
def update_consent(contact_id: str, request: ConsentUpdate, session: DatabaseSession): return model_dict(ConsentService(session).update(contact_id, purpose=request.purpose, status=request.status, basis=request.basis))


@router.get("/knowledge")
def list_knowledge(session: DatabaseSession, domain: str | None = None):
    service = KnowledgeBaseService(session); return [{**model_dict(item), "versions": _rows(service.repository.knowledge_versions(item.id))} for item in service.repository.list_knowledge(domain)]


@router.post("/knowledge", status_code=status.HTTP_201_CREATED)
def create_knowledge(request: KnowledgeCreate, session: DatabaseSession): return model_dict(KnowledgeBaseService(session).create(request))


@router.patch("/knowledge/{knowledge_id}")
def update_knowledge(knowledge_id: str, request: KnowledgeUpdate, session: DatabaseSession): return model_dict(KnowledgeBaseService(session).update(knowledge_id, request))


@router.get("/knowledge/search")
def search_knowledge(session: DatabaseSession, q: str, domain: str | None = None, language: str | None = None): return KnowledgeBaseService(session).retrieve(q, domain=domain, language=language)


@router.get("/crm/signals")
def list_crm_signals(session: DatabaseSession, signal_status: str | None = Query(None, alias="status")): return _rows(AnswerBotRepository(session).list_signals(signal_status))


@router.post("/crm/signals/{signal_id}/review")
def review_crm_signal(signal_id: str, request: CRMReview, session: DatabaseSession):
    signal = AnswerBotRepository(session).get_signal(signal_id)
    if signal is None: raise NotFoundError(f"CRM signal {signal_id} was not found")
    signal.status = request.status.upper(); signal.reviewed_by = request.reviewed_by; return model_dict(signal)


@router.post("/telesales/tasks", status_code=status.HTTP_201_CREATED)
def create_telesales_task(request: TelesalesTaskCreate, session: DatabaseSession): return model_dict(TelesalesService(session).create(request))


@router.post("/quotes/drafts", status_code=status.HTTP_201_CREATED)
def create_quote_draft(request: QuoteDraftCreate, session: DatabaseSession): return model_dict(SalesDraftService(session).quote(request))


@router.post("/orders/drafts", status_code=status.HTTP_201_CREATED)
def create_order_draft(request: OrderDraftCreate, session: DatabaseSession): return model_dict(SalesDraftService(session).order_draft(request))


@router.post("/orders/drafts/{draft_id}/confirm")
def confirm_order_draft(draft_id: str, request: OrderDraftConfirm, session: DatabaseSession): return model_dict(SalesDraftService(session).confirm_order_draft(draft_id))
