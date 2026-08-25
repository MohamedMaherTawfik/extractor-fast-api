"""Product, sales, inventory, MSC intake, and accounting bridge schema."""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_product_sales"
down_revision: str | None = "0007_generation_engine"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


TABLES = (
    "suppliers", "territories", "sales_reps", "pricebooks", "customers",
    "warehouses", "products", "product_versions", "pricebook_lines",
    "product_batches", "sales_orders", "sales_order_lines",
    "inventory_movements", "inventory_reservations", "stocktakes",
    "stocktake_lines", "sales_invoices", "sales_invoice_lines", "payments",
    "payment_allocations", "collection_activities", "purchase_orders",
    "purchase_order_lines", "goods_receipts", "goods_receipt_lines",
    "supplier_invoices", "supplier_payments", "sales_returns",
    "sales_return_lines", "delivery_orders", "daily_closes",
    "msc_intake_batches", "msc_intake_files", "msc_invoice_staging",
    "accounting_journals", "accounting_journal_lines", "approval_requests",
    "business_events", "sales_audit_ledger",
)


def upgrade() -> None:
    # Importing the model registry gives Alembic the exact Numeric, JSON, index,
    # and constraint definitions used at runtime while retaining an explicit,
    # reviewable list of tables owned by this revision.
    import backend.db.models  # noqa: F401
    from backend.db.base import Base

    bind = op.get_bind()
    for name in TABLES:
        Base.metadata.tables[name].create(bind=bind, checkfirst=True)


def downgrade() -> None:
    import backend.db.models  # noqa: F401
    from backend.db.base import Base

    bind = op.get_bind()
    for name in reversed(TABLES):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
