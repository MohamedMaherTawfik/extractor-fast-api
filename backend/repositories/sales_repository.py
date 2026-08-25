"""Single persistence boundary shared by the separated sales domain services."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, TypeVar

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from backend.db.models.sales import (
    AccountingJournal, AccountingJournalLine, ApprovalRequest, AuditLedger,
    BusinessEvent, CollectionActivity, Customer, DailyClose, Delivery,
    GoodsReceipt, GoodsReceiptLine, InventoryMovement, InventoryReservation,
    MscIntakeBatch, MscIntakeFile, MscInvoiceStaging, Payment,
    PaymentAllocation, PriceBook, PriceBookLine, Product, ProductBatch,
    ProductVersion, PurchaseOrder, PurchaseOrderLine, SalesInvoice,
    SalesInvoiceLine, SalesOrder, SalesOrderLine, SalesRep, SalesReturn,
    SalesReturnLine, Stocktake, StocktakeLine, Supplier, SupplierInvoice,
    SupplierPayment, Territory, Warehouse,
)


T = TypeVar("T")
ZERO = Decimal("0")


class SalesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, item: T) -> T:
        self.session.add(item)
        self.session.flush()
        return item

    def flush(self) -> None:
        self.session.flush()

    @staticmethod
    def _identifier_predicate(model, uid_field, identifier: int | str):
        if isinstance(identifier, int) or str(identifier).isdigit():
            return model.id == int(identifier)
        return or_(uid_field == str(identifier), *(
            [model.sku == str(identifier)] if model is Product else
            [model.customer_code == str(identifier)] if model is Customer else
            [model.supplier_code == str(identifier)] if model is Supplier else
            [model.code == str(identifier)] if model in {Warehouse, SalesRep, Territory} else
            [model.order_number == str(identifier)] if model in {SalesOrder, PurchaseOrder} else
            [model.invoice_number == str(identifier)] if model in {SalesInvoice, SupplierInvoice} else []
        ))

    def get_product(self, identifier: int | str) -> Product | None:
        return self.session.scalar(select(Product).where(self._identifier_predicate(Product, Product.product_uid, identifier)))

    def list_products(self, *, active: bool | None = None, query: str | None = None) -> list[Product]:
        statement = select(Product)
        if active is not None:
            statement = statement.where(Product.active == active)
        if query:
            needle = f"%{query}%"
            statement = statement.where(or_(Product.sku.ilike(needle), Product.product_name_en.ilike(needle), Product.product_name_ar.ilike(needle)))
        return list(self.session.scalars(statement.order_by(Product.sku)))

    def product_versions(self, product_id: int) -> list[ProductVersion]:
        return list(self.session.scalars(select(ProductVersion).where(ProductVersion.product_id == product_id).order_by(ProductVersion.version)))

    def get_customer(self, identifier: int | str) -> Customer | None:
        return self.session.scalar(select(Customer).where(self._identifier_predicate(Customer, Customer.customer_uid, identifier)))

    def list_customers(self) -> list[Customer]:
        return list(self.session.scalars(select(Customer).order_by(Customer.customer_code)))

    def get_supplier(self, identifier: int | str) -> Supplier | None:
        return self.session.scalar(select(Supplier).where(self._identifier_predicate(Supplier, Supplier.supplier_uid, identifier)))

    def list_suppliers(self) -> list[Supplier]:
        return list(self.session.scalars(select(Supplier).order_by(Supplier.supplier_code)))

    def get_warehouse(self, identifier: int | str) -> Warehouse | None:
        return self.session.scalar(select(Warehouse).where(self._identifier_predicate(Warehouse, Warehouse.warehouse_uid, identifier)))

    def list_warehouses(self) -> list[Warehouse]:
        return list(self.session.scalars(select(Warehouse).order_by(Warehouse.code)))

    def get_pricebook(self, identifier: int | str) -> PriceBook | None:
        predicate = PriceBook.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else or_(PriceBook.pricebook_uid == str(identifier), PriceBook.name == str(identifier))
        return self.session.scalar(select(PriceBook).where(predicate))

    def list_pricebooks(self) -> list[PriceBook]:
        return list(self.session.scalars(select(PriceBook).order_by(PriceBook.name, PriceBook.version.desc())))

    def pricebook_lines(self, pricebook_id: int, product_id: int | None = None) -> list[PriceBookLine]:
        statement = select(PriceBookLine).where(PriceBookLine.pricebook_id == pricebook_id)
        if product_id is not None:
            statement = statement.where(PriceBookLine.product_id == product_id)
        return list(self.session.scalars(statement.order_by(PriceBookLine.product_id, PriceBookLine.min_qty.desc())))

    def get_order(self, identifier: int | str) -> SalesOrder | None:
        return self.session.scalar(select(SalesOrder).where(self._identifier_predicate(SalesOrder, SalesOrder.order_uid, identifier)))

    def order_by_idempotency(self, key: str) -> SalesOrder | None:
        return self.session.scalar(select(SalesOrder).where(SalesOrder.idempotency_key == key))

    def order_lines(self, order_id: int) -> list[SalesOrderLine]:
        return list(self.session.scalars(select(SalesOrderLine).where(SalesOrderLine.order_id == order_id).order_by(SalesOrderLine.id)))

    def customer_orders(self, customer_id: int) -> list[SalesOrder]:
        return list(self.session.scalars(select(SalesOrder).where(SalesOrder.customer_id == customer_id).order_by(SalesOrder.order_date.desc())))

    def list_orders(self, *, customer_id: int | None = None) -> list[SalesOrder]:
        statement = select(SalesOrder)
        if customer_id is not None: statement = statement.where(SalesOrder.customer_id == customer_id)
        return list(self.session.scalars(statement.order_by(SalesOrder.order_date.desc())))

    def get_invoice(self, identifier: int | str) -> SalesInvoice | None:
        return self.session.scalar(select(SalesInvoice).where(self._identifier_predicate(SalesInvoice, SalesInvoice.invoice_uid, identifier)))

    def invoice_by_idempotency(self, key: str) -> SalesInvoice | None:
        return self.session.scalar(select(SalesInvoice).where(SalesInvoice.idempotency_key == key))

    def invoice_by_fingerprint(self, value: str) -> SalesInvoice | None:
        return self.session.scalar(select(SalesInvoice).where(SalesInvoice.fingerprint == value))

    def invoice_lines(self, invoice_id: int) -> list[SalesInvoiceLine]:
        return list(self.session.scalars(select(SalesInvoiceLine).where(SalesInvoiceLine.invoice_id == invoice_id).order_by(SalesInvoiceLine.id)))

    def customer_invoices(self, customer_id: int) -> list[SalesInvoice]:
        return list(self.session.scalars(select(SalesInvoice).where(SalesInvoice.customer_id == customer_id).order_by(SalesInvoice.invoice_date.desc())))

    def posted_invoices(self, *, customer_id: int | None = None, business_date: date | None = None) -> list[SalesInvoice]:
        statement = select(SalesInvoice).where(SalesInvoice.status.in_(("POSTED", "PARTIALLY_PAID", "PAID", "OVERDUE", "CREDITED")))
        if customer_id is not None:
            statement = statement.where(SalesInvoice.customer_id == customer_id)
        if business_date is not None:
            statement = statement.where(SalesInvoice.invoice_date == business_date)
        return list(self.session.scalars(statement.order_by(SalesInvoice.invoice_date, SalesInvoice.id)))

    def get_payment(self, identifier: int | str) -> Payment | None:
        predicate = Payment.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else Payment.payment_uid == str(identifier)
        return self.session.scalar(select(Payment).where(predicate))

    def payment_by_idempotency(self, key: str) -> Payment | None:
        return self.session.scalar(select(Payment).where(Payment.idempotency_key == key))

    def payment_allocations(self, payment_id: int) -> list[PaymentAllocation]:
        return list(self.session.scalars(select(PaymentAllocation).where(PaymentAllocation.payment_id == payment_id)))

    def invoice_allocated(self, invoice_id: int) -> Decimal:
        return self.session.scalar(select(func.coalesce(func.sum(PaymentAllocation.amount), ZERO)).where(PaymentAllocation.invoice_id == invoice_id)) or ZERO

    def invoice_return_total(self, invoice_id: int) -> Decimal:
        return self.session.scalar(select(func.coalesce(func.sum(SalesReturn.total), ZERO)).where(SalesReturn.invoice_id == invoice_id, SalesReturn.status == "POSTED")) or ZERO

    def payment_allocated(self, payment_id: int) -> Decimal:
        return self.session.scalar(select(func.coalesce(func.sum(PaymentAllocation.amount), ZERO)).where(PaymentAllocation.payment_id == payment_id)) or ZERO

    def customer_payments(self, customer_id: int) -> list[Payment]:
        return list(self.session.scalars(select(Payment).where(Payment.customer_id == customer_id).order_by(Payment.payment_date)))

    def stock_on_hand(self, product_id: int, warehouse_id: int | None = None) -> Decimal:
        statement = select(func.coalesce(func.sum(InventoryMovement.quantity * InventoryMovement.direction), ZERO)).where(InventoryMovement.product_id == product_id)
        if warehouse_id is not None:
            statement = statement.where(InventoryMovement.warehouse_id == warehouse_id)
        return self.session.scalar(statement) or ZERO

    def stock_reserved(self, product_id: int, warehouse_id: int | None = None) -> Decimal:
        statement = select(func.coalesce(func.sum(InventoryReservation.quantity), ZERO)).where(InventoryReservation.product_id == product_id, InventoryReservation.status == "ACTIVE")
        if warehouse_id is not None:
            statement = statement.where(InventoryReservation.warehouse_id == warehouse_id)
        return self.session.scalar(statement) or ZERO

    def inventory_movements(self, product_id: int | None = None, warehouse_id: int | None = None) -> list[InventoryMovement]:
        statement = select(InventoryMovement)
        if product_id is not None: statement = statement.where(InventoryMovement.product_id == product_id)
        if warehouse_id is not None: statement = statement.where(InventoryMovement.warehouse_id == warehouse_id)
        return list(self.session.scalars(statement.order_by(InventoryMovement.transaction_date, InventoryMovement.id)))

    def inventory_movement_by_key(self, key: str) -> InventoryMovement | None:
        return self.session.scalar(select(InventoryMovement).where(InventoryMovement.idempotency_key == key))

    def get_stocktake(self, identifier: int | str) -> Stocktake | None:
        predicate = Stocktake.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else Stocktake.stocktake_uid == str(identifier)
        return self.session.scalar(select(Stocktake).where(predicate))

    def stocktake_lines(self, stocktake_id: int) -> list[StocktakeLine]:
        return list(self.session.scalars(select(StocktakeLine).where(StocktakeLine.stocktake_id == stocktake_id)))

    def active_reservation(self, order_line_id: int) -> InventoryReservation | None:
        return self.session.scalar(select(InventoryReservation).where(InventoryReservation.order_line_id == order_line_id, InventoryReservation.status == "ACTIVE"))

    def get_purchase_order(self, identifier: int | str) -> PurchaseOrder | None:
        return self.session.scalar(select(PurchaseOrder).where(self._identifier_predicate(PurchaseOrder, PurchaseOrder.purchase_order_uid, identifier)))

    def purchase_order_lines(self, purchase_order_id: int) -> list[PurchaseOrderLine]:
        return list(self.session.scalars(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == purchase_order_id)))

    def receipt_by_key(self, key: str) -> GoodsReceipt | None:
        return self.session.scalar(select(GoodsReceipt).where(GoodsReceipt.idempotency_key == key))

    def get_daily_close(self, identifier: int | str | date) -> DailyClose | None:
        if isinstance(identifier, date): predicate = DailyClose.business_date == identifier
        elif isinstance(identifier, int) or str(identifier).isdigit(): predicate = DailyClose.id == int(identifier)
        else:
            try: predicate = DailyClose.business_date == date.fromisoformat(str(identifier))
            except ValueError: predicate = DailyClose.daily_close_uid == str(identifier)
        return self.session.scalar(select(DailyClose).where(predicate))

    def get_msc_batch(self, identifier: int | str) -> MscIntakeBatch | None:
        predicate = MscIntakeBatch.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else MscIntakeBatch.batch_uid == str(identifier)
        return self.session.scalar(select(MscIntakeBatch).where(predicate))

    def msc_batch_by_key(self, key: str) -> MscIntakeBatch | None:
        return self.session.scalar(select(MscIntakeBatch).where(MscIntakeBatch.idempotency_key == key))

    def msc_files(self, batch_id: int) -> list[MscIntakeFile]:
        return list(self.session.scalars(select(MscIntakeFile).where(MscIntakeFile.batch_id == batch_id).order_by(MscIntakeFile.sequence)))

    def get_msc_file(self, identifier: int | str) -> MscIntakeFile | None:
        predicate = MscIntakeFile.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else MscIntakeFile.file_uid == str(identifier)
        return self.session.scalar(select(MscIntakeFile).where(predicate))

    def msc_file_by_hash(self, value: str) -> MscIntakeFile | None:
        return self.session.scalar(select(MscIntakeFile).where(MscIntakeFile.file_hash == value))

    def msc_staging(self, batch_id: int) -> list[MscInvoiceStaging]:
        return list(self.session.scalars(select(MscInvoiceStaging).where(MscInvoiceStaging.batch_id == batch_id).order_by(MscInvoiceStaging.id)))

    def collection_activities(self, customer_id: int | None = None) -> list[CollectionActivity]:
        statement = select(CollectionActivity)
        if customer_id is not None: statement = statement.where(CollectionActivity.customer_id == customer_id)
        return list(self.session.scalars(statement.order_by(CollectionActivity.created_at.desc())))

    def get_territory(self, identifier: int | str) -> Territory | None:
        return self.session.scalar(select(Territory).where(self._identifier_predicate(Territory, Territory.territory_uid, identifier)))

    def get_sales_rep(self, identifier: int | str) -> SalesRep | None:
        return self.session.scalar(select(SalesRep).where(self._identifier_predicate(SalesRep, SalesRep.sales_rep_uid, identifier)))

    def get_delivery(self, identifier: int | str) -> Delivery | None:
        predicate = Delivery.id == int(identifier) if isinstance(identifier, int) or str(identifier).isdigit() else Delivery.delivery_uid == str(identifier)
        return self.session.scalar(select(Delivery).where(predicate))

    def delivery_for_order(self, order_id: int) -> Delivery | None:
        return self.session.scalar(select(Delivery).where(Delivery.order_id == order_id).order_by(Delivery.id.desc()))

    def customer_deliveries(self, customer_id: int) -> list[Delivery]:
        return list(self.session.scalars(select(Delivery).where(Delivery.customer_id == customer_id).order_by(Delivery.created_at.desc())))

    def customer_returns(self, customer_id: int) -> list[SalesReturn]:
        return list(self.session.scalars(select(SalesReturn).join(SalesInvoice, SalesInvoice.id == SalesReturn.invoice_id).where(SalesInvoice.customer_id == customer_id).order_by(SalesReturn.return_date.desc())))

    def list_purchase_orders(self, supplier_id: int | None = None) -> list[PurchaseOrder]:
        statement = select(PurchaseOrder)
        if supplier_id is not None: statement = statement.where(PurchaseOrder.supplier_id == supplier_id)
        return list(self.session.scalars(statement.order_by(PurchaseOrder.order_date.desc())))

    def journal_by_reference(self, reference_type: str, reference_id: str) -> AccountingJournal | None:
        return self.session.scalar(select(AccountingJournal).where(AccountingJournal.reference_type == reference_type, AccountingJournal.reference_id == reference_id))

    def event_by_key(self, key: str) -> BusinessEvent | None:
        return self.session.scalar(select(BusinessEvent).where(BusinessEvent.idempotency_key == key))

    def journal_lines(self, journal_id: int) -> list[AccountingJournalLine]:
        return list(self.session.scalars(select(AccountingJournalLine).where(AccountingJournalLine.journal_id == journal_id)))

    def posted_journals(self) -> list[AccountingJournal]:
        return list(self.session.scalars(select(AccountingJournal).where(AccountingJournal.status == "POSTED")))

    def supplier_invoiced_total(self, supplier_id: int) -> Decimal:
        return self.session.scalar(select(func.coalesce(func.sum(SupplierInvoice.total), ZERO)).where(SupplierInvoice.supplier_id == supplier_id, SupplierInvoice.status == "POSTED")) or ZERO

    def supplier_paid_total(self, supplier_id: int) -> Decimal:
        return self.session.scalar(select(func.coalesce(func.sum(SupplierPayment.amount), ZERO)).where(SupplierPayment.supplier_id == supplier_id)) or ZERO

    def daily_unposted_invoices(self, business_date: date) -> int:
        return int(self.session.scalar(select(func.count()).select_from(SalesInvoice).where(SalesInvoice.invoice_date == business_date, SalesInvoice.status.in_(("DRAFT", "VALIDATED")))) or 0)

    def daily_unallocated_payments(self, business_date: date) -> int:
        payments = list(self.session.scalars(select(Payment).where(func.date(Payment.payment_date) == business_date.isoformat(), Payment.status == "RECEIVED")))
        return sum(1 for payment in payments if self.payment_allocated(payment.id) < payment.amount)

    def daily_pending_msc(self, business_date: date) -> int:
        return int(self.session.scalar(select(func.count()).select_from(MscIntakeBatch).where(MscIntakeBatch.business_date == business_date, MscIntakeBatch.status.not_in(("POSTED", "CANCELLED")))) or 0)

    def sales_quantity(self, product_id: int, since: date) -> Decimal:
        return self.session.scalar(select(func.coalesce(func.sum(SalesInvoiceLine.quantity), ZERO)).join(SalesInvoice, SalesInvoice.id == SalesInvoiceLine.invoice_id).where(SalesInvoiceLine.product_id == product_id, SalesInvoice.invoice_date >= since, SalesInvoice.status.in_(("POSTED", "PARTIALLY_PAID", "PAID", "OVERDUE")))) or ZERO
