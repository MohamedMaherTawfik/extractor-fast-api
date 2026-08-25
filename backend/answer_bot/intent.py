"""Config-driven multilingual intent, entity, safety, and language analysis."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from backend.answer_bot.config import get_answer_bot_config
from backend.repositories.sales_repository import SalesRepository


ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").translate(ARABIC_DIGITS).casefold()
    text = re.sub("[أإآٱ]", "ا", text)
    text = text.replace("ى", "ي")
    text = re.sub(r"[ًٌٍَُِّْـ]", "", text)
    return " ".join(text.split())


def detect_language(text: str) -> tuple[str, Decimal]:
    arabic = len(re.findall(r"[\u0600-\u06ff]", text)); latin = len(re.findall(r"[A-Za-z]", text))
    if arabic and latin: return "mixed_ar_en", Decimal("0.90")
    if arabic: return "ar", Decimal("0.95")
    if latin: return "en", Decimal("0.95")
    return "unknown", Decimal("0.50")


@dataclass(slots=True)
class IntentAnalysis:
    primary: str
    secondary: list[str]
    confidence: Decimal
    sentiment: str
    urgency: str
    complaint_type: str | None
    complaint_severity: str | None
    prompt_injection: bool
    medical: bool
    opt_out: bool


class IntentClassifier:
    def __init__(self) -> None: self.config = get_answer_bot_config()

    def classify(self, text: str, media: list[dict[str, Any]] | None = None) -> IntentAnalysis:
        normalized = normalize_text(text)
        scores: list[tuple[str, int, int]] = []
        for intent, examples in self.config["intent_examples"].items():
            positions = [normalized.find(normalize_text(str(phrase))) for phrase in examples if normalize_text(str(phrase)) in normalized]
            if positions: scores.append((intent, len(positions), min(positions)))
        media = media or []
        if any(item.get("type") in {"payment_screenshot", "payment_evidence"} for item in media): scores.append(("PAYMENT_QUERY", 3, 0))
        medical = any(normalize_text(term) in normalized for term in self.config["medical_terms"])
        if medical: scores.append(("MEDICAL_CONCERN", 5, 0))
        prompt_injection = any(normalize_text(term) in normalized for term in self.config["prompt_injection_phrases"])
        opt_out = any(normalize_text(term) in normalized for term in self.config["opt_out_phrases"])
        if opt_out: scores.append(("OPT_OUT", 6, 0))
        if not scores: primary, secondary, confidence = "UNKNOWN", [], Decimal("0.35")
        else:
            # Preserve the customer's conversational order for ordinary multi-intent
            # messages. Safety and consent intents always take precedence.
            scores.sort(key=lambda item: (item[2], -item[1], item[0]))
            if opt_out:
                scores.sort(key=lambda item: item[0] != "OPT_OUT")
            elif medical:
                scores.sort(key=lambda item: item[0] != "MEDICAL_CONCERN")
            primary = scores[0][0]
            secondary = [name for name, _, _ in scores[1:] if name != primary]
            confidence = min(Decimal("0.99"), Decimal("0.72") + Decimal("0.08") * scores[0][1])
        complaint = "COMPLAINT" in [primary, *secondary]
        serious = any(normalize_text(term) in normalized for term in self.config["serious_complaint_terms"])
        angry = any(term in normalized for term in ("angry", "furious", "غاضب", "زعلان جدا", "نصب"))
        severity = "CRITICAL" if serious else "HIGH" if angry else "MEDIUM" if complaint else None
        complaint_type = "PAYMENT" if "PAYMENT_QUERY" in [primary, *secondary] else "DELIVERY_DELAY" if "DELIVERY_QUERY" in [primary, *secondary] else "OTHER" if complaint else None
        sentiment = "ANGRY" if angry or serious else "NEGATIVE" if complaint else "NEUTRAL"
        urgency = "URGENT" if serious or any(term in normalized for term in ("urgent", "asap", "ضروري", "حالاً", "حالا")) else "NORMAL"
        return IntentAnalysis(primary, secondary, confidence, sentiment, urgency, complaint_type, severity, prompt_injection, medical, opt_out)


class EntityExtractionService:
    def __init__(self, session: Session) -> None: self.sales = SalesRepository(session)

    def extract(self, text: str, *, customer_id: int | None = None) -> list[dict[str, Any]]:
        normalized = normalize_text(text); entities: list[dict[str, Any]] = []
        quantity_match = re.search(r"(?:qty|quantity|كمية|عايز|عاوز)\s*[:=]?\s*(\d+(?:\.\d+)?)", normalized)
        if quantity_match: entities.append({"type": "QUANTITY", "raw": quantity_match.group(1), "normalized": quantity_match.group(1), "confidence": Decimal("0.90"), "status": "VALID"})
        budget_match = re.search(r"(?:budget|ميزانية|في حدود|حدود)\s*[:=]?\s*(\d+(?:\.\d+)?)", normalized)
        if budget_match: entities.append({"type": "BUDGET", "raw": budget_match.group(1), "normalized": budget_match.group(1), "confidence": Decimal("0.90"), "status": "VALID"})
        customer_code = re.search(r"\b(?:customer|cust)[_-][a-z0-9_-]+\b", normalized)
        if customer_code: entities.append({"type": "CUSTOMER_CODE", "raw": customer_code.group(0), "normalized": customer_code.group(0).upper(), "confidence": Decimal("1"), "status": "VALID"})
        requested_date = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", normalized)
        if requested_date: entities.append({"type": "DATE", "raw": requested_date.group(1), "normalized": requested_date.group(1), "confidence": Decimal("0.98"), "status": "VALID"})
        catalogs = get_answer_bot_config().get("entity_catalogs", {})
        for entity_type, catalog_name in (("GOVERNORATE", "governorates"), ("PAYMENT_METHOD", "payment_methods"), ("REQUESTED_ACTION", "requested_actions")):
            matches = [(term, normalized.find(normalize_text(str(term)))) for term in catalogs.get(catalog_name, []) if normalize_text(str(term)) in normalized]
            if matches:
                value, _ = min(matches, key=lambda item: item[1])
                entities.append({"type": entity_type, "raw": str(value), "normalized": normalize_text(str(value)), "confidence": Decimal("0.92"), "status": "VALID"})
                if entity_type == "GOVERNORATE": entities.append({"type": "LOCATION", "raw": str(value), "normalized": normalize_text(str(value)), "confidence": Decimal("0.92"), "status": "VALID"})
        product_matches = []
        for product in self.sales.list_products(active=True):
            candidates = [product.sku, product.barcode, product.product_name_ar, product.product_name_en, product.brand]
            candidates.extend(product.facts.get("aliases", []) if product.facts else [])
            if any(candidate and normalize_text(str(candidate)) in normalized for candidate in candidates): product_matches.append(product)
        if len(product_matches) == 1:
            product = product_matches[0]; entities.append({"type": "PRODUCT", "raw": product.sku, "normalized": product.product_uid, "product_id": product.id, "confidence": Decimal("0.98"), "status": "VALID"})
        elif len(product_matches) > 1:
            entities.append({"type": "PRODUCT", "raw": text, "normalized": None, "candidates": [item.product_uid for item in product_matches], "confidence": Decimal("0.45"), "status": "AMBIGUOUS"})
        orders = self.sales.list_orders(customer_id=customer_id)
        matched_orders = [order for order in orders if normalize_text(order.order_number) in normalized or normalize_text(order.order_uid) in normalized]
        if len(matched_orders) == 1:
            order = matched_orders[0]; entities.append({"type": "ORDER", "raw": order.order_number, "normalized": order.order_uid, "order_id": order.id, "confidence": Decimal("1"), "status": "VALID"})
        invoice_matches = [invoice for invoice in (self.sales.customer_invoices(customer_id) if customer_id else []) if normalize_text(invoice.invoice_number) in normalized or normalize_text(invoice.invoice_uid) in normalized]
        if len(invoice_matches) == 1:
            invoice = invoice_matches[0]; entities.append({"type": "INVOICE", "raw": invoice.invoice_number, "normalized": invoice.invoice_uid, "invoice_id": invoice.id, "confidence": Decimal("1"), "status": "VALID"})
        return entities
