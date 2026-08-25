from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from backend.core.exceptions import ConflictError, NotFoundError, SalesValidationError
from backend.db.session import session_scope
from backend.sales.context import ProductSalesContextService
from backend.sales.audit import export_safe_cell
from backend.sales.finance import AccountingBridgeService, DailyCloseService, PaymentService, ReceivablesService
from backend.sales.inventory import InventoryService
from backend.sales.invoicing import InvoiceService
from backend.sales.master_data import CustomerService, PricingService, ProductService, SupplierService, WarehouseService
from backend.sales.msc import MSCIntakeService
from backend.sales.orders import SalesOrderService
from backend.sales.purchasing import PurchaseService, SupplierPayablesService
from backend.schemas.sales import (
    AllocationLine, ApprovalDecision, CustomerCreate, DailyCloseAction,
    DailyCloseCreate, GoodsReceiptCreate, InvoiceCreate, JournalCreate,
    JournalLineCreate, MscApprovalRequest, MscBatchCreate, MscExtractRequest,
    MscExtractionRecord, PaymentAllocate, PaymentCreate, PostRequest,
    PriceBookCreate, PriceBookLineCreate, ProductCreate, ProductUpdate,
    PurchaseOrderCreate, PurchaseOrderLineCreate, ReceiptLineCreate,
    SalesOrderCreate, SupplierCreate, SupplierInvoiceCreate, WarehouseCreate,
    OrderLineCreate,
)


def seed_commerce(session, *, stock=Decimal("20"), minimum=Decimal("1")):
    supplier = SupplierService(session).create(SupplierCreate(supplier_code="SUPPLIER-TEST-001", supplier_name="Synthetic Supplier", lead_time_days=5))
    warehouse = WarehouseService(session).create(WarehouseCreate(code="WH-TEST", name="Synthetic Warehouse"))
    product = ProductService(session).create(ProductCreate(sku="SKU-TEST-001", product_name_en="Synthetic Product", supplier_default_id=supplier.id, facts={"safety_stock": "2"}))
    pricebook = PricingService(session).create_pricebook(PriceBookCreate(name="Retail Test", effective_from=datetime.now(UTC) - timedelta(days=1), approved_by="tester", lines=[PriceBookLineCreate(product_id=product.id, min_qty=minimum, unit_price=Decimal("10.00"), net_price=Decimal("10.00"), approved=True)]))
    customer = CustomerService(session).create(CustomerCreate(customer_code="CUSTOMER-TEST-001", business_name="Synthetic Customer", default_pricebook_id=pricebook.id, credit_limit=Decimal("1000"), payment_terms_days=14))
    if stock > 0:
        InventoryService(session).post_movement(product_id=product.id, warehouse_id=warehouse.id, movement_type="OPENING_BALANCE", quantity_value=stock, reference_type="TEST", reference_id="opening", posted_by="tester", idempotency_key="test-opening")
    return supplier, warehouse, product, pricebook, customer


def test_product_versioning_unique_sku_and_no_unknown_autocreate():
    with session_scope() as session:
        _, _, product, _, _ = seed_commerce(session)
        with pytest.raises(ConflictError): ProductService(session).create(ProductCreate(sku="SKU-TEST-001"))
        ProductService(session).update(product.id, ProductUpdate(barcode="123456", approved_by="reviewer"))
        assert product.version == 2
        assert len(ProductService(session).versions(product.id)) == 2
        with pytest.raises((SalesValidationError, NotFoundError)): SalesOrderService(session).create(SalesOrderCreate(order_number="SO-BAD", customer_id="CUSTOMER-TEST-001", order_date=datetime.now(UTC), pricebook_id="Retail Test", lines=[OrderLineCreate(product_id="UNKNOWN-SKU", quantity=1, warehouse_id="WH-TEST")]))
        assert len(ProductService(session).list()) == 1


def test_order_invoice_inventory_payment_and_ar_are_ledger_driven():
    with session_scope() as session:
        _, warehouse, product, book, customer = seed_commerce(session)
        order_service = SalesOrderService(session)
        order = order_service.create(SalesOrderCreate(order_number="SO-TEST-001", customer_id=customer.id, order_date=datetime.now(UTC), pricebook_id=book.id, lines=[OrderLineCreate(product_id=product.id, quantity=Decimal("2"), warehouse_id=warehouse.id)]))
        order_service.approve(order.id, ApprovalDecision(approved_by="reviewer"))
        assert InventoryService(session).balance(product.id, warehouse.id)["reserved"] == Decimal("2")
        invoice = InvoiceService(session).create(InvoiceCreate(invoice_number="INV-TEST-001", order_id=order.id, invoice_date=date.today()))
        InvoiceService(session).post(invoice.id, PostRequest(posted_by="tester"))
        assert InventoryService(session).balance(product.id, warehouse.id)["on_hand"] == Decimal("18")
        payment = PaymentService(session).create(PaymentCreate(customer_id=customer.id, payment_date=datetime.now(UTC), amount=Decimal("20"), method="CASH", received_by="tester"))
        PaymentService(session).allocate(payment.id, PaymentAllocate(allocated_by="tester", allocations=[AllocationLine(invoice_id=invoice.id, amount=Decimal("20"))]))
        assert ReceivablesService(session).balance(customer.id) == Decimal("0.00")
        assert invoice.status == "PAID"


def test_moq_negative_stock_and_overallocation_are_blocked():
    with session_scope() as session:
        _, warehouse, product, book, customer = seed_commerce(session, stock=Decimal("1"), minimum=Decimal("2"))
        with pytest.raises(SalesValidationError, match="price/MOQ"):
            SalesOrderService(session).create(SalesOrderCreate(order_number="SO-MOQ", customer_id=customer.id, order_date=datetime.now(UTC), pricebook_id=book.id, lines=[OrderLineCreate(product_id=product.id, quantity=1, warehouse_id=warehouse.id)]))
        with pytest.raises(SalesValidationError, match="NEGATIVE_STOCK"):
            InventoryService(session).post_movement(product_id=product.id, warehouse_id=warehouse.id, movement_type="SALE_ISSUE", quantity_value=2, reference_type="TEST", reference_id="bad", posted_by="tester", idempotency_key="bad-negative")


def test_purchase_receipt_ap_and_product_context():
    with session_scope() as session:
        supplier, warehouse, product, _, _ = seed_commerce(session, stock=Decimal("0"))
        purchases = PurchaseService(session)
        po = purchases.create_order(PurchaseOrderCreate(order_number="PO-TEST-001", supplier_id=supplier.id, order_date=date.today(), lines=[PurchaseOrderLineCreate(product_id=product.id, quantity=10, unit_cost=5)]))
        line = purchases.repository.purchase_order_lines(po.id)[0]
        purchases.receive(GoodsReceiptCreate(receipt_number="GRN-TEST-001", purchase_order_id=po.id, warehouse_id=warehouse.id, received_at=datetime.now(UTC), received_by="tester", lines=[ReceiptLineCreate(purchase_order_line_id=line.id, quantity=10)]))
        assert InventoryService(session).balance(product.id, warehouse.id)["on_hand"] == Decimal("10")
        purchases.create_supplier_invoice(SupplierInvoiceCreate(invoice_number="SINV-001", supplier_id=supplier.id, purchase_order_id=po.id, invoice_date=date.today(), due_date=date.today(), total=50))
        assert SupplierPayablesService(session).balance(supplier.id) == Decimal("50.00")
        context = ProductSalesContextService(session).get_product_context(product.id, warehouse_id=warehouse.id)
        assert context["read_only"] is True and context["approved_price"] == Decimal("10.0000")
        assert context["reorder"]["creates_purchase_order"] is False


def test_msc_dedup_review_sequence_and_idempotent_posting():
    with session_scope() as session:
        _, warehouse, product, _, customer = seed_commerce(session)
        service = MSCIntakeService(session)
        batch = service.create_batch(MscBatchCreate(business_date=date.today(), capture_date=datetime.now(UTC), source_hash="a" * 64, sequence_start=1, sequence_end=1))
        file = service.add_file(batch.id, file_name="../../invoice.png", content=b"synthetic-image", mime_type="image/png", sequence=1)
        assert ".." not in file.relative_path and not file.relative_path.startswith(("C:", "D:"))
        with pytest.raises(ConflictError): service.add_file(batch.id, file_name="again.png", content=b"synthetic-image", mime_type="image/png", sequence=2)
        service.stage_extraction(batch.id, MscExtractRequest(records=[MscExtractionRecord(source_file_id=file.id, invoice_number="MSC-INV-TEST-001", invoice_date=date.today().isoformat(), customer=customer.customer_code, product=product.sku, quantity="2", price="10", total="20", confidence=Decimal("0.99"), fields={"warehouse_id": warehouse.id})]))
        assert service.validate(batch.id)["issues"] == []
        service.approve(batch.id, "reviewer")
        service.post(batch.id, "poster")
        invoice_id = service.repository.msc_staging(batch.id)[0].posted_invoice_id
        service.post(batch.id, "poster")
        assert service.repository.msc_staging(batch.id)[0].posted_invoice_id == invoice_id


def test_daily_close_and_balanced_journal_rules():
    with session_scope() as session:
        close = DailyCloseService(session).create(DailyCloseCreate(business_date=date.today()))
        DailyCloseService(session).validate(close.id)
        DailyCloseService(session).close(close.id, DailyCloseAction(actor="reviewer"))
        assert close.status == "CLOSED"
        accounting = AccountingBridgeService(session)
        with pytest.raises(SalesValidationError, match="balanced"):
            accounting.create_journal(JournalCreate(business_date=date.today(), reference_type="TEST", reference_id="BAD", lines=[JournalLineCreate(account_code="A", debit=10), JournalLineCreate(account_code="B", credit=9)]))
        accounting.create_journal(JournalCreate(business_date=date.today(), reference_type="TEST", reference_id="OK", lines=[JournalLineCreate(account_code="A", debit=10), JournalLineCreate(account_code="B", credit=10)]))
        assert accounting.trial_balance()["balanced"] is True


def test_product_sales_api_smoke(api_request):
    warehouse = api_request("POST", "/warehouses", json={"code": "WH-API", "name": "API Warehouse"})
    product = api_request("POST", "/products", json={"sku": "SKU-API", "product_name_en": "API Product"})
    assert warehouse.status_code == product.status_code == 201
    assert api_request("GET", "/products/SKU-API").status_code == 200


def test_atomic_invoice_posting_rolls_back_before_stock_write():
    with session_scope() as session:
        _, warehouse, product, _, customer = seed_commerce(session, stock=Decimal("1"))
        service = InvoiceService(session)
        invoice = service.create(InvoiceCreate(invoice_number="INV-ATOMIC", customer_id=customer.id, invoice_date=date.today(), lines=[{"product_id": product.id, "warehouse_id": warehouse.id, "quantity": "2", "unit_price": "10"}]))
        before = len(InventoryService(session).repository.inventory_movements(product.id, warehouse.id))
        with pytest.raises(SalesValidationError, match="ATOMIC_POST_BLOCKED"): service.post(invoice.id, PostRequest(posted_by="tester"))
        assert invoice.status == "VALIDATED"
        assert len(InventoryService(session).repository.inventory_movements(product.id, warehouse.id)) == before


def test_low_confidence_msc_never_posts_and_missing_sequence_blocks():
    with session_scope() as session:
        _, warehouse, product, _, customer = seed_commerce(session)
        service = MSCIntakeService(session)
        batch = service.create_batch(MscBatchCreate(business_date=date.today(), capture_date=datetime.now(UTC), source_hash="b" * 64, sequence_start=1, sequence_end=2))
        file = service.add_file(batch.id, file_name="low.png", content=b"low-confidence", mime_type="image/png", sequence=1)
        service.stage_extraction(batch.id, MscExtractRequest(records=[MscExtractionRecord(source_file_id=file.id, invoice_number="LOW-1", invoice_date=date.today().isoformat(), customer=customer.customer_code, product=product.sku, quantity="1", price="10", total="10", confidence=Decimal("0.50"), fields={"warehouse_id": warehouse.id})]))
        codes = {issue["code"] for issue in service.validate(batch.id)["issues"]}
        assert {"MISSING_SEQUENCE_2", "LOW_CONFIDENCE"} <= codes
        with pytest.raises(SalesValidationError): service.approve(batch.id, "reviewer")
        assert service.repository.get_invoice("LOW-1") is None


def test_decimal_math_and_formula_export_safety():
    assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")
    assert export_safe_cell("=HYPERLINK('bad')").startswith("'")
    assert export_safe_cell("ordinary") == "ordinary"
