"""Purchase orders, receipts, supplier invoices, and payables."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.core.exceptions import ConflictError, NotFoundError, SalesValidationError
from backend.db.models.sales import GoodsReceipt, GoodsReceiptLine, PurchaseOrder, PurchaseOrderLine, SupplierInvoice, SupplierPayment
from backend.repositories.sales_repository import SalesRepository
from backend.sales.common import money, stable_hash, uid
from backend.sales.audit import SalesAuditService
from backend.sales.inventory import InventoryService
from backend.sales.master_data import ProductService, SupplierService, WarehouseService
from backend.schemas.sales import GoodsReceiptCreate, PurchaseOrderCreate, SupplierInvoiceCreate, SupplierPaymentCreate


class PurchaseService:
    def __init__(self, session: Session) -> None:
        self.repository = SalesRepository(session); self.inventory = InventoryService(session)

    def create_order(self, request: PurchaseOrderCreate) -> PurchaseOrder:
        if self.repository.get_purchase_order(request.order_number): raise ConflictError(f"Purchase order {request.order_number} already exists")
        supplier = SupplierService(self.repository.session).get(request.supplier_id)
        if not supplier.active: raise SalesValidationError("Supplier is inactive")
        prepared = []
        subtotal = Decimal("0")
        for item in request.lines:
            product = ProductService(self.repository.session).get(item.product_id)
            if supplier.moq is not None and item.quantity < supplier.moq: raise SalesValidationError(f"Supplier MOQ is {supplier.moq}")
            line_total = money(item.quantity * item.unit_cost); subtotal += line_total; prepared.append((product, item, line_total))
        total = money(subtotal - request.discount + request.tax + request.shipping)
        order = self.repository.add(PurchaseOrder(purchase_order_uid=uid("PO"), order_number=request.order_number, supplier_id=supplier.id, order_date=request.order_date, expected_date=request.expected_date, currency=request.currency.upper(), status="APPROVED", subtotal=money(subtotal), discount=money(request.discount), tax=money(request.tax), shipping=money(request.shipping), total=total))
        for product, item, line_total in prepared: self.repository.add(PurchaseOrderLine(purchase_order_id=order.id, product_id=product.id, quantity=item.quantity, unit_cost=money(item.unit_cost), line_total=line_total))
        return order

    def get_order(self, identifier: int | str) -> PurchaseOrder:
        order = self.repository.get_purchase_order(identifier)
        if order is None: raise NotFoundError(f"Purchase order {identifier} was not found")
        return order

    def receive(self, request: GoodsReceiptCreate) -> GoodsReceipt:
        key = request.idempotency_key or stable_hash(request.model_dump())
        existing = self.repository.receipt_by_key(key)
        if existing: return existing
        order = self.get_order(request.purchase_order_id); warehouse = WarehouseService(self.repository.session).get(request.warehouse_id)
        if order.status not in {"APPROVED", "PARTIALLY_RECEIVED"}: raise SalesValidationError("Purchase order cannot be received")
        po_lines = {line.id: line for line in self.repository.purchase_order_lines(order.id)}
        prepared = []
        for item in request.lines:
            line = po_lines.get(item.purchase_order_line_id)
            if line is None: raise SalesValidationError("Receipt line does not belong to purchase order")
            if item.quantity > line.quantity: raise SalesValidationError("Receipt quantity exceeds ordered quantity")
            prepared.append((line, item))
        receipt = self.repository.add(GoodsReceipt(receipt_uid=uid("GRN"), receipt_number=request.receipt_number, purchase_order_id=order.id, warehouse_id=warehouse.id, received_at=request.received_at, status="POSTED", received_by=request.received_by, idempotency_key=key))
        for index, (line, item) in enumerate(prepared):
            self.repository.add(GoodsReceiptLine(receipt_id=receipt.id, purchase_order_line_id=line.id, product_id=line.product_id, quantity=item.quantity, batch_number=item.batch_number, expiry_date=item.expiry_date))
            self.inventory.post_movement(product_id=line.product_id, warehouse_id=warehouse.id, movement_type="PURCHASE_RECEIPT", quantity_value=item.quantity, reference_type="GOODS_RECEIPT", reference_id=receipt.receipt_uid, posted_by=request.received_by, idempotency_key=f"receipt:{receipt.receipt_uid}:{index}", transaction_date=request.received_at)
        order.status = "RECEIVED"
        SalesAuditService(self.repository.session).event("PURCHASE_RECEIVED", "GOODS_RECEIPT", receipt.receipt_uid, {"purchase_order": order.purchase_order_uid})
        return receipt

    def create_supplier_invoice(self, request: SupplierInvoiceCreate) -> SupplierInvoice:
        supplier = SupplierService(self.repository.session).get(request.supplier_id)
        purchase_order = self.get_order(request.purchase_order_id) if request.purchase_order_id is not None else None
        if purchase_order and purchase_order.supplier_id != supplier.id: raise SalesValidationError("Supplier invoice does not match purchase order supplier")
        return self.repository.add(SupplierInvoice(supplier_invoice_uid=uid("SINV"), invoice_number=request.invoice_number, supplier_id=supplier.id, purchase_order_id=purchase_order.id if purchase_order else None, invoice_date=request.invoice_date, due_date=request.due_date, currency=request.currency.upper(), total=money(request.total), status="POSTED"))


class SupplierPayablesService:
    def __init__(self, session: Session) -> None: self.repository = SalesRepository(session)

    def balance(self, supplier_id: int | str) -> Decimal:
        supplier = SupplierService(self.repository.session).get(supplier_id)
        return money(self.repository.supplier_invoiced_total(supplier.id) - self.repository.supplier_paid_total(supplier.id))

    def pay(self, request: SupplierPaymentCreate) -> SupplierPayment:
        supplier = SupplierService(self.repository.session).get(request.supplier_id)
        amount = money(request.amount)
        if amount > self.balance(supplier.id): raise SalesValidationError("Supplier payment exceeds payable balance")
        return self.repository.add(SupplierPayment(supplier_payment_uid=uid("SPAY"), supplier_id=supplier.id, payment_date=request.payment_date, amount=amount, currency=request.currency.upper(), method=request.method.upper(), reference=request.reference))
