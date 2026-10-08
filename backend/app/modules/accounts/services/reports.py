"""
Financial statements of a co-operative housing society for a financial year
(1 April – 31 March), as the statutory audit and the Annual General Meeting
use them, and the year-end closing of the books.

- Trial Balance: every ledger's balance at the year end, before the closing
  entry — debits and credits agree.
- Income & Expenditure Account for the year, with the previous year's
  figures: expenditure on one side, income on the other, the surplus or
  deficit carried to the Balance Sheet.
- Balance Sheet as at 31 March, with the previous year's figures: funds and
  liabilities against assets. Members' dues are split into dues receivable
  (asset) and maintenance received in advance (liability); vendors into
  amounts payable and advances paid. The Income & Expenditure Account shows
  the balance brought forward, the year's surplus or deficit and the
  transfer to the Reserve Fund.
- Receipts & Payments Account: opening cash and bank, what came in and went
  out under each head, closing cash and bank.
- Schedule of Funds: each fund's opening balance, additions, utilisation and
  closing balance.

Closing a year posts a Year-end Closing voucher dated 31 March that moves
every income and expenditure ledger to the Income & Expenditure Account,
carries the chosen share of a surplus to the Reserve Fund (the MCS Act
requires at least a quarter of a society's net surplus to go to it), and
locks the year. Statements of a year are always built from the vouchers
before its own closing entry, so they read the same before and after it.

Report payloads are plain dicts the app and the PDF both render:
  kind "two_sided": sides → sections → rows, one amount per column
  kind "table":     columns, rows of cells
Amounts are strings ("1500.00", negative for a deficit); "" is a blank.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, not_, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditAction
from app.models.society import Society
from app.models.user import User
from app.modules.accounts.models.accounts import (
    Account, AccountGroup, FinancialYearClosing, Voucher, VoucherEntry,
)
from app.modules.accounts.services.accounts_service import (
    CENT, ZERO, AccountsService, Line, fiscal_year, fiscal_year_bounds, fiscal_year_start, money,
    previous_fiscal_year, signed_opening,
)

REPORTS = {
    "trial-balance": "Trial Balance",
    "income-expenditure": "Income & Expenditure Account",
    "balance-sheet": "Balance Sheet",
    "receipts-payments": "Receipts & Payments Account",
    "funds": "Schedule of Funds",
}
DEFAULT_RESERVE_PCT = Decimal("25")


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def long_date(d: date) -> str:
    """'31st March 2027'."""
    return f"{_ordinal(d.day)} {d:%B %Y}"


def _a(v: Decimal) -> str:
    v = money(v)
    return "" if v == 0 else str(v)


class FinancialReports:

    def __init__(self, db: Session, accounts: Optional[AccountsService] = None):
        self.db = db
        self.acc = accounts or AccountsService(db)

    # ── Data helpers ──────────────────────────────────────────────────────────

    def _accounts(self, sid: UUID) -> List[Account]:
        return self.acc.list_accounts(sid, include_inactive=True)

    def _groups(self, sid: UUID) -> List[AccountGroup]:
        return self.acc.list_groups(sid)

    def _sums(self, sid: UUID, *, date_from: Optional[date] = None, date_to: Optional[date] = None,
              skip_closing_from: Optional[date] = None, by=(VoucherEntry.account_id,),
              **filters) -> Dict:
        """Signed (debit-positive) movement per key. `skip_closing_from`:
        leave out Year-end Closing vouchers dated on or after it."""
        q = (self.db.query(*by, func.coalesce(func.sum(VoucherEntry.debit), 0),
                           func.coalesce(func.sum(VoucherEntry.credit), 0))
             .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
             .filter(Voucher.society_id == sid, Voucher.is_cancelled == False, Voucher.approval_status == "approved"))  # noqa: E712
        if date_from:
            q = q.filter(Voucher.voucher_date >= date_from)
        if date_to:
            q = q.filter(Voucher.voucher_date <= date_to)
        if skip_closing_from:
            q = q.filter(not_(and_(Voucher.voucher_type == "closing", Voucher.voucher_date >= skip_closing_from)))
        for column, value in filters.items():
            q = q.filter(getattr(VoucherEntry, column) == value)
        out = {}
        for row in q.group_by(*by).all():
            key = row[0] if len(by) == 1 else tuple(row[:len(by)])
            out[key] = money(row[-2]) - money(row[-1])
        return out

    def _balances(self, sid: UUID, upto: date, skip_closing_from: Optional[date] = None) -> Dict[UUID, Decimal]:
        moves = self._sums(sid, date_to=upto, skip_closing_from=skip_closing_from)
        return {a.id: signed_opening(a) + moves.get(a.id, ZERO) for a in self._accounts(sid)}

    def _year_moves(self, sid: UUID, fy: str, upto: Optional[date] = None) -> Dict[UUID, Decimal]:
        """Each ledger's movement in the year, before its closing entry."""
        start, end = fiscal_year_bounds(fy)
        return self._sums(sid, date_from=start, date_to=min(end, upto) if upto else end, skip_closing_from=start)

    def closing_record(self, sid: UUID, fy: str) -> Optional[FinancialYearClosing]:
        return self.db.query(FinancialYearClosing).filter(
            FinancialYearClosing.society_id == sid, FinancialYearClosing.fiscal_year == fy,
            FinancialYearClosing.reopened_at.is_(None), FinancialYearClosing.is_active == True,  # noqa: E712
        ).first()

    def _income_expense(self, sid: UUID, fy: str, upto: Optional[date] = None) -> Tuple[Decimal, Decimal]:
        moves = self._year_moves(sid, fy, upto)
        income = expense = ZERO
        for a in self._accounts(sid):
            nature = a.group.nature if a.group else None
            if nature == "income":
                income -= moves.get(a.id, ZERO)
            elif nature == "expense":
                expense += moves.get(a.id, ZERO)
        return income, expense

    @staticmethod
    def _as_at(fy: str) -> Tuple[date, bool]:
        """The year end — or today, for the year still running (provisional)."""
        _, end = fiscal_year_bounds(fy)
        today = date.today()
        return (end, False) if end < today else (today, True)

    def _header(self, sid: UUID, key: str, fy: str, heading: str, provisional: bool) -> dict:
        society = self.db.query(Society).filter(Society.id == sid).first()
        return {
            "report": key, "title": REPORTS[key], "heading": heading, "fy": fy,
            "prev_fy": previous_fiscal_year(fy), "provisional": provisional,
            "society_name": society.name if society else "", "notes": [],
        }

    # ── Trial Balance ─────────────────────────────────────────────────────────

    def trial_balance(self, sid: UUID, fy: str) -> dict:
        start, _ = fiscal_year_bounds(fy)
        as_at, provisional = self._as_at(fy)
        bal = self._balances(sid, as_at, skip_closing_from=start)
        accounts = self._accounts(sid)
        rows, total_dr, total_cr = [], ZERO, ZERO
        for g in self._groups(sid):
            members = [(a, bal.get(a.id, ZERO)) for a in accounts if a.group_id == g.id and bal.get(a.id, ZERO)]
            if not members:
                continue
            g_dr = sum((b for _, b in members if b > 0), ZERO)
            g_cr = sum((-b for _, b in members if b < 0), ZERO)
            rows.append({"label": g.name, "level": 0, "bold": True, "cells": [_a(g_dr), _a(g_cr)]})
            for a, b in members:
                rows.append({"label": a.name, "code": a.code, "level": 1, "account_id": str(a.id),
                             "cells": [_a(b) if b > 0 else "", _a(-b) if b < 0 else ""]})
            total_dr += g_dr
            total_cr += g_cr
        out = self._header(sid, "trial-balance", fy,
                           f"Trial Balance as {'on' if provisional else 'at'} {long_date(as_at)}", provisional)
        diff = total_dr - total_cr
        if diff:
            rows.append({"label": "Difference in opening balances", "level": 0, "bold": True,
                         "cells": [_a(-diff) if diff < 0 else "", _a(diff) if diff > 0 else ""]})
            out["notes"].append("The opening balances entered don't agree (debits ≠ credits) — check them in "
                                "the Chart of Accounts.")
        top = max(total_dr, total_cr)
        out.update(kind="table", columns=["Debit (₹)", "Credit (₹)"], rows=rows,
                   totals=[_a(top), _a(top)], balanced=diff == 0)
        if self.closing_record(sid, fy):
            out["notes"].append("Balances before the year-end closing entry.")
        return out

    # ── Income & Expenditure ──────────────────────────────────────────────────

    def income_expenditure(self, sid: UUID, fy: str) -> dict:
        prev = previous_fiscal_year(fy)
        as_at, provisional = self._as_at(fy)
        cur_m, prev_m = self._year_moves(sid, fy, as_at), self._year_moves(sid, prev)
        accounts = self._accounts(sid)

        def side(nature: str, sign: int) -> Tuple[list, List[Decimal]]:
            sections, totals = [], [ZERO, ZERO]
            for g in self._groups(sid):
                if g.nature != nature:
                    continue
                rows = []
                for a in accounts:
                    if a.group_id != g.id:
                        continue
                    vals = [sign * cur_m.get(a.id, ZERO), sign * prev_m.get(a.id, ZERO)]
                    if any(vals):
                        rows.append({"label": a.name, "account_id": str(a.id), "amounts": [_a(v) for v in vals],
                                     "_v": vals})
                if rows:
                    t = [sum((r["_v"][i] for r in rows), ZERO) for i in (0, 1)]
                    totals = [totals[i] + t[i] for i in (0, 1)]
                    sections.append({"title": g.name, "rows": rows, "total": [_a(v) for v in t]})
            return sections, totals

        exp_sections, exp = side("expense", 1)
        inc_sections, inc = side("income", -1)
        surplus = [inc[i] - exp[i] for i in (0, 1)]
        if any(s > 0 for s in surplus):
            exp_sections.append({"title": None, "rows": [{
                "label": "Excess of Income over Expenditure (Surplus) carried to Balance Sheet", "bold": True,
                "amounts": [_a(max(s, ZERO)) for s in surplus]}]})
        if any(s < 0 for s in surplus):
            inc_sections.append({"title": None, "rows": [{
                "label": "Excess of Expenditure over Income (Deficit) carried to Balance Sheet", "bold": True,
                "amounts": [_a(max(-s, ZERO)) for s in surplus]}]})
        totals = [_a(max(inc[i], exp[i])) for i in (0, 1)]
        _, end = fiscal_year_bounds(fy)
        heading = (f"Income & Expenditure Account for the year ended {long_date(end)}" if not provisional
                   else f"Income & Expenditure Account from {long_date(fiscal_year_start(as_at))} "
                        f"to {long_date(as_at)} (provisional)")
        out = self._header(sid, "income-expenditure", fy, heading, provisional)
        out.update(kind="two_sided", columns=[fy, prev], sides=[
            {"title": "Expenditure", "sections": _clean(exp_sections), "total": totals},
            {"title": "Income", "sections": _clean(inc_sections), "total": totals},
        ], result={"label": "Surplus / (Deficit)", "amounts": [_a(s) for s in surplus]}, balanced=True)
        return out

    # ── Balance Sheet ─────────────────────────────────────────────────────────

    def _bs_column(self, sid: UUID, fy: str, as_at: date) -> Dict[str, Decimal]:
        """Every Balance Sheet figure as at `as_at`, keyed so two years line up."""
        start, end = fiscal_year_bounds(fy)
        bal = self._balances(sid, as_at)
        chart = self.acc.ensure_chart(sid)
        dues, creditors, ie = chart["members_dues"], chart["sundry_creditors"], chart["ie_surplus"]

        # Members' dues flat by flat, vendors one by one: what's owed one way
        # and the other is shown on its own side, not netted.
        flats = self._sums(sid, date_to=as_at, by=(VoucherEntry.flat_id,), account_id=dues.id)
        flats[None] = flats.get(None, ZERO) + signed_opening(dues)
        vendors = self._sums(sid, date_to=as_at, by=(VoucherEntry.vendor_id,), account_id=creditors.id)
        vendors[None] = vendors.get(None, ZERO) + signed_opening(creditors)

        income_expense = [a for a in self._accounts(sid) if a.group and a.group.nature in ("income", "expense")]
        unclosed = -sum((bal.get(a.id, ZERO) for a in income_expense), ZERO)   # surplus not yet transferred
        income, expense = self._income_expense(sid, fy, as_at)
        surplus = income - expense
        rec = self.closing_record(sid, fy) if as_at >= end else None
        transfer = money(rec.reserve_transfer) if rec else ZERO
        closing_effect = surplus - transfer if rec else ZERO
        col = {f"acc:{a.id}": (bal.get(a.id, ZERO)) for a in self._accounts(sid)}
        col.update({
            "dues_receivable": sum((v for v in flats.values() if v > 0), ZERO),
            "dues_advance": -sum((v for v in flats.values() if v < 0), ZERO),
            "creditors_payable": -sum((v for v in vendors.values() if v < 0), ZERO),
            "vendor_advances": sum((v for v in vendors.values() if v > 0), ZERO),
            "ie_opening": -bal.get(ie.id, ZERO) - closing_effect,
            "ie_surplus": surplus,
            "ie_transfer": -transfer,
            "ie_earlier": unclosed - (ZERO if rec else surplus),
            "opening_difference": sum((signed_opening(a) for a in self._accounts(sid)), ZERO),
        })
        return col

    def balance_sheet(self, sid: UUID, fy: str) -> dict:
        prev = previous_fiscal_year(fy)
        as_at, provisional = self._as_at(fy)
        _, prev_end = fiscal_year_bounds(prev)
        cols = [self._bs_column(sid, fy, as_at), self._bs_column(sid, prev, prev_end)]
        chart = self.acc.ensure_chart(sid)
        dues, creditors, ie = chart["members_dues"], chart["sundry_creditors"], chart["ie_surplus"]
        accounts = self._accounts(sid)

        def amounts(key: str, sign: int = 1) -> List[Decimal]:
            return [sign * c.get(key, ZERO) for c in cols]

        def row(label: str, vals: List[Decimal], account: Optional[Account] = None, **extra) -> dict:
            r = {"label": label, "amounts": [_a(v) for v in vals], "_v": vals, **extra}
            if account is not None:
                r["account_id"] = str(account.id)
            return r

        def side(nature: str) -> list:
            sections = []
            for g in self._groups(sid):
                if g.nature != nature:
                    continue
                rows = []
                if g.system_key == "ie_account":
                    rows += [
                        row("Balance as per last Balance Sheet", amounts("ie_opening")),
                        row("Add: Surplus / (Less: Deficit) for the year", amounts("ie_surplus")),
                        row("Less: Transferred to Reserve Fund", amounts("ie_transfer")),
                        row("Surplus / (Deficit) of earlier years not yet closed", amounts("ie_earlier")),
                    ]
                for a in accounts:
                    if a.group_id != g.id or a.id == ie.id:
                        continue
                    if a.id == dues.id:
                        rows.append(row(a.name, amounts("dues_receivable"), a))
                    elif a.id == creditors.id:
                        rows.append(row(a.name, amounts("creditors_payable"), a))
                    else:
                        rows.append(row(a.name, amounts(f"acc:{a.id}", 1 if nature == "asset" else -1), a))
                if g.system_key == "current_liabilities":
                    rows.append(row("Maintenance received in advance from members", amounts("dues_advance"),
                                    dues))
                if g.system_key == "current_assets":
                    rows.append(row("Advances paid to vendors", amounts("vendor_advances"), creditors))
                rows = [r for r in rows if any(r["_v"])]
                if rows:
                    t = [sum((r["_v"][i] for r in rows), ZERO) for i in (0, 1)]
                    sections.append({"title": g.name, "rows": rows, "total": [_a(v) for v in t], "_t": t})
            return sections

        liabilities, assets = side("liability"), side("asset")
        diff = amounts("opening_difference")
        if any(d > 0 for d in diff):
            liabilities.append({"title": "Suspense", "rows": [row("Difference in opening balances", diff)],
                                "_t": diff, "total": [_a(v) for v in diff]})
        elif any(d < 0 for d in diff):
            neg = [-d for d in diff]
            assets.append({"title": "Suspense", "rows": [row("Difference in opening balances", neg)],
                           "_t": neg, "total": [_a(v) for v in neg]})
        lt = [sum((s["_t"][i] for s in liabilities), ZERO) for i in (0, 1)]
        at = [sum((s["_t"][i] for s in assets), ZERO) for i in (0, 1)]
        out = self._header(sid, "balance-sheet", fy,
                           f"Balance Sheet as {'on' if provisional else 'at'} {long_date(as_at)}"
                           + (" (provisional)" if provisional else ""), provisional)
        out.update(kind="two_sided", columns=[fy, prev], sides=[
            {"title": "Funds & Liabilities", "sections": _clean(liabilities), "total": [_a(v) for v in lt]},
            {"title": "Property & Assets", "sections": _clean(assets), "total": [_a(v) for v in at]},
        ], balanced=all(abs(lt[i] - at[i]) < CENT for i in (0, 1)))
        if any(diff):
            out["notes"].append("The opening balances entered don't agree — the difference is shown under "
                                "Suspense. Correct them in the Chart of Accounts.")
        if cols[0]["ie_earlier"]:
            out["notes"].append("The books of an earlier year are not closed yet — close them from Year-end "
                                "Closing so the surplus is carried forward year by year.")
        return out

    # ── Receipts & Payments ───────────────────────────────────────────────────

    def receipts_payments(self, sid: UUID, fy: str) -> dict:
        start, end = fiscal_year_bounds(fy)
        as_at, provisional = self._as_at(fy)
        accounts = self._accounts(sid)
        cash = [a for a in accounts if a.is_cash_or_bank]
        cash_ids = {a.id for a in cash}
        opening = self._balances(sid, start - timedelta(days=1))
        closing = self._balances(sid, as_at)

        cash_vouchers = (select(VoucherEntry.voucher_id).join(Voucher, Voucher.id == VoucherEntry.voucher_id)
                         .where(Voucher.society_id == sid, Voucher.is_cancelled == False,  # noqa: E712
                                Voucher.voucher_date >= start, Voucher.voucher_date <= as_at,
                                VoucherEntry.account_id.in_(cash_ids)))
        moves = (self.db.query(VoucherEntry.account_id, func.coalesce(func.sum(VoucherEntry.debit), 0),
                               func.coalesce(func.sum(VoucherEntry.credit), 0))
                 .filter(VoucherEntry.voucher_id.in_(cash_vouchers), VoucherEntry.account_id.not_in(cash_ids))
                 .group_by(VoucherEntry.account_id).all()) if cash_ids else []
        received = {acc: money(cr) for acc, dr, cr in moves if money(cr)}
        paid = {acc: money(dr) for acc, dr, cr in moves if money(dr)}
        chart = self.acc.ensure_chart(sid)
        labels = {  # what the money was, rather than the ledger it passed through
            (chart["members_dues"].id, "in"): "Received from members (maintenance & other charges)",
            (chart["members_dues"].id, "out"): "Refunded to members",
            (chart["sundry_creditors"].id, "out"): "Paid to vendors (against their bills)",
            (chart["sundry_creditors"].id, "in"): "Refunds from vendors",
        }

        def section(title: str, amounts: Dict[UUID, Decimal], way: str) -> dict:
            rows = [{"label": labels.get((a.id, way), a.name), "account_id": str(a.id),
                     "amounts": [_a(amounts[a.id])], "_v": amounts[a.id]} for a in accounts if a.id in amounts]
            t = sum((r["_v"] for r in rows), ZERO)
            return {"title": title, "rows": rows or [{"label": "Nil", "amounts": [""]}], "total": [_a(t)], "_t": t}

        def cash_section(title: str, bal: Dict[UUID, Decimal]) -> dict:
            rows = [{"label": a.name, "account_id": str(a.id), "amounts": [_a(bal.get(a.id, ZERO))]}
                    for a in cash if bal.get(a.id, ZERO)]
            t = sum((bal.get(a.id, ZERO) for a in cash), ZERO)
            return {"title": title, "rows": rows or [{"label": "Nil", "amounts": [""]}],
                    "total": [_a(t)], "_t": t}

        rec_sections = [cash_section("Opening Balances (Cash & Bank)", opening),
                        section("Receipts during the year", received, "in")]
        pay_sections = [section("Payments during the year", paid, "out"),
                        cash_section("Closing Balances (Cash & Bank)", closing)]
        rt = sum((s["_t"] for s in rec_sections), ZERO)
        pt = sum((s["_t"] for s in pay_sections), ZERO)
        heading = (f"Receipts & Payments Account for the year ended {long_date(end)}" if not provisional
                   else f"Receipts & Payments Account from {long_date(start)} to {long_date(as_at)} (provisional)")
        out = self._header(sid, "receipts-payments", fy, heading, provisional)
        out.update(kind="two_sided", columns=[fy], sides=[
            {"title": "Receipts", "sections": _clean(rec_sections), "total": [_a(rt)]},
            {"title": "Payments", "sections": _clean(pay_sections), "total": [_a(pt)]},
        ], balanced=abs(rt - pt) < CENT)
        return out

    # ── Schedule of Funds ─────────────────────────────────────────────────────

    def funds(self, sid: UUID, fy: str) -> dict:
        start, end = fiscal_year_bounds(fy)
        as_at, provisional = self._as_at(fy)
        funds = [a for a in self._accounts(sid) if a.group and a.group.system_key in ("funds", "share_capital")]
        opening = self._balances(sid, start - timedelta(days=1))
        q = (self.db.query(VoucherEntry.account_id, func.coalesce(func.sum(VoucherEntry.debit), 0),
                           func.coalesce(func.sum(VoucherEntry.credit), 0))
             .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
             .filter(Voucher.society_id == sid, Voucher.is_cancelled == False,  # noqa: E712
                     Voucher.voucher_date >= start, Voucher.voucher_date <= as_at)
             .group_by(VoucherEntry.account_id).all())
        moved = {acc: (money(dr), money(cr)) for acc, dr, cr in q}
        rows, totals = [], [ZERO] * 4
        for a in funds:
            dr, cr = moved.get(a.id, (ZERO, ZERO))
            vals = [-opening.get(a.id, ZERO), cr, dr]
            vals.append(vals[0] + cr - dr)
            if not any(vals):
                continue
            totals = [totals[i] + vals[i] for i in range(4)]
            rows.append({"label": a.name, "level": 1, "account_id": str(a.id), "cells": [_a(v) for v in vals]})
        heading = (f"Schedule of Funds for the year ended {long_date(end)}" if not provisional
                   else f"Schedule of Funds from {long_date(start)} to {long_date(as_at)} (provisional)")
        out = self._header(sid, "funds", fy, heading, provisional)
        out.update(kind="table", columns=["Opening (₹)", "Additions (₹)", "Utilised (₹)", "Closing (₹)"],
                   rows=rows, totals=[_a(v) for v in totals], balanced=True)
        return out

    def report(self, sid: UUID, key: str, fy: str) -> dict:
        builders = {
            "trial-balance": self.trial_balance, "income-expenditure": self.income_expenditure,
            "balance-sheet": self.balance_sheet, "receipts-payments": self.receipts_payments,
            "funds": self.funds,
        }
        if key not in builders:
            raise HTTPException(404, "Unknown report")
        fiscal_year_bounds(fy)
        data = builders[key](sid, fy)
        self.db.commit()  # the standard chart, if this was the first visit
        return data

    # ── Financial years & closing ─────────────────────────────────────────────

    def _years_with_vouchers(self, sid: UUID) -> set:
        return {fy for (fy,) in self.db.query(Voucher.fiscal_year).filter(
            Voucher.society_id == sid, Voucher.is_cancelled == False,  # noqa: E712
            Voucher.voucher_type != "closing").distinct()}

    def years(self, sid: UUID) -> List[dict]:
        """Every financial year from the first one with entries to the
        current one, newest first, with its result and whether it can be
        closed (or reopened)."""
        self.acc.ensure_chart(sid)
        current = fiscal_year(date.today())
        with_vouchers = self._years_with_vouchers(sid)
        first = min(with_vouchers | {current})
        closed = self.acc.closed_years(sid)
        records = {r.fiscal_year: r for r in self.db.query(FinancialYearClosing).filter(
            FinancialYearClosing.society_id == sid, FinancialYearClosing.reopened_at.is_(None),
            FinancialYearClosing.is_active == True)}  # noqa: E712
        out, fy = [], first
        while True:
            start, end = fiscal_year_bounds(fy)
            income, expense = self._income_expense(sid, fy)
            earlier_open = sorted(y for y in with_vouchers if y < fy and y not in closed)
            later_closed = [y for y in closed if y > fy]
            if fy in closed:
                can_close, block = False, "Closed"
            elif end >= date.today():
                can_close, block = False, f"The year ends on {long_date(end)}"
            elif earlier_open:
                can_close, block = False, f"Close FY {earlier_open[0]} first"
            else:
                can_close, block = True, None
            rec = records.get(fy)
            out.append({
                "fy": fy, "start": start.isoformat(), "end": end.isoformat(),
                "is_current": fy == current, "is_closed": fy in closed, "has_entries": fy in with_vouchers,
                "income": str(income), "expenditure": str(expense), "surplus": str(income - expense),
                "can_close": can_close, "close_blocked_reason": block,
                "can_reopen": fy in closed and not later_closed,
                "suggested_reserve_pct": str(DEFAULT_RESERVE_PCT if income > expense else Decimal(0)),
                "closed_at": rec.closed_at.isoformat() if rec else None,
                "closed_by_name": rec.closer.full_name if rec and rec.closer else None,
                "reserve_pct": str(rec.reserve_pct) if rec else None,
                "reserve_transfer": str(rec.reserve_transfer) if rec else None,
                "closing_voucher_id": str(rec.closing_voucher_id) if rec and rec.closing_voucher_id else None,
            })
            if fy == current:
                break
            fy = f"{int(fy[:4]) + 1}-{str(int(fy[:4]) + 2)[-2:]}"
        return list(reversed(out))

    def close_year(self, sid: UUID, fy: str, reserve_pct, notes: Optional[str], user: User) -> FinancialYearClosing:
        from app.modules.accounts.services.postings import AccountPostings

        start, end = fiscal_year_bounds(fy)
        if end >= date.today():
            raise HTTPException(409, f"FY {fy} isn't over yet — it ends on {long_date(end)}")
        if fy in self.acc.closed_years(sid):
            raise HTTPException(409, f"The books for FY {fy} are already closed")
        pending = sorted(y for y in self._years_with_vouchers(sid)
                         if y < fy and y not in self.acc.closed_years(sid))
        if pending:
            raise HTTPException(409, f"Close FY {pending[0]} first — years are closed in order")
        pct = Decimal(str(reserve_pct if reserve_pct is not None else 0))
        if pct < 0 or pct > 100:
            raise HTTPException(422, "Reserve Fund share must be between 0 and 100%")

        # Everything billed, received and paid in the year goes in first.
        AccountPostings(self.db, self.acc).sync_society(sid, user)
        self.db.flush()

        moves = self._year_moves(sid, fy)
        accounts = [a for a in self._accounts(sid) if a.group and a.group.nature in ("income", "expense")]
        lines, income, expense = [], ZERO, ZERO
        for a in accounts:
            n = moves.get(a.id, ZERO)
            if not n:
                continue
            if a.group.nature == "income":
                income -= n
            else:
                expense += n
            lines.append(Line(a, debit=-n, narration="Transferred to Income & Expenditure Account") if n < 0
                         else Line(a, credit=n, narration="Transferred to Income & Expenditure Account"))
        surplus = income - expense
        ie = self.acc.system_account(sid, "ie_surplus")
        if surplus > 0:
            lines.append(Line(ie, credit=surplus, narration="Surplus for the year"))
        elif surplus < 0:
            lines.append(Line(ie, debit=-surplus, narration="Deficit for the year"))
        transfer = (surplus * pct / 100).quantize(CENT) if surplus > 0 else ZERO
        if transfer:
            lines += [Line(ie, debit=transfer, narration=f"{pct.normalize():f}% of surplus to Reserve Fund"),
                      Line(self.acc.system_account(sid, "reserve_fund"), credit=transfer,
                           narration=f"{pct.normalize():f}% of surplus for FY {fy}")]
        voucher = None
        if lines:
            voucher = self.acc.build_voucher(
                sid, "closing", end, lines, user=user, reference=f"FY {fy}",
                narration=(f"Closing of the books for FY {fy}: income and expenditure transferred to the "
                           f"Income & Expenditure Account"
                           + (f"; {pct.normalize():f}% of the surplus to the Reserve Fund" if transfer else "")))
        rec = FinancialYearClosing(
            society_id=sid, fiscal_year=fy, year_start=start, year_end=end,
            total_income=income, total_expenditure=expense, surplus=surplus,
            reserve_pct=pct if transfer else Decimal(0), reserve_transfer=transfer,
            closing_voucher_id=voucher.id if voucher else None, notes=notes,
            closed_at=datetime.utcnow(), closed_by=user.id,
        )
        self.db.add(rec)
        self.db.flush()
        self.acc.forget_closed_years(sid)
        self.acc._audit(AuditAction.UPDATE, rec, user, new_values={
            "closed": fy, "surplus": str(surplus), "reserve_transfer": str(transfer)})
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def reopen_year(self, sid: UUID, fy: str, reason: str, user: User) -> FinancialYearClosing:
        fiscal_year_bounds(fy)
        rec = self.closing_record(sid, fy)
        if not rec:
            raise HTTPException(409, f"The books for FY {fy} aren't closed")
        later = sorted(y for y in self.acc.closed_years(sid) if y > fy)
        if later:
            raise HTTPException(409, f"Reopen FY {later[-1]} first — the latest closed year is reopened first")
        rec.reopened_at = datetime.utcnow()
        rec.reopened_by = user.id
        rec.reopen_reason = reason
        if rec.closing_voucher_id:
            voucher = self.db.query(Voucher).filter(Voucher.id == rec.closing_voucher_id).first()
            if voucher and not voucher.is_cancelled:
                self.acc.cancel(voucher, f"FY {fy} reopened: {reason}", user)
        self.acc.forget_closed_years(sid)
        self.acc._audit(AuditAction.UPDATE, rec, user, new_values={"reopened": fy, "reason": reason})
        self.db.commit()
        self.db.refresh(rec)
        return rec


def _clean(sections: Iterable[dict]) -> list:
    """Drop the internal working figures before a payload leaves."""
    out = []
    for s in sections:
        s = {k: v for k, v in s.items() if not k.startswith("_")}
        s["rows"] = [{k: v for k, v in r.items() if not k.startswith("_")} for r in s["rows"]]
        out.append(s)
    return out
