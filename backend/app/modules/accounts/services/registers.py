"""
The registers a society's books keep, each line carrying the name of the person who made the entry:

- the cash and bank book: every receipt and payment through each cash and bank account, with the running balance;
- the invoice register: the maintenance invoices raised on members (who generated them, what was billed, paid and is
  still due);
- the bills register: the bills received from vendors (who entered them, what was billed, paid and is still to pay).

All three are read-only views of what is already posted; they change nothing. Only approved, live vouchers are in
the cash and bank book (the same rule as every balance and statement).
"""
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.flat import Flat
from app.modules.accounts.models.accounts import Voucher
from app.modules.accounts.services.accounts_service import AccountsService, money
from app.modules.billing.models.billing import BillStatus, MaintenanceBill
from app.modules.billing.services.bill_pdf import flat_label, member_name
from app.modules.vendor.models.vendor import VendorInvoice

ZERO = Decimal("0.00")


def _s(v) -> str:
    return str(money(v))


class RegistersService:
    def __init__(self, db: Session):
        self.db = db
        self.accounts = AccountsService(db)

    # ── Cash and bank book ────────────────────────────────────────────────────

    def cash_bank_book(self, society_id: UUID, date_from: Optional[date] = None, date_to: Optional[date] = None,
                       account_id: Optional[UUID] = None) -> dict:
        """One section per cash or bank account (or only `account_id`): opening balance, receipts (debits) and
        payments (credits) in order with the balance after each, and the closing balance."""
        accounts = [a for a in self.accounts.list_accounts(society_id) if a.is_cash or a.is_bank]
        if account_id:
            accounts = [a for a in accounts if a.id == account_id]
        sections = []
        total_in = total_out = opening = closing = ZERO
        for a in accounts:
            st = self.accounts.ledger_statement(a.id, date_from, date_to)
            sections.append({
                "account_id": str(a.id), "account_name": a.name, "kind": "cash" if a.is_cash else "bank",
                "bank_name": a.bank_name, "bank_account_number": a.bank_account_number,
                "opening": _s(st["opening"]), "receipts": _s(st["total_debit"]), "payments": _s(st["total_credit"]),
                "closing": _s(st["closing"]),
                "lines": [{
                    "voucher_id": str(l["voucher_id"]), "date": l["date"].isoformat(),
                    "voucher_number": l["voucher_number"], "voucher_type": l["voucher_type"],
                    "particulars": l["particulars"], "narration": l["narration"], "reference": l["reference"],
                    "receipt": _s(l["debit"]), "payment": _s(l["credit"]), "balance": _s(l["balance"]),
                    "entered_by": l["entered_by"], "approved_by": l["approved_by"], "is_auto": l["is_auto"],
                } for l in st["lines"]],
            })
            opening += st["opening"]
            closing += st["closing"]
            total_in += st["total_debit"]
            total_out += st["total_credit"]
        return {"date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "sections": sections,
                "totals": {"opening": _s(opening), "receipts": _s(total_in), "payments": _s(total_out),
                           "closing": _s(closing)}}

    # ── Invoice register (invoices raised on members) ─────────────────────────

    def invoice_register(self, society_id: UUID, date_from: Optional[date] = None, date_to: Optional[date] = None,
                         status: Optional[str] = None, q: Optional[str] = None) -> dict:
        query = (self.db.query(MaintenanceBill)
                 .options(joinedload(MaintenanceBill.flat).joinedload(Flat.wing),
                          joinedload(MaintenanceBill.flat).selectinload(Flat.residents),
                          joinedload(MaintenanceBill.cycle), joinedload(MaintenanceBill.generator))
                 .filter(MaintenanceBill.society_id == society_id, MaintenanceBill.bill_status != BillStatus.DRAFT))
        if date_from:
            query = query.filter(MaintenanceBill.bill_date >= date_from)
        if date_to:
            query = query.filter(MaintenanceBill.bill_date <= date_to)
        if status:
            query = query.filter(MaintenanceBill.bill_status == BillStatus(status))
        bills = query.order_by(MaintenanceBill.bill_date, MaintenanceBill.invoice_number).all()
        rows = []
        for b in bills:
            label, member = flat_label(b.flat), member_name(b.flat, b.resident)
            if q and q.lower() not in f"{b.invoice_number} {label} {member}".lower():
                continue
            rows.append({
                "bill_id": str(b.id), "invoice_number": b.invoice_number,
                "bill_date": b.bill_date.isoformat(), "due_date": b.due_date.isoformat(),
                "flat": label, "member": member, "cycle": b.cycle.name if b.cycle else None,
                "subtotal": _s(b.subtotal), "tax": _s(b.tax_amount), "penalty": _s(b.penalty_amount),
                "discount": _s(b.discount_amount), "total": _s(b.total_amount), "paid": _s(b.paid_amount),
                "outstanding": _s(b.outstanding), "status": b.bill_status.value,
                "is_cancelled": b.bill_status == BillStatus.CANCELLED,
                "entered_by": b.generator.full_name if b.generator else None,
            })
        live = [r for r in rows if not r["is_cancelled"]]
        return {"date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None, "rows": rows,
                "totals": {"count": len(live), "total": _s(sum((Decimal(r["total"]) for r in live), ZERO)),
                           "paid": _s(sum((Decimal(r["paid"]) for r in live), ZERO)),
                           "outstanding": _s(sum((Decimal(r["outstanding"]) for r in live), ZERO))}}

    # ── Bills register (bills received from vendors) ──────────────────────────

    def bills_register(self, society_id: UUID, date_from: Optional[date] = None, date_to: Optional[date] = None,
                       vendor_id: Optional[UUID] = None, status: Optional[str] = None,
                       q: Optional[str] = None) -> dict:
        query = (self.db.query(VendorInvoice).options(joinedload(VendorInvoice.vendor))
                 .filter(VendorInvoice.society_id == society_id))
        if date_from:
            query = query.filter(VendorInvoice.invoice_date >= date_from)
        if date_to:
            query = query.filter(VendorInvoice.invoice_date <= date_to)
        if vendor_id:
            query = query.filter(VendorInvoice.vendor_id == vendor_id)
        invoices: List[VendorInvoice] = query.order_by(VendorInvoice.invoice_date, VendorInvoice.invoice_number).all()
        # The bill is booked by a voucher posted when it is entered; that voucher carries who entered it.
        entered: Dict[UUID, Optional[str]] = {}
        if invoices:
            vs = (self.db.query(Voucher).options(joinedload(Voucher.creator))
                  .filter(Voucher.society_id == society_id, Voucher.source_type == "vendor_invoice",
                          Voucher.source_id.in_([i.id for i in invoices]))
                  .order_by(Voucher.created_at).all())
            for v in vs:
                entered.setdefault(v.source_id, v.creator.full_name if v.creator else None)
        ledger = {a.id: a.name for a in self.accounts.list_accounts(society_id, True)}
        rows = []
        for i in invoices:
            total, paid = money(i.total_amount), money(i.paid_amount)
            net = money(i.net_payable_amount) if i.net_payable_amount is not None else total
            state = "paid" if i.is_paid else ("part_paid" if paid > 0 else "unpaid")
            if status and state != status:
                continue
            vendor = i.vendor.company_name if i.vendor else None
            if q and q.lower() not in f"{i.invoice_number} {vendor or ''} {i.description or ''}".lower():
                continue
            rows.append({
                "invoice_id": str(i.id), "invoice_number": i.invoice_number, "invoice_date": i.invoice_date.isoformat(),
                "due_date": i.due_date.isoformat() if i.due_date else None, "vendor": vendor,
                "description": i.description, "expense_head": ledger.get(i.expense_account_id),
                "amount": _s(i.amount), "gst": _s(i.gst_amount), "tds": _s(i.tds_amount), "total": _s(total),
                "net_payable": _s(net), "paid": _s(paid), "outstanding": _s(max(net - paid, ZERO)),
                "status": state, "entered_by": entered.get(i.id),
            })
        return {"date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None, "rows": rows,
                "totals": {"count": len(rows),
                           "total": _s(sum((Decimal(r["total"]) for r in rows), ZERO)),
                           "paid": _s(sum((Decimal(r["paid"]) for r in rows), ZERO)),
                           "outstanding": _s(sum((Decimal(r["outstanding"]) for r in rows), ZERO))}}
