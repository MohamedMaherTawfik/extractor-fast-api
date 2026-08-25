"""End-to-end Answer Bot orchestration with conservative send decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from backend.answer_bot.config import get_answer_bot_config
from backend.answer_bot.conversations import ConversationService, MessageIngestionService
from backend.answer_bot.intent import EntityExtractionService, IntentClassifier
from backend.answer_bot.response import (
    BusinessContextService, ConversationPromptCompiler, ResponseGenerator,
    ResponsePlanner, ResponseValidator,
)
from backend.answer_bot.workflows import CRMExtractionService, ConsentService, HumanHandoffService, MessageQueueService
from backend.core.exceptions import MessagingValidationError
from backend.db.models.answer_bot import BotDecision, EntityExtraction, IntentResult, ResponsePlan
from backend.repositories.answer_bot_repository import AnswerBotRepository
from backend.sales.common import json_safe, uid


class AnswerBotEngine:
    def __init__(self, session: Session) -> None:
        self.repository = AnswerBotRepository(session); self.ingestion = MessageIngestionService(session); self.config = get_answer_bot_config()

    def process(self, message_id: int | str, *, dry_run: bool = False, force_human_review: bool = False) -> dict[str, Any]:
        message = self.ingestion.get_message(message_id)
        if message.direction != "INBOUND": raise MessagingValidationError("Answer Bot processes inbound messages only")
        existing = self.repository.latest_decision(message.id)
        if existing:
            response = self.repository.get_message(existing.response_message_id) if existing.response_message_id else None
            return self._result(message, existing, response, duplicate=True, dry_run=dry_run)
        conversation = ConversationService(self.repository.session).get(message.conversation_id); contact = self.repository.get_contact(conversation.contact_id)
        analysis = IntentClassifier().classify(message.text or "", message.media)
        intent_record = self.repository.add(IntentResult(intent_uid=uid("INTENT"), message_id=message.id, primary_intent=analysis.primary, secondary_intents=analysis.secondary, confidence=analysis.confidence, sentiment=analysis.sentiment, urgency=analysis.urgency, complaint_type=analysis.complaint_type, complaint_severity=analysis.complaint_severity, classifier="config_taxonomy", classifier_version=self.config["version"]))
        ConversationService(self.repository.session).event(conversation, "answer_bot", "INTENT_CLASSIFIED", {"primary": analysis.primary, "secondary": analysis.secondary, "confidence": str(analysis.confidence)})
        entity_values = EntityExtractionService(self.repository.session).extract(message.text or "", customer_id=conversation.customer_id)
        for value in entity_values:
            self.repository.add(EntityExtraction(entity_uid=uid("ENTITY"), message_id=message.id, entity_type=value["type"], raw_value=value["raw"], normalized_value=value.get("normalized"), confidence=value["confidence"], validation_status=value["status"], source_span={"candidates": value.get("candidates", []), "product_id": value.get("product_id"), "order_id": value.get("order_id"), "invoice_id": value.get("invoice_id")}))
        state = self.repository.get_state(conversation.id); state.current_intent = analysis.primary
        product_entity = next((item for item in entity_values if item["type"] == "PRODUCT" and item.get("status") == "VALID"), None)
        qty_entity = next((item for item in entity_values if item["type"] == "QUANTITY"), None)
        if product_entity: state.selected_product_id = product_entity["product_id"]; state.requested_product = product_entity["raw"]
        if qty_entity: state.requested_qty = Decimal(qty_entity["normalized"])
        context = BusinessContextService(self.repository.session).build(conversation, contact, analysis.primary, entity_values, message)
        ConversationService(self.repository.session).event(conversation, "answer_bot", "CONTEXT_LOADED", {"tools": context["tools_used"]})
        plan_values = ResponsePlanner().plan(intent=analysis.primary, confidence=analysis.confidence, context=context, injection=analysis.prompt_injection, medical=analysis.medical, force_human=force_human_review)
        try:
            draft_text, provider = ResponseGenerator().generate(intent=analysis.primary, language=message.language, context=context, plan=plan_values, injection=analysis.prompt_injection)
            provider_failed = False
        except Exception:
            draft_text = "A team member will review your message and respond safely."; provider = "safe_template_fallback"; provider_failed = True; plan_values["human_review_required"] = True; plan_values["auto_send_allowed"] = False
        prompt = ConversationPromptCompiler().compile(conversation=conversation, recent_messages=self.repository.conversation_messages(conversation.id), intent=analysis.primary, entities=entity_values, context=context, draft_text=draft_text)
        validation = ResponseValidator().validate(text=draft_text, intent=analysis.primary, context=context, plan=plan_values, injection=analysis.prompt_injection, medical=analysis.medical)
        if provider_failed: validation = {"status": "HUMAN_REVIEW", "auto_send": False, "results": [*validation["results"], {"code": "PROVIDER_FAILURE", "result": "HUMAN_REVIEW", "message": "Safe local fallback used"}]}
        auto_send = validation["auto_send"] and not dry_run
        plan = self.repository.add(ResponsePlan(plan_uid=uid("RPLAN"), conversation_id=conversation.id, source_message_id=message.id, intent=analysis.primary, required_facts=plan_values["required_facts"], business_queries=plan_values["business_queries"], response_tone=plan_values["response_tone"], allowed_claims=plan_values["allowed_claims"], cta=plan_values["cta"], follow_up_needed=plan_values["follow_up_needed"], auto_send_allowed=plan_values["auto_send_allowed"], human_review_required=plan_values["human_review_required"], tools_allowed=plan_values["tools_allowed"], context=json_safe(context)))
        response_status = "APPROVED" if auto_send else "DRAFT" if dry_run else "PENDING_REVIEW"
        response = self.ingestion.create_outbound(conversation, draft_text, actor="answer_bot", status=response_status, idempotency_key=f"bot:{message.message_uid}", provider=provider)
        reason = "AUTO_SEND_APPROVED" if auto_send else "DRY_RUN_NO_SEND" if dry_run else f"AUTO_SEND_BLOCKED:{validation['status']}"
        provenance = {"provider": provider, "prompt_version": self.config["prompt_version"], "rules_version": self.config["version"], "knowledge": [{"knowledge_uid": item["knowledge_uid"], "version": item["version"]} for item in context.get("knowledge", [])], "business_records": {key: context.get(key) for key in ("product", "price", "stock", "order", "delivery") if context.get(key) is not None}, "tools": context["tools_used"], "privacy_mode": conversation.privacy_mode}
        decision = self.repository.add(BotDecision(decision_uid=uid("BDEC"), conversation_id=conversation.id, source_message_id=message.id, response_message_id=response.id, intent=analysis.primary, auto_send=auto_send, human_review=not auto_send, reason=reason, rule_refs=["NO_UNSOURCED_PRICE", "NO_UNSOURCED_STOCK", "NO_MEDICAL_DIAGNOSIS", "NO_PAYMENT_DISPUTE_AUTOSEND"], confidence=analysis.confidence, validation_status=validation["status"], validation_results=validation["results"], provenance=json_safe(provenance), prompt_version=self.config["prompt_version"], provider=provider))
        state.human_required = not auto_send; state.pending_action = "SEND_RESPONSE" if auto_send else "HUMAN_REVIEW"; state.pricing_context = context.get("price") or {}; state.delivery_context = context.get("delivery") or {}
        CRMExtractionService(self.repository.session).create(conversation_id=conversation.id, message_id=message.id, intent=analysis.primary, confidence=analysis.confidence, entities=entity_values)
        if analysis.opt_out: ConsentService(self.repository.session).update(contact.id, purpose="MARKETING", status="OPTED_OUT", basis="CUSTOMER_REQUEST", source_message_uid=message.message_uid)
        if auto_send:
            ConversationService(self.repository.session).event(conversation, "answer_bot", "AUTO_SEND_APPROVED", {"decision_uid": decision.decision_uid}); MessageQueueService(self.repository.session).enqueue(response.id, "answer_bot"); MessageQueueService(self.repository.session).process(limit=1)
        else:
            conversation.status = "WAITING_AGENT" if not dry_run else conversation.status
            if not dry_run and (analysis.primary in {"COMPLAINT", "PAYMENT_QUERY", "BALANCE_QUERY", "MEDICAL_CONCERN"} or analysis.prompt_injection or provider_failed):
                queue = "PAYMENTS" if analysis.primary in {"PAYMENT_QUERY", "BALANCE_QUERY"} else "MANAGER" if analysis.prompt_injection else "CUSTOMER_SERVICE"
                HumanHandoffService(self.repository.session).create(conversation.id, reason=reason, priority="CRITICAL" if analysis.complaint_severity == "CRITICAL" else "HIGH", assigned_queue=queue, actor="answer_bot", relevant_order_id=next((item.get("order_id") for item in entity_values if item["type"] == "ORDER"), None))
        ConversationService(self.repository.session).event(conversation, "answer_bot", "DRAFT_CREATED", {"message_uid": response.message_uid, "validation": validation["status"]})
        return self._result(message, decision, response, duplicate=False, dry_run=dry_run)

    def validate_draft(self, message_id: int | str, draft_text: str) -> dict[str, Any]:
        message = self.ingestion.get_message(message_id); decision = self.repository.latest_decision(message.id); plan = self.repository.latest_plan(message.id)
        if not decision or not plan: raise MessagingValidationError("Message has not been processed")
        context = plan.context; injection = any(item["code"] == "PROMPT_INJECTION" for item in decision.validation_results); medical = decision.intent == "MEDICAL_CONCERN"
        return ResponseValidator().validate(text=draft_text, intent=decision.intent, context=context, plan={"human_review_required": plan.human_review_required, "auto_send_allowed": plan.auto_send_allowed}, injection=injection, medical=medical)

    @staticmethod
    def _result(message, decision, response, *, duplicate: bool, dry_run: bool) -> dict[str, Any]:
        return {"source_message_uid": message.message_uid, "decision_uid": decision.decision_uid, "intent": decision.intent, "confidence": decision.confidence, "draft_message_uid": response.message_uid if response else None, "draft": response.text if response else None, "validation": decision.validation_status, "validation_results": decision.validation_results, "auto_send": decision.auto_send, "human_review": decision.human_review, "reason": decision.reason, "provenance": decision.provenance, "duplicate": duplicate, "dry_run": dry_run}
