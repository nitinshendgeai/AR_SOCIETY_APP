"""Petty cash, kept as an imprest: a float is drawn from the bank into the Petty Cash ledger, small expenses are
paid out of it against their own expense heads, and when it runs low it is topped up from the bank again.

Everything goes through the books, so nothing here can drift from them:
- a **top-up** is a Contra voucher (debit Petty Cash, credit the bank);
- **daily expenses** are one Payment voucher for the day (debit each expense head, credit Petty Cash), so they follow
  the society's ordinary approval rule and count towards each head's maintenance element like any other expense;
- the **book** (the day-wise petty cash register) is read from the Petty Cash ledger, with the cash counts beside it.

The float, the limit for one expense and the custodian are kept in `petty_cash_settings`; cash counts in
`petty_cash_counts`. A count records a shortage or excess; it posts nothing, because writing it off is a decision.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditAction
from app.models.society import Society
from app.models.user import User
from app.modules.accounts.models.accounts import Account, AccountGroup, Voucher, VoucherEntry
from app.modules.accounts.models.petty_cash import PettyCashCount, PettyCashSetting
from app.modules.accounts.services.accounts_service import AccountsService, money
from app.utils.local_time import local_today, zone

ZERO = Decimal("0.00")
MAX_ITEMS = 50


def _amt(v) -> str:
    return str(money(v))


def _fmt(d: Optional[date]) -> str:
    return d.strftime("%d-%m-%Y") if d else ""


class PettyCashService:
    def __init__(self, db: Session):
        self.db = db
        self.accounts = AccountsService(db)

    # ── Basics ────────────────────────────────────────────────────────────────

    def today(self, society_id: UUID) -> date:
        society = self.db.query(Society).filter(Society.id == society_id).first()
        return local_today(zone(society.timezone if society else None))

    def account(self, society_id: UUID) -> Account:
        self.accounts.ensure_chart(society_id)
        return self.accounts.system_account(society_id, "petty_cash")

    def settings(self, society_id: UUID) -> Optional[PettyCashSetting]:
        return self.db.query(PettyCashSetting).filter(PettyCashSetting.society_id == society_id).first()

    def balance(self, society_id: UUID, as_of: Optional[date] = None) -> Decimal:
        """What the books say is in the box (approved vouchers only)."""
        acct = self.account(society_id)
        return self.accounts.balances(society_id, as_of).get(acct.id, ZERO)

    def pending_out(self, society_id: UUID) -> Decimal:
        """Petty cash already committed by expenses still waiting for approval."""
        acct = self.account(society_id)
        total = (self.db.query(func.coalesce(func.sum(VoucherEntry.credit), 0))
                 .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
                 .filter(VoucherEntry.account_id == acct.id, Voucher.society_id == society_id,
                         Voucher.is_cancelled == False, Voucher.approval_status == "pending")  # noqa: E712
                 .scalar())
        return money(total)

    # ── Settings ──────────────────────────────────────────────────────────────

    def update_settings(self, society_id: UUID, data: dict, user: User, request=None) -> PettyCashSetting:
        row = self.settings(society_id)
        if row is None:
            row = PettyCashSetting(society_id=society_id)
            self.db.add(row)
        for key in ("float_amount", "expense_limit", "custodian_name"):
            if key in data:
                value = data[key]
                if key == "custodian_name":
                    value = (value or "").strip() or None
                elif value is not None and Decimal(value) < 0:
                    raise HTTPException(422, "An amount can't be negative")
                setattr(row, key, value)
        self.db.flush()
        self.accounts._audit(AuditAction.UPDATE, row, user, request,
                             new_values={"float": str(row.float_amount), "limit": str(row.expense_limit),
                                         "custodian": row.custodian_name})
        self.db.commit()
        self.db.refresh(row)
        return row

    # ── The overview ──────────────────────────────────────────────────────────

    def overview(self, society_id: UUID) -> dict:
        acct = self.account(society_id)
        today = self.today(society_id)
        cfg = self.settings(society_id)
        balance = self.balance(society_id)
        pending = self.pending_out(society_id)
        float_amount = money(cfg.float_amount) if cfg and cfg.float_amount is not None else None
        spent_today, spent_month = self._spent(society_id, acct, today, today), self._spent(
            society_id, acct, today.replace(day=1), today)
        last = (self.db.query(PettyCashCount).filter(PettyCashCount.society_id == society_id)
                .order_by(PettyCashCount.count_date.desc(), PettyCashCount.created_at.desc()).first())
        available = balance - pending
        return {
            "account_id": str(acct.id), "account_name": acct.name,
            "balance": _amt(balance), "pending": _amt(pending), "available": _amt(available),
            "float_amount": _amt(float_amount) if float_amount is not None else None,
            "expense_limit": _amt(cfg.expense_limit) if cfg and cfg.expense_limit is not None else None,
            "custodian_name": cfg.custodian_name if cfg else None,
            "top_up_needed": _amt(max(float_amount - balance, ZERO)) if float_amount is not None else None,
            "spent_today": _amt(spent_today), "spent_month": _amt(spent_month),
            "last_count": self._count_out(last) if last else None,
            "today": today.isoformat(),
        }

    def _spent(self, society_id: UUID, acct: Account, start: date, end: date) -> Decimal:
        total = (self.db.query(func.coalesce(func.sum(VoucherEntry.credit), 0))
                 .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
                 .filter(VoucherEntry.account_id == acct.id, Voucher.society_id == society_id,
                         Voucher.is_cancelled == False, Voucher.approval_status == "approved",  # noqa: E712
                         Voucher.voucher_type == "payment", Voucher.voucher_date >= start, Voucher.voucher_date <= end)
                 .scalar())
        return money(total)

    # ── Money in: topping the float up from the bank ──────────────────────────

    def top_up(self, society_id: UUID, data: dict, user: User, request=None) -> Voucher:
        amount = money(data["amount"])
        if amount <= 0:
            raise HTTPException(422, "Enter the amount to move into petty cash")
        petty = self.account(society_id)
        source_id = data.get("from_account_id")
        source = (self.accounts.get_account(source_id) if source_id else self.accounts.default_bank(society_id))
        if source.society_id != society_id or not source.is_active or not source.is_cash_or_bank:
            raise HTTPException(422, "Take the money from a bank or cash ledger of this society")
        if source.id == petty.id:
            raise HTTPException(422, "Petty cash can't be topped up from itself")
        day = data.get("voucher_date") or self.today(society_id)
        if day > self.today(society_id):
            raise HTTPException(422, "The date can't be in the future")
        note = (data.get("note") or "").strip()
        narration = " · ".join(x for x in (f"Petty cash top-up from {source.name}", note or None) if x)
        return self.accounts.create_manual_voucher({
            "society_id": society_id, "voucher_type": "contra", "voucher_date": day, "narration": narration,
            "reference": data.get("reference"),
            "entries": [{"account_id": petty.id, "debit": amount}, {"account_id": source.id, "credit": amount}],
        }, user, request)

    # ── Money out: the day's expenses ─────────────────────────────────────────

    def spend(self, society_id: UUID, data: dict, user: User, request=None) -> Voucher:
        items = data.get("items") or []
        if not items:
            raise HTTPException(422, "Add at least one expense")
        if len(items) > MAX_ITEMS:
            raise HTTPException(422, f"At most {MAX_ITEMS} expenses at a time")
        day = data.get("voucher_date") or self.today(society_id)
        if day > self.today(society_id):
            raise HTTPException(422, "The date can't be in the future")
        petty = self.account(society_id)
        cfg = self.settings(society_id)
        limit = money(cfg.expense_limit) if cfg and cfg.expense_limit is not None else None

        entries: List[dict] = []
        parts: List[str] = []
        total = ZERO
        for n, item in enumerate(items, 1):
            amount = money(item["amount"])
            if amount <= 0:
                raise HTTPException(422, f"Expense {n}: enter an amount")
            head = self.accounts.get_account(item["expense_account_id"])
            group = self.db.query(AccountGroup).filter(AccountGroup.id == head.group_id).first()
            if head.society_id != society_id or not head.is_active or group is None or group.nature != "expense":
                raise HTTPException(422, f"Expense {n}: choose an expense head of this society")
            if limit is not None and amount > limit:
                raise HTTPException(
                    422, f"Expense {n} ({head.name}) is Rs. {amount}, over the petty cash limit of Rs. {limit} for one "
                         "expense. Pay it with Add Expense from the bank instead.")
            note = (item.get("note") or "").strip()
            entries.append({"account_id": head.id, "debit": amount, "narration": note or None})
            parts.append(f"{head.name} {amount}" + (f" ({note})" if note else ""))
            total += amount
        available = self.balance(society_id) - self.pending_out(society_id)
        if total > available:
            raise HTTPException(
                422, f"Petty cash holds Rs. {max(available, ZERO)} that is free to spend, but these expenses come to "
                     f"Rs. {total}. Top up petty cash from the bank first.")
        entries.append({"account_id": petty.id, "credit": total})
        narration = "Petty cash: " + "; ".join(parts)
        return self.accounts.create_manual_voucher({
            "society_id": society_id, "voucher_type": "payment", "voucher_date": day,
            "narration": narration[:1000], "reference": data.get("reference"), "entries": entries,
        }, user, request)

    # ── Counting the cash ─────────────────────────────────────────────────────

    def count(self, society_id: UUID, data: dict, user: User, request=None) -> PettyCashCount:
        counted = money(data["counted_amount"])
        if counted < 0:
            raise HTTPException(422, "The counted amount can't be negative")
        day = data.get("count_date") or self.today(society_id)
        if day > self.today(society_id):
            raise HTTPException(422, "The date can't be in the future")
        book = self.balance(society_id, day)
        row = PettyCashCount(society_id=society_id, count_date=day, counted_amount=counted, book_balance=book,
                             note=(data.get("note") or "").strip() or None, counted_by=user.id)
        self.db.add(row)
        self.db.flush()
        self.accounts._audit(AuditAction.CREATE, row, user, request,
                             new_values={"date": day.isoformat(), "counted": str(counted), "book": str(book)})
        self.db.commit()
        self.db.refresh(row)
        return row

    def counts(self, society_id: UUID, limit: int = 30) -> List[dict]:
        rows = (self.db.query(PettyCashCount).filter(PettyCashCount.society_id == society_id)
                .order_by(PettyCashCount.count_date.desc(), PettyCashCount.created_at.desc()).limit(limit).all())
        return [self._count_out(r) for r in rows]

    @staticmethod
    def _count_out(r: PettyCashCount) -> dict:
        diff = money(r.counted_amount) - money(r.book_balance)
        return {"id": str(r.id), "date": r.count_date.isoformat(), "counted": _amt(r.counted_amount),
                "book": _amt(r.book_balance), "difference": _amt(diff),
                "state": "tallies" if diff == 0 else ("excess" if diff > 0 else "short"),
                "note": r.note, "counted_by": r.counter.full_name if r.counter else None}

    # ── The petty cash book (a register in the shared shape) ──────────────────

    def book_register(self, society_id: UUID, date_from: Optional[date] = None, date_to: Optional[date] = None) -> dict:
        today = self.today(society_id)
        date_to = date_to or today
        date_from = date_from or date_to.replace(day=1)
        if date_from > date_to:
            raise ValueError("The start date is after the end date")
        acct = self.account(society_id)
        st = self.accounts.ledger_statement(acct.id, date_from, date_to)
        by_day: Dict[date, dict] = {}
        for line in st["lines"]:
            d = by_day.setdefault(line["date"], {"in": ZERO, "out": ZERO, "on": [], "closing": None})
            d["in"] += line["debit"]
            d["out"] += line["credit"]
            if line["credit"]:
                d["on"].append(line["narration"] or line["particulars"])
            elif line["debit"]:
                d["on"].append("Top-up: " + (line["particulars"] or ""))
            d["closing"] = line["balance"]
        counts: Dict[date, PettyCashCount] = {}
        for c in (self.db.query(PettyCashCount)
                  .filter(PettyCashCount.society_id == society_id, PettyCashCount.count_date >= date_from,
                          PettyCashCount.count_date <= date_to).order_by(PettyCashCount.created_at).all()):
            counts[c.count_date] = c                                       # the last count of a day stands
        days = sorted(set(by_day) | set(counts))
        rows, running = [], st["opening"]
        short = excess = ZERO
        for d in days:
            info = by_day.get(d)
            opening = running
            received = info["in"] if info else ZERO
            spent = info["out"] if info else ZERO
            running = opening + received - spent
            count = counts.get(d)
            diff = (money(count.counted_amount) - running) if count else None
            if diff is not None:
                if diff < 0:
                    short += -diff
                elif diff > 0:
                    excess += diff
            rows.append({
                "date": _fmt(d), "opening": _amt(opening), "received": _amt(received) if received else "",
                "spent": _amt(spent) if spent else "", "closing": _amt(running),
                "on": "; ".join(x for x in (info["on"] if info else []) if x),
                "counted": _amt(count.counted_amount) if count else "",
                "difference": ("" if diff is None else ("Tallies" if diff == 0 else _amt(diff)))})
        return {
            "kind": "petty_cash", "title": "Petty Cash Book",
            "subtitle": f"{_fmt(date_from)} to {_fmt(date_to)} · {acct.name}",
            "columns": [
                {"key": "date", "label": "Date", "width": 22, "right": False, "phone": True},
                {"key": "opening", "label": "Opening Rs.", "width": 22, "right": True, "phone": False},
                {"key": "received", "label": "Received Rs.", "width": 22, "right": True, "phone": False},
                {"key": "spent", "label": "Spent Rs.", "width": 22, "right": True, "phone": True},
                {"key": "closing", "label": "Closing Rs.", "width": 22, "right": True, "phone": True},
                {"key": "on", "label": "Spent on", "width": 90, "right": False, "phone": False},
                {"key": "counted", "label": "Counted Rs.", "width": 22, "right": True, "phone": False},
                {"key": "difference", "label": "Count vs books", "width": 24, "right": True, "phone": False}],
            "rows": rows,
            "totals": [{"label": "Opening Rs.", "value": _amt(st["opening"])},
                       {"label": "Received Rs.", "value": _amt(st["total_debit"])},
                       {"label": "Spent Rs.", "value": _amt(st["total_credit"])},
                       {"label": "Closing Rs.", "value": _amt(st["closing"])},
                       {"label": "Counted short Rs.", "value": _amt(short)},
                       {"label": "Counted in excess Rs.", "value": _amt(excess)}],
            "statuses": [], "uses_period": True, "uses_month": False,
        }
