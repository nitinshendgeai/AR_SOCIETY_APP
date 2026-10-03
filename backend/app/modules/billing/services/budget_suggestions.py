"""Charge-head amounts from what the society actually spent.

Maintenance is billed from a budget set in advance (bye-law 67), usually last
year's spend on each head plus an allowance for increases. Each expense ledger
in the accounts can be linked to the maintenance element it pays for (the
Security Charges ledger to Security, the Lift ledger to Lift Maintenance …);
everything posted to those ledgers — vendor bills, payment vouchers, journals —
is that element's actual cost. This works out the last N months of it,
annualises it, and converts it to the unit of the charge head's basis (annual
budget, ₹ per flat per month, ₹ per sq ft per month).

Two uses:
- `suggest_budgets`: the committee reviews the figures and applies the ones it
  wants. Nothing is changed.
- `ExpenseBudgets` (used by the maintenance calculator): a charge head with
  "budget from expenses" switched on is billed at this figure instead of its
  typed amount.
"""
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.flat import Flat
from app.modules.accounts.models.accounts import Account, AccountGroup, Voucher, VoucherEntry
from app.modules.billing.models.billing import ChargeBasis, MaintenanceChargeConfig
from app.modules.billing.services.maintenance_calculator import ZERO, money

# Bases whose amount follows from spend; % of construction cost and parking
# rates are policy decisions, not expenses to recover.
SUGGESTIBLE_BASES = {ChargeBasis.BUDGET_EQUAL, ChargeBasis.BUDGET_AREA, ChargeBasis.FIXED, ChargeBasis.PER_SQFT}


def months_back(d: date, months: int) -> date:
    """The first day of the month `months - 1` months before `d`'s month, so
    a 12-month window ending in September starts on 1 October last year."""
    index = d.year * 12 + (d.month - 1) - (months - 1)
    return date(index // 12, index % 12 + 1, 1)


def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def _window_spend(db: Session, society_id: UUID, start: date, end: date):
    """Net spend (debits less credits) per linked expense ledger in the
    window, and the date of the earliest posting: ({account: amount}, first)."""
    rows = (
        db.query(Account.id, Account.maintenance_element_id,
                 func.coalesce(func.sum(VoucherEntry.debit), 0) - func.coalesce(func.sum(VoucherEntry.credit), 0),
                 func.min(Voucher.voucher_date))
        .join(VoucherEntry, VoucherEntry.account_id == Account.id)
        .join(Voucher, Voucher.id == VoucherEntry.voucher_id)
        .join(AccountGroup, AccountGroup.id == Account.group_id)
        .filter(Account.society_id == society_id, AccountGroup.nature == "expense",
                Voucher.is_cancelled == False,  # noqa: E712
                Voucher.voucher_date >= start, Voucher.voucher_date <= end)
        .group_by(Account.id, Account.maintenance_element_id)
        .all()
    )
    return rows


def suggested_rate(basis: ChargeBasis, spent: Decimal, months_covered: int,
                   flat_count: int, total_area: Decimal) -> Optional[Decimal]:
    """The charge head's amount in its own unit, from the spend over the months
    covered (annualised); None when there is nothing to go on."""
    if spent <= 0 or not months_covered:
        return None
    annual = money(spent * 12 / months_covered)
    if basis in (ChargeBasis.BUDGET_EQUAL, ChargeBasis.BUDGET_AREA):
        return annual
    if basis == ChargeBasis.FIXED and flat_count:
        return money(annual / flat_count / 12)
    if basis == ChargeBasis.PER_SQFT and total_area:
        return money(annual / total_area / 12)
    return None


class ExpenseBudgets:
    """Spend per maintenance element over a window ending on `end`, read once
    and reused for every charge head."""

    def __init__(self, db: Session, society_id: UUID, months: int, end: date):
        self.start = months_back(end, months)
        self.end = end
        self.months = months
        self.spent: Dict[UUID, Decimal] = {}
        self.heads: Dict[UUID, List[str]] = {}
        self.unlinked: Dict[UUID, Decimal] = {}
        self.names: Dict[UUID, str] = {}
        first: Optional[date] = None
        for account_id, element_id, net, first_on in _window_spend(db, society_id, self.start, end):
            net = Decimal(str(net or 0))
            if element_id is None:
                if net > 0:
                    self.unlinked[account_id] = net
                continue
            self.spent[element_id] = self.spent.get(element_id, ZERO) + net
            self.heads.setdefault(element_id, []).append(account_id)
            first = first_on if first is None or first_on < first else first
        # A society with only a few months of postings gets those months scaled
        # up to a year, rather than a year's budget built from a partial year.
        self.months_covered = min(months, _months_between(first, end)) if first else 0
        if self.unlinked:
            for acc_id, name in db.query(Account.id, Account.name).filter(Account.id.in_(list(self.unlinked))):
                self.names[acc_id] = name
        self.head_names: Dict[UUID, List[str]] = {}
        for element_id, ids in self.heads.items():
            self.head_names[element_id] = [n for _, n in db.query(Account.id, Account.name)
                                           .filter(Account.id.in_(ids)).order_by(Account.sort_order, Account.name)]

    def rate_for(self, charge: MaintenanceChargeConfig, flat_count: int, total_area: Decimal) -> Optional[Decimal]:
        if not charge.element_id or (charge.basis or ChargeBasis.FIXED) not in SUGGESTIBLE_BASES:
            return None
        return suggested_rate(charge.basis or ChargeBasis.FIXED, self.spent.get(charge.element_id, ZERO),
                              self.months_covered, flat_count, total_area)


def society_shape(db: Session, society_id: UUID):
    flats = db.query(Flat).filter(Flat.wing.has(society_id=society_id), Flat.is_active == True).all()  # noqa: E712
    total_area = sum((Decimal(str(f.area_sqft)) for f in flats if f.area_sqft), ZERO)
    return len(flats), total_area


def suggest_budgets(db: Session, society_id: UUID, months: int = 12,
                    today: Optional[date] = None) -> dict:
    end = today or date.today()
    budgets = ExpenseBudgets(db, society_id, months, end)
    flat_count, total_area = society_shape(db, society_id)

    charges = (
        db.query(MaintenanceChargeConfig)
        .filter(MaintenanceChargeConfig.society_id == society_id,
                MaintenanceChargeConfig.is_active == True)  # noqa: E712
        .all()
    )

    suggestions = []
    for charge in charges:
        basis = charge.basis or ChargeBasis.FIXED
        if not charge.element_id or basis not in SUGGESTIBLE_BASES:
            continue
        total = budgets.spent.get(charge.element_id, ZERO)
        annual = money(total * 12 / budgets.months_covered) if budgets.months_covered else ZERO
        suggested = budgets.rate_for(charge, flat_count, total_area)
        suggestions.append({
            "charge_id": str(charge.id),
            "charge_name": charge.name,
            "basis": basis.value,
            "current_amount": str(charge.default_amount) if charge.default_amount is not None else None,
            "expense_heads": budgets.head_names.get(charge.element_id, []),
            "spent": str(money(total)),
            "annual_estimate": str(annual),
            "suggested_amount": str(suggested) if suggested is not None else None,
            "auto_from_expenses": bool(charge.auto_from_expenses),
        })

    unlinked = [
        {"account_id": str(a), "name": budgets.names.get(a, ""), "spent": str(money(v))}
        for a, v in sorted(budgets.unlinked.items(), key=lambda kv: budgets.names.get(kv[0], ""))
    ]
    return {
        "period_start": budgets.start.isoformat(),
        "period_end": end.isoformat(),
        "months_covered": budgets.months_covered,
        "flat_count": flat_count,
        "total_area": str(total_area),
        "suggestions": suggestions,
        "unlinked": unlinked,
    }
