"""
Automatic postings — the vouchers the society's books get from the rest of
the app, so maintenance billing, receipts and vendor bills never have to be
entered twice:

  Maintenance bill issued   Member Bill   Dr Members' Dues (flat)
                                          Cr Service Charges / recoveries / Sinking
                                             Fund / Repairs Fund / Interest on Arrears…
                                             (by the bill line's charge head), GST Payable
  Bill cancelled            its Member Bill voucher is cancelled
  Payment received          Receipt       Dr Cash in Hand (cash) or the default bank
                                          Cr Members' Dues (flat)
  Payment bounced/rejected  its Receipt voucher is cancelled
  Vendor bill entered       Purchase      Dr the expense head (the bill's own, else
                                             by vendor category)
                                          Cr Sundry Creditors (vendor)
  Vendor paid               Payment       Dr Sundry Creditors (vendor)
                                          Cr Cash in Hand (cash) or the default bank

Hooks never fail the billing or vendor action they follow: a posting that
can't be made is logged, and "Sync postings" (sync_society) catches up
whatever is missing — which is also how books opened after bills and
payments already exist get them.
"""
import logging
from datetime import date
from decimal import Decimal
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import and_, func, not_, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.modules.accounts.models.accounts import Account, Voucher
from app.modules.accounts.services.accounts_service import (
    ZERO, AccountsService, Line, fiscal_year, live_posting, money,
)
from app.modules.accounts.services.chart_of_accounts import VENDOR_CATEGORY_LEDGER, bill_line_ledger_key
from app.modules.billing.models.billing import (
    BillStatus, MaintenanceBill, MaintenanceChargeConfig, MaintenanceElement, OnlinePaymentSubmission,
    PaymentMode, PaymentReceipt, ReconciliationStatus,
)
from app.modules.billing.services.bill_pdf import _bill_month, flat_label, member


def _member_of(flat, resident=None) -> str:
    """'Wing A 101 (Rahul Nair)', or just the flat when no member is on record."""
    m = member(flat, resident) if flat else None
    return f"{flat_label(flat)} ({m.full_name})" if m else flat_label(flat)
from app.modules.billing.services.receipt_pdf import payment_detail
from app.modules.vendor.models.vendor import VendorInvoice, VendorPaymentTransaction

logger = logging.getLogger(__name__)

POSTED_BILL_STATUSES = (BillStatus.ISSUED, BillStatus.PARTIALLY_PAID, BillStatus.PAID, BillStatus.OVERDUE)


class AccountPostings:

    def __init__(self, db: Session, accounts: Optional[AccountsService] = None):
        self.db = db
        self.accounts = accounts or AccountsService(db)
        self._element_codes: Dict[UUID, Dict[str, str]] = {}

    # ── helpers ───────────────────────────────────────────────────────────────

    def active_voucher(self, source_type: str, source_id: UUID) -> Optional[Voucher]:
        return self.db.query(Voucher).filter(
            Voucher.source_type == source_type, Voucher.source_id == source_id, live_posting()).first()

    def _cancel_source(self, source_type: str, source_id: UUID, reason: str, user: Optional[User]) -> bool:
        """Cancel the posting of a cancelled bill or payment — or, if its
        year's books are closed, reverse it in the open year."""
        voucher = self.active_voucher(source_type, source_id)
        if voucher:
            self.accounts.void(voucher, reason, user)
            return True
        return False

    def _post(self, society_id: UUID, voucher_type: str, d: date, lines, *, narration: str, **kw) -> Voucher:
        """Post on the document's own date — or, if that year's books are
        closed, on the first day of the next open year."""
        on = self.accounts.open_posting_date(society_id, d)
        if on != d:
            narration = f"{narration} (dated {d:%d %b %Y}; FY {fiscal_year(d)} books closed)"
        return self.accounts.build_voucher(society_id, voucher_type, on, lines, narration=narration, **kw)

    def _element_code(self, society_id: UUID, description: str) -> Optional[str]:
        if society_id not in self._element_codes:
            rows = (self.db.query(MaintenanceChargeConfig.name, MaintenanceElement.code)
                    .join(MaintenanceElement, MaintenanceElement.id == MaintenanceChargeConfig.element_id)
                    .filter(MaintenanceChargeConfig.society_id == society_id).all())
            self._element_codes[society_id] = {name: code for name, code in rows}
        return self._element_codes[society_id].get(description)

    def _cash_or_bank(self, society_id: UUID, is_cash: bool) -> Account:
        if is_cash:
            return self.accounts.system_account(society_id, "cash")
        return self.accounts.default_bank(society_id)

    def run(self, hook: str, *args) -> None:
        """Run a posting hook inside a savepoint, never failing the caller's
        action: if the posting can't be made, only it is rolled back."""
        try:
            with self.db.begin_nested():
                getattr(self, hook)(*args)
        except Exception:  # noqa: BLE001 — logged; Sync postings catches it up
            self.accounts._charts.clear()
            self._element_codes.clear()
            logger.exception("[accounts] automatic posting %s failed", hook)

    # ── Maintenance bills ─────────────────────────────────────────────────────

    def post_bill(self, bill: MaintenanceBill, user: Optional[User] = None) -> Optional[Voucher]:
        if self.active_voucher("maintenance_bill", bill.id):
            return None
        sid = bill.society_id
        dues = self.accounts.system_account(sid, "members_dues")
        credits: Dict[str, Decimal] = {}
        for li in bill.line_items:
            key = bill_line_ledger_key(li, self._element_code(sid, li.description))
            credits[key] = credits.get(key, ZERO) + money(li.amount)
            if money(li.tax_amount):
                credits["gst_payable"] = credits.get("gst_payable", ZERO) + money(li.tax_amount)
        if money(bill.penalty_amount):
            credits["interest_on_arrears"] = credits.get("interest_on_arrears", ZERO) + money(bill.penalty_amount)
        total = money(bill.total_amount) + money(bill.penalty_amount)
        if total <= 0:
            return None
        diff = total - sum(credits.values(), ZERO)
        if diff:
            credits["round_off"] = credits.get("round_off", ZERO) + diff

        flat = bill.flat
        lines = [Line(dues, debit=total, flat_id=bill.flat_id)]
        for key, amount in credits.items():
            if amount > 0:
                lines.append(Line(self.accounts.system_account(sid, key), credit=amount))
            elif amount < 0:
                lines.append(Line(self.accounts.system_account(sid, key), debit=-amount))
        return self._post(
            sid, "bill", bill.bill_date, lines, user=user,
            narration=f"{_bill_month(bill)} — {_member_of(flat, bill.resident)}",
            reference=bill.invoice_number, source_type="maintenance_bill", source_id=bill.id)

    def cancel_bill(self, bill: MaintenanceBill, user: Optional[User] = None) -> None:
        self._cancel_source("maintenance_bill", bill.id,
                            f"Bill {bill.invoice_number} cancelled: {bill.cancellation_reason or ''}".strip(), user)

    # ── Payments from members ─────────────────────────────────────────────────

    def _post_member_receipt(self, source_type: str, p, user: Optional[User]) -> Optional[Voucher]:
        if self.active_voucher(source_type, p.id) or money(p.amount) <= 0:
            return None
        sid = p.society_id
        flat = p.flat or (p.bill.flat if p.bill else None)
        flat_id = p.flat_id or (p.bill.flat_id if p.bill else None)
        cash_bank = self._cash_or_bank(sid, p.payment_mode == PaymentMode.CASH)
        dues = self.accounts.system_account(sid, "members_dues")
        advance_control = self.accounts.system_account(sid, "member_deposits")
        against = f" against Bill {p.bill.invoice_number}" if p.bill else " on account"

        # PaymentReceipt is always on-bill. OnlinePaymentSubmission can leave
        # an unapplied balance, which is a member credit/advance rather than
        # a negative AR balance. Keep both amounts in the receipt voucher so
        # the GL and the member subledgers reconcile.
        applied = money(p.amount)
        unapplied_amount = ZERO
        if source_type == "online_payment":
            from app.modules.billing.services.allocations import allocated
            applied = min(money(p.amount), allocated(p))
            unapplied_amount = money(p.amount) - applied

        lines = [Line(cash_bank, debit=money(p.amount))]
        if applied > 0:
            from app.modules.accounts.services.entities import AccountingEntityService
            ar = AccountingEntityService(self.db).ensure_flat_member(flat, dues)
            lines.append(Line(dues, credit=applied, flat_id=flat_id, entity_account_id=ar.id))
        if unapplied_amount > 0:
            from app.modules.accounts.services.entities import AccountingEntityService
            advance = AccountingEntityService(self.db).ensure_flat_advance(flat, advance_control)
            lines.append(Line(advance_control, credit=unapplied_amount,
                              entity_account_id=advance.id))

        narration = (f"Received from {_member_of(flat, p.bill.resident if p.bill else None)} "
                     f"vide {payment_detail(p)}{against}")
        return self._post(
            sid, "receipt", p.payment_date, lines,
            narration=narration, reference=p.receipt_number,
            source_type=source_type, source_id=p.id, user=user)

    def post_advance_allocation(self, allocation, user: Optional[User] = None) -> Optional[Voucher]:
        """Move an already-recorded member advance onto a maintenance demand.

        This is only used when a previously unapplied payment is later set
        off. The original receipt remains the cash receipt; this voucher is
        the appropriation from the member advance liability to member AR.
        """
        if self.active_voucher("advance_allocation", allocation.id) or money(allocation.amount) <= 0:
            return None
        payment = allocation.payment
        bill = allocation.bill
        if not payment or not bill:
            return None
        flat = payment.flat or bill.flat
        dues = self.accounts.system_account(payment.society_id, "members_dues")
        advance_control = self.accounts.system_account(payment.society_id, "member_deposits")
        from app.modules.accounts.services.entities import AccountingEntityService
        entities = AccountingEntityService(self.db)
        ar = entities.ensure_flat_member(flat, dues)
        advance = entities.ensure_flat_advance(flat, advance_control)
        return self._post(
            payment.society_id, "journal", bill.bill_date,
            [Line(advance_control, debit=money(allocation.amount), entity_account_id=advance.id),
             Line(dues, credit=money(allocation.amount), flat_id=flat.id, entity_account_id=ar.id)],
            narration=f"Advance applied to Bill {bill.invoice_number} — {flat.flat_number}",
            reference=payment.receipt_number,
            source_type="advance_allocation", source_id=allocation.id, user=user)

    def post_receipt(self, receipt: PaymentReceipt, user: Optional[User] = None) -> Optional[Voucher]:
        if receipt.is_reversed:
            return None
        return self._post_member_receipt("payment_receipt", receipt, user)

    def post_online_payment(self, sub: OnlinePaymentSubmission, user: Optional[User] = None) -> Optional[Voucher]:
        if sub.status == ReconciliationStatus.REJECTED or not sub.is_active:
            return None
        return self._post_member_receipt("online_payment", sub, user)

    def online_payment_status_changed(self, sub: OnlinePaymentSubmission, user: Optional[User] = None) -> None:
        if sub.status == ReconciliationStatus.REJECTED:
            self._cancel_source("online_payment", sub.id,
                                f"Payment {sub.receipt_number} rejected: {sub.review_notes or ''}".strip(), user)
        else:
            self.post_online_payment(sub, user)

    # ── Vendor bills ──────────────────────────────────────────────────────────

    def _expense_account(self, inv: VendorInvoice) -> Account:
        sid = inv.society_id
        if inv.expense_account_id:
            account = self.db.query(Account).filter(Account.id == inv.expense_account_id).first()
            if account and account.society_id == sid:
                return account
        category = inv.vendor.category.value if inv.vendor and inv.vendor.category else "other"
        return self.accounts.system_account(sid, VENDOR_CATEGORY_LEDGER.get(category, "repairs_general"))

    def post_vendor_invoice(self, inv: VendorInvoice, user: Optional[User] = None) -> Optional[Voucher]:
        if self.active_voucher("vendor_invoice", inv.id) or money(inv.total_amount) <= 0:
            return None
        sid, total = inv.society_id, money(inv.total_amount)
        creditors = self.accounts.system_account(sid, "sundry_creditors")
        vendor = inv.vendor.company_name if inv.vendor else "vendor"
        return self._post(
            sid, "purchase", inv.invoice_date,
            [Line(self._expense_account(inv), debit=total),
             Line(creditors, credit=total, vendor_id=inv.vendor_id)],
            narration=f"Bill {inv.invoice_number} of {vendor}" + (f" — {inv.description}" if inv.description else ""),
            reference=inv.invoice_number, source_type="vendor_invoice", source_id=inv.id, user=user)

    def post_vendor_payment(self, payment: VendorPaymentTransaction,
                            user: Optional[User] = None) -> Optional[Voucher]:
        if payment.is_reversed or self.active_voucher("vendor_payment", payment.id):
            return None
        inv = payment.invoice
        if not inv or money(payment.amount) <= 0:
            return None
        sid = payment.society_id
        creditors = self.accounts.system_account(sid, "sundry_creditors")
        vendor = payment.vendor.company_name if payment.vendor else "vendor"
        from app.modules.accounts.services.entities import AccountingEntityService
        ap = AccountingEntityService(self.db).ensure_vendor(payment.vendor, creditors)
        is_cash = payment.payment_mode.value == "cash"
        detail = payment.payment_mode.value.replace("_", " ").upper()
        if payment.transaction_ref:
            detail += f" {payment.transaction_ref}"
        return self._post(
            sid, "payment", payment.payment_date,
            [Line(creditors, debit=money(payment.amount),
                  vendor_id=payment.vendor_id, entity_account_id=ap.id),
             Line(self._cash_or_bank(sid, is_cash), credit=money(payment.amount))],
            narration=f"Paid {vendor} against bill {inv.invoice_number} — {detail}",
            reference=payment.payment_number,
            source_type="vendor_payment", source_id=payment.id, user=user)

    def reverse_vendor_payment(self, payment: VendorPaymentTransaction, reason: str,
                               user: Optional[User] = None) -> None:
        self._cancel_source("vendor_payment", payment.id,
                            f"Vendor payment {payment.payment_number} reversed: {reason}", user)

    def _posted_vendor_payments(self, inv_id: UUID) -> Decimal:
        return money(self.db.query(func.coalesce(func.sum(Voucher.amount), 0))
                     .join(VendorPaymentTransaction, VendorPaymentTransaction.id == Voucher.source_id)
                     .filter(Voucher.source_type == "vendor_payment",
                             VendorPaymentTransaction.invoice_id == inv_id,
                             live_posting()).scalar())

    # ── Catch-up ──────────────────────────────────────────────────────────────

    def pending_count(self, society_id: UUID) -> int:
        """How many postings sync_society would make — counted in SQL, for
        the Accounts screen to show without loading every bill."""
        def posted(source_type):
            return select(Voucher.source_id).where(
                Voucher.society_id == society_id, Voucher.source_type == source_type, live_posting())

        def count(model, *conditions) -> int:
            return self.db.query(func.count(model.id)).filter(model.society_id == society_id, *conditions).scalar()

        live_bill = and_(MaintenanceBill.bill_status.in_(POSTED_BILL_STATUSES), MaintenanceBill.is_active == True)
        live_receipt = and_(PaymentReceipt.is_reversed == False, PaymentReceipt.is_active == True)
        live_online = and_(OnlinePaymentSubmission.status != ReconciliationStatus.REJECTED,
                           OnlinePaymentSubmission.is_active == True)
        n = (count(MaintenanceBill, live_bill, MaintenanceBill.id.not_in(posted("maintenance_bill")))
             + count(MaintenanceBill, not_(live_bill), MaintenanceBill.id.in_(posted("maintenance_bill")))
             + count(PaymentReceipt, live_receipt, PaymentReceipt.id.not_in(posted("payment_receipt")))
             + count(PaymentReceipt, not_(live_receipt), PaymentReceipt.id.in_(posted("payment_receipt")))
             + count(OnlinePaymentSubmission, live_online, OnlinePaymentSubmission.id.not_in(posted("online_payment")))
             + count(OnlinePaymentSubmission, not_(live_online), OnlinePaymentSubmission.id.in_(posted("online_payment")))
             + count(VendorInvoice, VendorInvoice.is_active == True, VendorInvoice.id.not_in(posted("vendor_invoice"))))
        paid_posted = (select(Voucher.source_id, func.sum(Voucher.amount).label("amount"))
                       .where(Voucher.society_id == society_id, Voucher.source_type == "vendor_payment",
                              live_posting())
                       .group_by(Voucher.source_id).subquery())
        n += (self.db.query(func.count(VendorInvoice.id))
              .outerjoin(paid_posted, paid_posted.c.source_id == VendorInvoice.id)
              .filter(VendorInvoice.society_id == society_id, VendorInvoice.is_active == True,
                      VendorInvoice.paid_amount > func.coalesce(paid_posted.c.amount, 0))
              .scalar())
        return n

    def sync_society(self, society_id: UUID, user: Optional[User] = None, dry_run: bool = False) -> dict:
        """Post every automatic voucher that's missing and cancel the ones
        whose bill or payment was cancelled. Idempotent. With dry_run, only
        counts what would change."""
        counts = {"bills": 0, "bills_cancelled": 0, "receipts": 0, "receipts_cancelled": 0,
                  "vendor_bills": 0, "vendor_payments": 0}
        self.accounts.ensure_chart(society_id)

        def active_ids(source_type):
            return {sid for (sid,) in self.db.query(Voucher.source_id).filter(
                Voucher.society_id == society_id, Voucher.source_type == source_type, live_posting())}

        posted_bills = active_ids("maintenance_bill")
        for bill in self.db.query(MaintenanceBill).filter(MaintenanceBill.society_id == society_id).order_by(
                MaintenanceBill.bill_date, MaintenanceBill.created_at):
            live = bill.bill_status in POSTED_BILL_STATUSES and bill.is_active
            if live and bill.id not in posted_bills:
                counts["bills"] += 1
                if not dry_run:
                    self.post_bill(bill, user)
            elif not live and bill.id in posted_bills:
                counts["bills_cancelled"] += 1
                if not dry_run:
                    self.cancel_bill(bill, user)

        for source_type, model, is_live in (
            ("payment_receipt", PaymentReceipt, lambda p: not p.is_reversed and p.is_active),
            ("online_payment", OnlinePaymentSubmission,
             lambda p: p.status != ReconciliationStatus.REJECTED and p.is_active),
        ):
            posted = active_ids(source_type)
            for p in self.db.query(model).filter(model.society_id == society_id).order_by(model.payment_date):
                if is_live(p) and p.id not in posted:
                    counts["receipts"] += 1
                    if not dry_run:
                        self._post_member_receipt(source_type, p, user)
                elif not is_live(p) and p.id in posted:
                    counts["receipts_cancelled"] += 1
                    if not dry_run:
                        self._cancel_source(source_type, p.id, "Payment reversed or rejected", user)

        posted_invoices = active_ids("vendor_invoice")
        for inv in self.db.query(VendorInvoice).filter(VendorInvoice.society_id == society_id,
                                                        VendorInvoice.is_active == True):
            if inv.id not in posted_invoices:
                counts["vendor_bills"] += 1
                if not dry_run:
                    self.post_vendor_invoice(inv, user)
            missing = money(inv.paid_amount) - self._posted_vendor_payments(inv.id)
            if missing > 0:
                counts["vendor_payments"] += 1
                if not dry_run:
                    mode = inv.payment_mode.value if inv.payment_mode else None
                    self.post_vendor_payment(inv, missing, inv.paid_date or inv.invoice_date, mode == "cash",
                                             inv.payment_ref, user)
        counts["total"] = sum(counts.values())
        return counts
