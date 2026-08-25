"""Transactional business-event outbox and append-only mutation audit."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.db.models.sales import AuditLedger, BusinessEvent
from backend.repositories.sales_repository import SalesRepository
from backend.sales.common import json_safe, stable_hash, uid


class SalesAuditService:
    def __init__(self, session: Session) -> None: self.repository = SalesRepository(session)

    def event(self, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict | None = None) -> BusinessEvent:
        key = stable_hash({"event_type": event_type, "aggregate_type": aggregate_type, "aggregate_id": aggregate_id})
        existing = self.repository.event_by_key(key)
        if existing: return existing
        return self.repository.add(BusinessEvent(event_uid=uid("EVT"), event_type=event_type, aggregate_type=aggregate_type, aggregate_id=str(aggregate_id), payload=json_safe(payload or {}), idempotency_key=key))

    def mutation(self, *, actor: str, action: str, entity_type: str, entity_id: str, before: dict | None, after: dict | None, reason: str | None = None, source: str = "API", approval_reference: str | None = None) -> AuditLedger:
        return self.repository.add(AuditLedger(audit_uid=uid("AUD"), actor=actor, action=action, entity_type=entity_type, entity_id=str(entity_id), before=json_safe(before), after=json_safe(after), reason=reason, source=source, approval_reference=approval_reference))


def export_safe_cell(value):
    """Prevent spreadsheet clients from interpreting user text as a formula."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value
