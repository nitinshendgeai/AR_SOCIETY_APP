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

The proof is the last step: the balance the bank's own statement shows (read from the imported PDF, or typed) must equal
"balance as per the bank" above. If it does not, the difference is the bank's own items the books do not have yet
(charges, interest, direct credits) -- which are recorded in the books from the statement row -- and whatever is left
after that is shown as unexplained, never hidden.
"""
import re
from datetime import date, datetime, timedelta
from app.utils.local_time import society_today
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
    BankStatementBalance, BankStatementEntry, BankStatementMatchStatus, OnlinePaymentSubmission, ReconciliationStatus,
)
from app.services.audit_service import AuditService

# A deposit reaches the bank within days; a cheque can be presented weeks after it was written.
CREDIT_WINDOW_BEFORE, CREDIT_WINDOW_AFTER = 10, 5
DEBIT_WINDOW_BEFORE, DEBIT_WINDOW_AFTER = 90, 5
# An automatic match is only made when the bank's own reference agrees, or when nothing else could be meant.
AUTO_WINDOW_DAYS = 3


def _squash(text: Optional[str]) -> str:
    """A reference without spaces, dashes or leading zeros: banks print cheque 123 as 000123 and a UTR in capitals."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower()).lstrip("0")


def _same_ref(a: Optional[str], b: Optional[str]) -> bool:
    return bool(_squash(a) and _squash(a) == _squash(b))


def _ref_agrees(row: BankStatementEntry, voucher_ref: Optional[str]) -> bool:
    """The bank's reference is the voucher's cheque / UTR number: the same number, or (for a transfer, where the bank
    prints the UTR inside the narration) a reference of six or more characters found in the bank's text."""
    if _same_ref(row.reference, voucher_ref):
        return True
    ref = _squash(voucher_ref)
    return len(ref) >= 6 and ref in _squash(f"{row.reference or ''}{row.description or ''}")


def statement_line_key(txn_date, amount, direction, reference, description) -> tuple:
    """What makes two statement lines the same line: the bank's reference identifies it; without one, what it says does."""
    return (txn_date, Decimal(amount), direction, reference or "", "" if reference else (description or "")[:500])


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

    def home_ledger_id(self, society_id: UUID, ledger_id: Optional[UUID] = None) -> Optional[UUID]:
        """The bank ledger a statement belongs to: the one named, else the society's only bank ledger (nothing else
        could be meant), else none."""
        if ledger_id is not None:
            return ledger_id
        banks = self.bank_accounts(society_id)
        return banks[0].id if len(banks) == 1 else None

    def _belongs_to(self, society_id: UUID, account: Account):
        """Statement rows of this bank ledger. A row saved with no bank (older imports) belongs to the default bank only,
        so it is listed once, not under every bank the society has."""
        mine = BankStatementEntry.bank_account_id == account.id
        if self.accounts.default_bank(society_id).id == account.id:
            return mine | BankStatementEntry.bank_account_id.is_(None)
        return mine

    def rows_for(self, society_id: UUID, account_id: Optional[UUID] = None, match_status: Optional[str] = None,
                 limit: int = 500) -> List[BankStatementEntry]:
        """The statement rows of one bank ledger, newest first, each line once: a row saved with no bank is hidden when
        the same line is also stored against a bank (a statement imported twice, with and without the bank chosen)."""
        account = self.bank_account(society_id, account_id)
        q = (self.db.query(BankStatementEntry).options(joinedload(BankStatementEntry.matched_submission))
             .filter(BankStatementEntry.society_id == society_id, BankStatementEntry.is_active == True,  # noqa: E712
                     self._belongs_to(society_id, account)))
        every = q.order_by(BankStatementEntry.txn_date.desc(), BankStatementEntry.created_at.desc()).all()
        seen: Dict[tuple, int] = {}
        for r in every:
            if r.bank_account_id is not None:
                k = statement_line_key(r.txn_date, r.amount, r.direction, r.reference, r.description)
                seen[k] = seen.get(k, 0) + 1
        out = []
        for r in every:
            if r.bank_account_id is None:
                k = statement_line_key(r.txn_date, r.amount, r.direction, r.reference, r.description)
                if seen.get(k, 0) > 0:                       # the same line is stored against the bank: hide this copy
                    seen[k] -= 1
                    continue
            if match_status is None or r.match_status.value == match_status:
                out.append(r)
        return out[:limit]

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

    def _line_out(self, e: VoucherEntry, as_on: Optional[date] = None) -> dict:
        v = e.voucher
        amount = money(e.debit) or money(e.credit)
        who = v.vendor.company_name if v.vendor else None
        return {
            "entry_id": str(e.id), "voucher_id": str(v.id), "voucher_number": v.voucher_number,
            "voucher_type": v.voucher_type, "date": v.voucher_date.isoformat(),
            "reference": v.reference, "narration": e.narration or v.narration, "party": who,
            "amount": str(amount), "direction": "deposit" if money(e.debit) else "payment",
            "cleared_date": e.cleared_date.isoformat() if e.cleared_date else None,
            "days_pending": max(0, ((as_on or society_today(self.db, v.society_id)) - v.voucher_date).days),
        }

    # ── The statement ─────────────────────────────────────────────────────────

    def statement(self, society_id: UUID, account_id: Optional[UUID] = None, as_on: Optional[date] = None,
                  bank_balance: Optional[Decimal] = None) -> dict:
        """The Bank Reconciliation Statement of one bank ledger as on a date (default today), checked against the balance
        the bank's statement shows that day: the one given, else the one stored from the imported PDF / typed in."""
        as_on = as_on or society_today(self.db, society_id)
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
            self._belongs_to(society_id, account)).count())
        out = {
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
        out.update(self._proof(society_id, account, as_on, money(per_bank), bank_balance))
        return out

    def _bank_only_rows(self, society_id: UUID, account: Account, as_on: date) -> List[BankStatementEntry]:
        """Statement rows up to the date that are in no line of the books (not matched): the bank's own charges,
        interest and direct credits, or a transaction the society has not entered yet."""
        return (self.db.query(BankStatementEntry).filter(
            BankStatementEntry.society_id == society_id, BankStatementEntry.is_active == True,  # noqa: E712
            BankStatementEntry.match_status != BankStatementMatchStatus.MATCHED,
            BankStatementEntry.txn_date <= as_on, self._belongs_to(society_id, account))
            .order_by(BankStatementEntry.txn_date, BankStatementEntry.created_at).all())

    def _proof(self, society_id: UUID, account: Account, as_on: date, per_bank: Decimal,
               typed: Optional[Decimal]) -> dict:
        """Balance per the bank's statement, the difference from the computed balance, and what explains it."""
        stored = (self.db.query(BankStatementBalance).filter(
            BankStatementBalance.bank_account_id == account.id, BankStatementBalance.as_on == as_on).first())
        latest = (self.db.query(BankStatementBalance).filter(BankStatementBalance.bank_account_id == account.id)
                  .order_by(BankStatementBalance.as_on.desc()).first())
        bank_only = self._bank_only_rows(society_id, account, as_on)
        credits = sum((r.amount for r in bank_only if r.direction == "credit"), ZERO)
        debits = sum((r.amount for r in bank_only if r.direction != "credit"), ZERO)
        todo = [r for r in bank_only if r.match_status == BankStatementMatchStatus.UNMATCHED]
        proof = {
            "statement_balance": None, "statement_balance_source": None, "difference": None, "unexplained": None,
            "status": "no_statement_balance",
            "latest_statement": {"as_on": latest.as_on.isoformat(), "balance": str(money(latest.balance))}
            if latest else None,
            "bank_only_rows": [{
                "id": str(r.id), "txn_date": r.txn_date.isoformat(), "description": r.description,
                "reference": r.reference, "amount": str(r.amount), "direction": r.direction,
                "match_status": r.match_status.value} for r in todo],
            "bank_only_credits": str(credits), "bank_only_debits": str(debits),
        }
        balance, source = (money(typed), "typed") if typed is not None else (
            (money(stored.balance), stored.source) if stored else (None, None))
        if balance is None:
            return proof
        difference = per_bank - balance
        # the bank holds credits the books lack (the books are short by them) and has paid debits the books lack
        unexplained = difference + credits - debits
        proof.update(statement_balance=str(balance), statement_balance_source=source,
                     difference=str(money(difference)), unexplained=str(money(unexplained)),
                     status="reconciled" if difference == ZERO else (
                         "bank_items_to_book" if unexplained == ZERO else "difference"))
        return proof

    def set_statement_balance(self, society_id: UUID, account_id: Optional[UUID], as_on: date, balance: Decimal,
                              user: Optional[User], source: str = "manual", commit: bool = True) -> BankStatementBalance:
        """Keep the balance the bank statement shows on a day (replacing an earlier one for the same day)."""
        account = self.bank_account(society_id, account_id)
        if as_on > society_today(self.db, society_id):
            raise HTTPException(422, "The bank statement can't show a balance in the future")
        row = (self.db.query(BankStatementBalance).filter(
            BankStatementBalance.bank_account_id == account.id, BankStatementBalance.as_on == as_on).first())
        if row is None:
            row = BankStatementBalance(society_id=society_id, bank_account_id=account.id, as_on=as_on)
            self.db.add(row)
        row.balance, row.source, row.entered_by = money(balance), source, user.id if user else None
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return row

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
        if cleared_date > society_today(self.db, society_id):
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
        """Take back a clearing made by mistake. A line matched to a statement row is released from it too -- and when
        several lines were cleared together by one row, the whole group goes back."""
        rows = self._lines_to_clear(society_id, entry_ids)
        group_rows = {e.matched_row_id for e in rows if e.matched_row_id}
        if group_rows:
            have = {e.id for e in rows}
            rows += [e for e in self.db.query(VoucherEntry).filter(VoucherEntry.matched_row_id.in_(group_rows))
                     .options(joinedload(VoucherEntry.voucher)).all() if e.id not in have]
        for e in rows:
            e.cleared_date = e.cleared_by = e.matched_row_id = None
            for row in self.db.query(BankStatementEntry).filter(BankStatementEntry.matched_entry_id == e.id):
                row.match_status, row.matched_entry_id = BankStatementMatchStatus.UNMATCHED, None
                row.matched_by = row.matched_at = None
        for row_id in group_rows:
            row = self.db.get(BankStatementEntry, row_id)
            if row is not None:
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
            ref = _ref_agrees(row, e.voucher.reference)
            return (not ref, abs((e.voucher.voucher_date - row.txn_date).days))

        found.sort(key=rank)
        return [{**self._line_out(e), "reference_matches": _ref_agrees(row, e.voucher.reference)}
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
            account = self.bank_account(society_id, account_id)
            home_is_default = self.accounts.default_bank(society_id).id == account.id
            rows = [r for r in rows if r.bank_account_id == account.id or (r.bank_account_id is None and home_is_default)]
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

    def match_selected(self, society_id: UUID, row_ids: List[UUID], entry_ids: List[UUID], user: User) -> dict:
        """Match what the treasurer ticked on both sides: lines of the books and rows of the bank statement. The two
        sides must be the same money: credits against deposits, debits against payments, and the same total.
        One row can clear several lines (a deposit slip of cheques) and several rows can clear one line (a payment the
        bank took in parts), but not several against several -- that cannot be told apart later."""
        row_ids, entry_ids = list(dict.fromkeys(row_ids)), list(dict.fromkeys(entry_ids))
        if not row_ids or not entry_ids:
            raise HTTPException(422, "Tick at least one line of the books and one row of the bank statement")
        if len(row_ids) > 1 and len(entry_ids) > 1:
            raise HTTPException(422, "Match one bank row to several lines of the books, or several bank rows to one "
                                     "line -- not several on both sides at once")
        rows = [self._line(society_id, rid) for rid in row_ids]
        for r in rows:
            if r.match_status != BankStatementMatchStatus.UNMATCHED:
                raise HTTPException(409, f"The bank row of {r.txn_date:%d %b %Y} ({r.amount}) is already {r.match_status.value}")
        entries = self._lines_to_clear(society_id, entry_ids)
        for e in entries:
            if e.cleared_date is not None:
                raise HTTPException(409, f"{e.voucher.voucher_number} is already reconciled")
        credit = rows[0].direction == "credit"
        if any((r.direction == "credit") != credit for r in rows):
            raise HTTPException(422, "Tick bank credits or bank debits, not both together")
        if any(bool(money(e.debit)) != credit for e in entries):
            raise HTTPException(422, "A bank credit is matched to deposits in the books, and a bank debit to payments")
        accounts = {e.account_id for e in entries}
        if len(accounts) != 1 or any(r.bank_account_id and r.bank_account_id not in accounts for r in rows):
            raise HTTPException(422, "The lines and the bank rows must belong to the same bank account")
        rows_total = sum((money(r.amount) for r in rows), ZERO)
        books_total = sum((money(e.debit if credit else e.credit) for e in entries), ZERO)
        if rows_total != books_total:
            raise HTTPException(422, f"The bank rows total {rows_total} but the lines of the books total {books_total} "
                                     f"-- they differ by {abs(rows_total - books_total)}")
        account_id = next(iter(accounts))
        bank_day = max(r.txn_date for r in rows)
        grouped = len(entries) > 1
        for e in entries:
            e.cleared_date, e.cleared_by = max(bank_day, e.voucher.voucher_date), user.id
            e.matched_row_id = rows[0].id if grouped else None
            self._after_cleared(e, e.cleared_date, user)
        for r in rows:
            r.match_status, r.matched_entry_id = BankStatementMatchStatus.MATCHED, entries[0].id
            r.matched_by, r.matched_at, r.bank_account_id = user.id, datetime.utcnow(), account_id
        self._audit(entries[0].voucher, user, matched_statement_rows=[str(r.id) for r in rows],
                    cleared=[e.voucher.voucher_number for e in entries], amount=str(rows_total))
        self.db.commit()
        return {"rows": len(rows), "lines": len(entries), "amount": str(rows_total)}

    def book_row(self, society_id: UUID, line_id: UUID, ledger_id: UUID, user: User,
                 narration: Optional[str] = None) -> BankStatementEntry:
        """Record a bank-only statement row in the books -- bank charges, interest, a direct credit -- the way a
        treasurer does it from the bank statement: a Receipt (money in) or Payment (money out) against the other ledger
        the row belongs to, dated the day the bank did it, and cleared at once because the bank has already done it."""
        row = self._line(society_id, line_id)
        if row.match_status == BankStatementMatchStatus.MATCHED:
            raise HTTPException(409, "This statement row is already matched to the books")
        bank = self.bank_account(society_id, row.bank_account_id)
        other = self.db.query(Account).filter(Account.id == ledger_id).first()
        if not other or other.society_id != society_id or not other.is_active:
            raise HTTPException(422, "Choose a ledger of this society")
        if other.is_cash_or_bank:
            raise HTTPException(422, "Choose the ledger the money belongs to (bank charges, interest ...), not a cash or "
                                     "bank ledger")
        chart = self.accounts.ensure_chart(society_id)
        if other.id in (chart["members_dues"].id, chart["sundry_creditors"].id):
            raise HTTPException(422, f"{other.name} is not booked from here: a resident's payment or a vendor's bill is "
                                     "entered through its own screen, then matched to this row")
        credit = row.direction == "credit"
        amount = money(row.amount)
        vtype = "receipt" if credit else "payment"
        lines = self.accounts._manual_lines(society_id, vtype, [
            {"account_id": bank.id, ("debit" if credit else "credit"): amount},
            {"account_id": other.id, ("credit" if credit else "debit"): amount}])
        note = (narration or "").strip() or f"Per bank statement: {row.description}"
        voucher = self.accounts.build_voucher(
            society_id, vtype, row.txn_date, lines, narration=note[:500], reference=(row.reference or None),
            user=user, approval_status="approved",
            approval_note="Recorded from the bank statement: the bank has already done it")
        voucher.approved_at, voucher.approved_by = datetime.utcnow(), user.id
        entry = next(e for e in voucher.entries if e.account_id == bank.id)
        entry.cleared_date, entry.cleared_by = row.txn_date, user.id
        row.match_status, row.matched_entry_id = BankStatementMatchStatus.MATCHED, entry.id
        row.matched_by, row.matched_at, row.bank_account_id = user.id, datetime.utcnow(), bank.id
        row.ignore_reason = None
        self._audit(voucher, user, booked_statement_row=str(row.id), amount=str(amount), ledger=other.name,
                    voucher_number=voucher.voucher_number)
        self.db.commit()
        self.db.refresh(row)
        return row

    def unmatch(self, society_id: UUID, line_id: UUID, user: User) -> BankStatementEntry:
        row = self._line(society_id, line_id)
        if row.match_status != BankStatementMatchStatus.MATCHED or not row.matched_entry_id:
            raise HTTPException(409, "Only a row matched to a line of the books can be taken back here")
        self.unclear(society_id, [row.matched_entry_id], user)
        self.db.refresh(row)
        return row
