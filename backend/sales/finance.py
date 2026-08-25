"""Payments, receivables, collections, accounting bridge, and daily close."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.core.exceptions import ConflictError, NotFoundError, SalesValidationError
from backend.db.models.sales import (
    AccountingJournal, AccountingJournalLine, CollectionActivity, DailyClose,
    Payment, PaymentAllocation,
)
from backend.repositories.sales_repository import SalesRepository
from backend.sales.common import money, stable_hash, uid
from backend.sales.audit import SalesAuditService
from backend.sales.master_data import CustomerService
from backend.schemas.sales import DailyCloseAction, DailyCloseCreate, JournalCreate, PaymentAllocate, PaymentCreate


PAYMENT_METHODS = {"CASH", "BANK_TRANSFER", "INSTAPAY", "MOBILE_WALLET", "CARD", "COD", "CHEQUE", "OTHER"}


class PaymentService:
    def __init__(self, session: Session) -> None: self.repository = SalesRepository(session)

    def create(self, request: PaymentCreate) -> Payment:
        key = request.idempotency_key or stable_hash(request.model_dump())
        existing = self.repository.payment_by_idempotency(key)
        if existing: return existing
        customer = CustomerService(self.repository.session).get(request.customer_id)
        method = request.method.upper()
        if method not in PAYMENT_METHODS: raise SalesValidationError("Unknown payment method")
        payment = self.repository.add(Payment(payment_uid=uid("PAY"), customer_id=customer.id, payment_date=request.payment_date, amount=money(request.amount), currency=request.currency.upper(), method=method, reference=request.reference, bank_wallet_account=request.bank_wallet_account, received_by=request.received_by, status="RECEIVED", idempotency_key=key))
        SalesAuditService(self.repository.session).event("PAYMENT_RECEIVED", "PAYMENT", payment.payment_uid, {"customer_id": customer.customer_uid, "amount": payment.amount})
        return payment

    def get(self, identifier: int | str) -> Payment:
        payment = self.repository.get_payment(identifier)
        if payment is None: raise NotFoundError(f"Payment {identifier} was not found")
        return payment

    def allocate(self, identifier: int | str, request: PaymentAllocate) -> Payment:
        payment = self.get(identifier)
        allocated = self.repository.payment_allocated(payment.id)
        requested = sum((money(item.amount) for item in request.allocations), Decimal("0"))
        if allocated + requested > payment.amount: raise SalesValidationError("Payment over-allocation is not allowed")
        seen: set[int] = set()
        for item in request.allocations:
            invoice = self.repository.get_invoice(item.invoice_id)
            if invoice is None: raise NotFoundError(f"Invoice {item.invoice_id} was not found")
            if invoice.id in seen: raise SalesValidationError("Duplicate invoice in allocation request")
            seen.add(invoice.id)
            if invoice.customer_id != payment.customer_id: raise SalesValidationError("Payment and invoice customers differ")
            if invoice.status not in {"POSTED", "PARTIALLY_PAID", "OVERDUE"}: raise SalesValidationError("Only posted outstanding invoices can receive allocations")
            invoice_balance = money(invoice.total - self.repository.invoice_return_total(invoice.id) - self.repository.invoice_allocated(invoice.id))
            if money(item.amount) > invoice_balance: raise SalesValidationError("Allocation exceeds invoice balance")
        for item in request.allocations:
            invoice = self.repository.get_invoice(item.invoice_id)
            self.repository.add(PaymentAllocation(allocation_uid=uid("ALLOC"), payment_id=payment.id, invoice_id=invoice.id, amount=money(item.amount), allocated_by=request.allocated_by))
            self.repository.flush()
            balance = money(invoice.total - self.repository.invoice_return_total(invoice.id) - self.repository.invoice_allocated(invoice.id))
            invoice.status = "PAID" if balance == 0 else "PARTIALLY_PAID"
        payment.status = "ALLOCATED" if allocated + requested == payment.amount else "PARTIALLY_ALLOCATED"
        SalesAuditService(self.repository.session).event("PAYMENT_ALLOCATED", "PAYMENT", f"{payment.payment_uid}:{allocated + requested}", {"allocated": allocated + requested})
        return payment


class ReceivablesService:
    def __init__(self, session: Session) -> None: self.repository = SalesRepository(session)

    def balance(self, customer_id: int | str) -> Decimal:
        customer = CustomerService(self.repository.session).get(customer_id)
        return money(sum((invoice.total - self.repository.invoice_return_total(invoice.id) - self.repository.invoice_allocated(invoice.id) for invoice in self.repository.posted_invoices(customer_id=customer.id)), Decimal("0")))

    def statement(self, customer_id: int | str) -> dict:
        customer = CustomerService(self.repository.session).get(customer_id)
        entries: list[dict] = []
        for invoice in self.repository.posted_invoices(customer_id=customer.id):
            entries.append({"date": invoice.invoice_date, "type": "INVOICE", "reference": invoice.invoice_uid, "debit": invoice.total, "credit": Decimal("0")})
            returned = self.repository.invoice_return_total(invoice.id)
            if returned: entries.append({"date": invoice.invoice_date, "type": "CREDIT_RETURN", "reference": f"{invoice.invoice_uid}:RETURN", "debit": Decimal("0"), "credit": returned})
        for payment in self.repository.customer_payments(customer.id):
            allocated = self.repository.payment_allocated(payment.id)
            entries.append({"date": payment.payment_date.date(), "type": "PAYMENT", "reference": payment.payment_uid, "debit": Decimal("0"), "credit": allocated})
        entries.sort(key=lambda item: (item["date"], item["reference"]))
        running = Decimal("0")
        for entry in entries: running = money(running + entry["debit"] - entry["credit"]); entry["balance"] = running
        return {"customer_uid": customer.customer_uid, "opening_balance": Decimal("0"), "entries": entries, "closing_balance": running}

    def aging(self, *, as_of: date | None = None, customer_id: int | str | None = None) -> dict:
        as_of = as_of or date.today(); customer = CustomerService(self.repository.session).get(customer_id) if customer_id is not None else None
        buckets = {"CURRENT": Decimal("0"), "1-30": Decimal("0"), "31-60": Decimal("0"), "61-90": Decimal("0"), "90+": Decimal("0")}
        details = []
        for invoice in self.repository.posted_invoices(customer_id=customer.id if customer else None):
            balance = money(invoice.total - self.repository.invoice_return_total(invoice.id) - self.repository.invoice_allocated(invoice.id))
            if balance <= 0: continue
            days = max(0, (as_of - invoice.due_date).days)
            bucket = "CURRENT" if days == 0 else "1-30" if days <= 30 else "31-60" if days <= 60 else "61-90" if days <= 90 else "90+"
            buckets[bucket] += balance; details.append({"invoice_uid": invoice.invoice_uid, "customer_id": invoice.customer_id, "due_date": invoice.due_date, "days_overdue": days, "bucket": bucket, "balance": balance})
        return {"as_of": as_of, "buckets": {key: money(value) for key, value in buckets.items()}, "total": money(sum(buckets.values(), Decimal("0"))), "details": details}

    def exposure(self, customer_id: int | str) -> dict:
        customer = CustomerService(self.repository.session).get(customer_id); current = self.balance(customer.id)
        return {"customer_uid": customer.customer_uid, "current_exposure": current, "credit_limit": customer.credit_limit, "available_credit": money(customer.credit_limit - current), "credit_status": customer.credit_status}


class CollectionService:
    def __init__(self, session: Session) -> None: self.repository = SalesRepository(session)
    def list(self, customer_id: int | None = None) -> list[CollectionActivity]: return self.repository.collection_activities(customer_id)

    def record(self, *, customer_id: int | str, activity_type: str, status: str, actor: str, invoice_id: int | None = None, promise_date: date | None = None, promise_amount: Decimal | None = None, notes: str | None = None) -> CollectionActivity:
        customer = CustomerService(self.repository.session).get(customer_id)
        return self.repository.add(CollectionActivity(collection_uid=uid("COLL"), customer_id=customer.id, invoice_id=invoice_id, activity_type=activity_type.upper(), status=status.upper(), promise_date=promise_date, promise_amount=money(promise_amount) if promise_amount is not None else None, notes=notes, actor=actor))


class AccountingBridgeService:
    def __init__(self, session: Session) -> None: self.repository = SalesRepository(session)

    def create_journal(self, request: JournalCreate, *, post: bool = True) -> AccountingJournal:
        existing = self.repository.journal_by_reference(request.reference_type, request.reference_id)
        if existing: return existing
        debit = money(sum((line.debit for line in request.lines), Decimal("0"))); credit = money(sum((line.credit for line in request.lines), Decimal("0")))
        if debit != credit: raise SalesValidationError("BLOCK_POSTING: journal debits and credits are not balanced")
        journal = self.repository.add(AccountingJournal(journal_uid=uid("JRN"), business_date=request.business_date, reference_type=request.reference_type, reference_id=request.reference_id, currency=request.currency.upper(), status="POSTED" if post else "DRAFT", posted_at=datetime.now(UTC) if post else None))
        for line in request.lines: self.repository.add(AccountingJournalLine(journal_id=journal.id, account_code=line.account_code, debit=money(line.debit), credit=money(line.credit), memo=line.memo))
        return journal

    def trial_balance(self) -> dict:
        totals: dict[str, dict[str, Decimal]] = {}
        for journal in self.repository.posted_journals():
            for line in self.repository.journal_lines(journal.id):
                row = totals.setdefault(line.account_code, {"debit": Decimal("0"), "credit": Decimal("0")}); row["debit"] += line.debit; row["credit"] += line.credit
        rows = [{"account_code": code, "debit": money(values["debit"]), "credit": money(values["credit"]), "balance": money(values["debit"] - values["credit"])} for code, values in sorted(totals.items())]
        total_debit = money(sum((row["debit"] for row in rows), Decimal("0"))); total_credit = money(sum((row["credit"] for row in rows), Decimal("0")))
        return {"rows": rows, "total_debit": total_debit, "total_credit": total_credit, "balanced": total_debit == total_credit}


class DailyCloseService:
    def __init__(self, session: Session) -> None: self.repository = SalesRepository(session)

    def create(self, request: DailyCloseCreate) -> DailyClose:
        existing = self.repository.get_daily_close(request.business_date)
        if existing: return existing
        return self.repository.add(DailyClose(daily_close_uid=uid("CLOSE"), business_date=request.business_date, status="OPEN", started_at=datetime.now(UTC)))

    def get(self, identifier: int | str | date) -> DailyClose:
        record = self.repository.get_daily_close(identifier)
        if record is None: raise NotFoundError(f"Daily close {identifier} was not found")
        return record

    def validate(self, identifier: int | str | date) -> DailyClose:
        record = self.get(identifier); record.status = "VALIDATING"
        exceptions = []
        unposted = self.repository.daily_unposted_invoices(record.business_date)
        unallocated = self.repository.daily_unallocated_payments(record.business_date)
        pending_msc = self.repository.daily_pending_msc(record.business_date)
        if unposted: exceptions.append({"code": "UNPOSTED_INVOICE", "count": unposted})
        if unallocated: exceptions.append({"code": "UNALLOCATED_PAYMENT", "count": unallocated})
        if pending_msc: exceptions.append({"code": "PENDING_MSC_EXTRACTION", "count": pending_msc})
        invoices = self.repository.posted_invoices(business_date=record.business_date)
        record.sales_total = money(sum((item.total for item in invoices), Decimal("0"))); record.discount_total = money(sum((item.discount for item in invoices), Decimal("0")))
        payments = []
        for customer in self.repository.list_customers(): payments.extend([p for p in self.repository.customer_payments(customer.id) if p.payment_date.date() == record.business_date])
        record.cash_total = money(sum((p.amount for p in payments if p.method == "CASH"), Decimal("0")))
        record.transfer_total = money(sum((p.amount for p in payments if p.method in {"BANK_TRANSFER", "INSTAPAY"}), Decimal("0")))
        record.wallet_total = money(sum((p.amount for p in payments if p.method == "MOBILE_WALLET"), Decimal("0")))
        record.exceptions = exceptions; record.financial_exception_count = sum(item["count"] for item in exceptions); record.status = "EXCEPTIONS" if exceptions else "PENDING_APPROVAL"
        return record

    def close(self, identifier: int | str, action: DailyCloseAction) -> DailyClose:
        record = self.validate(identifier)
        if record.exceptions and not action.approved_override: raise SalesValidationError("Daily close has unresolved exceptions")
        record.approved_override = action.approved_override; record.approved_by = action.actor; record.status = "CLOSED"; record.completed_at = datetime.now(UTC)
        SalesAuditService(self.repository.session).event("DAILY_CLOSE_COMPLETED", "DAILY_CLOSE", record.daily_close_uid, {"business_date": record.business_date, "override": action.approved_override})
        return record

    def reopen(self, identifier: int | str, action: DailyCloseAction) -> DailyClose:
        record = self.get(identifier)
        if record.status != "CLOSED": raise SalesValidationError("Only a closed day can be reopened")
        if not action.reason: raise SalesValidationError("Reopen reason is required")
        record.status = "REOPENED"; record.reopen_reason = action.reason; record.approved_by = action.actor
        return record
