"""Targeted business context, response planning/generation, and safety validation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from backend.answer_bot.config import get_answer_bot_config
from backend.answer_bot.knowledge import KnowledgeBaseService
from backend.answer_bot.providers import ProviderRegistry
from backend.db.models.answer_bot import Contact, Conversation, Message
from backend.repositories.sales_repository import SalesRepository
from backend.sales.common import json_safe
from backend.sales.context import ProductSalesContextService
from backend.sales.finance import ReceivablesService
from backend.sales.master_data import PricingService


class BusinessContextService:
    """Allow-listed read-only tools over Product/Sales and approved knowledge."""

    def __init__(self, session: Session) -> None:
        self.session = session; self.sales = SalesRepository(session); self.config = get_answer_bot_config()

    def build(self, conversation: Conversation, contact: Contact, intent: str, entities: list[dict[str, Any]], message: Message) -> dict[str, Any]:
        context: dict[str, Any] = {"retrieved_at": datetime.now(UTC), "customer": None, "product": None, "price": None, "stock": None, "order": None, "invoice": None, "balance": None, "delivery": None, "knowledge": [], "payment_evidence_only": any(item.get("type") in {"payment_screenshot", "payment_evidence"} for item in message.media), "tools_used": []}
        customer = self.sales.get_customer(contact.customer_id) if contact.customer_id else None
        if customer:
            context["customer"] = {"customer_uid": customer.customer_uid, "business_name": customer.business_name, "pricing_tier": customer.pricing_tier, "segment": customer.segment, "status": customer.status}; context["tools_used"].append("get_customer")
        product_entity = next((item for item in entities if item["type"] == "PRODUCT" and item.get("status") == "VALID"), None)
        ambiguous_product = next((item for item in entities if item["type"] == "PRODUCT" and item.get("status") == "AMBIGUOUS"), None)
        quantity_entity = next((item for item in entities if item["type"] == "QUANTITY"), None)
        qty = Decimal(quantity_entity["normalized"]) if quantity_entity else Decimal("1")
        if product_entity:
            product = self.sales.get_product(product_entity["product_id"])
            product_context = ProductSalesContextService(self.session).get_product_context(product.id)
            context["product"] = {"product_uid": product.product_uid, "sku": product.sku, "name_ar": product.product_name_ar, "name_en": product.product_name_en, "unit": product.unit, "case_size": product.case_size, "facts": product.facts, "version": product.version}; context["stock"] = product_context["stock"]; context["tools_used"].extend(["get_product", "get_stock"])
            if customer and customer.default_pricebook_id:
                try:
                    line = PricingService(self.session).get_price(customer.default_pricebook_id, product.id, qty)
                    book = self.sales.get_pricebook(customer.default_pricebook_id); context["price"] = {"amount": line.net_price, "currency": book.currency, "pricebook_uid": book.pricebook_uid, "pricebook_version": book.version, "min_qty": line.min_qty, "retrieved_at": datetime.now(UTC)}; context["tools_used"].append("get_customer_price")
                except Exception: context["price"] = None
            elif product_context["approved_price"] is not None:
                context["price"] = {"amount": product_context["approved_price"], "currency": product_context["currency"], "pricebook_uid": None, "pricebook_version": None, "min_qty": Decimal("1"), "retrieved_at": datetime.now(UTC)}; context["tools_used"].append("get_price")
        elif ambiguous_product:
            context["product"] = {"ambiguous": True, "candidates": ambiguous_product.get("candidates", [])}
        order_entity = next((item for item in entities if item["type"] == "ORDER" and item.get("status") == "VALID"), None)
        if order_entity:
            order = self.sales.get_order(order_entity["order_id"])
            if order and (not customer or order.customer_id == customer.id):
                context["order"] = {"order_uid": order.order_uid, "order_number": order.order_number, "status": order.order_status, "fulfillment_status": order.fulfillment_status, "payment_status": order.payment_status}; context["tools_used"].append("get_order")
                delivery = self.sales.delivery_for_order(order.id)
                if delivery: context["delivery"] = {"delivery_uid": delivery.delivery_uid, "status": delivery.status, "scheduled_at": delivery.scheduled_at, "delivered_at": delivery.delivered_at}; context["tools_used"].append("get_delivery")
        if intent in {"BALANCE_QUERY", "PAYMENT_QUERY"} and customer:
            context["balance"] = ReceivablesService(self.session).balance(customer.id); context["tools_used"].append("get_balance")
        context["knowledge"] = KnowledgeBaseService(self.session).retrieve(message.text or "", language=message.language, limit=3)
        if context["knowledge"]: context["tools_used"].append("search_knowledge")
        return json_safe(context)


class ConversationPromptCompiler:
    def __init__(self) -> None: self.config = get_answer_bot_config()

    def compile(self, *, conversation: Conversation, recent_messages: list[Message], intent: str, entities: list[dict], context: dict, draft_text: str) -> dict[str, Any]:
        selected = recent_messages[-self.config["max_context_messages"]:]
        messages = [{"direction": item.direction, "text": (item.text or "")[:1000], "language": item.language} for item in selected]
        return {"prompt_version": self.config["prompt_version"], "privacy_mode": conversation.privacy_mode, "channel": conversation.channel, "language": conversation.language, "intent": intent, "entities": entities, "recent_messages": messages, "business_context": context, "allowed_tools": context.get("tools_used", []), "system_policy": {"source_of_truth": "Product/Sales + approved Knowledge", "user_content_untrusted": True, "transactional_writes": False}, "draft_text": draft_text}


class ResponsePlanner:
    NEVER_AUTO = {"COMPLAINT", "PAYMENT_QUERY", "BALANCE_QUERY", "RETURN_QUERY", "MEDICAL_CONCERN", "UNKNOWN", "OPT_OUT"}

    def plan(self, *, intent: str, confidence: Decimal, context: dict, injection: bool, medical: bool, force_human: bool = False) -> dict[str, Any]:
        required = {"PRICE_QUERY": ["product", "price"], "STOCK_QUERY": ["product", "stock"], "ORDER_STATUS": ["order"], "PAYMENT_QUERY": ["customer"], "BALANCE_QUERY": ["customer", "balance"], "PRODUCT_INFO": ["product"]}.get(intent, [])
        missing = [name for name in required if context.get(name) is None]
        human = force_human or injection or medical or intent in self.NEVER_AUTO or bool(missing) or bool(context.get("product", {}).get("ambiguous") if isinstance(context.get("product"), dict) else False)
        auto = intent in get_answer_bot_config()["auto_send_intents"] and confidence >= Decimal(str(get_answer_bot_config()["intent_confidence_threshold"])) and not human
        tone = "SUPPORTIVE" if intent in {"COMPLAINT", "MEDICAL_CONCERN"} else "WHOLESALE" if intent == "WHOLESALE_QUERY" else "FRIENDLY"
        return {"intent": intent, "required_facts": required, "missing_facts": missing, "business_queries": [{"tool": tool, "permission": "READ_ONLY"} for tool in context.get("tools_used", [])], "response_tone": tone, "allowed_claims": list((context.get("product") or {}).get("facts", {}).get("approved_claims", [])) if isinstance(context.get("product"), dict) else [], "cta": "How can I help further?", "follow_up_needed": intent in {"PRICE_QUERY", "WHOLESALE_QUERY", "ORDER_CREATE_INTENT", "SALES_OBJECTION"}, "auto_send_allowed": auto, "human_review_required": human, "tools_allowed": context.get("tools_used", []), "context": context}


class ResponseGenerator:
    def __init__(self) -> None: self.providers = ProviderRegistry(); self.config = get_answer_bot_config()

    @staticmethod
    def _name(context: dict) -> str:
        product = context.get("product") or {}; return product.get("name_ar") or product.get("name_en") or product.get("sku") or "the product"

    def generate(self, *, intent: str, language: str | None, context: dict, plan: dict, injection: bool = False) -> tuple[str, str]:
        ar = language in {"ar", "mixed_ar_en"}; name = self._name(context)
        if injection: text = "لا أقدر أنفذ الطلب ده. هحوّل المحادثة لموظف للمراجعة." if ar else "I can’t follow that request. I’ll route this conversation for human review."
        elif intent == "GREETING": text = "أهلاً بحضرتك، أقدر أساعدك في المنتجات والأسعار والطلبات." if ar else "Hello! I can help with products, prices, and order information."
        elif intent == "PRICE_QUERY" and context.get("product") is None:
            text = "ممكن توضح اسم المنتج أو الـSKU علشان أجيب السعر الصحيح؟" if ar else "Please provide the product name or SKU so I can check the correct price."
        elif intent == "PRICE_QUERY" and context.get("price"):
            price = context["price"]; text = f"سعر {name} هو {price['amount']} {price['currency']}." if ar else f"The approved price for {name} is {price['amount']} {price['currency']}."
        elif intent == "PRICE_QUERY": text = "السعر غير متاح حاليًا، وهحوّل الطلب لموظف يراجعه." if ar else "PRICE_NOT_AVAILABLE. A team member needs to review this request."
        elif intent == "STOCK_QUERY" and context.get("product") is None:
            text = "ممكن توضح اسم المنتج أو الـSKU علشان أراجع المخزون؟" if ar else "Please provide the product name or SKU so I can check stock."
        elif intent == "STOCK_QUERY" and context.get("stock"):
            stock = context["stock"]; state = "OUT_OF_STOCK" if Decimal(str(stock["available"])) <= 0 else "LOW_STOCK" if Decimal(str(stock["available"])) <= 5 else "IN_STOCK"
            labels = {"OUT_OF_STOCK": "غير متوفر حاليًا", "LOW_STOCK": "متوفر بكمية محدودة", "IN_STOCK": "متوفر"}; text = f"{name}: {labels[state]}." if ar else f"{name}: {state}."
        elif intent == "ORDER_STATUS" and context.get("order"):
            order = context["order"]; text = f"حالة الطلب {order['order_number']}: {order['status']}، والتنفيذ: {order['fulfillment_status']}." if ar else f"Order {order['order_number']} is {order['status']}; fulfillment is {order['fulfillment_status']}."
        elif intent == "PAYMENT_QUERY" and context.get("payment_evidence_only"):
            text = "استلمنا صورة الدفع كدليل للمراجعة، لكنها لا تؤكد تسجيل الدفع. فريق المدفوعات هيراجعها." if ar else "We received the payment screenshot as evidence for review; it does not confirm payment. The payments team will verify it."
        elif intent == "MEDICAL_CONCERN": text = "أقدر أشارك معلومات تجميل عامة فقط، لكن لا أقدر أشخّص أو أوصي بعلاج طبي. الأفضل مراجعة طبيب مختص." if ar else "I can provide general cosmetic information, but I can’t diagnose or recommend medical treatment. Please consult a qualified clinician."
        elif intent == "OPT_OUT": text = "تم تسجيل طلب إيقاف الرسائل التسويقية." if ar else "Your marketing opt-out request has been recorded."
        elif intent == "COMPLAINT": text = "آسفين على التجربة. تم تحويل الشكوى لموظف مختص مع تفاصيل المحادثة." if ar else "We’re sorry about the experience. Your complaint has been routed to a specialist with the conversation details."
        elif context.get("knowledge"):
            text = context["knowledge"][0]["content"]
        elif context.get("product", {}).get("ambiguous") if isinstance(context.get("product"), dict) else False:
            text = "ممكن توضح اسم المنتج أو الـSKU؟" if ar else "Please clarify the product name or SKU."
        else: text = "محتاج معلومات إضافية، وهحوّل سؤالك لموظف يساعدك بدقة." if ar else "I need more information and will route this to a team member for an accurate answer."
        prompt = {"draft_text": text}; provider = self.providers.get(self.config["provider"], self.config["privacy_mode"]); return provider.generate(prompt)["text"], provider.code


class ResponseValidator:
    def __init__(self) -> None: self.config = get_answer_bot_config()

    def validate(self, *, text: str, intent: str, context: dict, plan: dict, injection: bool, medical: bool) -> dict[str, Any]:
        results = []
        def add(code: str, result: str, message: str): results.append({"code": code, "result": result, "message": message})
        if injection: add("PROMPT_INJECTION", "BLOCK", "Untrusted content attempted to override policy")
        if medical: add("MEDICAL_DIAGNOSIS", "HUMAN_REVIEW", "Medical diagnosis/treatment intent requires safe escalation")
        if intent == "PRICE_QUERY" and context.get("price") is None: add("PRICE_SOURCE", "HUMAN_REVIEW", "No approved current price")
        if intent == "STOCK_QUERY" and context.get("stock") is None: add("STOCK_SOURCE", "HUMAN_REVIEW", "No live stock context")
        if intent == "ORDER_STATUS" and context.get("order") is None: add("ORDER_SOURCE", "HUMAN_REVIEW", "No exact order match")
        if intent in {"PAYMENT_QUERY", "BALANCE_QUERY", "COMPLAINT", "RETURN_QUERY"}: add("HIGH_IMPACT_INTENT", "HUMAN_REVIEW", "Intent is not eligible for automatic send")
        retrieved_at = context.get("retrieved_at")
        if retrieved_at and intent in {"PRICE_QUERY", "STOCK_QUERY", "ORDER_STATUS"}:
            try:
                stamp = datetime.fromisoformat(str(retrieved_at)); stamp = stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)
                if (datetime.now(UTC) - stamp).total_seconds() > self.config["stale_business_data_seconds"]: add("STALE_BUSINESS_DATA", "HUMAN_REVIEW", "Business data exceeds freshness policy")
            except ValueError: add("STALE_BUSINESS_DATA", "HUMAN_REVIEW", "Business data timestamp is invalid")
        unsupported = [claim for claim in self.config["forbidden_claims"] if claim.casefold() in text.casefold()]
        if unsupported: add("UNSUPPORTED_CLAIM", "BLOCK", "Draft contains a forbidden unsupported claim")
        if "{" in text or "}" in text: add("UNRESOLVED_TEMPLATE", "BLOCK", "Draft contains an unresolved placeholder")
        if not results: add("FACT_AND_POLICY_CHECK", "PASS", "Draft is grounded in selected context")
        status = "BLOCK" if any(item["result"] == "BLOCK" for item in results) else "HUMAN_REVIEW" if any(item["result"] == "HUMAN_REVIEW" for item in results) or plan["human_review_required"] else "PASS"
        return {"status": status, "results": results, "auto_send": status == "PASS" and plan["auto_send_allowed"]}
