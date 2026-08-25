"""Read-only operational reporting and 360 views."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.repositories.sales_repository import SalesRepository
from backend.sales.common import money, model_dict
from backend.sales.context import ProductSalesContextService
from backend.sales.finance import ReceivablesService
from backend.sales.inventory import InventoryService
from backend.sales.master_data import CustomerService, ProductService, SupplierService
from backend.sales.purchasing import SupplierPayablesService


class SalesReportingService:
    def __init__(self, session: Session) -> None: self.repository = SalesRepository(session)

    def sales(self, *, business_date: date | None = None) -> dict:
        invoices = self.repository.posted_invoices(business_date=business_date)
        by_day = defaultdict(lambda: Decimal("0")); by_sku = defaultdict(lambda: Decimal("0")); by_customer = defaultdict(lambda: Decimal("0"))
        for invoice in invoices:
            by_day[invoice.invoice_date.isoformat()] += invoice.total; by_customer[str(invoice.customer_id)] += invoice.total
            for line in self.repository.invoice_lines(invoice.id):
                product = self.repository.get_product(line.product_id); by_sku[product.sku] += line.quantity
        return {"invoice_count": len(invoices), "sales_total": money(sum((item.total for item in invoices), Decimal("0"))), "by_day": dict(by_day), "quantity_by_sku": dict(by_sku), "by_customer": dict(by_customer)}

    def customer_360(self, customer_id: int | str) -> dict:
        customer = CustomerService(self.repository.session).get(customer_id); orders = self.repository.customer_orders(customer.id); invoices = self.repository.customer_invoices(customer.id); payments = self.repository.customer_payments(customer.id)
        return {"customer": model_dict(customer), "orders": [model_dict(x) for x in orders], "invoices": [model_dict(x) for x in invoices], "payments": [model_dict(x) for x in payments], "balance": ReceivablesService(self.repository.session).balance(customer.id), "returns": [model_dict(x) for x in self.repository.customer_returns(customer.id)], "deliveries": [model_dict(x) for x in self.repository.customer_deliveries(customer.id)], "last_order": model_dict(orders[0]) if orders else None, "average_order": money(sum((x.total for x in orders), Decimal("0")) / len(orders)) if orders else Decimal("0")}

    def product_360(self, product_id: int | str) -> dict:
        product = ProductService(self.repository.session).get(product_id)
        return {"product": model_dict(product), "sales_context": ProductSalesContextService(self.repository.session).get_product_context(product.id), "stock_by_warehouse": [InventoryService(self.repository.session).balance(product.id, warehouse.id) for warehouse in self.repository.list_warehouses()], "movement_history": [model_dict(x) for x in self.repository.inventory_movements(product.id)]}

    def supplier_360(self, supplier_id: int | str) -> dict:
        supplier = SupplierService(self.repository.session).get(supplier_id)
        return {"supplier": model_dict(supplier), "purchase_orders": [model_dict(x) for x in self.repository.list_purchase_orders(supplier.id)], "balance": SupplierPayablesService(self.repository.session).balance(supplier.id)}
