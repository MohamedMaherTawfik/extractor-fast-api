"""Read-only product/customer/supplier context and operating signals."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.exceptions import SalesValidationError
from backend.repositories.sales_repository import SalesRepository
from backend.sales.common import money
from backend.sales.inventory import InventoryService
from backend.sales.master_data import PricingService, ProductService


class ProductSalesContextService:
    """A read-only boundary consumed by creative/generation workflows."""

    def __init__(self, session: Session) -> None:
        self.repository = SalesRepository(session); self.inventory = InventoryService(session); self.settings = get_settings()

    def get_product_context(self, product_id: int | str, *, warehouse_id: int | str | None = None) -> dict:
        product = ProductService(self.repository.session).get(product_id)
        stock = self.inventory.balance(product.id, warehouse_id)
        today = date.today(); velocity = {}
        for days in self.settings.sales_velocity_windows:
            qty = self.repository.sales_quantity(product.id, today - timedelta(days=days - 1))
            velocity[f"{days}d"] = {"quantity": qty, "daily_average": (qty / Decimal(days)).quantize(Decimal("0.0001"))}
        v30 = velocity.get("30d", next(iter(velocity.values()), {"daily_average": Decimal("0")}))["daily_average"]
        lead_time = 0
        if product.supplier_default_id:
            supplier = self.repository.get_supplier(product.supplier_default_id); lead_time = supplier.lead_time_days or 0 if supplier else 0
        safety_stock = Decimal(str(product.facts.get("safety_stock", "0"))) if product.facts else Decimal("0")
        reorder_point = (v30 * Decimal(lead_time)) + safety_stock
        reorder_qty = max(Decimal("0"), (v30 * Decimal(self.settings.sales_reorder_cover_days)) + safety_stock - stock["available"])
        if stock["available"] <= 0: priority = "OUT_OF_STOCK"
        elif stock["available"] <= reorder_point: priority = "LOW_STOCK"
        elif v30 == 0: priority = "SLOW_MOVER"
        else: priority = "NORMAL"
        approved_price = None; currency = None
        for book in self.repository.list_pricebooks():
            try:
                line = PricingService(self.repository.session).get_price(book.id, product.id, Decimal("1")); approved_price = line.net_price; currency = book.currency; break
            except SalesValidationError: continue
        return {
            "read_only": True, "product_uid": product.product_uid, "sku": product.sku,
            "product_version": product.version, "status": product.status,
            "approved_price": approved_price, "currency": currency,
            "stock": stock, "priority": priority, "sales_velocity": velocity,
            "campaign_eligibility": product.active and stock["available"] > 0,
            "product_facts": product.facts, "reorder": {
                "suggested": reorder_qty > 0, "suggested_quantity": reorder_qty,
                "reorder_point": reorder_point, "safety_stock": safety_stock,
                "lead_time_days": lead_time, "creates_purchase_order": False,
            },
        }

    def movers(self) -> dict:
        contexts = [self.get_product_context(product.id) for product in self.repository.list_products(active=True)]
        contexts.sort(key=lambda item: item["sales_velocity"].get("30d", {}).get("quantity", Decimal("0")), reverse=True)
        nonzero = [item for item in contexts if item["sales_velocity"].get("30d", {}).get("quantity", Decimal("0")) > 0]
        zero = [item for item in contexts if item not in nonzero]
        return {"fast_movers": nonzero, "slow_movers": zero, "as_of": date.today()}
