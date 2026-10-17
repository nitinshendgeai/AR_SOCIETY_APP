"""A charge head that bills the ACTUAL expenses of the billing cycle's own period.

"Budget from expenses" in its original (trailing) mode reads the last N months up to the day the bills are made and
annualises them (budget_suggestions.py). The period mode here is different and exact:

1. The pool. The approved expenses dated inside the cycle's period (first to last day, both included) on the expense
   ledgers linked to the head's maintenance element. A voucher counts once, as its debits less credits on those
   ledgers. Left out, and said so on the preview: vouchers still waiting for approval, rejected or cancelled ones,
   reversed ones and their reversals (a void nets to nothing), and anything spent on expense ledgers that no element
   covers (so no head recovers it).
2. The shares. The pool is shared over the flats that are billed in this run, in proportion to their WEIGHT: the flat's
   area for the per-sq-ft and area-budget bases, one for the fixed and equal-budget bases, each multiplied by the share
   of the cycle the flat is charged for (a flat that is billed for half the cycle carries half a weight).
3. The rounding. Every share is rounded down to the paisa and the paise left over go, one each, to the flats with the
   largest fractions, so the shares add up to the pool EXACTLY. A flat's bill line is its share; nothing is rounded
   again.

Nothing is stored here. The calculator uses this for both the preview and the real generation; generation then
writes the working down (BillingExpenseAllocation) in the same transaction as the bills.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.accounts.models.accounts import Account, AccountGroup, Voucher, VoucherEntry
from app.modules.billing.models.billing import (
    BillingCycle, BillingExpenseAllocation, BillStatus, ChargeBasis, MaintenanceBill, MaintenanceChargeConfig,
)

ZERO = Decimal(0)
CENT = Decimal("0.01")

#: The bases a period-mode head may have, and how each shares the pool.
AREA_BASES = {ChargeBasis.PER_SQFT, ChargeBasis.BUDGET_AREA}
EQUAL_BASES = {ChargeBasis.FIXED, ChargeBasis.BUDGET_EQUAL}
PERIOD_BASES = AREA_BASES | EQUAL_BASES

MODE_TRAILING = "trailing"
MODE_PERIOD = "period"
EXPENSE_MODES = (MODE_TRAILING, MODE_PERIOD)


def money(v) -> Decimal:
    return Decimal(v).quantize(CENT, rounding=ROUND_HALF_UP)


def is_period_head(charge: MaintenanceChargeConfig) -> bool:
    return bool(charge.auto_from_expenses and charge.element_id and (charge.expense_mode or MODE_TRAILING) == MODE_PERIOD)


def method_for(basis: Optional[ChargeBasis]) -> str:
    return "area" if (basis or ChargeBasis.FIXED) in AREA_BASES else "equal"


@dataclass
class PoolSource:
    voucher_id: UUID
    voucher_number: str
    voucher_date: date
    account_id: UUID
    ledger_name: str
    amount: Decimal


@dataclass
class PeriodSpend:
    """What the books show for one period."""
    pools: Dict[UUID, List[PoolSource]] = field(default_factory=dict)   # element id -> approved sources
    pending: Dict[UUID, Decimal] = field(default_factory=dict)          # element id -> spend waiting for approval
    unlinked: Dict[str, Decimal] = field(default_factory=dict)          # ledger name -> approved spend no element covers

    def total(self, element_id: UUID) -> Decimal:
        return money(sum((s.amount for s in self.pools.get(element_id, [])), ZERO))


def period_spend(db: Session, society_id: UUID, start: date, end: date) -> PeriodSpend:
    """The expense postings dated start..end, split into what counts (approved, live), what is waiting for approval
    and what no element covers."""
    rows = (
        db.query(Voucher.id, Voucher.voucher_number, Voucher.voucher_date, Voucher.approval_status,
                 Account.id, Account.name, Account.maintenance_element_id,
                 func.coalesce(func.sum(VoucherEntry.debit), 0) - func.coalesce(func.sum(VoucherEntry.credit), 0))
        .join(VoucherEntry, VoucherEntry.voucher_id == Voucher.id)
        .join(Account, Account.id == VoucherEntry.account_id)
        .join(AccountGroup, AccountGroup.id == Account.group_id)
        .filter(Voucher.society_id == society_id, Account.society_id == society_id, AccountGroup.nature == "expense",
                Voucher.is_cancelled == False,  # noqa: E712
                Voucher.reversed_at.is_(None), Voucher.reversal_of_id.is_(None),
                Voucher.voucher_date >= start, Voucher.voucher_date <= end)
        .group_by(Voucher.id, Voucher.voucher_number, Voucher.voucher_date, Voucher.approval_status,
                  Account.id, Account.name, Account.maintenance_element_id)
        .order_by(Voucher.voucher_date, Voucher.voucher_number)
        .all()
    )
    out = PeriodSpend()
    for vid, number, vdate, status, acc_id, acc_name, element_id, net in rows:
        net = money(net or 0)
        if net == 0:
            continue
        if status == "pending":
            if element_id is not None:
                out.pending[element_id] = out.pending.get(element_id, ZERO) + net
            continue
        if status != "approved":
            continue                                            # rejected: not an expense
        if element_id is None:
            out.unlinked[acc_name] = out.unlinked.get(acc_name, ZERO) + net
            continue
        out.pools.setdefault(element_id, []).append(PoolSource(vid, number, vdate, acc_id, acc_name, net))
    out.unlinked = {k: v for k, v in out.unlinked.items() if v > 0}
    return out


def allocate_exact(pool: Decimal, weights: Dict[UUID, Decimal]) -> Dict[UUID, Decimal]:
    """Share `pool` over the keys in proportion to `weights`, to the paisa, so the shares add up to `pool` exactly.
    Each share is rounded down; the paise left over go one each to the largest fractions (ties: the order given)."""
    live = {k: w for k, w in weights.items() if w > 0}
    total_w = sum(live.values(), ZERO)
    if pool <= 0 or total_w <= 0:
        return {}
    pool = money(pool)
    pool_cents = int(pool * 100)
    exact = {k: Decimal(pool_cents) * w / total_w for k, w in live.items()}          # in paise, unrounded
    floors = {k: int(v.to_integral_value(rounding=ROUND_FLOOR)) for k, v in exact.items()}
    left = pool_cents - sum(floors.values())
    order = sorted(live, key=lambda k: -(exact[k] - floors[k]))                      # stable: ties keep input order
    for k in order[:left]:
        floors[k] += 1
    return {k: Decimal(c) / 100 for k, c in floors.items()}


@dataclass
class AllocationResult:
    """One head's shared-out pool for one cycle, as the preview shows it and generation records it."""
    charge: MaintenanceChargeConfig
    element_name: Optional[str]
    method: str
    period_start: date
    period_end: date
    pool: Decimal
    total_weight: Decimal
    rate: Decimal
    sources: List[PoolSource]
    amounts: Dict[UUID, Decimal]              # flat id -> its share
    pending: Decimal = ZERO                   # spend on the element's ledgers still waiting for approval (not included)

    @property
    def allocated(self) -> Decimal:
        return sum(self.amounts.values(), ZERO)

    @property
    def eligible_flats(self) -> int:
        return len(self.amounts)


def overlapping_allocations(db: Session, society_id: UUID, element_id: UUID, start: date, end: date,
                            exclude_cycle_id: UUID) -> List[BillingExpenseAllocation]:
    """Allocations of this element for another cycle whose period overlaps start..end and whose bills still stand
    (a cycle whose bills have all been cancelled no longer holds its period)."""
    candidates = (
        db.query(BillingExpenseAllocation)
        .filter(BillingExpenseAllocation.society_id == society_id, BillingExpenseAllocation.element_id == element_id,
                BillingExpenseAllocation.cycle_id != exclude_cycle_id,
                BillingExpenseAllocation.period_start <= end, BillingExpenseAllocation.period_end >= start)
        .all()
    )
    live = []
    for a in candidates:
        standing = (db.query(MaintenanceBill.id)
                    .filter(MaintenanceBill.cycle_id == a.cycle_id, MaintenanceBill.is_active == True,  # noqa: E712
                            MaintenanceBill.bill_status != BillStatus.CANCELLED).first())
        if standing is not None:
            live.append(a)
    return live


def cycle_label(db: Session, cycle_id: UUID) -> str:
    cycle = db.get(BillingCycle, cycle_id)
    return f"“{cycle.name}”" if cycle else "another cycle"
