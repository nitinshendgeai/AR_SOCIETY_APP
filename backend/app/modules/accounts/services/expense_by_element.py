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
    """Net spend (debits less credits, so a refund reduces it) per element and per ledger between the two dates,
    cancelled vouchers left out."""
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
