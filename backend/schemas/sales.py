"""Transport contracts for the Product/Sales operating engine."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SalesSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ProductCreate(SalesSchema):
    sku: str = Field(min_length=1, max_length=100)
    barcode: str | None = None
    product_name_ar: str | None = None
    product_name_en: str | None = None
    brand: str | None = None
    category: str | None = None
    subcategory: str | None = None
    variant: str | None = None
    size: str | None = None
    unit: str = "piece"
    pack_size: Decimal | None = None
    case_size: Decimal | None = None
    color: str | None = None
    shade: str | None = None
    model: str | None = None
    manufacturer: str | None = None
    supplier_default_id: int | None = None
    status: str = "ACTIVE"
    tax_profile: str | None = None
    cost_basis: str | None = None
    standard_cost: Decimal | None = None
    facts: dict[str, Any] = Field(default_factory=dict)


class ProductUpdate(SalesSchema):
    barcode: str | None = None
    product_name_ar: str | None = None
    product_name_en: str | None = None
    brand: str | None = None
    category: str | None = None
    subcategory: str | None = None
    variant: str | None = None
    size: str | None = None
    unit: str | None = None
    pack_size: Decimal | None = None
    case_size: Decimal | None = None
    color: str | None = None
    shade: str | None = None
    model: str | None = None
    manufacturer: str | None = None
    supplier_default_id: int | None = None
    status: str | None = None
    active: bool | None = None
    tax_profile: str | None = None
    cost_basis: str | None = None
    standard_cost: Decimal | None = None
    facts: dict[str, Any] | None = None
    approved_by: str | None = None
    reason: str | None = None


class PriceBookLineCreate(SalesSchema):
    product_id: int | str
    min_qty: Decimal = Field(default=Decimal("1"), gt=0)
    max_qty: Decimal | None = None
    unit_price: Decimal = Field(ge=0)
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    net_price: Decimal | None = Field(default=None, ge=0)
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    approved: bool = False


class PriceBookCreate(SalesSchema):
    name: str
    currency: str = "EGP"
    customer_segment: str | None = None
    sales_channel: str | None = None
    effective_from: datetime
    effective_to: datetime | None = None
    version: int = Field(default=1, ge=1)
    status: str = "ACTIVE"
    approved_by: str | None = None
    lines: list[PriceBookLineCreate] = Field(default_factory=list)


class CustomerCreate(SalesSchema):
    customer_code: str
    lead_uid: str | None = None
    business_name: str
    trade_name: str | None = None
    customer_type: str = "OTHER"
    segment: str | None = None
    pricing_tier: str = "RETAIL"
    default_pricebook_id: int | None = None
    commercial_class: str | None = None
    tax_id: str | None = None
    commercial_registry: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    website: str | None = None
    address: str | None = None
    governorate: str | None = None
    city: str | None = None
    district: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    delivery_zone: str | None = None
    sales_rep_id: int | None = None
    status: str = "ACTIVE"
    credit_status: str = "CLEAR"
    credit_limit: Decimal = Field(default=Decimal("0"), ge=0)
    payment_terms_days: int = Field(default=0, ge=0)
    source: str = "DIRECT"


class SupplierCreate(SalesSchema):
    supplier_code: str
    supplier_name: str
    tax_id: str | None = None
    commercial_registry: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    payment_terms: str | None = None
    lead_time_days: int | None = Field(default=None, ge=0)
    moq: Decimal | None = Field(default=None, ge=0)
    currency: str = "EGP"


class WarehouseCreate(SalesSchema):
    code: str
    name: str
    location: str | None = None
    warehouse_type: str = "STORAGE"


class OrderLineCreate(SalesSchema):
    product_id: int | str
    quantity: Decimal = Field(gt=0)
    warehouse_id: int | str
    unit: str | None = None
    manual_unit_price: Decimal | None = Field(default=None, ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    tax: Decimal = Field(default=Decimal("0"), ge=0)


class SalesOrderCreate(SalesSchema):
    order_number: str
    customer_id: int | str
    order_date: datetime
    channel: str = "DIRECT"
    sales_rep_id: int | None = None
    pricebook_id: int | str
    currency: str = "EGP"
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    tax: Decimal = Field(default=Decimal("0"), ge=0)
    shipping: Decimal = Field(default=Decimal("0"), ge=0)
    idempotency_key: str | None = None
    lines: list[OrderLineCreate] = Field(min_length=1)


class ApprovalDecision(SalesSchema):
    approved_by: str
    allow_overrides: bool = False


class InvoiceLineCreate(SalesSchema):
    product_id: int | str
    warehouse_id: int | str
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    tax: Decimal = Field(default=Decimal("0"), ge=0)


class InvoiceCreate(SalesSchema):
    invoice_number: str
    order_id: int | str | None = None
    customer_id: int | str | None = None
    invoice_date: date
    due_date: date | None = None
    currency: str = "EGP"
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    tax: Decimal = Field(default=Decimal("0"), ge=0)
    shipping: Decimal = Field(default=Decimal("0"), ge=0)
    source_system: str = "DIRECT"
    idempotency_key: str | None = None
    lines: list[InvoiceLineCreate] = Field(default_factory=list)


class PostRequest(SalesSchema):
    posted_by: str


class PaymentCreate(SalesSchema):
    customer_id: int | str
    payment_date: datetime
    amount: Decimal = Field(gt=0)
    currency: str = "EGP"
    method: str
    reference: str | None = None
    bank_wallet_account: str | None = None
    received_by: str
    idempotency_key: str | None = None


class AllocationLine(SalesSchema):
    invoice_id: int | str
    amount: Decimal = Field(gt=0)


class PaymentAllocate(SalesSchema):
    allocated_by: str
    allocations: list[AllocationLine] = Field(min_length=1)


class InventoryAdjustment(SalesSchema):
    product_id: int | str
    warehouse_id: int | str
    quantity: Decimal = Field(gt=0)
    direction: str
    reason: str
    posted_by: str
    idempotency_key: str | None = None

    @field_validator("direction")
    @classmethod
    def direction_allowed(cls, value: str) -> str:
        value = value.upper()
        if value not in {"IN", "OUT"}:
            raise ValueError("direction must be IN or OUT")
        return value


class InventoryTransfer(SalesSchema):
    product_id: int | str
    source_warehouse_id: int | str
    destination_warehouse_id: int | str
    quantity: Decimal = Field(gt=0)
    posted_by: str
    idempotency_key: str | None = None


class StocktakeLineCreate(SalesSchema):
    product_id: int | str
    counted_qty: Decimal = Field(ge=0)
    reason: str | None = None


class StocktakeCreate(SalesSchema):
    warehouse_id: int | str
    started_at: datetime
    lines: list[StocktakeLineCreate] = Field(default_factory=list)


class StocktakeComplete(SalesSchema):
    approved_by: str
    approve_all_variances: bool = False


class PurchaseOrderLineCreate(SalesSchema):
    product_id: int | str
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)


class PurchaseOrderCreate(SalesSchema):
    order_number: str
    supplier_id: int | str
    order_date: date
    expected_date: date | None = None
    currency: str = "EGP"
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    tax: Decimal = Field(default=Decimal("0"), ge=0)
    shipping: Decimal = Field(default=Decimal("0"), ge=0)
    lines: list[PurchaseOrderLineCreate] = Field(min_length=1)


class ReceiptLineCreate(SalesSchema):
    purchase_order_line_id: int
    quantity: Decimal = Field(gt=0)
    batch_number: str | None = None
    expiry_date: date | None = None


class GoodsReceiptCreate(SalesSchema):
    receipt_number: str
    purchase_order_id: int | str
    warehouse_id: int | str
    received_at: datetime
    received_by: str
    idempotency_key: str | None = None
    lines: list[ReceiptLineCreate] = Field(min_length=1)


class SupplierInvoiceCreate(SalesSchema):
    invoice_number: str
    supplier_id: int | str
    purchase_order_id: int | str | None = None
    invoice_date: date
    due_date: date
    currency: str = "EGP"
    total: Decimal = Field(gt=0)


class SupplierPaymentCreate(SalesSchema):
    supplier_id: int | str
    payment_date: datetime
    amount: Decimal = Field(gt=0)
    currency: str = "EGP"
    method: str
    reference: str | None = None


class CollectionActivityCreate(SalesSchema):
    customer_id: int | str
    invoice_id: int | None = None
    activity_type: str
    status: str
    actor: str
    promise_date: date | None = None
    promise_amount: Decimal | None = Field(default=None, gt=0)
    notes: str | None = None


class DailyCloseCreate(SalesSchema):
    business_date: date


class DailyCloseAction(SalesSchema):
    actor: str
    approved_override: bool = False
    reason: str | None = None


class MscBatchCreate(SalesSchema):
    business_date: date
    capture_date: datetime
    source_hash: str
    sequence_start: int | None = None
    sequence_end: int | None = None
    extractor: str = "mock"
    extractor_version: str = "1.0.0"
    idempotency_key: str | None = None


class MscExtractionRecord(SalesSchema):
    source_file_id: int | str
    invoice_number: str | None = None
    invoice_date: str | None = None
    customer: str | None = None
    product: str | None = None
    quantity: str | None = None
    price: str | None = None
    total: str | None = None
    confidence: Decimal = Field(ge=0, le=1)
    fields: dict[str, Any] = Field(default_factory=dict)


class MscExtractRequest(SalesSchema):
    records: list[MscExtractionRecord] = Field(default_factory=list)


class MscApprovalRequest(SalesSchema):
    approved_by: str


class JournalLineCreate(SalesSchema):
    account_code: str
    debit: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    memo: str | None = None


class JournalCreate(SalesSchema):
    business_date: date
    reference_type: str
    reference_id: str
    currency: str = "EGP"
    lines: list[JournalLineCreate] = Field(min_length=2)


class TerritoryCreate(SalesSchema):
    code: str
    name: str
    scope: dict[str, Any] = Field(default_factory=dict)


class SalesRepCreate(SalesSchema):
    code: str
    name: str
    territory_id: int | str | None = None
    targets: dict[str, Any] = Field(default_factory=dict)
    collections_responsibility: bool = False


class DeliveryCreate(SalesSchema):
    order_id: int | str
    address: str
    zone: str | None = None
    driver: str | None = None
    vehicle: str | None = None
    scheduled_at: datetime | None = None
    company_delivery_cost: Decimal = Field(default=Decimal("0"), ge=0)
    customer_delivery_charge: Decimal = Field(default=Decimal("0"), ge=0)


class DeliveryUpdate(SalesSchema):
    status: str
    actor: str
    failure_reason: str | None = None


class SalesReturnLineCreate(SalesSchema):
    product_id: int | str
    warehouse_id: int | str
    quantity: Decimal = Field(gt=0)
    amount: Decimal = Field(ge=0)
    condition: str = "GOOD"
    disposition: str = "RESTOCK"


class SalesReturnCreate(SalesSchema):
    invoice_id: int | str
    reason: str
    actor: str
    lines: list[SalesReturnLineCreate] = Field(min_length=1)
