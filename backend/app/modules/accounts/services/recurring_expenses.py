"""Recurring monthly expenses: the standing ones a society pays every month, brought up as *due* for a
person to confirm. Nothing is posted until someone records it, so the books only carry what was paid.

A month of a template is due once its day has come (the day is capped to the month's last day) and nothing has
been decided for it: recorded as a payment voucher, or skipped. A recorded month whose voucher is later
cancelled becomes due again.
"""
import calendar
from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.audit_log import AuditAction
from app.models.user import User
from app.modules.accounts.models.accounts import Account, RecurringExpense, RecurringExpenseRun
from app.modules.accounts.services.accounts_service import AccountsService
from app.utils.local_time import local_today, zone
from app.models.society import Society

LOOKBACK_MONTHS = 12      # a template left alone for longer than this is shown from this far back only


def first_of(d: date) -> date:
    return date(d.year, d.month, 1)


def add_month(d: date, n: int = 1) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def due_date(month: date, day: int) -> date:
    return date(month.year, month.month, min(day, calendar.monthrange(month.year, month.month)[1]))


class RecurringExpenseService:
    def __init__(self, db: Session):
        self.db = db
        self.accounts = AccountsService(db)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _in_scope(user: Optional[User], society_id) -> bool:
        return user is None or user.society_id is None or user.society_id == society_id

    def _today(self, society_id: UUID) -> date:
        society = self.db.query(Society).filter(Society.id == society_id).first()
        return local_today(zone(society.timezone if society else None))

    def get(self, recurring_id: UUID, user: Optional[User] = None) -> RecurringExpense:
        r = self.db.query(RecurringExpense).filter(RecurringExpense.id == recurring_id).first()
        if r is None or not self._in_scope(user, r.society_id):
            raise HTTPException(404, "Recurring expense not found")
        return r

    def _expense_head(self, society_id: UUID, account_id: UUID) -> Account:
        a = self.db.query(Account).filter(Account.id == account_id).first()
        if a is None or a.society_id != society_id or not a.is_active or a.group.nature != "expense":
            raise HTTPException(422, "Choose an expense head of this society")
        return a

    def _cash_or_bank(self, society_id: UUID, account_id: UUID) -> Account:
        a = self.db.query(Account).filter(Account.id == account_id).first()
        if a is None or a.society_id != society_id or not a.is_active or not a.is_cash_or_bank:
            raise HTTPException(422, "Choose a cash or bank account of this society")
        return a

    @staticmethod
    def _check_day(day: Optional[int]) -> None:
        if day is not None and not (1 <= day <= 31):
            raise HTTPException(422, "The day of the month must be 1 to 31")

    # ── Templates ────────────────────────────────────────────────────────────

    def create(self, data: dict, user: User, request=None) -> RecurringExpense:
        society_id = data["society_id"]
        self.accounts.ensure_chart(society_id)
        name = (data.get("name") or "").strip()
        if not name:
            raise HTTPException(422, "Give the expense a name")
        self._expense_head(society_id, data["expense_account_id"])
        if data.get("paid_from_id"):
            self._cash_or_bank(society_id, data["paid_from_id"])
        self._check_day(data.get("day_of_month"))
        if data.get("amount") is not None and Decimal(data["amount"]) < 0:
            raise HTTPException(422, "The amount can't be negative")
        start = first_of(data.get("start_month") or self._today(society_id))
        end = first_of(data["end_month"]) if data.get("end_month") else None
        if end is not None and end < start:
            raise HTTPException(422, "The last month can't be before the first")
        vendor = self.accounts.vendor_in_society(data.get("vendor_id"), society_id)
        r = RecurringExpense(
            society_id=society_id, name=name, expense_account_id=data["expense_account_id"],
            paid_from_id=data.get("paid_from_id"), amount=data.get("amount"),
            day_of_month=data.get("day_of_month") or 1, start_month=start, end_month=end,
            vendor_id=vendor.id if vendor else None,
            payee=vendor.company_name if vendor else ((data.get("payee") or "").strip() or None),
            note=(data.get("note") or "").strip() or None, created_by=user.id)
        self.db.add(r)
        self.db.flush()
        self._audit(AuditAction.CREATE, r, user, request, new_values={"name": name, "amount": str(r.amount)})
        self.db.commit()
        self.db.refresh(r)
        return r

    def update(self, recurring_id: UUID, data: dict, user: User, request=None) -> RecurringExpense:
        r = self.get(recurring_id, user)
        if "name" in data:
            name = (data["name"] or "").strip()
            if not name:
                raise HTTPException(422, "Give the expense a name")
            data["name"] = name
        if data.get("expense_account_id"):
            self._expense_head(r.society_id, data["expense_account_id"])
        if data.get("paid_from_id"):
            self._cash_or_bank(r.society_id, data["paid_from_id"])
        self._check_day(data.get("day_of_month"))
        if data.get("amount") is not None and Decimal(data["amount"]) < 0:
            raise HTTPException(422, "The amount can't be negative")
        if "start_month" in data and data["start_month"]:
            data["start_month"] = first_of(data["start_month"])
        if "end_month" in data and data["end_month"]:
            data["end_month"] = first_of(data["end_month"])
        for key in ("expense_account_id", "name", "day_of_month", "start_month", "is_active"):
            if key in data and data[key] is None:
                data.pop(key)            # these can't be cleared
        if "vendor_id" in data:
            vendor = self.accounts.vendor_in_society(data["vendor_id"], r.society_id)
            if vendor:
                data["payee"] = vendor.company_name      # the vendor's name is the payee
            elif "payee" not in data:
                data["payee"] = None                     # unlinked: no payee left behind
        elif "payee" in data and data["payee"] is not None:
            data["vendor_id"] = None                     # a typed payee replaces the link
        for key, value in data.items():
            setattr(r, key, value)
        if r.end_month is not None and r.end_month < r.start_month:
            raise HTTPException(422, "The last month can't be before the first")
        self._audit(AuditAction.UPDATE, r, user, request, new_values={k: str(v) for k, v in data.items()})
        self.db.commit()
        self.db.refresh(r)
        return r

    def list(self, society_id: UUID) -> List[RecurringExpense]:
        return (self.db.query(RecurringExpense).filter(RecurringExpense.society_id == society_id)
                .order_by(RecurringExpense.is_active.desc(), RecurringExpense.name).all())

    # ── What is due ──────────────────────────────────────────────────────────

    def _decided(self, r: RecurringExpense) -> dict:
        """{month: run} for the months settled: skipped, or recorded with a voucher that still stands."""
        out = {}
        for run in r.runs:
            if run.skipped or (run.voucher is not None and not run.voucher.is_cancelled):
                out[run.month] = run
        return out

    def due_months(self, r: RecurringExpense, today: date) -> List[date]:
        """The months of this template that have come due and are undecided, oldest first."""
        if not r.is_active:
            return []
        last = first_of(today) if r.end_month is None else min(r.end_month, first_of(today))
        first = max(r.start_month, add_month(first_of(today), -LOOKBACK_MONTHS))
        decided = self._decided(r)
        months, m = [], first
        while m <= last:
            if m not in decided and due_date(m, r.day_of_month) <= today:
                months.append(m)
            m = add_month(m)
        return months

    def due(self, society_id: UUID) -> List[dict]:
        today = self._today(society_id)
        rows = []
        for r in self.list(society_id):
            for m in self.due_months(r, today):
                d = due_date(m, r.day_of_month)
                rows.append({"recurring": r, "month": m, "due_date": d, "days_late": (today - d).days})
        rows.sort(key=lambda x: (x["due_date"], x["recurring"].name))
        return rows

    # ── Deciding a month ─────────────────────────────────────────────────────

    def _month_open_for_decision(self, r: RecurringExpense, month: date, today: date) -> date:
        month = first_of(month)
        if month < r.start_month or (r.end_month is not None and month > r.end_month):
            raise HTTPException(422, "That month is outside this expense's period")
        if due_date(month, r.day_of_month) > today:
            raise HTTPException(422, "That month isn't due yet")
        if month in self._decided(r):
            raise HTTPException(409, "That month has already been recorded or skipped")
        return month

    def _clear_stale_run(self, r: RecurringExpense, month: date) -> None:
        """A run whose voucher was cancelled is replaced when the month is decided again."""
        for run in list(r.runs):
            if run.month == month:
                self.db.delete(run)
        self.db.flush()

    def record(self, recurring_id: UUID, data: dict, user: User, request=None):
        r = self.get(recurring_id, user)
        today = self._today(r.society_id)
        month = self._month_open_for_decision(r, data["month"], today)
        amount = data.get("amount") if data.get("amount") is not None else r.amount
        if amount is None or Decimal(amount) <= 0:
            raise HTTPException(422, "Enter the amount for this month")
        paid_from = data.get("paid_from_id") or r.paid_from_id
        if paid_from is None:
            paid_from = self.accounts.system_account(r.society_id, "cash").id
        self._cash_or_bank(r.society_id, paid_from)
        vdate = data.get("voucher_date") or today
        if vdate > today:
            raise HTTPException(422, "The payment date can't be in the future")
        label = f"{r.name} — {calendar.month_name[month.month]} {month.year}"
        narration = " · ".join(x for x in (label, r.payee, (data.get("note") or "").strip() or None) if x)
        # The voucher and the note that this month is settled go in together, or not at all.
        lines = self.accounts._manual_lines(r.society_id, "payment", [
            {"account_id": r.expense_account_id, "debit": amount},
            {"account_id": paid_from, "credit": amount}])
        voucher = self.accounts.build_voucher(r.society_id, "payment", vdate, lines, narration=narration,
                                              reference=(data.get("reference") or None), vendor_id=r.vendor_id,
                                              user=user)
        self._clear_stale_run(r, month)
        run = RecurringExpenseRun(recurring_id=r.id, society_id=r.society_id, month=month,
                                  voucher_id=voucher.id, decided_by=user.id)
        self.db.add(run)
        self._audit(AuditAction.UPDATE, r, user, request,
                    new_values={"recorded": month.isoformat(), "voucher": voucher.voucher_number})
        self.db.commit()
        self.db.refresh(voucher)
        return voucher

    def skip(self, recurring_id: UUID, month: date, reason: Optional[str], user: User, request=None):
        r = self.get(recurring_id, user)
        month = self._month_open_for_decision(r, month, self._today(r.society_id))
        self._clear_stale_run(r, month)
        self.db.add(RecurringExpenseRun(recurring_id=r.id, society_id=r.society_id, month=month, skipped=True,
                                        skip_reason=(reason or "").strip() or None, decided_by=user.id))
        self._audit(AuditAction.UPDATE, r, user, request, new_values={"skipped": month.isoformat()})
        self.db.commit()

    def _audit(self, action, entity, user, request=None, **kw):
        self.accounts._audit(action, entity, user, request, **kw)
