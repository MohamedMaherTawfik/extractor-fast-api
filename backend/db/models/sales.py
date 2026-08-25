"""Canonical product, sales, inventory, intake, and accounting records.

Money and quantities use ``Decimal``-backed ``Numeric`` columns.  Balances are
derived from ledgers; master rows never expose a mutable balance field.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON,
    Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, TimestampMixin, utc_now


MONEY = Numeric(18, 4)
QTY = Numeric(18, 4)


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_name", "product_name_en", "product_name_ar"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(100), unique=True)
    product_name_ar: Mapped[str | None] = mapped_column(String(255))
    product_name_en: Mapped[str | None] = mapped_column(String(255))
    brand: Mapped[str | None] = mapped_column(String(150))
    category: Mapped[str | None] = mapped_column(String(150))
    subcategory: Mapped[str | None] = mapped_column(String(150))
    variant: Mapped[str | None] = mapped_column(String(150))
    size: Mapped[str | None] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(String(50), default="piece", nullable=False)
    pack_size: Mapped[Decimal | None] = mapped_column(QTY)
    case_size: Mapped[Decimal | None] = mapped_column(QTY)
    color: Mapped[str | None] = mapped_column(String(100))
    shade: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    supplier_default_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tax_profile: Mapped[str | None] = mapped_column(String(100))
    cost_basis: Mapped[str | None] = mapped_column(String(30))
    standard_cost: Mapped[Decimal | None] = mapped_column(MONEY)
    facts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ProductVersion(Base):
    __tablename__ = "product_versions"
    __table_args__ = (UniqueConstraint("product_id", "version", name="uq_product_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(255))
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("product_versions.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    supplier_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(100))
    commercial_registry: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    payment_terms: Mapped[str | None] = mapped_column(String(100))
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    moq: Mapped[Decimal | None] = mapped_column(QTY)
    currency: Mapped[str] = mapped_column(String(3), default="EGP", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"
    __table_args__ = (Index("ix_customers_name_phone", "business_name", "phone"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    customer_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    lead_uid: Mapped[str | None] = mapped_column(String(100), unique=True)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(255))
    customer_type: Mapped[str] = mapped_column(String(50), default="OTHER", nullable=False)
    segment: Mapped[str | None] = mapped_column(String(100))
    pricing_tier: Mapped[str] = mapped_column(String(50), default="RETAIL", nullable=False)
    default_pricebook_id: Mapped[int | None] = mapped_column(ForeignKey("pricebooks.id", ondelete="SET NULL"))
    commercial_class: Mapped[str | None] = mapped_column(String(20))
    tax_id: Mapped[str | None] = mapped_column(String(100))
    commercial_registry: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(50))
    whatsapp: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(500))
    address: Mapped[str | None] = mapped_column(Text)
    governorate: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    delivery_zone: Mapped[str | None] = mapped_column(String(100))
    sales_rep_id: Mapped[int | None] = mapped_column(ForeignKey("sales_reps.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    credit_status: Mapped[str] = mapped_column(String(30), default="CLEAR", nullable=False)
    credit_limit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="DIRECT", nullable=False)


class PriceBook(Base, TimestampMixin):
    __tablename__ = "pricebooks"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_pricebook_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pricebook_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EGP", nullable=False)
    customer_segment: Mapped[str | None] = mapped_column(String(100))
    sales_channel: Mapped[str | None] = mapped_column(String(100))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))


class PriceBookLine(Base, TimestampMixin):
    __tablename__ = "pricebook_lines"
    __table_args__ = (
        UniqueConstraint("pricebook_id", "product_id", "min_qty", name="uq_pricebook_product_tier"),
        CheckConstraint("min_qty > 0", name="ck_pricebook_min_qty_positive"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pricebook_line_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    pricebook_id: Mapped[int] = mapped_column(ForeignKey("pricebooks.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    min_qty: Mapped[Decimal] = mapped_column(QTY, default=Decimal("1"), nullable=False)
    max_qty: Mapped[Decimal | None] = mapped_column(QTY)
    unit_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("0"), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    net_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Warehouse(Base, TimestampMixin):
    __tablename__ = "warehouses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    warehouse_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(Text)
    warehouse_type: Mapped[str] = mapped_column(String(50), default="STORAGE", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProductBatch(Base, TimestampMixin):
    __tablename__ = "product_batches"
    __table_args__ = (UniqueConstraint("product_id", "warehouse_id", "batch_number", name="uq_product_batch"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lot_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(100), nullable=False)
    manufacture_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    __table_args__ = (
        Index("ix_inventory_product_warehouse", "product_id", "warehouse_id", "transaction_date"),
        UniqueConstraint("idempotency_key", name="uq_inventory_idempotency"),
        CheckConstraint("quantity > 0", name="ck_inventory_qty_positive"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movement_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    direction: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    posted_by: Mapped[str] = mapped_column(String(255), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("product_batches.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)


class InventoryReservation(Base, TimestampMixin):
    __tablename__ = "inventory_reservations"
    __table_args__ = (UniqueConstraint("order_line_id", name="uq_reservation_order_line"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reservation_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    order_line_id: Mapped[int] = mapped_column(ForeignKey("sales_order_lines.id", ondelete="CASCADE"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Stocktake(Base, TimestampMixin):
    __tablename__ = "stocktakes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stocktake_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="OPEN", nullable=False)


class StocktakeLine(Base):
    __tablename__ = "stocktake_lines"
    __table_args__ = (UniqueConstraint("stocktake_id", "product_id", name="uq_stocktake_product"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stocktake_id: Mapped[int] = mapped_column(ForeignKey("stocktakes.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    system_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    counted_qty: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    variance: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    approved_adjustment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SalesOrder(Base, TimestampMixin):
    __tablename__ = "sales_orders"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_sales_order_idempotency"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    order_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    order_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), default="DIRECT", nullable=False)
    sales_rep_id: Mapped[int | None] = mapped_column(ForeignKey("sales_reps.id", ondelete="SET NULL"))
    pricebook_id: Mapped[int] = mapped_column(ForeignKey("pricebooks.id", ondelete="RESTRICT"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    tax: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    shipping: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    payment_status: Mapped[str] = mapped_column(String(30), default="UNPAID", nullable=False)
    fulfillment_status: Mapped[str] = mapped_column(String(30), default="UNFULFILLED", nullable=False)
    order_status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))


class SalesOrderLine(Base):
    __tablename__ = "sales_order_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_line_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    net_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    tax: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    manual_price_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SalesInvoice(Base, TimestampMixin):
    __tablename__ = "sales_invoices"
    __table_args__ = (
        UniqueConstraint("source_system", "invoice_number", name="uq_invoice_source_number"),
        UniqueConstraint("idempotency_key", name="uq_invoice_idempotency"),
        UniqueConstraint("fingerprint", name="uq_invoice_fingerprint"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("sales_orders.id", ondelete="RESTRICT"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    tax: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    shipping: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), default="DIRECT", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posted_by: Mapped[str | None] = mapped_column(String(255))


class SalesInvoiceLine(Base):
    __tablename__ = "sales_invoice_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_line_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("sales_invoices.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    tax: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_payment_idempotency"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255))
    bank_wallet_account: Mapped[str | None] = mapped_column(String(255))
    received_by: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="RECEIVED", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (UniqueConstraint("payment_id", "invoice_id", name="uq_payment_invoice_allocation"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    allocation_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("sales_invoices.id", ondelete="RESTRICT"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    allocated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    allocated_by: Mapped[str] = mapped_column(String(255), nullable=False)


class CollectionActivity(Base, TimestampMixin):
    __tablename__ = "collection_activities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("sales_invoices.id", ondelete="SET NULL"))
    activity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    promise_date: Mapped[date | None] = mapped_column(Date)
    promise_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    notes: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)


class PurchaseOrder(Base, TimestampMixin):
    __tablename__ = "purchase_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_order_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    order_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    discount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    tax: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    shipping: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)


class GoodsReceipt(Base, TimestampMixin):
    __tablename__ = "goods_receipts"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_goods_receipt_idempotency"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    receipt_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="POSTED", nullable=False)
    received_by: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)


class GoodsReceiptLine(Base):
    __tablename__ = "goods_receipt_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("goods_receipts.id", ondelete="CASCADE"), nullable=False)
    purchase_order_line_id: Mapped[int] = mapped_column(ForeignKey("purchase_order_lines.id", ondelete="RESTRICT"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    batch_number: Mapped[str | None] = mapped_column(String(100))
    expiry_date: Mapped[date | None] = mapped_column(Date)


class SupplierInvoice(Base, TimestampMixin):
    __tablename__ = "supplier_invoices"
    __table_args__ = (UniqueConstraint("supplier_id", "invoice_number", name="uq_supplier_invoice"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_invoice_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id", ondelete="SET NULL"))
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="POSTED", nullable=False)


class SupplierPayment(Base, TimestampMixin):
    __tablename__ = "supplier_payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_payment_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False)
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255))


class SalesReturn(Base, TimestampMixin):
    __tablename__ = "sales_returns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    return_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("sales_invoices.id", ondelete="RESTRICT"), nullable=False)
    return_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)


class SalesReturnLine(Base):
    __tablename__ = "sales_return_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    return_id: Mapped[int] = mapped_column(ForeignKey("sales_returns.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    condition: Mapped[str] = mapped_column(String(30), nullable=False)
    disposition: Mapped[str] = mapped_column(String(30), nullable=False)


class Territory(Base, TimestampMixin):
    __tablename__ = "territories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    territory_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SalesRep(Base, TimestampMixin):
    __tablename__ = "sales_reps"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sales_rep_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    territory_id: Mapped[int | None] = mapped_column(ForeignKey("territories.id", ondelete="SET NULL"))
    targets: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    collections_responsibility: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Delivery(Base, TimestampMixin):
    __tablename__ = "delivery_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delivery_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("sales_orders.id", ondelete="RESTRICT"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    zone: Mapped[str | None] = mapped_column(String(100))
    driver: Mapped[str | None] = mapped_column(String(255))
    vehicle: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    company_delivery_cost: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    customer_delivery_charge: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)


class DailyClose(Base, TimestampMixin):
    __tablename__ = "daily_closes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    daily_close_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    business_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sales_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    cash_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    transfer_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    wallet_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    returns_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    stock_exception_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    financial_exception_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exceptions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    approved_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    reopen_reason: Mapped[str | None] = mapped_column(Text)


class MscIntakeBatch(Base, TimestampMixin):
    __tablename__ = "msc_intake_batches"
    __table_args__ = (UniqueConstraint("source_hash", name="uq_msc_batch_hash"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_system: Mapped[str] = mapped_column(String(30), default="MSC", nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    capture_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sequence_start: Mapped[int | None] = mapped_column(Integer)
    sequence_end: Mapped[int | None] = mapped_column(Integer)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    extractor: Mapped[str] = mapped_column(String(100), default="mock", nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(100), default="1.0.0", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="INTAKE", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)


class MscIntakeFile(Base, TimestampMixin):
    __tablename__ = "msc_intake_files"
    __table_args__ = (
        UniqueConstraint("batch_id", "sequence", name="uq_msc_batch_sequence"),
        UniqueConstraint("file_hash", name="uq_msc_file_hash"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("msc_intake_batches.id", ondelete="CASCADE"), nullable=False)
    document_uid: Mapped[str | None] = mapped_column(String(64))
    page_number: Mapped[int | None] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    capture_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extraction_status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    validation_status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    duplicate_status: Mapped[str] = mapped_column(String(30), default="UNIQUE", nullable=False)


class MscInvoiceStaging(Base, TimestampMixin):
    __tablename__ = "msc_invoice_staging"
    __table_args__ = (UniqueConstraint("batch_id", "fingerprint", name="uq_msc_batch_fingerprint"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staging_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("msc_intake_batches.id", ondelete="CASCADE"), nullable=False)
    source_file_id: Mapped[int] = mapped_column(ForeignKey("msc_intake_files.id", ondelete="CASCADE"), nullable=False)
    invoice_number_raw: Mapped[str | None] = mapped_column(String(255))
    invoice_date_raw: Mapped[str | None] = mapped_column(String(100))
    customer_raw: Mapped[str | None] = mapped_column(String(500))
    product_raw: Mapped[str | None] = mapped_column(String(500))
    qty_raw: Mapped[str | None] = mapped_column(String(100))
    price_raw: Mapped[str | None] = mapped_column(String(100))
    total_raw: Mapped[str | None] = mapped_column(String(100))
    extracted_fields: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    product_match: Mapped[str] = mapped_column(String(30), default="NO_MATCH", nullable=False)
    customer_match: Mapped[str] = mapped_column(String(30), default="NO_MATCH", nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    validation_status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    posted_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("sales_invoices.id", ondelete="SET NULL"), unique=True)
    corrections: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)


class AccountingJournal(Base, TimestampMixin):
    __tablename__ = "accounting_journals"
    __table_args__ = (UniqueConstraint("reference_type", "reference_id", name="uq_journal_reference"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    journal_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccountingJournalLine(Base):
    __tablename__ = "accounting_journal_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    journal_id: Mapped[int] = mapped_column(ForeignKey("accounting_journals.id", ondelete="CASCADE"), nullable=False)
    account_code: Mapped[str] = mapped_column(String(100), nullable=False)
    debit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    credit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"), nullable=False)
    memo: Mapped[str | None] = mapped_column(Text)


class ApprovalRequest(Base, TimestampMixin):
    __tablename__ = "approval_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    approval_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    approval_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String(255))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BusinessEvent(Base):
    __tablename__ = "business_events"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_business_event_idempotency"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLedger(Base):
    __tablename__ = "sales_audit_ledger"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    approval_reference: Mapped[str | None] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
