"""Sales orders and stock reservation policy."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.core.exceptions import ConflictError, NotFoundError, SalesValidationError
from backend.db.models.sales import ApprovalRequest, SalesOrder, SalesOrderLine
from backend.repositories.sales_repository import SalesRepository
from backend.sales.common import money, stable_hash, uid
from backend.sales.audit import SalesAuditService
from backend.sales.inventory import InventoryService
from backend.sales.master_data import CustomerService, PricingService, ProductService, WarehouseService
from backend.schemas.sales import ApprovalDecision, SalesOrderCreate


class SalesOrderService:
    def __init__(self, session: Session) -> None:
        self.repository = SalesRepository(session)
        self.inventory = InventoryService(session)

    def get(self, identifier: int | str) -> SalesOrder:
        order = self.repository.get_order(identifier)
        if order is None: raise NotFoundError(f"Sales order {identifier} was not found")
        return order

    def create(self, request: SalesOrderCreate) -> SalesOrder:
        key = request.idempotency_key or stable_hash(request.model_dump())
        existing = self.repository.order_by_idempotency(key)
        if existing: return existing
        if self.repository.get_order(request.order_number): raise ConflictError(f"Order {request.order_number} already exists")
        customer = CustomerService(self.repository.session).get(request.customer_id)
        if not customer.active or customer.status not in {"ACTIVE", "PROSPECT_CONVERTED"}: raise SalesValidationError("Customer is not active")
        if customer.credit_status == "CREDIT_HOLD" or customer.status == "CREDIT_HOLD": raise SalesValidationError("CREDIT_HOLD: order requires an approved credit override")
        pricing = PricingService(self.repository.session)
        book = pricing.repository.get_pricebook(request.pricebook_id)
        if book is None: raise NotFoundError(f"PriceBook {request.pricebook_id} was not found")
        prepared: list[dict] = []
        subtotal = Decimal("0"); line_discount = Decimal("0"); line_tax = Decimal("0"); override = False
        for item in request.lines:
            product = ProductService(self.repository.session).get(item.product_id)
            if not product.active or product.status != "ACTIVE": raise SalesValidationError(f"SKU {product.sku} cannot be sold with status {product.status}")
            warehouse = WarehouseService(self.repository.session).get(item.warehouse_id)
            price = pricing.get_price(book.id, product.id, item.quantity, at=request.order_date)
            unit_price = money(item.manual_unit_price if item.manual_unit_price is not None else price.net_price)
            manual = item.manual_unit_price is not None and unit_price != money(price.net_price)
            override = override or manual
            gross = money(unit_price * item.quantity)
            total = money(gross - item.discount + item.tax)
            if total < 0: raise SalesValidationError("Order line total cannot be negative")
            prepared.append({"product": product, "warehouse": warehouse, "request": item, "unit_price": unit_price, "gross": gross, "total": total, "manual": manual})
            subtotal += gross; line_discount += item.discount; line_tax += item.tax
        total_discount = money(line_discount + request.discount)
        total_tax = money(line_tax + request.tax)
        total = money(subtotal - total_discount + total_tax + request.shipping)
        if total < 0: raise SalesValidationError("Order total cannot be negative")
        exposure = sum((invoice.total - self.repository.invoice_return_total(invoice.id) - self.repository.invoice_allocated(invoice.id) for invoice in self.repository.posted_invoices(customer_id=customer.id)), Decimal("0"))
        if customer.credit_limit > 0 and exposure + total > customer.credit_limit:
            raise SalesValidationError("CREDIT_LIMIT_EXCEEDED: order requires an approved credit override")
        order = self.repository.add(SalesOrder(order_uid=uid("SO"), order_number=request.order_number, customer_id=customer.id, order_date=request.order_date, channel=request.channel, sales_rep_id=request.sales_rep_id, pricebook_id=book.id, currency=request.currency.upper(), subtotal=money(subtotal), discount=total_discount, tax=total_tax, shipping=money(request.shipping), total=total, order_status="PENDING_APPROVAL" if override else "DRAFT", idempotency_key=key))
        for prepared_line in prepared:
            item = prepared_line["request"]
            self.repository.add(SalesOrderLine(order_line_uid=uid("SOL"), order_id=order.id, product_id=prepared_line["product"].id, quantity=item.quantity, unit=item.unit or prepared_line["product"].unit, unit_price=prepared_line["unit_price"], discount=money(item.discount), net_price=money(prepared_line["unit_price"] - (item.discount / item.quantity)), tax=money(item.tax), line_total=prepared_line["total"], warehouse_id=prepared_line["warehouse"].id, manual_price_override=prepared_line["manual"]))
        if override:
            self.repository.add(ApprovalRequest(approval_uid=uid("APR"), approval_type="PRICE_OVERRIDE", reference_type="SALES_ORDER", reference_id=order.order_uid, reason="Manual order price differs from approved PriceBook", status="PENDING", requested_by="system"))
        SalesAuditService(self.repository.session).event("ORDER_CREATED", "SALES_ORDER", order.order_uid, {"customer_id": customer.customer_uid, "total": order.total})
        return order

    def approve(self, identifier: int | str, decision: ApprovalDecision) -> SalesOrder:
        order = self.get(identifier)
        if order.order_status in {"APPROVED", "RESERVED"}: return order
        if order.order_status not in {"DRAFT", "PENDING_APPROVAL"}: raise SalesValidationError(f"Order cannot be approved from {order.order_status}")
        lines = self.repository.order_lines(order.id)
        if any(line.manual_price_override for line in lines) and not decision.allow_overrides: raise SalesValidationError("PRICE_OVERRIDE_REQUIRES_APPROVAL")
        # Validate all availability before creating any reservation.
        for line in lines:
            balance = self.inventory.balance(line.product_id, line.warehouse_id)
            if balance["available"] < line.quantity and not self.inventory.settings.allow_negative_stock: raise SalesValidationError(f"INSUFFICIENT_STOCK for order line {line.order_line_uid}")
        for line in lines: self.inventory.reserve(order_line_id=line.id, product_id=line.product_id, warehouse_id=line.warehouse_id, amount=line.quantity)
        order.order_status = "RESERVED"; order.fulfillment_status = "RESERVED"; order.approved_by = decision.approved_by
        SalesAuditService(self.repository.session).event("ORDER_APPROVED", "SALES_ORDER", order.order_uid, {"approved_by": decision.approved_by})
        return order

    def cancel(self, identifier: int | str) -> SalesOrder:
        order = self.get(identifier)
        if order.order_status in {"FULFILLED", "CLOSED"}: raise SalesValidationError("Fulfilled/closed order cannot be cancelled")
        for line in self.repository.order_lines(order.id): self.inventory.release_reservation(line.id)
        order.order_status = "CANCELLED"; order.fulfillment_status = "CANCELLED"
        return order
