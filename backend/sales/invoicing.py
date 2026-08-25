"""Invoice validation, immutable posting, returns, and atomic stock issue."""

from __future__ import annotations

from datetime import UTC, timedelta, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.core.exceptions import ConflictError, NotFoundError, SalesValidationError
from backend.db.models.sales import SalesInvoice, SalesInvoiceLine, SalesReturn, SalesReturnLine
from backend.repositories.sales_repository import SalesRepository
from backend.sales.common import money, stable_hash, uid
from backend.sales.audit import SalesAuditService
from backend.sales.inventory import InventoryService
from backend.sales.master_data import CustomerService, ProductService, WarehouseService
from backend.sales.orders import SalesOrderService
from backend.schemas.sales import InvoiceCreate, PostRequest


class InvoiceService:
    def __init__(self, session: Session) -> None:
        self.repository = SalesRepository(session)
        self.inventory = InventoryService(session)

    def get(self, identifier: int | str) -> SalesInvoice:
        invoice = self.repository.get_invoice(identifier)
        if invoice is None: raise NotFoundError(f"Invoice {identifier} was not found")
        return invoice

    def create(self, request: InvoiceCreate) -> SalesInvoice:
        key = request.idempotency_key or stable_hash(request.model_dump())
        existing = self.repository.invoice_by_idempotency(key)
        if existing: return existing
        order = SalesOrderService(self.repository.session).get(request.order_id) if request.order_id is not None else None
        customer_identifier = request.customer_id if request.customer_id is not None else order.customer_id if order else None
        if customer_identifier is None: raise SalesValidationError("No invoice without customer")
        customer = CustomerService(self.repository.session).get(customer_identifier)
        if order and customer.id != order.customer_id: raise SalesValidationError("Invoice customer differs from order customer")
        prepared: list[dict] = []
        if order:
            if order.order_status not in {"APPROVED", "RESERVED", "PARTIALLY_FULFILLED"}: raise SalesValidationError("Order must be approved/reserved before invoicing")
            for line in self.repository.order_lines(order.id):
                prepared.append({"product_id": line.product_id, "warehouse_id": line.warehouse_id, "quantity": line.quantity, "unit_price": line.unit_price, "discount": line.discount, "tax": line.tax})
        else:
            for line in request.lines:
                product = ProductService(self.repository.session).get(line.product_id)
                if not product.active or product.status != "ACTIVE": raise SalesValidationError(f"SKU {product.sku} cannot be invoiced")
                warehouse = WarehouseService(self.repository.session).get(line.warehouse_id)
                prepared.append({"product_id": product.id, "warehouse_id": warehouse.id, "quantity": line.quantity, "unit_price": line.unit_price, "discount": line.discount, "tax": line.tax})
        if not prepared: raise SalesValidationError("Invoice requires at least one line")
        subtotal = sum((money(line["unit_price"] * line["quantity"]) for line in prepared), Decimal("0"))
        line_discounts = sum((money(line["discount"]) for line in prepared), Decimal("0"))
        line_taxes = sum((money(line["tax"]) for line in prepared), Decimal("0"))
        total_discount = order.discount if order else money(line_discounts + request.discount)
        total_tax = order.tax if order else money(line_taxes + request.tax)
        shipping = order.shipping if order else money(request.shipping)
        subtotal = order.subtotal if order else money(subtotal)
        total = order.total if order else money(subtotal - total_discount + total_tax + shipping)
        if total < 0: raise SalesValidationError("Invoice arithmetic produces a negative total")
        due = request.due_date or (request.invoice_date + timedelta(days=customer.payment_terms_days))
        fingerprint = stable_hash({"source": request.source_system, "number": request.invoice_number, "date": request.invoice_date, "customer": customer.customer_uid, "lines": prepared, "total": total})
        if self.repository.invoice_by_fingerprint(fingerprint): raise ConflictError("Duplicate invoice fingerprint")
        invoice = self.repository.add(SalesInvoice(invoice_uid=uid("INV"), invoice_number=request.invoice_number, order_id=order.id if order else None, customer_id=customer.id, invoice_date=request.invoice_date, due_date=due, currency=request.currency.upper(), subtotal=money(subtotal), discount=total_discount, tax=total_tax, shipping=shipping, total=total, status="VALIDATED", source_system=request.source_system.upper(), idempotency_key=key, fingerprint=fingerprint))
        for line in prepared:
            line_total = money(line["unit_price"] * line["quantity"] - line["discount"] + line["tax"])
            self.repository.add(SalesInvoiceLine(invoice_line_uid=uid("INVL"), invoice_id=invoice.id, line_total=line_total, **line))
        return invoice

    def post(self, identifier: int | str, request: PostRequest) -> SalesInvoice:
        invoice = self.get(identifier)
        if invoice.status in {"POSTED", "PARTIALLY_PAID", "PAID", "OVERDUE"}: return invoice
        if invoice.status != "VALIDATED": raise SalesValidationError(f"Invoice cannot post from {invoice.status}")
        lines = self.repository.invoice_lines(invoice.id)
        # Preflight every line so a known stock failure occurs before any write.
        for line in lines:
            available = self.inventory.balance(line.product_id, line.warehouse_id)["available"]
            reservation = None
            if invoice.order_id:
                for order_line in self.repository.order_lines(invoice.order_id):
                    if order_line.product_id == line.product_id and order_line.warehouse_id == line.warehouse_id:
                        reservation = self.repository.active_reservation(order_line.id); break
            effective_available = available + (reservation.quantity if reservation else Decimal("0"))
            if effective_available < line.quantity and not self.inventory.settings.allow_negative_stock: raise SalesValidationError("ATOMIC_POST_BLOCKED: insufficient stock")
        for line in lines:
            if invoice.order_id:
                for order_line in self.repository.order_lines(invoice.order_id):
                    if order_line.product_id == line.product_id and order_line.warehouse_id == line.warehouse_id: self.inventory.release_reservation(order_line.id)
            self.inventory.post_movement(product_id=line.product_id, warehouse_id=line.warehouse_id, movement_type="SALE_ISSUE", quantity_value=line.quantity, reference_type="SALES_INVOICE", reference_id=invoice.invoice_uid, posted_by=request.posted_by, idempotency_key=f"invoice:{invoice.invoice_uid}:line:{line.id}", transaction_date=datetime.now(UTC))
        invoice.status = "POSTED"; invoice.posted_at = datetime.now(UTC); invoice.posted_by = request.posted_by
        if invoice.order_id:
            order = self.repository.get_order(invoice.order_id)
            order.order_status = "FULFILLED"; order.fulfillment_status = "FULFILLED"
        SalesAuditService(self.repository.session).event("INVOICE_POSTED", "SALES_INVOICE", invoice.invoice_uid, {"customer_id": invoice.customer_id, "total": invoice.total})
        return invoice

    def balance(self, invoice: SalesInvoice) -> Decimal:
        return money(invoice.total - self.repository.invoice_return_total(invoice.id) - self.repository.invoice_allocated(invoice.id))


class ReturnService:
    def __init__(self, session: Session) -> None:
        self.repository = SalesRepository(session); self.inventory = InventoryService(session)

    def post_sales_return(self, *, invoice_id: int | str, lines: list[dict], reason: str, actor: str) -> SalesReturn:
        invoice = InvoiceService(self.repository.session).get(invoice_id)
        if invoice.status not in {"POSTED", "PARTIALLY_PAID", "PAID", "OVERDUE"}: raise SalesValidationError("Return requires a posted invoice")
        total = sum((money(item["amount"]) for item in lines), Decimal("0"))
        record = self.repository.add(SalesReturn(return_uid=uid("RET"), invoice_id=invoice.id, return_date=datetime.now(UTC), reason=reason, status="POSTED", total=total))
        for index, item in enumerate(lines):
            product = ProductService(self.repository.session).get(item["product_id"]); warehouse = WarehouseService(self.repository.session).get(item["warehouse_id"])
            line = self.repository.add(SalesReturnLine(return_id=record.id, product_id=product.id, warehouse_id=warehouse.id, quantity=item["quantity"], amount=money(item["amount"]), condition=item.get("condition", "GOOD"), disposition=item.get("disposition", "RESTOCK")))
            if line.disposition == "RESTOCK": self.inventory.post_movement(product_id=product.id, warehouse_id=warehouse.id, movement_type="SALE_RETURN", quantity_value=line.quantity, reference_type="SALES_RETURN", reference_id=record.return_uid, posted_by=actor, idempotency_key=f"return:{record.return_uid}:{index}")
        return record
