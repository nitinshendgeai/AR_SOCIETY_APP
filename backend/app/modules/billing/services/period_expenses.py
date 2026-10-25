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
    MaintenanceElement,
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
    unlinked_accounts: Dict[UUID, tuple] = field(default_factory=dict)  # ledger id -> (name, approved spend no element covers)
    pending_vouchers: set = field(default_factory=set)                  # every expense voucher waiting for approval
    pending_total: Decimal = ZERO                                       # ...and what they add up to, on any ledger

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
                Voucher.is_cancelled == False, Voucher.voucher_type != "closing",  # noqa: E712
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
            out.pending_vouchers.add(vid)
            out.pending_total += net
            if element_id is not None:
                out.pending[element_id] = out.pending.get(element_id, ZERO) + net
            continue
        if status != "approved":
            continue                                            # rejected: not an expense
        if element_id is None:
            out.unlinked[acc_name] = out.unlinked.get(acc_name, ZERO) + net
            prev = out.unlinked_accounts.get(acc_id, (acc_name, ZERO))[1]
            out.unlinked_accounts[acc_id] = (acc_name, prev + net)
            continue
        out.pools.setdefault(element_id, []).append(PoolSource(vid, number, vdate, acc_id, acc_name, net))
    out.unlinked = {k: v for k, v in out.unlinked.items() if v > 0}
    out.unlinked_accounts = {k: v for k, v in out.unlinked_accounts.items() if v[1] > 0}
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


def cycle_readiness(db: Session, society_id: UUID, cycle: BillingCycle, charges: List[MaintenanceChargeConfig],
                    allocations: Dict[UUID, AllocationResult]) -> dict:
    """The month-end checklist for a cycle: what in the books would leave the bills short of what was spent. Each
    list is empty when that check is clear. Nothing here blocks generating the bills; it says what to look at first.
    `applies` is false when no head bills actual expenses, so the checklist has nothing to say."""
    period_heads = [c for c in charges if is_period_head(c)]
    out = {"applies": bool(period_heads), "pending_count": 0, "pending_amount": "0.00",
           "unlinked_ledgers": [], "uncovered_elements": [], "heads_without_spend": [], "ready": True}
    if not period_heads:
        return out
    spend = period_spend(db, society_id, cycle.cycle_start, cycle.cycle_end)
    out["pending_count"] = len(spend.pending_vouchers)
    out["pending_amount"] = str(money(spend.pending_total))
    out["unlinked_ledgers"] = [
        {"account_id": str(acc_id), "name": name, "amount": str(money(amount))}
        for acc_id, (name, amount) in sorted(spend.unlinked_accounts.items(), key=lambda kv: kv[1][0])]
    covered = {c.element_id for c in period_heads}
    missing = {eid: spend.total(eid) for eid in spend.pools if eid not in covered and spend.total(eid) > 0}
    if missing:
        names = dict(db.query(MaintenanceElement.id, MaintenanceElement.name)
                     .filter(MaintenanceElement.id.in_(list(missing))).all())
        out["uncovered_elements"] = [
            {"element_id": str(eid), "element_name": names.get(eid, "Element"), "amount": str(amount),
             "has_head": any(c.element_id == eid for c in charges)}
            for eid, amount in sorted(missing.items(), key=lambda kv: names.get(kv[0], ""))]
    out["heads_without_spend"] = [c.name for c in period_heads if c.id not in allocations]
    out["ready"] = not (out["pending_count"] or out["unlinked_ledgers"] or out["uncovered_elements"]
                        or out["heads_without_spend"])
    return out
