"""
Bank reconciliation against the books — what a treasurer does every month with the bank statement in hand.

The books' bank ledger says what the society thinks is in the bank; the statement says what the bank thinks. They
differ by what is still on its way: cheques and transfers the society has paid that the bank has not yet debited, and
deposits it has recorded that the bank has not yet credited. Marking each line of the bank ledger with the day the
bank cleared it leaves the Bank Reconciliation Statement (BRS):

    Balance as per the books                          (the bank ledger, approved vouchers only)
    Add:   payments not yet cleared (cheques issued)  (credit lines the bank has not debited)
    Less:  deposits not yet cleared                   (debit lines the bank has not credited)
    ─────────────────────────────────────────────
    Balance as per the bank                           (what the statement shows on the day)

Opening balances are taken as cleared. Only a bank ledger is reconciled — cash has no statement.

Statement rows (BankStatementEntry, imported from the bank's CSV, credits *and* debits) are matched to those lines by
amount and nearby date; confirming a match is what clears the line. A line that is a resident's online payment also
moves that payment from PENDING to RECONCILED, which is the same confirmation the billing screen gives.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.audit_log import AuditAction
from app.models.user import User
from app.modules.accounts.models.accounts import Account, Voucher, VoucherEntry
from app.modules.accounts.services.accounts_service import ZERO, AccountsService, money, signed_opening
from app.modules.billing.models.billing import (
    BankStatementEntry, BankStatementMatchStatus, OnlinePaymentSubmission, ReconciliationStatus,
)
from app.services.audit_service import AuditService

# A deposit reaches the bank within days; a cheque can be presented weeks after it was written.
CREDIT_WINDOW_BEFORE, CREDIT_WINDOW_AFTER = 10, 5
DEBIT_WINDOW_BEFORE, DEBIT_WINDOW_AFTER = 90, 5
# An automatic match is only made when the bank's own reference agrees, or when nothing else could be meant.
AUTO_WINDOW_DAYS = 3


def _same_ref(a: Optional[str], b: Optional[str]) -> bool:
    return bool(a and b and a.strip().lower() == b.strip().lower())


class BankReconciliationService:

    def __init__(self, db: Session, accounts: Optional[AccountsService] = None):
        self.db = db
        self.accounts = accounts or AccountsService(db)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def bank_account(self, society_id: UUID, account_id: Optional[UUID] = None) -> Account:
        """The bank ledger to reconcile: the one asked for, else the society's default bank."""
        if account_id is None:
            return self.accounts.default_bank(society_id)
        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account or account.society_id != society_id:
            raise HTTPException(404, "Bank ledger not found in this society")
        if not account.is_bank:
            raise HTTPException(422, "Only a bank ledger is reconciled — cash has no bank statement")
        return account

    def bank_accounts(self, society_id: UUID) -> List[Account]:
        return [a for a in self.accounts.list_accounts(society_id) if a.is_bank]

    def _live_lines(self, society_id: UUID, account_id: UUID):
        """The bank ledger's lines that stand in the books: approved, not cancelled, and not a voucher that was
        reversed or the reversal of one (the pair nets to nothing and the bank never sees either)."""
        return (self.db.query(VoucherEntry).join(Voucher, Voucher.id == VoucherEntry.voucher_id)
                .options(joinedload(VoucherEntry.voucher).joinedload(Voucher.vendor))
                .filter(Voucher.society_id == society_id, VoucherEntry.account_id == account_id,
                        Voucher.is_cancelled == False, Voucher.approval_status == "approved",  # noqa: E712
                        Voucher.reversed_at.is_(None), Voucher.reversal_of_id.is_(None)))

    def _audit(self, voucher: Voucher, user: Optional[User], **values) -> None:
        AuditService.log(db=self.db, action=AuditAction.UPDATE, module="accounts", entity_id=str(voucher.id),
                         entity_type="BankReconciliation", user=user, new_values=values)

    @staticmethod
    def _line_out(e: VoucherEntry, as_on: Optional[date] = None) -> dict:
        v = e.voucher
        amount = money(e.debit) or money(e.credit)
        who = v.vendor.company_name if v.vendor else None
        return {
            "entry_id": str(e.id), "voucher_id": str(v.id), "voucher_number": v.voucher_number,
            "voucher_type": v.voucher_type, "date": v.voucher_date.isoformat(),
            "reference": v.reference, "narration": e.narration or v.narration, "party": who,
            "amount": str(amount), "direction": "deposit" if money(e.debit) else "payment",
            "cleared_date": e.cleared_date.isoformat() if e.cleared_date else None,
            "days_pending": max(0, ((as_on or date.today()) - v.voucher_date).days),
        }

    # ── The statement ─────────────────────────────────────────────────────────

    def statement(self, society_id: UUID, account_id: Optional[UUID] = None, as_on: Optional[date] = None) -> dict:
        """The Bank Reconciliation Statement of one bank ledger as on a date (default today)."""
        as_on = as_on or date.today()
        account = self.bank_account(society_id, account_id)
        book = signed_opening(account) + self.accounts._movements(
            society_id, upto=as_on, account_id=account.id).get(account.id, ZERO)

        lines = (self._live_lines(society_id, account.id)
                 .filter(Voucher.voucher_date <= as_on)
                 .order_by(Voucher.voucher_date, Voucher.created_at, VoucherEntry.line_no).all())
        pending = [e for e in lines if e.cleared_date is None or e.cleared_date > as_on]
        deposits = [e for e in pending if money(e.debit)]
        payments = [e for e in pending if money(e.credit)]
        deposits_total = sum((money(e.debit) for e in deposits), ZERO)
        payments_total = sum((money(e.credit) for e in payments), ZERO)
        per_bank = book + payments_total - deposits_total

        unmatched = (self.db.query(BankStatementEntry).filter(
            BankStatementEntry.society_id == society_id, BankStatementEntry.is_active == True,  # noqa: E712
            BankStatementEntry.match_status == BankStatementMatchStatus.UNMATCHED,
            (BankStatementEntry.bank_account_id == account.id) | BankStatementEntry.bank_account_id.is_(None)).count())
        return {
            "account_id": str(account.id), "account_name": account.name, "bank_name": account.bank_name,
            "as_on": as_on.isoformat(),
            "balance_per_books": str(money(book)),
            "payments_not_cleared": [self._line_out(e, as_on) for e in payments],
            "payments_not_cleared_total": str(payments_total),
            "deposits_not_cleared": [self._line_out(e, as_on) for e in deposits],
            "deposits_not_cleared_total": str(deposits_total),
            "balance_per_bank": str(money(per_bank)),
            "uncleared_count": len(pending), "unmatched_statement_rows": unmatched,
        }

    def cleared_lines(self, society_id: UUID, account_id: Optional[UUID] = None, date_from: Optional[date] = None,
                      date_to: Optional[date] = None) -> List[dict]:
        """Lines already cleared, most recent first — to review or to take back a mistake."""
        account = self.bank_account(society_id, account_id)
        q = self._live_lines(society_id, account.id).filter(VoucherEntry.cleared_date.isnot(None))
        if date_from:
            q = q.filter(VoucherEntry.cleared_date >= date_from)
        if date_to:
            q = q.filter(VoucherEntry.cleared_date <= date_to)
        return [self._line_out(e) for e in q.order_by(VoucherEntry.cleared_date.desc(), Voucher.voucher_date.desc())
                .limit(500).all()]

    # ── Clearing ──────────────────────────────────────────────────────────────

    def _lines_to_clear(self, society_id: UUID, entry_ids: List[UUID]) -> List[VoucherEntry]:
        ids = list(dict.fromkeys(entry_ids))
        rows = (self.db.query(VoucherEntry).join(Voucher, Voucher.id == VoucherEntry.voucher_id)
                .options(joinedload(VoucherEntry.voucher), joinedload(VoucherEntry.account))
                .filter(VoucherEntry.id.in_(ids), Voucher.society_id == society_id).all())
        if len(rows) != len(ids):
            raise HTTPException(404, "A line to reconcile was not found in this society")
        for e in rows:
            v = e.voucher
            if not e.account or not e.account.is_bank:
                raise HTTPException(422, f"{v.voucher_number}: only a line on a bank ledger can be reconciled")
            if v.is_cancelled or v.approval_status != "approved" or v.reversed_at is not None or v.reversal_of_id:
                raise HTTPException(422, f"{v.voucher_number} is not a live entry in the books — it can't be reconciled")
        return rows

    def _after_cleared(self, e: VoucherEntry, on: date, user: Optional[User]) -> None:
        """A resident's online payment is confirmed once its money shows in the bank."""
        v = e.voucher
        if v.source_type == "online_payment" and v.source_id:
            sub = self.db.get(OnlinePaymentSubmission, v.source_id)
            if sub and sub.status == ReconciliationStatus.PENDING:
                sub.status = ReconciliationStatus.RECONCILED
                sub.reviewed_by = user.id if user else None
                sub.reviewed_at = datetime.utcnow()

    def clear(self, society_id: UUID, entry_ids: List[UUID], cleared_date: date, user: User) -> int:
        """Mark lines of a bank ledger as cleared by the bank on `cleared_date`."""
        if cleared_date > date.today():
            raise HTTPException(422, "The bank can't have cleared it in the future")
        rows = self._lines_to_clear(society_id, entry_ids)
        for e in rows:
            if cleared_date < e.voucher.voucher_date:
                raise HTTPException(422, f"{e.voucher.voucher_number} is dated {e.voucher.voucher_date:%d %b %Y} — "
                                         f"the bank can't have cleared it earlier")
        for e in rows:
            e.cleared_date, e.cleared_by = cleared_date, user.id if user else None
            self._after_cleared(e, cleared_date, user)
        self._audit(rows[0].voucher, user, cleared=[e.voucher.voucher_number for e in rows],
                    cleared_date=cleared_date)
        self.db.commit()
        return len(rows)

    def unclear(self, society_id: UUID, entry_ids: List[UUID], user: User) -> int:
        """Take back a clearing made by mistake. A line matched to a statement row is released from it too."""
        rows = self._lines_to_clear(society_id, entry_ids)
        for e in rows:
            e.cleared_date = e.cleared_by = None
            for row in self.db.query(BankStatementEntry).filter(BankStatementEntry.matched_entry_id == e.id):
                row.match_status, row.matched_entry_id = BankStatementMatchStatus.UNMATCHED, None
                row.matched_by = row.matched_at = None
        self._audit(rows[0].voucher, user, uncleared=[e.voucher.voucher_number for e in rows])
        self.db.commit()
        return len(rows)

    def clear_for_source(self, source_type: str, source_id: UUID, on: date, user: Optional[User]) -> Optional[UUID]:
        """Clear the bank line of the voucher posted for a bill or payment (used when the billing screen confirms an
        online payment against the bank statement). Returns the bank ledger it was on, or None when there is none."""
        v = self.db.query(Voucher).filter(
            Voucher.source_type == source_type, Voucher.source_id == source_id, Voucher.is_cancelled == False,  # noqa: E712
            Voucher.approval_status == "approved", Voucher.reversed_at.is_(None)).first()
        if not v:
            return None
        for e in v.entries:
            if e.account and e.account.is_bank:
                if e.cleared_date is None:
                    e.cleared_date, e.cleared_by = max(on, v.voucher_date), user.id if user else None
                return e.account_id
        return None

    # ── Matching statement rows to the books ─────────────────────────────────

    def _line(self, society_id: UUID, line_id: UUID) -> BankStatementEntry:
        row = self.db.query(BankStatementEntry).filter(BankStatementEntry.id == line_id).first()
        if not row or row.society_id != society_id:
            raise HTTPException(404, "Bank statement row not found")
        return row

    def suggestions(self, society_id: UUID, line_id: UUID) -> List[dict]:
        """The books' own lines this statement row could be: same amount, the opposite side of the bank ledger
        (money the bank received is a debit in the books), not cleared yet, dated near the row. The ones whose
        reference agrees come first."""
        row = self._line(society_id, line_id)
        accounts = [row.bank_account_id] if row.bank_account_id else [a.id for a in self.bank_accounts(society_id)]
        if not accounts:
            return []
        credit = row.direction == "credit"
        before, after = (CREDIT_WINDOW_BEFORE, CREDIT_WINDOW_AFTER) if credit else (DEBIT_WINDOW_BEFORE, DEBIT_WINDOW_AFTER)
        found = []
        for account_id in accounts:
            q = (self._live_lines(society_id, account_id).filter(
                VoucherEntry.cleared_date.is_(None),
                Voucher.voucher_date >= row.txn_date - timedelta(days=before),
                Voucher.voucher_date <= row.txn_date + timedelta(days=after)))
            q = q.filter(VoucherEntry.debit == row.amount) if credit else q.filter(VoucherEntry.credit == row.amount)
            found += q.all()

        def rank(e: VoucherEntry):
            ref = _same_ref(row.reference, e.voucher.reference)
            return (not ref, abs((e.voucher.voucher_date - row.txn_date).days))

        found.sort(key=rank)
        return [{**self._line_out(e), "reference_matches": _same_ref(row.reference, e.voucher.reference)}
                for e in found]

    def confirm_match(self, society_id: UUID, line_id: UUID, entry_id: UUID, user: User) -> BankStatementEntry:
        row = self._line(society_id, line_id)
        if row.match_status != BankStatementMatchStatus.UNMATCHED:
            raise HTTPException(409, f"This statement row is already {row.match_status.value}")
        (e,) = self._lines_to_clear(society_id, [entry_id])
        if e.cleared_date is not None:
            raise HTTPException(409, f"{e.voucher.voucher_number} is already reconciled")
        if row.bank_account_id and row.bank_account_id != e.account_id:
            raise HTTPException(422, "That line is on a different bank account than this statement")
        credit = row.direction == "credit"
        if money(e.debit if credit else e.credit) != money(row.amount):
            raise HTTPException(422, "The amount or the side (deposit / payment) doesn't agree with the statement row")
        e.cleared_date, e.cleared_by = max(row.txn_date, e.voucher.voucher_date), user.id
        row.match_status, row.matched_entry_id = BankStatementMatchStatus.MATCHED, e.id
        row.matched_by, row.matched_at, row.bank_account_id = user.id, datetime.utcnow(), e.account_id
        self._after_cleared(e, e.cleared_date, user)
        self._audit(e.voucher, user, matched_statement_row=str(row.id), amount=row.amount,
                    cleared_date=e.cleared_date)
        self.db.commit()
        self.db.refresh(row)
        return row

    def auto_match(self, society_id: UUID, account_id: Optional[UUID], user: User) -> dict:
        """Match every statement row that can only mean one line of the books: the bank's reference agrees with the
        voucher's, or a single line has the amount within a few days and no other statement row competes for it.
        Anything doubtful is left for a person to choose."""
        rows = (self.db.query(BankStatementEntry).filter(
            BankStatementEntry.society_id == society_id, BankStatementEntry.is_active == True,  # noqa: E712
            BankStatementEntry.match_status == BankStatementMatchStatus.UNMATCHED)
            .order_by(BankStatementEntry.txn_date).all())
        if account_id is not None:
            self.bank_account(society_id, account_id)
            rows = [r for r in rows if r.bank_account_id in (None, account_id)]
        matched = left = 0
        taken: set = set()
        for row in rows:
            options = [s for s in self.suggestions(society_id, row.id) if UUID(s["entry_id"]) not in taken]
            pick = None
            by_ref = [s for s in options if s["reference_matches"]]
            if len(by_ref) == 1:
                pick = by_ref[0]
            elif not by_ref and len(options) == 1:
                near = abs((date.fromisoformat(options[0]["date"]) - row.txn_date).days) <= AUTO_WINDOW_DAYS
                rivals = [r for r in rows if r.id != row.id and r.amount == row.amount
                          and r.direction == row.direction and r.match_status == BankStatementMatchStatus.UNMATCHED]
                if near and not rivals:
                    pick = options[0]
            if pick is None:
                left += 1
                continue
            taken.add(UUID(pick["entry_id"]))
            self.confirm_match(society_id, row.id, UUID(pick["entry_id"]), user)
            matched += 1
        return {"matched": matched, "left_for_a_person": left}

    def unmatch(self, society_id: UUID, line_id: UUID, user: User) -> BankStatementEntry:
        row = self._line(society_id, line_id)
        if row.match_status != BankStatementMatchStatus.MATCHED or not row.matched_entry_id:
            raise HTTPException(409, "Only a row matched to a line of the books can be taken back here")
        self.unclear(society_id, [row.matched_entry_id], user)
        self.db.refresh(row)
        return row
