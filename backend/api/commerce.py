"""HTTP surface for product, sales, inventory, purchasing, MSC, and finance."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.repositories.sales_repository import SalesRepository
from backend.sales.common import model_dict
from backend.sales.context import ProductSalesContextService
from backend.sales.distribution import DistributionService
from backend.sales.finance import AccountingBridgeService, CollectionService, DailyCloseService, PaymentService, ReceivablesService
from backend.sales.inventory import InventoryService
from backend.sales.invoicing import InvoiceService, ReturnService
from backend.sales.master_data import CustomerService, PricingService, ProductService, SupplierService, WarehouseService
from backend.sales.msc import MSCIntakeService, SalesSheetImportService
from backend.sales.orders import SalesOrderService
from backend.sales.purchasing import PurchaseService, SupplierPayablesService
from backend.sales.reporting import SalesReportingService
from backend.schemas.sales import (
    ApprovalDecision, CustomerCreate, DailyCloseAction, DailyCloseCreate,
    GoodsReceiptCreate, InventoryAdjustment, InventoryTransfer, InvoiceCreate,
    JournalCreate, MscApprovalRequest, MscBatchCreate, MscExtractRequest,
    PaymentAllocate, PaymentCreate, PostRequest, PriceBookCreate, ProductCreate,
    ProductUpdate, PurchaseOrderCreate, SalesOrderCreate, StocktakeCreate,
    SupplierCreate, SupplierInvoiceCreate, WarehouseCreate, TerritoryCreate,
    SalesRepCreate, DeliveryCreate, DeliveryUpdate, SalesReturnCreate,
    StocktakeComplete, SupplierPaymentCreate, CollectionActivityCreate,
)


router = APIRouter(tags=["product-sales"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _rows(items): return [model_dict(item) for item in items]


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(request: ProductCreate, session: DatabaseSession): return model_dict(ProductService(session).create(request))


@router.get("/products")
def list_products(session: DatabaseSession, active: bool | None = None, q: str | None = None): return _rows(ProductService(session).list(active=active, query=q))


@router.get("/products/{product_id}")
def get_product(product_id: str, session: DatabaseSession):
    service = ProductService(session); product = service.get(product_id)
    return {**model_dict(product), "versions": _rows(service.versions(product.id))}


@router.patch("/products/{product_id}")
def update_product(product_id: str, request: ProductUpdate, session: DatabaseSession): return model_dict(ProductService(session).update(product_id, request))


@router.get("/products/{product_id}/stock")
def product_stock(product_id: str, session: DatabaseSession, warehouse_id: str | None = None): return InventoryService(session).balance(product_id, warehouse_id)


@router.get("/products/{product_id}/sales-context")
def product_sales_context(product_id: str, session: DatabaseSession, warehouse_id: str | None = None): return ProductSalesContextService(session).get_product_context(product_id, warehouse_id=warehouse_id)


@router.get("/products/movers/summary")
def product_movers(session: DatabaseSession): return ProductSalesContextService(session).movers()


@router.post("/pricebooks", status_code=status.HTTP_201_CREATED)
def create_pricebook(request: PriceBookCreate, session: DatabaseSession):
    service = PricingService(session); book = service.create_pricebook(request)
    return {**model_dict(book), "lines": _rows(service.repository.pricebook_lines(book.id))}


@router.get("/pricebooks")
def list_pricebooks(session: DatabaseSession): return _rows(PricingService(session).list_pricebooks())


@router.post("/customers", status_code=status.HTTP_201_CREATED)
def create_customer(request: CustomerCreate, session: DatabaseSession): return model_dict(CustomerService(session).create(request))


@router.get("/customers")
def list_customers(session: DatabaseSession): return _rows(CustomerService(session).list())


@router.get("/customers/{customer_id}")
def get_customer(customer_id: str, session: DatabaseSession): return model_dict(CustomerService(session).get(customer_id))


@router.get("/customers/{customer_id}/statement")
def customer_statement(customer_id: str, session: DatabaseSession): return ReceivablesService(session).statement(customer_id)


@router.get("/customers/{customer_id}/orders")
def customer_orders(customer_id: str, session: DatabaseSession):
    customer = CustomerService(session).get(customer_id); return _rows(SalesRepository(session).customer_orders(customer.id))


@router.get("/customers/{customer_id}/invoices")
def customer_invoices(customer_id: str, session: DatabaseSession):
    customer = CustomerService(session).get(customer_id); return _rows(SalesRepository(session).customer_invoices(customer.id))


@router.get("/customers/{customer_id}/balance")
def customer_balance(customer_id: str, session: DatabaseSession): return ReceivablesService(session).exposure(customer_id)


@router.post("/suppliers", status_code=status.HTTP_201_CREATED)
def create_supplier(request: SupplierCreate, session: DatabaseSession): return model_dict(SupplierService(session).create(request))


@router.get("/suppliers")
def list_suppliers(session: DatabaseSession): return _rows(SalesRepository(session).list_suppliers())


@router.get("/suppliers/{supplier_id}/balance")
def supplier_balance(supplier_id: str, session: DatabaseSession): return {"supplier_id": supplier_id, "balance": SupplierPayablesService(session).balance(supplier_id)}


@router.post("/warehouses", status_code=status.HTTP_201_CREATED)
def create_warehouse(request: WarehouseCreate, session: DatabaseSession): return model_dict(WarehouseService(session).create(request))


@router.get("/warehouses")
def list_warehouses(session: DatabaseSession): return _rows(SalesRepository(session).list_warehouses())


@router.post("/sales/orders", status_code=status.HTTP_201_CREATED)
def create_sales_order(request: SalesOrderCreate, session: DatabaseSession):
    service = SalesOrderService(session); order = service.create(request)
    return {**model_dict(order), "lines": _rows(service.repository.order_lines(order.id))}


@router.get("/sales/orders/{order_id}")
def get_sales_order(order_id: str, session: DatabaseSession):
    service = SalesOrderService(session); order = service.get(order_id)
    return {**model_dict(order), "lines": _rows(service.repository.order_lines(order.id))}


@router.post("/sales/orders/{order_id}/approve")
def approve_sales_order(order_id: str, request: ApprovalDecision, session: DatabaseSession): return model_dict(SalesOrderService(session).approve(order_id, request))


@router.post("/sales/orders/{order_id}/cancel")
def cancel_sales_order(order_id: str, session: DatabaseSession): return model_dict(SalesOrderService(session).cancel(order_id))


@router.post("/sales/invoices", status_code=status.HTTP_201_CREATED)
def create_sales_invoice(request: InvoiceCreate, session: DatabaseSession):
    service = InvoiceService(session); invoice = service.create(request)
    return {**model_dict(invoice), "lines": _rows(service.repository.invoice_lines(invoice.id)), "paid_amount": service.repository.invoice_allocated(invoice.id), "balance": service.balance(invoice)}


@router.post("/sales/invoices/{invoice_id}/post")
def post_sales_invoice(invoice_id: str, request: PostRequest, session: DatabaseSession): return model_dict(InvoiceService(session).post(invoice_id, request))


@router.get("/sales/invoices/{invoice_id}")
def get_sales_invoice(invoice_id: str, session: DatabaseSession):
    service = InvoiceService(session); invoice = service.get(invoice_id)
    return {**model_dict(invoice), "lines": _rows(service.repository.invoice_lines(invoice.id)), "paid_amount": service.repository.invoice_allocated(invoice.id), "balance": service.balance(invoice)}


@router.post("/sales/returns", status_code=status.HTTP_201_CREATED)
def create_sales_return(request: SalesReturnCreate, session: DatabaseSession):
    record = ReturnService(session).post_sales_return(invoice_id=request.invoice_id, lines=[line.model_dump() for line in request.lines], reason=request.reason, actor=request.actor)
    return model_dict(record)


@router.post("/payments", status_code=status.HTTP_201_CREATED)
def create_payment(request: PaymentCreate, session: DatabaseSession): return model_dict(PaymentService(session).create(request))


@router.post("/payments/{payment_id}/allocate")
def allocate_payment(payment_id: str, request: PaymentAllocate, session: DatabaseSession):
    service = PaymentService(session); payment = service.allocate(payment_id, request)
    return {**model_dict(payment), "allocations": _rows(service.repository.payment_allocations(payment.id)), "unallocated": payment.amount - service.repository.payment_allocated(payment.id)}


@router.get("/receivables")
def receivables(session: DatabaseSession, customer_id: str | None = None, as_of: date | None = None): return ReceivablesService(session).aging(as_of=as_of, customer_id=customer_id)


@router.get("/collections")
def collections(session: DatabaseSession, customer_id: int | None = None): return _rows(CollectionService(session).list(customer_id))


@router.post("/collections", status_code=status.HTTP_201_CREATED)
def create_collection_activity(request: CollectionActivityCreate, session: DatabaseSession):
    return model_dict(CollectionService(session).record(**request.model_dump()))


@router.get("/inventory")
def list_inventory(session: DatabaseSession, warehouse_id: str | None = None):
    service = InventoryService(session); return [service.balance(item.id, warehouse_id) for item in service.repository.list_products()]


@router.get("/inventory/{product_id}")
def get_inventory(product_id: str, session: DatabaseSession, warehouse_id: str | None = None): return InventoryService(session).balance(product_id, warehouse_id)


@router.post("/inventory/transfers")
def transfer_inventory(request: InventoryTransfer, session: DatabaseSession):
    result = InventoryService(session).transfer(request); return {"transfer_id": result["transfer_id"], "out_movement": model_dict(result["out_movement"]), "in_movement": model_dict(result["in_movement"])}


@router.post("/inventory/adjustments")
def adjust_inventory(request: InventoryAdjustment, session: DatabaseSession): return model_dict(InventoryService(session).adjustment(request))


@router.post("/stocktakes", status_code=status.HTTP_201_CREATED)
def create_stocktake(request: StocktakeCreate, session: DatabaseSession): return model_dict(InventoryService(session).create_stocktake(request))


@router.post("/stocktakes/{stocktake_id}/complete")
def complete_stocktake(stocktake_id: str, request: StocktakeComplete, session: DatabaseSession): return model_dict(InventoryService(session).complete_stocktake(stocktake_id, request))


@router.post("/purchases/orders", status_code=status.HTTP_201_CREATED)
def create_purchase_order(request: PurchaseOrderCreate, session: DatabaseSession): return model_dict(PurchaseService(session).create_order(request))


@router.post("/purchases/receipts", status_code=status.HTTP_201_CREATED)
def create_goods_receipt(request: GoodsReceiptCreate, session: DatabaseSession): return model_dict(PurchaseService(session).receive(request))


@router.post("/supplier-invoices", status_code=status.HTTP_201_CREATED)
def create_supplier_invoice(request: SupplierInvoiceCreate, session: DatabaseSession): return model_dict(PurchaseService(session).create_supplier_invoice(request))


@router.post("/supplier-payments", status_code=status.HTTP_201_CREATED)
def create_supplier_payment(request: SupplierPaymentCreate, session: DatabaseSession): return model_dict(SupplierPayablesService(session).pay(request))


@router.post("/territories", status_code=status.HTTP_201_CREATED)
def create_territory(request: TerritoryCreate, session: DatabaseSession): return model_dict(DistributionService(session).create_territory(request))


@router.post("/sales-reps", status_code=status.HTTP_201_CREATED)
def create_sales_rep(request: SalesRepCreate, session: DatabaseSession): return model_dict(DistributionService(session).create_sales_rep(request))


@router.post("/deliveries", status_code=status.HTTP_201_CREATED)
def create_delivery(request: DeliveryCreate, session: DatabaseSession): return model_dict(DistributionService(session).create_delivery(request))


@router.post("/deliveries/{delivery_id}/status")
def update_delivery(delivery_id: str, request: DeliveryUpdate, session: DatabaseSession): return model_dict(DistributionService(session).update_delivery(delivery_id, request))


@router.post("/msc/intake/batches", status_code=status.HTTP_201_CREATED)
def create_msc_batch(request: MscBatchCreate, session: DatabaseSession): return model_dict(MSCIntakeService(session).create_batch(request))


@router.post("/msc/intake/batches/{batch_id}/files", status_code=status.HTTP_201_CREATED)
async def add_msc_file(batch_id: str, session: DatabaseSession, file: UploadFile = File(...), sequence: int = Form(...), capture_time: datetime | None = Form(None), document_uid: str | None = Form(None), page_number: int | None = Form(None), page_count: int | None = Form(None)):
    content = await file.read(); return model_dict(MSCIntakeService(session).add_file(batch_id, file_name=file.filename or "upload", content=content, mime_type=file.content_type or "application/octet-stream", sequence=sequence, capture_time=capture_time, document_uid=document_uid, page_number=page_number, page_count=page_count))


@router.post("/msc/intake/batches/{batch_id}/extract")
def extract_msc_batch(batch_id: str, request: MscExtractRequest, session: DatabaseSession): return _rows(MSCIntakeService(session).stage_extraction(batch_id, request))


@router.post("/msc/intake/batches/{batch_id}/validate")
def validate_msc_batch(batch_id: str, session: DatabaseSession):
    result = MSCIntakeService(session).validate(batch_id); return {**result, "batch": model_dict(result["batch"])}


@router.post("/msc/intake/batches/{batch_id}/approve")
def approve_msc_batch(batch_id: str, request: MscApprovalRequest, session: DatabaseSession): return model_dict(MSCIntakeService(session).approve(batch_id, request.approved_by))


@router.post("/msc/intake/batches/{batch_id}/post")
def post_msc_batch(batch_id: str, request: PostRequest, session: DatabaseSession): return model_dict(MSCIntakeService(session).post(batch_id, request.posted_by))


@router.get("/msc/intake/batches/{batch_id}")
def get_msc_batch(batch_id: str, session: DatabaseSession):
    service = MSCIntakeService(session); batch = service.get(batch_id)
    return {**model_dict(batch), "files": _rows(service.repository.msc_files(batch.id)), "staging": _rows(service.repository.msc_staging(batch.id))}


@router.post("/sales/import/preview")
async def preview_sales_sheet(file: UploadFile = File(...)):
    return SalesSheetImportService().preview(await file.read(), file.filename or "upload")


@router.post("/daily-close", status_code=status.HTTP_201_CREATED)
def create_daily_close(request: DailyCloseCreate, session: DatabaseSession): return model_dict(DailyCloseService(session).create(request))


@router.get("/daily-close/{business_date}")
def get_daily_close(business_date: str, session: DatabaseSession): return model_dict(DailyCloseService(session).get(business_date))


@router.post("/daily-close/{close_id}/validate")
def validate_daily_close(close_id: str, session: DatabaseSession): return model_dict(DailyCloseService(session).validate(close_id))


@router.post("/daily-close/{close_id}/close")
def close_daily_close(close_id: str, request: DailyCloseAction, session: DatabaseSession): return model_dict(DailyCloseService(session).close(close_id, request))


@router.post("/daily-close/{close_id}/reopen")
def reopen_daily_close(close_id: str, request: DailyCloseAction, session: DatabaseSession): return model_dict(DailyCloseService(session).reopen(close_id, request))


@router.post("/accounting/journals", status_code=status.HTTP_201_CREATED)
def create_journal(request: JournalCreate, session: DatabaseSession): return model_dict(AccountingBridgeService(session).create_journal(request))


@router.get("/accounting/trial-balance")
def trial_balance(session: DatabaseSession): return AccountingBridgeService(session).trial_balance()


@router.get("/reports/sales")
def sales_report(session: DatabaseSession, business_date: date | None = None): return SalesReportingService(session).sales(business_date=business_date)


@router.get("/reports/customers/{customer_id}/360")
def customer_360(customer_id: str, session: DatabaseSession): return SalesReportingService(session).customer_360(customer_id)


@router.get("/reports/products/{product_id}/360")
def product_360(product_id: str, session: DatabaseSession): return SalesReportingService(session).product_360(product_id)


@router.get("/reports/suppliers/{supplier_id}/360")
def supplier_360(supplier_id: str, session: DatabaseSession): return SalesReportingService(session).supplier_360(supplier_id)
