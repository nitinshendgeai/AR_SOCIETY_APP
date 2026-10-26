"""
MaintenanceCalculator — turns a society's charge heads and rules into
per-flat bill lines. Used for both the preview and actual generation, so
the two can never disagree.

How each piece is worked out (Maharashtra model bye-laws 13(c), 65-71,
as amended by the MCS (Amendment) Rules 2026; the same building blocks
cover RWAs elsewhere):

- Charge heads (see ChargeBasis): fixed per flat, ₹/sq ft, % p.a. of the
  flat's construction cost (sinking fund 0.25%, repair fund 0.75%), an
  annual budget split equally or by area, or per allotted parking slot.
  Every monthly rate is multiplied by the number of months the cycle
  covers (quarterly = 3, etc).
- Non-occupancy: flats let out to tenants pay X% (max 10%) of the
  service-charge heads only.
- GST (when the society is registered): 18% on every GST-applicable line,
  but only once the flat's monthly contribution exceeds ₹7,500 — and then
  on the whole amount, not just the excess.
- Budget from expenses: a charge head can take its amount from what was
  actually spent on the expense ledgers linked to its element instead of its
  typed amount - either as a trailing, annualised average (budget_suggestions.py)
  or, in period mode, as the approved expenses of the cycle's own period shared
  out exactly over the flats billed (period_expenses.py).
- Fines and additional charges on one flat (FlatCharge): every active one
  goes on the flat's bill — fines as non-interest-bearing penalty lines,
  additional charges as their own lines.
- Interest on arrears: simple interest at the society's rate on the
  unpaid principal of earlier issued bills, from their due date (+ grace)
  or from where it was last billed, up to this bill's date.
"""
import calendar
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.flat import Flat, OccupancyStatus
from app.modules.billing.models.billing import (
    BillingCycle, BillStatus, ChargeBasis, ChargeType, CycleFrequency,
    FlatCharge, FlatChargeKind, FlatChargeStatus, InterestWaiver,
    MaintenanceBill, MaintenanceChargeConfig, MaintenanceSettings,
)
from app.modules.billing.services.period_expenses import (
    AREA_BASES, AllocationResult, allocate_exact, is_period_head, method_for, period_spend,
)

CENT = Decimal("0.01")
ZERO = Decimal(0)
# The vehicle kinds that pay a parking head's two-wheeler rate (VehicleType values).
TWO_WHEELER_TYPES = {"motorcycle", "scooter", "bicycle"}
FREQUENCY_MONTHS = {
    CycleFrequency.MONTHLY: 1,
    CycleFrequency.QUARTERLY: 3,
    CycleFrequency.HALF_YEARLY: 6,
    CycleFrequency.YEARLY: 12,
}
INTEREST_BEARING = (BillStatus.ISSUED, BillStatus.PARTIALLY_PAID, BillStatus.OVERDUE)


def money(v) -> Decimal:
    return Decimal(v).quantize(CENT, rounding=ROUND_HALF_UP)


def round_to_rupee(amount) -> Decimal:
    """What to add to `amount` to make it a whole rupee: the nearest, half a rupee up (e.g. 1,234.50 -> +0.50,
    1,234.49 -> -0.49)."""
    amount = Decimal(amount)
    return money(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP) - amount)


def cycle_months(cycle: BillingCycle) -> int:
    months = FREQUENCY_MONTHS.get(cycle.frequency)
    if months:
        return months
    days = (cycle.cycle_end - cycle.cycle_start).days + 1
    return max(1, round(days / 30.44))


def calendar_months(start: date, end: date) -> Decimal:
    """The months from `start` to `end` inclusive, a part of a month by its days: 12 Jan – 31 Jan is 20/31."""
    total, cur = ZERO, start
    while cur <= end:
        days_in_month = calendar.monthrange(cur.year, cur.month)[1]
        month_end = date(cur.year, cur.month, days_in_month)
        last = min(month_end, end)
        total += Decimal((last - cur).days + 1) / Decimal(days_in_month)
        cur = month_end + timedelta(days=1)
    return total.quantize(Decimal("0.000001"))


def months_to_bill(start: date, cycle: BillingCycle) -> Decimal:
    """How many months a flat is charged for when its bill runs from `start` to the end of `cycle`. The cycle's own
    length is `cycle_months` (so a bill that starts with the cycle is charged exactly as before); days before the
    cycle are charged by calendar month, days of the cycle that the flat was not yet there for by the cycle's share."""
    whole = Decimal(cycle_months(cycle))
    if start > cycle.cycle_end:
        return ZERO
    if start >= cycle.cycle_start:
        length = (cycle.cycle_end - cycle.cycle_start).days + 1
        return (whole * Decimal((cycle.cycle_end - start).days + 1) / Decimal(length)).quantize(Decimal("0.000001"))
    return whole + calendar_months(start, cycle.cycle_start - timedelta(days=1))


def default_settings(society_id) -> MaintenanceSettings:
    """Unsaved settings carrying the column defaults (SQLAlchemy only
    applies those on INSERT)."""
    return MaintenanceSettings(
        society_id=society_id, construction_cost_per_sqft=None,
        interest_rate_pct=Decimal(12), interest_grace_days=0,
        non_occupancy_pct=ZERO, gst_enabled=False,
        gst_rate_pct=Decimal(18), gst_threshold_monthly=Decimal(7500), round_to_rupee=False,
    )


@dataclass
class LineDraft:
    charge_type: ChargeType
    description: str
    amount: Decimal
    gst_applicable: bool = False
    is_service: bool = False
    tax_percent: Decimal = ZERO
    tax_amount: Decimal = ZERO
    flat_charge_id: Optional[UUID] = None   # set when the line is a fine / additional charge on this flat
    allocation_charge_id: Optional[UUID] = None   # set when the line is a flat's share of a period-expense pool

    @property
    def total(self) -> Decimal:
        return self.amount + self.tax_amount


def _split_interest(rows: List[dict], total: Decimal) -> List[dict]:
    """Give each earlier bill its share of the interest charged, in whole paise that add up to exactly `total` (the
    largest remainders get the odd paise), so the working on the bill agrees with the Interest line."""
    if not rows or total <= 0:
        return []
    cents = [int((r["raw"] * 100).to_integral_value(rounding=ROUND_FLOOR)) for r in rows]
    short = int(total * 100) - sum(cents)
    order = sorted(range(len(rows)), key=lambda i: rows[i]["raw"] * 100 - cents[i], reverse=True)
    for i in order[:max(short, 0)]:
        cents[i] += 1
    out = []
    for r, c in zip(rows, cents):
        item = {k: v for k, v in r.items() if k != "raw"}
        item["interest"] = str((Decimal(c) / 100).quantize(CENT))
        out.append(item)
    return out


@dataclass
class FlatBillDraft:
    flat: Flat
    period_start: Optional[date] = None      # the days this bill charges for
    period_end: Optional[date] = None
    months: Decimal = Decimal(1)
    lines: List[LineDraft] = field(default_factory=list)
    previous_dues: Decimal = ZERO
    interest_bills: List[MaintenanceBill] = field(default_factory=list)
    interest_adjusted: bool = False          # a waiver changed the interest on this bill
    interest_working: List[dict] = field(default_factory=list)   # interest per earlier bill, printed on the bill
    round_off: Decimal = ZERO                # to the whole rupee, when the society rounds its bills

    @property
    def subtotal(self) -> Decimal:
        return money(sum((l.amount for l in self.lines), ZERO))

    @property
    def tax(self) -> Decimal:
        return money(sum((l.tax_amount for l in self.lines), ZERO))

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.tax + self.round_off


class MaintenanceCalculator:

    def __init__(self, db: Session, society_id: UUID):
        self.db = db
        self.society_id = society_id
        self.settings = db.query(MaintenanceSettings).filter(
            MaintenanceSettings.society_id == society_id).first() or default_settings(society_id)
        self.charges = db.query(MaintenanceChargeConfig).filter(
            MaintenanceChargeConfig.society_id == society_id,
            MaintenanceChargeConfig.is_active == True,
        ).all()
        self.flats = db.query(Flat).filter(
            Flat.wing.has(society_id=society_id), Flat.is_active == True,
        ).all()
        self.total_area = sum((Decimal(str(f.area_sqft)) for f in self.flats if f.area_sqft), ZERO)
        self.parking = self._parking_by_flat()
        self.warnings: List[str] = []
        # Warnings the month-end checklist already shows (as rows with their own fix), so the preview can leave
        # them out of the plain warning list
        self.checklist_warnings: List[str] = []
        self._auto_rate: Dict[UUID, Decimal] = {}
        self.allocations: Dict[UUID, AllocationResult] = {}      # charge id -> its period-expense allocation
        # A partial regenerate leaves the flats whose bills are already issued or paid alone: they are not billed
        # again, and what their bills took of each period-expense head's pool (charge id -> amount) is not shared out
        # again.
        self.skip_flats: set = set()
        self.pool_taken: Dict[UUID, Decimal] = {}
        self.flat_charges = self._flat_charges_by_flat()
        self.waivers = self._waivers_by_flat()

    def _flat_charges_by_flat(self) -> Dict[UUID, List[FlatCharge]]:
        rows = self.db.query(FlatCharge).filter(
            FlatCharge.society_id == self.society_id,
            FlatCharge.status == FlatChargeStatus.ACTIVE,
            FlatCharge.is_active == True,  # noqa: E712
        ).order_by(FlatCharge.effective_date, FlatCharge.created_at).all()
        by_flat: Dict[UUID, List[FlatCharge]] = defaultdict(list)
        for c in rows:
            by_flat[c.flat_id].append(c)
        return by_flat

    def _waivers_by_flat(self) -> Dict[UUID, List[InterestWaiver]]:
        """Each flat's interest concessions, newest first (the newest wins where they overlap)."""
        rows = self.db.query(InterestWaiver).filter(
            InterestWaiver.society_id == self.society_id,
            InterestWaiver.status == "active",
            InterestWaiver.is_active == True,  # noqa: E712
        ).order_by(InterestWaiver.created_at.desc()).all()
        by_flat: Dict[UUID, List[InterestWaiver]] = defaultdict(list)
        for w in rows:
            by_flat[w.flat_id].append(w)
        return by_flat

    def _apply_expense_budgets(self, bill_date: date) -> None:
        """Charge heads set to budget from expenses: work out their rate from
        the linked expense ledgers (heads with no expenses keep the typed amount)."""
        from app.modules.billing.services.budget_suggestions import ExpenseBudgets
        self._auto_rate = {}
        auto = [c for c in self.charges if c.auto_from_expenses and c.element_id and not is_period_head(c)]
        for months in sorted({c.expense_months or 12 for c in auto}):
            budgets = ExpenseBudgets(self.db, self.society_id, months, bill_date)
            for c in (c for c in auto if (c.expense_months or 12) == months):
                rate = budgets.rate_for(c, len(self.flats), self.total_area)
                if rate is None:
                    self.warnings.append(
                        f"{c.name}: no expenses are recorded on its linked expense ledgers in the last "
                        f"{months} month(s) — billed at the typed amount.")
                else:
                    self._auto_rate[c.id] = rate

    def _checklist_note(self, message: str) -> None:
        self.warnings.append(message)
        self.checklist_warnings.append(message)

    def _apply_period_allocations(self, cycle: BillingCycle,
                                  periods: Dict[UUID, Tuple[date, date, Decimal]]) -> None:
        """Period-mode heads: share each head's pool of approved expenses (dated inside the cycle) over the flats that
        are billed in this run. A flat's weight is its area (area bases) or one (equal bases), times the share of the
        cycle it is billed for. A head with nothing spent in the period puts no line on any bill."""
        self.allocations = {}
        heads = [c for c in self.charges if is_period_head(c)]
        if not heads:
            return
        spend = period_spend(self.db, self.society_id, cycle.cycle_start, cycle.cycle_end)
        whole = Decimal(cycle_months(cycle))
        for charge in heads:
            area_based = (charge.basis or ChargeBasis.FIXED) in AREA_BASES
            sources = spend.pools.get(charge.element_id, [])
            spent = spend.total(charge.element_id)
            taken = self.pool_taken.get(charge.id, ZERO)
            pool = spent - taken
            weights: Dict[UUID, Decimal] = {}
            no_area = 0
            for flat in self.flats:
                period = periods.get(flat.id)
                if flat.id in self.skip_flats:
                    continue
                if period is None:
                    continue
                share = min(Decimal(1), period[2] / whole) if whole else Decimal(1)
                if area_based:
                    area = Decimal(str(flat.area_sqft)) if flat.area_sqft else ZERO
                    if area <= 0:
                        no_area += 1
                    weights[flat.id] = area * share
                else:
                    weights[flat.id] = share
            pending = spend.pending.get(charge.element_id, ZERO)
            label = f"{charge.name}: "
            window = f"{cycle.cycle_start:%d %b %Y} – {cycle.cycle_end:%d %b %Y}"
            if pending > 0:
                self._checklist_note(
                    f"{label}₹{pending:,.2f} of expenses in {window} are still waiting for approval and are not "
                    f"included — approve them first if they should be billed.")
            if no_area:
                self.warnings.append(f"{label}{no_area} flat(s) have no area set and carry none of this head.")
            if taken > 0 and pool <= 0:
                self._checklist_note(
                    f"{label}the approved expenses in {window} (₹{spent:,.2f}) are already covered by bills that were "
                    f"issued (₹{taken:,.2f}) — nothing more is billed for this head.")
                continue
            if pool <= 0:
                self._checklist_note(
                    f"{label}no approved expenses are recorded on its linked expense ledgers in {window} — "
                    f"nothing is billed for this head.")
                continue
            if taken > 0:
                self._checklist_note(
                    f"{label}₹{taken:,.2f} of the ₹{spent:,.2f} spent in {window} is already on bills that were "
                    f"issued; the other ₹{pool:,.2f} is shared over the flats being billed now.")
            amounts = allocate_exact(pool, weights)
            total_weight = sum((w for w in weights.values() if w > 0), ZERO)
            if not amounts:
                self.warnings.append(f"{label}there is no flat to share ₹{pool:,.2f} over — nothing is billed.")
                continue
            self.allocations[charge.id] = AllocationResult(
                charge=charge, element_name=charge.element.name if charge.element else None,
                method=method_for(charge.basis), period_start=cycle.cycle_start, period_end=cycle.cycle_end,
                pool=pool, total_weight=total_weight, rate=pool / total_weight, sources=list(sources),
                amounts=amounts, pending=pending)
        if spend.unlinked:
            names = ", ".join(f"{n} (₹{v:,.2f})" for n, v in sorted(spend.unlinked.items()))
            self._checklist_note(
                f"Approved expenses in the period on ledgers no maintenance element covers are not recovered by any "
                f"charge head: {names}.")

    def _parking_by_flat(self) -> Dict[UUID, List[Tuple[Optional[int], bool]]]:
        """The slots each flat holds today, as (the slot's own monthly charge, held for a two-wheeler). A charge of
        None means the charge head's rate applies. A slot whose allotment hasn't begun or whose end date has passed
        isn't billed, even before the sweep that marks it expired has run. A slot is a two-wheeler's when the
        vehicle it was allotted to is a motorcycle, scooter or bicycle; with no vehicle on it, it is a car's."""
        from app.modules.parking.models.parking import ParkingAllocation, AllocationStatus
        today = date.today()
        rows = self.db.query(ParkingAllocation).options(joinedload(ParkingAllocation.vehicle)).filter(
            ParkingAllocation.society_id == self.society_id,
            ParkingAllocation.status == AllocationStatus.ACTIVE,
            ParkingAllocation.flat_id.isnot(None),
            ParkingAllocation.is_active == True,
            ParkingAllocation.start_date <= today,
            or_(ParkingAllocation.end_date.is_(None), ParkingAllocation.end_date >= today),
        ).all()
        by_flat: Dict[UUID, List[Tuple[Optional[int], bool]]] = defaultdict(list)
        for a in rows:
            vtype = getattr(a.vehicle.vehicle_type, "value", a.vehicle.vehicle_type) if a.vehicle else None
            by_flat[a.flat_id].append((a.monthly_charge, vtype in TWO_WHEELER_TYPES))
        return by_flat

    def _open_bills_by_flat(self, exclude_cycle_id: UUID) -> Dict[UUID, List[MaintenanceBill]]:
        rows = self.db.query(MaintenanceBill).filter(
            MaintenanceBill.society_id == self.society_id,
            MaintenanceBill.is_active == True,
            MaintenanceBill.cycle_id != exclude_cycle_id,
            MaintenanceBill.bill_status.in_(INTEREST_BEARING),
            MaintenanceBill.outstanding > 0,
        ).all()
        by_flat: Dict[UUID, List[MaintenanceBill]] = defaultdict(list)
        for b in rows:
            by_flat[b.flat_id].append(b)
        return by_flat

    def _billed_through(self, exclude_cycle_id: UUID) -> Dict[UUID, date]:
        """For each flat, the last day any of its (not cancelled) bills charged for."""
        rows = self.db.query(MaintenanceBill.flat_id, MaintenanceBill.period_end, BillingCycle.cycle_end).join(
            BillingCycle, BillingCycle.id == MaintenanceBill.cycle_id).filter(
            MaintenanceBill.society_id == self.society_id,
            MaintenanceBill.is_active == True,
            MaintenanceBill.bill_status != BillStatus.CANCELLED,
            MaintenanceBill.cycle_id != exclude_cycle_id,
        ).all()
        through: Dict[UUID, date] = {}
        for flat_id, period_end, cycle_end in rows:
            end = period_end or cycle_end
            if flat_id not in through or end > through[flat_id]:
                through[flat_id] = end
        return through

    def _period_for(self, flat: Flat, cycle: BillingCycle, through: Dict[UUID, date]) -> Optional[tuple]:
        """(from, to, months) the flat's bill covers, or None when there is nothing to charge it for in this cycle.
        Without a billing start date every flat is charged for the cycle itself."""
        begin = self.settings.billing_start_date
        if begin is None:
            return cycle.cycle_start, cycle.cycle_end, Decimal(cycle_months(cycle))
        if flat.id in through:
            start = through[flat.id] + timedelta(days=1)                 # carry on from the last bill
        else:
            start = max(begin, flat.possession_date or begin)             # a first bill: possession, but not before `begin`
        if start > cycle.cycle_end:
            return None
        months = months_to_bill(start, cycle)
        return (start, cycle.cycle_end, months) if months > 0 else None

    # ── Charge heads ─────────────────────────────────────────────────────────

    def _charge_lines(self, charge: MaintenanceChargeConfig, flat: Flat, months: Decimal) -> List[Tuple[str, Decimal]]:
        """The (description, amount) lines a charge head puts on a flat's bill: one, except that a parking head with
        a two-wheeler rate bills a flat's cars and two-wheelers on lines of their own. A period-expense head bills the
        flat's exact share of its pool (nothing when the flat carries none)."""
        if is_period_head(charge):
            alloc = self.allocations.get(charge.id)
            return [(charge.name, alloc.amounts.get(flat.id, ZERO))] if alloc else []
        if (charge.basis == ChargeBasis.PARKING and charge.two_wheeler_rate is not None
                and any(is_tw for _own, is_tw in self.parking.get(flat.id, []))):
            cars, two_wheelers = self._parking_split(charge, flat)
            return [(f"{charge.name} — cars", money(cars * months)),
                    (f"{charge.name} — two-wheelers", money(two_wheelers * months))]
        return [(charge.name, money(self._charge_amount(charge, flat, months)))]

    def _charge_amount(self, charge: MaintenanceChargeConfig, flat: Flat, months: Decimal) -> Decimal:
        rate = self._auto_rate.get(charge.id, charge.default_amount or ZERO)
        area = Decimal(str(flat.area_sqft)) if flat.area_sqft else ZERO
        basis = charge.basis or ChargeBasis.FIXED

        if basis == ChargeBasis.FIXED:
            return rate * months
        if basis == ChargeBasis.PER_SQFT:
            return rate * area * months
        if basis == ChargeBasis.CONSTRUCTION_COST_PCT:
            cost = self.settings.construction_cost_per_sqft
            if not cost:
                return ZERO
            return area * cost * rate / 100 / 12 * months
        if basis == ChargeBasis.BUDGET_EQUAL:
            return rate / len(self.flats) / 12 * months if self.flats else ZERO
        if basis == ChargeBasis.BUDGET_AREA:
            return rate * area / self.total_area / 12 * months if self.total_area else ZERO
        if basis == ChargeBasis.PARKING:
            cars, two_wheelers = self._parking_split(charge, flat)
            return (cars + two_wheelers) * months
        return ZERO

    def _parking_split(self, charge: MaintenanceChargeConfig, flat: Flat) -> Tuple[Decimal, Decimal]:
        """A flat's parking per month, as (cars, two-wheelers). A slot's own charge wins; otherwise a two-wheeler
        pays the head's two-wheeler rate when it has one, and every other slot the head's rate."""
        rate = self._auto_rate.get(charge.id, charge.default_amount or ZERO)
        tw_rate = charge.two_wheeler_rate if charge.two_wheeler_rate is not None else rate
        cars = two_wheelers = ZERO
        for own, is_two_wheeler in self.parking.get(flat.id, []):
            amount = Decimal(own) if own is not None else (tw_rate if is_two_wheeler else rate)
            if is_two_wheeler and charge.two_wheeler_rate is not None:
                two_wheelers += amount
            else:
                cars += amount
        return cars, two_wheelers

    def _collect_warnings(self, flats_skipped: int) -> None:
        bases = {c.basis for c in self.charges}
        area_based = bases & {ChargeBasis.PER_SQFT, ChargeBasis.CONSTRUCTION_COST_PCT, ChargeBasis.BUDGET_AREA}
        missing_area = sum(1 for f in self.flats if not f.area_sqft)
        if area_based and missing_area:
            self.warnings.append(
                f"{missing_area} flat(s) have no area set — area-based charges are ₹0 for them.")
        if ChargeBasis.CONSTRUCTION_COST_PCT in bases and not self.settings.construction_cost_per_sqft:
            names = ", ".join(c.name for c in self.charges if c.basis == ChargeBasis.CONSTRUCTION_COST_PCT)
            self.warnings.append(
                f"Set the construction cost per sq ft in Rules — {names} can't be calculated without it.")
        if flats_skipped:
            self.warnings.append(f"{flats_skipped} flat(s) have nothing to bill and will be skipped.")

    # ── Main entry point ─────────────────────────────────────────────────────

    def calculate(self, cycle: BillingCycle, bill_date: date) -> List[FlatBillDraft]:
        s = self.settings
        self._apply_expense_budgets(bill_date)
        open_bills = self._open_bills_by_flat(cycle.id)
        through = self._billed_through(cycle.id) if s.billing_start_date else {}
        drafts: List[FlatBillDraft] = []
        skipped = 0
        catch_up = not_yet = 0

        periods: Dict[UUID, Tuple[date, date, Decimal]] = {}
        for flat in self.flats:
            period = self._period_for(flat, cycle, through)
            if period is not None:
                periods[flat.id] = period
        self._apply_period_allocations(cycle, periods)

        for flat in self.flats:
            if flat.id in self.skip_flats:
                continue
            period = periods.get(flat.id)
            if period is None:
                not_yet += 1
                continue
            start, end, months = period
            if months > Decimal(cycle_months(cycle)):
                catch_up += 1
            draft = FlatBillDraft(flat=flat, period_start=start, period_end=end, months=months)

            for charge in self.charges:
                for description, amount in self._charge_lines(charge, flat, months):
                    if amount <= 0:
                        continue
                    line = LineDraft(
                        charge_type=charge.charge_type, description=description, amount=amount,
                        gst_applicable=charge.gst_applicable, is_service=charge.is_service_charge,
                        allocation_charge_id=charge.id if charge.id in self.allocations else None,
                    )
                    if not s.gst_enabled and charge.tax_percent:
                        line.tax_percent = charge.tax_percent
                        line.tax_amount = money(amount * charge.tax_percent / 100)
                    draft.lines.append(line)

            if s.non_occupancy_pct and flat.occupancy_status == OccupancyStatus.TENANT_OCCUPIED:
                service_total = sum((l.amount for l in draft.lines if l.is_service), ZERO)
                noc = money(service_total * s.non_occupancy_pct / 100)
                if noc > 0:
                    draft.lines.append(LineDraft(
                        charge_type=ChargeType.OTHER,
                        description=f"Non-occupancy charges ({s.non_occupancy_pct.normalize():f}% of service charges)",
                        amount=noc, gst_applicable=True,
                    ))

            for fc in self.flat_charges.get(flat.id, []):
                if self._applies(fc, cycle):
                    is_fine = fc.kind == FlatChargeKind.FINE
                    draft.lines.append(LineDraft(
                        charge_type=ChargeType.PENALTY if is_fine else (fc.charge_type or ChargeType.OTHER),
                        description=f"Fine — {fc.title}" if is_fine else fc.title,
                        amount=money(fc.amount), gst_applicable=bool(fc.gst_applicable) and not is_fine,
                        flat_charge_id=fc.id,
                    ))

            if s.gst_enabled:
                taxable = sum((l.amount for l in draft.lines if l.gst_applicable), ZERO)
                if taxable / months > s.gst_threshold_monthly:
                    for l in draft.lines:
                        if l.gst_applicable:
                            l.tax_percent = s.gst_rate_pct
                            l.tax_amount = money(l.amount * s.gst_rate_pct / 100)

            self._add_arrears(draft, open_bills.get(flat.id, []), bill_date, self.waivers.get(flat.id, []))
            if s.round_to_rupee:
                draft.round_off = round_to_rupee(draft.subtotal + draft.tax)

            if draft.total > 0:
                drafts.append(draft)
            else:
                skipped += 1

        self._collect_warnings(skipped)
        if catch_up:
            self.warnings.append(
                f"{catch_up} flat(s) are charged for more than this cycle — from their possession date or the end of "
                f"their last bill (billing starts on {s.billing_start_date:%d %b %Y}).")
        if not_yet:
            self.warnings.append(
                f"{not_yet} flat(s) are not billed in this cycle: possession is after it, or an earlier bill already "
                f"covers it.")
        return drafts

    @staticmethod
    def _applies(fc: FlatCharge, cycle: BillingCycle) -> bool:
        """A one-off goes on the first bill from its effective date; a recurring
        one on every bill whose cycle falls between its effective and end dates."""
        if fc.effective_date > cycle.cycle_end:
            return False
        if fc.recurring and fc.end_date and fc.end_date < cycle.cycle_start:
            return False
        return True

    def _rate_days(self, start: date, end: date, waivers: List[InterestWaiver]) -> Tuple[Decimal, bool]:
        """Rate-days (the % p.a. summed over each day) for the days start..end-1, with each day at the society's
        rate unless a waiver covers it: no interest for `waive`, the waiver's own rate for `rate`. Also says
        whether any waiver touched these days."""
        base = self.settings.interest_rate_pct
        if not waivers:
            return base * (end - start).days, False
        cuts = {start, end}
        for w in waivers:
            for d in (w.from_date, w.to_date + timedelta(days=1) if w.to_date else None):
                if d is not None and start < d < end:
                    cuts.add(d)
        points = sorted(cuts)
        total, touched = ZERO, False
        for a, b in zip(points, points[1:]):
            rule = next((w for w in waivers if w.covers(a)), None)
            if rule is None:
                rate = base
            else:
                touched = True
                rate = ZERO if rule.mode == "waive" else Decimal(rule.rate_pct or 0)
            total += rate * (b - a).days
        return total, touched

    def _add_arrears(self, draft: FlatBillDraft, earlier: List[MaintenanceBill], bill_date: date,
                     waivers: Optional[List[InterestWaiver]] = None) -> None:
        s = self.settings
        draft.previous_dues = money(sum((b.outstanding for b in earlier), ZERO))
        if not s.interest_rate_pct:
            return
        interest = ZERO
        working: List[dict] = []
        for b in earlier:
            start = b.due_date + timedelta(days=s.interest_grace_days or 0)
            if b.arrears_interest_upto and b.arrears_interest_upto > start:
                start = b.arrears_interest_upto
            days = (bill_date - start).days
            if days <= 0:
                continue
            # Interest is simple: charge it on the unpaid principal only,
            # never on interest billed earlier.
            billed_interest = sum((li.total for li in b.line_items
                                   if li.charge_type == ChargeType.PENALTY), ZERO)
            principal = max(ZERO, b.outstanding - billed_interest)
            if principal <= 0:
                continue
            rate_days, touched = self._rate_days(start, bill_date, waivers or [])
            draft.interest_adjusted = draft.interest_adjusted or touched
            raw = principal * rate_days / 100 / 365
            interest += raw
            draft.interest_bills.append(b)
            working.append({
                "bill": b.invoice_number, "principal": str(money(principal)),
                "from": start.isoformat(), "to": bill_date.isoformat(), "days": days,
                "rate": str((rate_days / days).quantize(Decimal("0.01"))), "raw": raw,
            })
        interest = money(interest)
        draft.interest_working = _split_interest(working, interest)
        if interest > 0:
            draft.lines.append(LineDraft(
                charge_type=ChargeType.PENALTY,
                description=f"Interest on arrears @ {s.interest_rate_pct.normalize():f}% p.a."
                            + (" (adjusted as approved by the committee)" if draft.interest_adjusted else ""),
                amount=interest,
            ))
