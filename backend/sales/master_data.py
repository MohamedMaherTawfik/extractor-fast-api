"""Product, pricing, customer, supplier, and warehouse master services."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.core.exceptions import ConflictError, NotFoundError, SalesValidationError
from backend.db.models.sales import Customer, PriceBook, PriceBookLine, Product, ProductVersion, Supplier, Warehouse
from backend.repositories.sales_repository import SalesRepository
from backend.sales.common import json_safe, money, uid
from backend.sales.audit import SalesAuditService
from backend.schemas.sales import CustomerCreate, PriceBookCreate, ProductCreate, ProductUpdate, SupplierCreate, WarehouseCreate


PRODUCT_STATUSES = {"ACTIVE", "INACTIVE", "DISCONTINUED", "OUT_OF_STOCK", "BLOCKED", "PENDING_REVIEW"}
CUSTOMER_TYPES = {"WHOLESALER", "DISTRIBUTOR", "RETAILER", "BEAUTY_CENTER", "SALON", "BARBER", "PHARMACY", "CLINIC", "ONLINE_SELLER", "INDIVIDUAL", "OTHER"}
CUSTOMER_STATUSES = {"PROSPECT_CONVERTED", "ACTIVE", "DORMANT", "ON_HOLD", "CREDIT_HOLD", "BLOCKED", "CLOSED"}


def _snapshot(product: Product) -> dict:
    excluded = {"id", "created_at", "updated_at"}
    return {column.name: json_safe(getattr(product, column.name)) for column in product.__table__.columns if column.name not in excluded}


class ProductService:
    VERSIONED_FIELDS = {"product_name_ar", "product_name_en", "pack_size", "case_size", "barcode", "category", "subcategory", "tax_profile", "cost_basis", "standard_cost", "facts"}

    def __init__(self, session: Session) -> None:
        self.repository = SalesRepository(session)

    def create(self, request: ProductCreate) -> Product:
        if self.repository.get_product(request.sku):
            raise ConflictError(f"SKU {request.sku} already exists")
        if request.status.upper() not in PRODUCT_STATUSES:
            raise SalesValidationError("Unsupported product status")
        values = request.model_dump()
        values["sku"] = values["sku"].strip().upper()
        values["status"] = values["status"].upper()
        values["active"] = values["status"] == "ACTIVE"
        product = self.repository.add(Product(product_uid=uid("PROD"), **values))
        self.repository.add(ProductVersion(product_id=product.id, version=1, snapshot=_snapshot(product), effective_from=datetime.now(UTC)))
        SalesAuditService(self.repository.session).event("PRODUCT_CREATED", "PRODUCT", product.product_uid, {"sku": product.sku, "version": 1})
        return product

    def get(self, identifier: int | str) -> Product:
        item = self.repository.get_product(identifier)
        if item is None: raise NotFoundError(f"Product {identifier} was not found")
        return item

    def list(self, *, active: bool | None = None, query: str | None = None) -> list[Product]:
        return self.repository.list_products(active=active, query=query)

    def update(self, identifier: int | str, request: ProductUpdate) -> Product:
        product = self.get(identifier)
        before = _snapshot(product)
        changes = request.model_dump(exclude_unset=True, exclude={"approved_by", "reason"})
        if "status" in changes and changes["status"].upper() not in PRODUCT_STATUSES:
            raise SalesValidationError("Unsupported product status")
        important = bool(self.VERSIONED_FIELDS.intersection(changes))
        if important:
            versions = self.repository.product_versions(product.id)
            if versions: versions[-1].effective_to = datetime.now(UTC)
        for field, value in changes.items():
            if field == "status" and value is not None: value = value.upper()
            setattr(product, field, value)
        if "status" in changes and "active" not in changes:
            product.active = product.status == "ACTIVE"
        if important:
            old_version = product.version
            product.version += 1
            self.repository.flush()
            self.repository.add(ProductVersion(product_id=product.id, version=product.version, snapshot=_snapshot(product), effective_from=datetime.now(UTC), approved_by=request.approved_by, supersedes_id=versions[-1].id if versions else None))
        SalesAuditService(self.repository.session).mutation(actor=request.approved_by or "system", action="PRODUCT_UPDATED", entity_type="PRODUCT", entity_id=product.product_uid, before=before, after=_snapshot(product), reason=request.reason, approval_reference=request.approved_by)
        SalesAuditService(self.repository.session).event("PRODUCT_CHANGED", "PRODUCT", f"{product.product_uid}:v{product.version}", {"sku": product.sku, "version": product.version})
        return product

    def versions(self, identifier: int | str) -> list[ProductVersion]:
        return self.repository.product_versions(self.get(identifier).id)


class PricingService:
    def __init__(self, session: Session) -> None: self.repository = SalesRepository(session)

    def create_pricebook(self, request: PriceBookCreate) -> PriceBook:
        book = self.repository.add(PriceBook(pricebook_uid=uid("PB"), **request.model_dump(exclude={"lines"})))
        for line in request.lines:
            product = ProductService(self.repository.session).get(line.product_id)
            values = line.model_dump(exclude={"product_id"})
            values["net_price"] = money(values["net_price"] if values["net_price"] is not None else values["unit_price"] - values["discount_amount"] - (values["unit_price"] * values["discount_percent"] / Decimal("100")))
            self.repository.add(PriceBookLine(pricebook_line_uid=uid("PBL"), pricebook_id=book.id, product_id=product.id, **values))
        return book

    def get_price(self, pricebook_id: int | str, product_id: int | str, qty: Decimal, *, at: datetime | None = None) -> PriceBookLine:
        book = self.repository.get_pricebook(pricebook_id)
        if book is None: raise NotFoundError(f"PriceBook {pricebook_id} was not found")
        product = ProductService(self.repository.session).get(product_id)
        when = at or datetime.now(UTC)
        # SQLite stores timezone-aware values without an offset. Compare in the
        # same representation while API inputs and runtime clocks remain aware.
        if book.effective_from.tzinfo is None and when.tzinfo is not None:
            when = when.replace(tzinfo=None)
        if book.status != "ACTIVE" or book.effective_from > when or (book.effective_to and book.effective_to < when):
            raise SalesValidationError("PriceBook is not active for the transaction date")
        candidates = [line for line in self.repository.pricebook_lines(book.id, product.id) if line.approved and line.min_qty <= qty and (line.max_qty is None or qty <= line.max_qty) and (line.effective_from is None or line.effective_from <= when) and (line.effective_to is None or line.effective_to >= when)]
        if not candidates: raise SalesValidationError(f"No approved price/MOQ tier for SKU {product.sku} and quantity {qty}")
        return max(candidates, key=lambda item: item.min_qty)

    def list_pricebooks(self) -> list[PriceBook]: return self.repository.list_pricebooks()


class CustomerService:
    def __init__(self, session: Session) -> None: self.repository = SalesRepository(session)

    def create(self, request: CustomerCreate) -> Customer:
        if self.repository.get_customer(request.customer_code): raise ConflictError(f"Customer {request.customer_code} already exists")
        values = request.model_dump()
        values["customer_code"] = values["customer_code"].strip().upper()
        values["customer_type"] = values["customer_type"].upper()
        values["status"] = values["status"].upper()
        if values["customer_type"] not in CUSTOMER_TYPES: raise SalesValidationError("Unsupported customer type")
        if values["status"] not in CUSTOMER_STATUSES: raise SalesValidationError("Unsupported customer status")
        values["active"] = values["status"] in {"ACTIVE", "PROSPECT_CONVERTED"}
        return self.repository.add(Customer(customer_uid=uid("CUST"), **values))

    def get(self, identifier: int | str) -> Customer:
        item = self.repository.get_customer(identifier)
        if item is None: raise NotFoundError(f"Customer {identifier} was not found")
        return item

    def list(self) -> list[Customer]: return self.repository.list_customers()


class SupplierService:
    def __init__(self, session: Session) -> None: self.repository = SalesRepository(session)

    def create(self, request: SupplierCreate) -> Supplier:
        if self.repository.get_supplier(request.supplier_code): raise ConflictError(f"Supplier {request.supplier_code} already exists")
        values = request.model_dump(); values["supplier_code"] = values["supplier_code"].strip().upper()
        return self.repository.add(Supplier(supplier_uid=uid("SUP"), active=True, **values))

    def get(self, identifier: int | str) -> Supplier:
        item = self.repository.get_supplier(identifier)
        if item is None: raise NotFoundError(f"Supplier {identifier} was not found")
        return item


class WarehouseService:
    def __init__(self, session: Session) -> None: self.repository = SalesRepository(session)

    def create(self, request: WarehouseCreate) -> Warehouse:
        if self.repository.get_warehouse(request.code): raise ConflictError(f"Warehouse {request.code} already exists")
        values = request.model_dump(); values["code"] = values["code"].strip().upper()
        return self.repository.add(Warehouse(warehouse_uid=uid("WH"), active=True, **values))

    def get(self, identifier: int | str) -> Warehouse:
        item = self.repository.get_warehouse(identifier)
        if item is None: raise NotFoundError(f"Warehouse {identifier} was not found")
        return item
