"""What the society spent on each maintenance element in a period.

An expense ledger can "count towards" a maintenance element (Security Charges → Security, Lift Maintenance
→ Lift Maintenance …). Everything posted to such a ledger — payment vouchers, vendor bills, journals — is that
element's spend. This adds it up for a period so the committee can see, element by element, what was spent
this month or this year, which element has had nothing recorded yet, and what was spent on expense ledgers that
no element covers (so it is not in any budget).
"""
from datetime import date
from decimal import Decimal
from typing import Dict, List
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.accounts.models.accounts import Account, AccountGroup, Voucher, VoucherEntry
from app.modules.accounts.services.accounts_service import money
from app.modules.billing.models.billing import MaintenanceElement

ZERO = Decimal("0")


def expenses_by_element(db: Session, society_id: UUID, date_from: date, date_to: date) -> dict:
    """Net spend (debits less credits, so a refund reduces it) per element and per ledger between the two dates.
    Only approved vouchers count — not cancelled ones, ones waiting for approval or rejected — and the year-end
    closing entry, which only moves the year's result to the Income & Expenditure Account, is not a refund."""
    expense_ledgers = (
        db.query(Account)
        .join(AccountGroup, AccountGroup.id == Account.group_id)
        .filter(Account.society_id == society_id, AccountGroup.nature == "expense", Account.is_active == True)  # noqa: E712
        .order_by(Account.sort_order, Account.name)
        .all()
    )
    spent: Dict[UUID, Decimal] = {
        account_id: Decimal(str(net or 0))
        for account_id, net in (
            db.query(VoucherEntry.account_id,
                     func.coalesce(func.sum(VoucherEntry.debit), 0) - func.coalesce(func.sum(VoucherEntry.credit), 0))
            .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
            .filter(Voucher.society_id == society_id, Voucher.is_cancelled == False,  # noqa: E712
                    Voucher.approval_status == "approved", Voucher.voucher_type != "closing",
                    Voucher.voucher_date >= date_from, Voucher.voucher_date <= date_to,
                    VoucherEntry.account_id.in_([a.id for a in expense_ledgers] or [None]))
            .group_by(VoucherEntry.account_id)
        )
    }

    elements = {e.id: e for e in db.query(MaintenanceElement).filter(MaintenanceElement.society_id == society_id).all()}
    by_element: Dict[UUID, dict] = {}
    unlinked: List[dict] = []
    for ledger in expense_ledgers:
        amount = spent.get(ledger.id, ZERO)
        row = {"account_id": str(ledger.id), "name": ledger.name, "amount": str(money(amount))}
        element = elements.get(ledger.maintenance_element_id) if ledger.maintenance_element_id else None
        if element is None:
            if amount != 0:
                unlinked.append(row)          # worth showing only when something was spent
            continue
        bucket = by_element.setdefault(element.id, {
            "element_id": str(element.id), "code": element.code, "name": element.name,
            "total": ZERO, "ledgers": [],
        })
        bucket["total"] += amount
        bucket["ledgers"].append(row)

    rows = sorted(by_element.values(), key=lambda r: (-r["total"], r["name"]))
    linked_total = sum((r["total"] for r in rows), ZERO)
    unlinked_total = sum((Decimal(r["amount"]) for r in unlinked), ZERO)
    for r in rows:
        r["total"] = str(money(r["total"]))
    return {
        "date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
        "total": str(money(linked_total + unlinked_total)),
        "linked_total": str(money(linked_total)), "unlinked_total": str(money(unlinked_total)),
        "elements": rows, "unlinked": unlinked,
    }


def _months_between(start: date, end: date) -> List[date]:
    """The first day of every calendar month from `start`'s to `end`'s."""
    out, cur = [], date(start.year, start.month, 1)
    while cur <= end:
        out.append(cur)
        cur = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
    return out


def element_months(db: Session, society_id: UUID, element_id: str, date_from: date, date_to: date) -> dict:
    """One element's spend month by month between two dates, with the ledgers behind each month: what the books show
    was spent on the element's expense ledgers, the same rule as `expenses_by_element` (net of refunds, approved and
    live vouchers only). `element_id` is an element's id, or "none" for the expense ledgers no element covers. Every
    month in the range is listed, an empty one at zero."""
    ledgers = (
        db.query(Account)
        .join(AccountGroup, AccountGroup.id == Account.group_id)
        .filter(Account.society_id == society_id, AccountGroup.nature == "expense", Account.is_active == True)  # noqa: E712
        .order_by(Account.sort_order, Account.name)
        .all()
    )
    if element_id == "none":
        title = "Not counted towards any element"
        chosen = [a for a in ledgers if a.maintenance_element_id is None]
    else:
        element = db.get(MaintenanceElement, UUID(element_id))
        if element is None or element.society_id != society_id:
            raise ValueError("No such element")
        title = element.name
        chosen = [a for a in ledgers if a.maintenance_element_id == element.id]

    spend: Dict[tuple, Decimal] = {}               # (month's first day, ledger id) -> net spend
    if chosen:
        rows = (
            db.query(Voucher.voucher_date, VoucherEntry.account_id, VoucherEntry.debit, VoucherEntry.credit)
            .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
            .filter(Voucher.society_id == society_id, Voucher.is_cancelled == False,  # noqa: E712
                    Voucher.approval_status == "approved", Voucher.voucher_type != "closing",
                    Voucher.voucher_date >= date_from, Voucher.voucher_date <= date_to,
                    VoucherEntry.account_id.in_([a.id for a in chosen]))
            .all()
        )
        for day, account_id, debit, credit in rows:
            key = (date(day.year, day.month, 1), account_id)
            spend[key] = spend.get(key, ZERO) + Decimal(str(debit or 0)) - Decimal(str(credit or 0))

    months, grand = [], ZERO
    for first in _months_between(date_from, date_to):
        per = [(a, spend.get((first, a.id), ZERO)) for a in chosen]
        total = sum((amount for _, amount in per), ZERO)
        grand += total
        months.append({
            "month": f"{first:%Y-%m}", "label": f"{first:%b %Y}", "total": str(money(total)),
            "ledgers": [{"account_id": str(a.id), "name": a.name, "amount": str(money(amount))}
                        for a, amount in per if amount != 0],
        })
    return {"element_id": element_id, "title": title, "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(), "total": str(money(grand)), "months": months}


def monthly_by_element(db: Session, society_id: UUID, date_from: date, date_to: date) -> dict:
    """Every element's spend month by month in one table, from the books (every approved expense entry: payment
    vouchers, vendor bills, journals, net of refunds — the same rule as `expenses_by_element`), with what the bills
    charged members for the element in the same month beside it. Elements as rows, months as columns; expense ledgers
    no element covers make their own row; totals per month and per element."""
    from app.modules.billing.models.billing import BillStatus, MaintenanceBill, MaintenanceChargeConfig
    firsts = list(_months_between(date_from, date_to))
    index = {f: i for i, f in enumerate(firsts)}
    ledgers = (db.query(Account).join(AccountGroup, AccountGroup.id == Account.group_id)
               .filter(Account.society_id == society_id, AccountGroup.nature == "expense").all())
    element_of = {a.id: a.maintenance_element_id for a in ledgers}
    spent: Dict[object, List[Decimal]] = {}
    if ledgers:
        rows = (db.query(Voucher.voucher_date, VoucherEntry.account_id, VoucherEntry.debit, VoucherEntry.credit)
                .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
                .filter(Voucher.society_id == society_id, Voucher.is_cancelled == False,  # noqa: E712
                        Voucher.approval_status == "approved", Voucher.voucher_type != "closing",
                        Voucher.voucher_date >= date_from, Voucher.voucher_date <= date_to,
                        VoucherEntry.account_id.in_(list(element_of))))
        for day, account_id, debit, credit in rows:
            key = element_of.get(account_id) or "none"
            spent.setdefault(key, [ZERO] * len(firsts))[index[date(day.year, day.month, 1)]] += (
                Decimal(str(debit or 0)) - Decimal(str(credit or 0)))

    # What the bills charged for each element (bill lines carry the charge head's name; the head names its element).
    head_element = {name: el for name, el in db.query(MaintenanceChargeConfig.name, MaintenanceChargeConfig.element_id)
                    .filter(MaintenanceChargeConfig.society_id == society_id, MaintenanceChargeConfig.element_id.isnot(None))}
    billed: Dict[object, List[Decimal]] = {}
    live = (BillStatus.GENERATED, BillStatus.ISSUED, BillStatus.PARTIALLY_PAID, BillStatus.PAID, BillStatus.OVERDUE)
    for b in (db.query(MaintenanceBill).filter(MaintenanceBill.society_id == society_id,
                                               MaintenanceBill.bill_status.in_(live),
                                               MaintenanceBill.bill_date >= date_from,
                                               MaintenanceBill.bill_date <= date_to)):
        i = index[date(b.bill_date.year, b.bill_date.month, 1)]
        for li in b.line_items:
            el = head_element.get(li.description)
            if el is not None:
                billed.setdefault(el, [ZERO] * len(firsts))[i] += Decimal(str(li.amount or 0))

    elements = (db.query(MaintenanceElement).filter(MaintenanceElement.society_id == society_id)
                .order_by(MaintenanceElement.sort_order, MaintenanceElement.name).all())
    out_rows, month_spent, month_billed = [], [ZERO] * len(firsts), [ZERO] * len(firsts)

    def row(key, name, code):
        s = spent.get(key, [ZERO] * len(firsts))
        bl = billed.get(key, [ZERO] * len(firsts))
        for i in range(len(firsts)):
            month_spent[i] += s[i]
            month_billed[i] += bl[i]
        ts, tb = sum(s, ZERO), sum(bl, ZERO)
        return {"element_id": str(key) if key != "none" else "none", "element": name, "code": code,
                "spent": [str(money(v)) for v in s], "billed": [str(money(v)) for v in bl],
                "spent_total": str(money(ts)), "billed_total": str(money(tb)), "difference": str(money(tb - ts)),
                "has_ledger": key == "none" or any(el == key for el in element_of.values())}

    for e in elements:
        r = row(e.id, e.name, e.code)
        if r["has_ledger"] or Decimal(r["spent_total"]) or Decimal(r["billed_total"]):
            out_rows.append(r)
    if spent.get("none"):
        out_rows.append(row("none", "Not counted towards any element", None))
    ts, tb = sum(month_spent, ZERO), sum(month_billed, ZERO)
    return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
            "months": [{"month": f"{f:%Y-%m}", "label": f"{f:%b %Y}"} for f in firsts],
            "rows": out_rows,
            "totals": {"spent": [str(money(v)) for v in month_spent], "billed": [str(money(v)) for v in month_billed],
                       "spent_total": str(money(ts)), "billed_total": str(money(tb)), "difference": str(money(tb - ts))},
            "note": "Spent: every approved expense entry in the books (payments, vendor bills, journals, net of refunds) "
                    "on the ledgers linked to each element. Billed: what the maintenance bills charged members for the "
                    "element. A ledger counts towards an element when it is linked (Accounts Agent → element review)."}
