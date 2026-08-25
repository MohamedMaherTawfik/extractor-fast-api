# Product / Sales Operating Engine

## Boundary

The Product/Sales Engine owns product, pricing, customer, supplier, order,
inventory, invoice, payment, collection, purchasing, distribution, MSC intake,
daily-close, and accounting-bridge data. Creator/content, lead/prospect, and CRO
data remain separate. A converted lead may be retained only as `customers.lead_uid`;
conversion creates a new `customer_uid` and never reuses a lead as the customer key.

AI and OCR providers are extractors only. They can write field-level evidence to
MSC staging, but they cannot create a product, post an invoice, issue stock,
allocate payment, or write accounting records without validation and approval.

## Operating flow

```text
Converted lead reference (optional)
    -> Customer Master
    -> validated Sales Order + approved PriceBook/MOQ
    -> stock reservation
    -> validated Invoice
    -> atomic invoice posting + Inventory Ledger issue
    -> Payment + explicit invoice allocation
    -> ledger-derived AR and Aging
    -> Daily Close validation/approval
    -> balanced Accounting Bridge journal
```

The canonical product identity is an immutable `product_uid` plus unique business
`sku`. Names are attributes, never keys. Significant product changes close the
old `product_versions` record and append a snapshot with a new version. Unknown
barcodes, products, prices, costs, stock, suppliers, and facts remain null or in
review; the system does not infer them.

## Pricing and orders

PriceBooks are versioned and effective-dated. Their lines contain approved
quantity tiers, MOQ bounds, gross price, discount, and net price. Order validation
checks customer/product status, effective approved price, MOQ, manual overrides,
credit hold/limit, warehouse, and stock. A manual price different from the
PriceBook produces a `PRICE_OVERRIDE` approval request. Approval reserves stock;
it does not issue it.

Money uses `Decimal`/`NUMERIC(18,4)` and is rounded deliberately. Quantities use
four decimal places so weights and volumes are supported. Invoice totals are
validated from line quantities/prices, discounts, tax, and shipping. Posted
invoices have no update endpoint; corrections use returns/credit workflows.

## Inventory and purchasing

Current stock is derived from signed `inventory_movements`. It is never updated
as a free-standing product field.

```text
on_hand   = SUM(movement.quantity * movement.direction)
reserved  = SUM(active reservations)
available = on_hand - reserved
```

Negative stock defaults to disabled. Transfers write paired `TRANSFER_OUT` and
`TRANSFER_IN` ledger records in one database transaction. Purchase receipts write
receipt lines and `PURCHASE_RECEIPT` movements atomically. Stocktakes preserve
system quantity, counted quantity, variance, reason, and approval state. Product
batches support lot/manufacture/expiry metadata for later FEFO selection.

Supplier payables are derived from posted supplier invoices less supplier
payments. Customer receivables are derived from posted sales invoices less
payment allocations; neither master table contains an editable balance.

## MSC intake

```text
MSC screenshot/report/export
    -> Intake Batch
    -> hashed managed file + explicit sequence/page metadata
    -> Extractor interface (mock by default; no live provider in tests)
    -> raw and evidence-bearing staging
    -> exact/fuzzy-candidate normalization
    -> confidence, arithmetic, identity, sequence, and duplicate validation
    -> human approval
    -> atomic, idempotent Invoice + Inventory posting
```

Files use generated storage names beneath project-relative `data/imports/msc`.
Extension, MIME type, size, SHA-256, path containment, duplicate hash, batch
sequence, and multi-page document metadata are checked. Low-confidence fields,
unknown SKU, ambiguous customer, missing sequence, invalid quantity/date/price,
and arithmetic mismatch block approval. Manual extraction corrections remain in
the staging correction history. The same batch or staging fingerprint posts once.

`BaseMSCExtractor` exposes invoice, sales-report, stock-report, payment-report,
and normalization methods. `MockMSCExtractor` is deterministic and has no network
dependency. Live extraction remains opt-in through
`run_live_msc_extraction_tests=false`.

## Daily close and accounting bridge

Daily close aggregates posted invoices and payments for the business date and
checks unposted invoices, unallocated payments, and pending MSC batches. Exceptions
produce `EXCEPTIONS`; close requires resolution or an explicit approved override.
Reopen requires a reason and approver.

The accounting bridge persists journal drafts/posts rather than claiming a full
ERP or regulatory accounting implementation. Every journal must have equal debit
and credit totals before posting. Trial balance is derived only from posted journal
lines and reports `balanced=false` if totals diverge. No GAAP or tax-compliance
claim is made.

## Read-only creative integration

`GET /products/{id}/sales-context` supplies approved price (or null), stock,
configured 7/30/90-day velocity, deterministic priority, approved product facts,
campaign eligibility, and a reorder suggestion. The response is explicitly
read-only. Reorder suggestions never create purchase orders. The Generation Engine
has no write path to sales, inventory, price, customer, or accounting tables.

## Audit, idempotency, and security

Business events share the transaction with the mutation through a local outbox
table. The append-only sales audit stores actor, action, before/after, reason,
source, and approval reference. Unique idempotency constraints protect order,
invoice, payment, movement, receipt, event, MSC batch, and MSC posting paths.

Managed paths are relative and traversal-safe. User filenames never become stored
filenames. Export helpers prefix spreadsheet formula-control characters (`=`,
`+`, `-`, `@`). Logs do not contain bank secrets, documents, or provider keys.

## API groups

- Products, versions, stock, PriceBooks, sales context, and mover signals
- Customers, statements, orders, invoices, balance, and Customer 360
- Sales orders, approval/cancel, invoices/posting, and returns
- Payments, allocations, receivables, collections, and aging
- Inventory balances, transfer, adjustment, and stocktake
- Suppliers, purchase orders, goods receipts, supplier invoices, and AP
- Territories, representatives, deliveries, and operational reports
- MSC batch/file/extract/validate/approve/post and Sales Sheet dry-run preview
- Daily close validation/close/reopen and accounting journals/trial balance

## Persistence

Alembic revision `0008_product_sales` adds 39 normalized tables across Product,
Pricing, Customer/Supplier, Inventory, Sales, Payments/Collections, Purchases,
Returns/Distribution, Daily Close, MSC staging, Accounting Bridge, approvals,
business-event outbox, and audit ledger domains.
