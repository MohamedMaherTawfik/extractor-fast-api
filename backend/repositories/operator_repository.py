"""Read-only persistence queries for the desktop operator control center."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.core.enums import CollectionRunStatus, GenerationJobStatus, ReviewStatus
from backend.db.models.analysis import AnalysisRun
from backend.db.models.answer_bot import Conversation, FollowUp, HandoffRequest, Message
from backend.db.models.collection_run import CollectionRun
from backend.db.models.content_item import ContentItem
from backend.db.models.generation import GeneratedAsset, GenerationJob
from backend.db.models.pattern_recipe import Pattern, Recipe
from backend.db.models.rules import HumanReviewRequest, Rule, RuleAuditLog
from backend.db.models.sales import (
    ApprovalRequest, AuditLedger, CollectionActivity, Customer, DailyClose,
    InventoryMovement, MscIntakeBatch, Payment, PriceBook, Product,
    PurchaseOrder, SalesInvoice, SalesOrder, Supplier, Warehouse,
)
from backend.sales.common import model_dict


WORKSPACES: dict[str, type] = {
    "content": ContentItem, "analysis": AnalysisRun, "patterns": Pattern,
    "recipes": Recipe, "rules": Rule, "generation-jobs": GenerationJob,
    "assets": GeneratedAsset, "products": Product, "pricebooks": PriceBook,
    "customers": Customer, "orders": SalesOrder, "invoices": SalesInvoice,
    "payments": Payment, "collections": CollectionActivity,
    "inventory": InventoryMovement, "warehouses": Warehouse,
    "suppliers": Supplier, "purchases": PurchaseOrder,
    "msc": MscIntakeBatch, "daily-close": DailyClose,
    "conversations": Conversation, "handoffs": HandoffRequest,
    "followups": FollowUp, "approvals": ApprovalRequest,
    "rule-reviews": HumanReviewRequest, "audit": AuditLedger,
    "rule-audit": RuleAuditLog, "collection-jobs": CollectionRun,
}


class OperatorRepository:
    def __init__(self, session: Session) -> None: self.session = session

    def workspace(self, name: str, *, offset: int, limit: int) -> dict[str, Any] | None:
        model = WORKSPACES.get(name)
        if model is None: return None
        total = self.session.scalar(select(func.count()).select_from(model)) or 0
        order = getattr(model, "created_at", getattr(model, "id"))
        rows = list(self.session.scalars(select(model).order_by(order.desc()).offset(offset).limit(limit)))
        return {"workspace": name, "items": [model_dict(item) for item in rows], "total": total, "offset": offset, "limit": limit}

    def count(self, model: type, *criteria) -> int:
        statement = select(func.count()).select_from(model)
        if criteria: statement = statement.where(*criteria)
        return int(self.session.scalar(statement) or 0)

    def dashboard(self) -> dict[str, Any]:
        today = datetime.now(UTC).date()
        sales_total = self.session.scalar(select(func.coalesce(func.sum(SalesOrder.total), 0)).where(func.date(SalesOrder.order_date) == today.isoformat())) or 0
        return {
            "as_of": datetime.now(UTC),
            "metrics": {
                "pending_jobs": self.count(CollectionRun, CollectionRun.status.in_((CollectionRunStatus.QUEUED, CollectionRunStatus.RUNNING, CollectionRunStatus.RETRYING))),
                "generation_jobs": self.count(GenerationJob, GenerationJob.status.in_((GenerationJobStatus.QUEUED, GenerationJobStatus.VALIDATING, GenerationJobStatus.PLANNING, GenerationJobStatus.GENERATING, GenerationJobStatus.PROCESSING, GenerationJobStatus.QA_PENDING, GenerationJobStatus.RETRY_PENDING))),
                "content_items": self.count(ContentItem),
                "approvals": self.count(ApprovalRequest, ApprovalRequest.status == "PENDING") + self.count(HumanReviewRequest, HumanReviewRequest.status == ReviewStatus.PENDING),
                "sales_today": str(sales_total),
                "orders": self.count(SalesOrder),
                "msc_pending": self.count(MscIntakeBatch, MscIntakeBatch.status.notin_(("POSTED", "CANCELLED"))),
                "open_conversations": self.count(Conversation, Conversation.status.notin_(("RESOLVED", "CLOSED"))),
                "human_handoffs": self.count(HandoffRequest, HandoffRequest.status == "OPEN"),
            },
            "notifications": self.notifications(limit=8),
        }

    def notifications(self, *, limit: int) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for handoff in self.session.scalars(select(HandoffRequest).where(HandoffRequest.status == "OPEN").order_by(HandoffRequest.created_at.desc()).limit(limit)):
            items.append({"id": handoff.handoff_uid, "severity": handoff.priority, "type": "HUMAN_HANDOFF", "title": handoff.reason, "created_at": handoff.created_at})
        for job in self.session.scalars(select(GenerationJob).where(GenerationJob.status == GenerationJobStatus.FAILED).order_by(GenerationJob.created_at.desc()).limit(limit)):
            items.append({"id": job.job_uid, "severity": "ERROR", "type": "GENERATION_FAILED", "title": job.error_message or "Generation job failed", "created_at": job.created_at})
        return sorted(items, key=lambda item: item["created_at"], reverse=True)[:limit]

    def search(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        pattern = f"%{query}%"; results: list[dict[str, Any]] = []
        searches = (
            ("product", Product, or_(Product.sku.ilike(pattern), Product.product_name_en.ilike(pattern), Product.product_name_ar.ilike(pattern)), "product_uid", "product_name_en"),
            ("customer", Customer, or_(Customer.customer_code.ilike(pattern), Customer.business_name.ilike(pattern), Customer.phone.ilike(pattern)), "customer_uid", "business_name"),
            ("order", SalesOrder, or_(SalesOrder.order_uid.ilike(pattern), SalesOrder.order_number.ilike(pattern)), "order_uid", "order_number"),
            ("invoice", SalesInvoice, or_(SalesInvoice.invoice_uid.ilike(pattern), SalesInvoice.invoice_number.ilike(pattern)), "invoice_uid", "invoice_number"),
            ("conversation", Conversation, or_(Conversation.conversation_uid.ilike(pattern), Conversation.external_thread_id.ilike(pattern)), "conversation_uid", "conversation_uid"),
            ("recipe", Recipe, or_(Recipe.recipe_uid.ilike(pattern), Recipe.name.ilike(pattern)), "recipe_uid", "name"),
            ("generation", GenerationJob, GenerationJob.job_uid.ilike(pattern), "job_uid", "job_uid"),
            ("asset", GeneratedAsset, GeneratedAsset.asset_uid.ilike(pattern), "asset_uid", "asset_uid"),
        )
        per_type = max(1, limit // len(searches))
        for kind, model, predicate, uid_field, label_field in searches:
            for row in self.session.scalars(select(model).where(predicate).limit(per_type)):
                results.append({"type": kind, "uid": getattr(row, uid_field), "label": getattr(row, label_field) or getattr(row, uid_field)})
        return results[:limit]
