"""Territory, sales representative, and delivery workflow."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.core.exceptions import ConflictError, NotFoundError, SalesValidationError
from backend.db.models.sales import Delivery, SalesRep, Territory
from backend.repositories.sales_repository import SalesRepository
from backend.sales.common import money, uid
from backend.sales.orders import SalesOrderService
from backend.schemas.sales import DeliveryCreate, DeliveryUpdate, SalesRepCreate, TerritoryCreate


DELIVERY_STATUSES = {"PENDING", "SCHEDULED", "OUT_FOR_DELIVERY", "DELIVERED", "FAILED", "PARTIAL", "RETURNED", "CANCELLED"}


class DistributionService:
    def __init__(self, session: Session) -> None: self.repository = SalesRepository(session)

    def create_territory(self, request: TerritoryCreate) -> Territory:
        if self.repository.get_territory(request.code): raise ConflictError(f"Territory {request.code} already exists")
        return self.repository.add(Territory(territory_uid=uid("TER"), code=request.code.upper(), name=request.name, scope=request.scope, active=True))

    def create_sales_rep(self, request: SalesRepCreate) -> SalesRep:
        if self.repository.get_sales_rep(request.code): raise ConflictError(f"Sales rep {request.code} already exists")
        territory = self.repository.get_territory(request.territory_id) if request.territory_id is not None else None
        if request.territory_id is not None and territory is None: raise NotFoundError("Territory was not found")
        return self.repository.add(SalesRep(sales_rep_uid=uid("REP"), code=request.code.upper(), name=request.name, territory_id=territory.id if territory else None, targets=request.targets, collections_responsibility=request.collections_responsibility, active=True))

    def create_delivery(self, request: DeliveryCreate) -> Delivery:
        order = SalesOrderService(self.repository.session).get(request.order_id)
        if order.order_status in {"DRAFT", "PENDING_APPROVAL", "CANCELLED"}: raise SalesValidationError("Delivery requires an approved order")
        return self.repository.add(Delivery(delivery_uid=uid("DLV"), order_id=order.id, customer_id=order.customer_id, address=request.address, zone=request.zone, driver=request.driver, vehicle=request.vehicle, status="SCHEDULED" if request.scheduled_at else "PENDING", scheduled_at=request.scheduled_at, company_delivery_cost=money(request.company_delivery_cost), customer_delivery_charge=money(request.customer_delivery_charge)))

    def update_delivery(self, identifier: int | str, request: DeliveryUpdate) -> Delivery:
        delivery = self.repository.get_delivery(identifier)
        if delivery is None: raise NotFoundError(f"Delivery {identifier} was not found")
        target = request.status.upper()
        if target not in DELIVERY_STATUSES: raise SalesValidationError("Unsupported delivery status")
        now = datetime.now(UTC)
        if target == "OUT_FOR_DELIVERY": delivery.dispatched_at = now
        elif target == "DELIVERED": delivery.delivered_at = now
        elif target == "FAILED": delivery.failed_at = now; delivery.failure_reason = request.failure_reason
        delivery.status = target
        return delivery
