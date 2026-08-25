"""Immutable stock ledger, reservations, transfers, and stocktakes."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.exceptions import NotFoundError, SalesValidationError
from backend.db.models.sales import InventoryMovement, InventoryReservation, Stocktake, StocktakeLine
from backend.repositories.sales_repository import SalesRepository
from backend.sales.common import quantity, stable_hash, uid
from backend.sales.master_data import ProductService, WarehouseService
from backend.schemas.sales import InventoryAdjustment, InventoryTransfer, StocktakeComplete, StocktakeCreate


INBOUND = {"OPENING_BALANCE", "PURCHASE_RECEIPT", "SALE_RETURN", "TRANSFER_IN", "ADJUSTMENT_IN", "STOCKTAKE_ADJUSTMENT"}
OUTBOUND = {"SALE_ISSUE", "PURCHASE_RETURN", "TRANSFER_OUT", "ADJUSTMENT_OUT", "DAMAGE", "EXPIRY", "SAMPLE", "GIFT", "PROMOTION"}


class InventoryService:
    def __init__(self, session: Session) -> None:
        self.repository = SalesRepository(session)
        self.settings = get_settings()

    def balance(self, product_id: int | str, warehouse_id: int | str | None = None) -> dict:
        product = ProductService(self.repository.session).get(product_id)
        warehouse = WarehouseService(self.repository.session).get(warehouse_id) if warehouse_id is not None else None
        on_hand = self.repository.stock_on_hand(product.id, warehouse.id if warehouse else None)
        reserved = self.repository.stock_reserved(product.id, warehouse.id if warehouse else None)
        return {"product_uid": product.product_uid, "sku": product.sku, "warehouse_uid": warehouse.warehouse_uid if warehouse else None, "on_hand": on_hand, "reserved": reserved, "available": on_hand - reserved, "incoming": Decimal("0"), "damaged": Decimal("0"), "expired": Decimal("0")}

    def post_movement(self, *, product_id: int | str, warehouse_id: int | str, movement_type: str, quantity_value: Decimal, reference_type: str, reference_id: str, posted_by: str, idempotency_key: str, unit: str | None = None, transaction_date: datetime | None = None, notes: str | None = None) -> InventoryMovement:
        existing = self.repository.inventory_movement_by_key(idempotency_key)
        if existing: return existing
        product = ProductService(self.repository.session).get(product_id)
        warehouse = WarehouseService(self.repository.session).get(warehouse_id)
        movement_type = movement_type.upper()
        if movement_type not in INBOUND | OUTBOUND: raise SalesValidationError("Unsupported inventory movement type")
        amount = quantity(quantity_value)
        if amount <= 0: raise SalesValidationError("Inventory quantity must be positive")
        direction = 1 if movement_type in INBOUND else -1
        if direction < 0 and not self.settings.allow_negative_stock:
            available = self.balance(product.id, warehouse.id)["available"]
            if available < amount: raise SalesValidationError(f"NEGATIVE_STOCK_BLOCKED: available {available}, requested {amount}")
        return self.repository.add(InventoryMovement(movement_uid=uid("MOV"), product_id=product.id, warehouse_id=warehouse.id, movement_type=movement_type, quantity=amount, direction=direction, unit=unit or product.unit, reference_type=reference_type, reference_id=str(reference_id), idempotency_key=idempotency_key, transaction_date=transaction_date or datetime.now(UTC), posted_by=posted_by, notes=notes))

    def adjustment(self, request: InventoryAdjustment) -> InventoryMovement:
        key = request.idempotency_key or stable_hash(request.model_dump())
        return self.post_movement(product_id=request.product_id, warehouse_id=request.warehouse_id, movement_type=f"ADJUSTMENT_{request.direction}", quantity_value=request.quantity, reference_type="ADJUSTMENT", reference_id=key[:16], posted_by=request.posted_by, idempotency_key=key, notes=request.reason)

    def transfer(self, request: InventoryTransfer) -> dict:
        if str(request.source_warehouse_id) == str(request.destination_warehouse_id): raise SalesValidationError("Transfer warehouses must differ")
        key = request.idempotency_key or stable_hash(request.model_dump())
        out = self.post_movement(product_id=request.product_id, warehouse_id=request.source_warehouse_id, movement_type="TRANSFER_OUT", quantity_value=request.quantity, reference_type="TRANSFER", reference_id=key[:16], posted_by=request.posted_by, idempotency_key=f"{key}:OUT")
        incoming = self.post_movement(product_id=request.product_id, warehouse_id=request.destination_warehouse_id, movement_type="TRANSFER_IN", quantity_value=request.quantity, reference_type="TRANSFER", reference_id=key[:16], posted_by=request.posted_by, idempotency_key=f"{key}:IN")
        return {"transfer_id": key[:16], "out_movement": out, "in_movement": incoming}

    def reserve(self, *, order_line_id: int, product_id: int, warehouse_id: int, amount: Decimal) -> InventoryReservation:
        existing = self.repository.active_reservation(order_line_id)
        if existing: return existing
        available = self.balance(product_id, warehouse_id)["available"]
        amount = quantity(amount)
        if available < amount and not self.settings.allow_negative_stock: raise SalesValidationError(f"INSUFFICIENT_STOCK: available {available}, requested {amount}")
        return self.repository.add(InventoryReservation(reservation_uid=uid("RES"), product_id=product_id, warehouse_id=warehouse_id, order_line_id=order_line_id, quantity=amount, status="ACTIVE"))

    def release_reservation(self, order_line_id: int) -> None:
        reservation = self.repository.active_reservation(order_line_id)
        if reservation:
            reservation.status = "RELEASED"; reservation.released_at = datetime.now(UTC)

    def create_stocktake(self, request: StocktakeCreate) -> Stocktake:
        warehouse = WarehouseService(self.repository.session).get(request.warehouse_id)
        stocktake = self.repository.add(Stocktake(stocktake_uid=uid("STK"), warehouse_id=warehouse.id, started_at=request.started_at, status="OPEN"))
        for line in request.lines:
            product = ProductService(self.repository.session).get(line.product_id)
            system_qty = self.repository.stock_on_hand(product.id, warehouse.id)
            counted = quantity(line.counted_qty)
            self.repository.add(StocktakeLine(stocktake_id=stocktake.id, product_id=product.id, system_qty=system_qty, counted_qty=counted, variance=counted - system_qty, reason=line.reason, approved_adjustment=False))
        return stocktake

    def complete_stocktake(self, identifier: int | str, request: StocktakeComplete) -> Stocktake:
        stocktake = self.repository.get_stocktake(identifier)
        if stocktake is None: raise NotFoundError(f"Stocktake {identifier} was not found")
        if stocktake.status == "COMPLETED": return stocktake
        if stocktake.status != "OPEN": raise SalesValidationError("Only an open stocktake can be completed")
        lines = self.repository.stocktake_lines(stocktake.id)
        variances = [line for line in lines if line.variance != 0]
        if variances and not request.approve_all_variances: raise SalesValidationError("Stocktake variances require approval")
        for line in variances:
            line.approved_adjustment = True
            self.post_movement(product_id=line.product_id, warehouse_id=stocktake.warehouse_id, movement_type="ADJUSTMENT_IN" if line.variance > 0 else "ADJUSTMENT_OUT", quantity_value=abs(line.variance), reference_type="STOCKTAKE", reference_id=stocktake.stocktake_uid, posted_by=request.approved_by, idempotency_key=f"stocktake:{stocktake.stocktake_uid}:line:{line.id}", notes=line.reason or "Approved stocktake variance")
        stocktake.status = "COMPLETED"; stocktake.completed_at = datetime.now(UTC)
        return stocktake
