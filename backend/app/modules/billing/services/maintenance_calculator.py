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
  actually spent on the expense ledgers linked to its element (see
  budget_suggestions.py) instead of its typed amount.
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
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.flat import Flat, OccupancyStatus
from app.modules.billing.models.billing import (
    BillingCycle, BillStatus, ChargeBasis, ChargeType, CycleFrequency,
    FlatCharge, FlatChargeKind, FlatChargeStatus,
    MaintenanceBill, MaintenanceChargeConfig, MaintenanceSettings,
)

CENT = Decimal("0.01")
ZERO = Decimal(0)
FREQUENCY_MONTHS = {
    CycleFrequency.MONTHLY: 1,
    CycleFrequency.QUARTERLY: 3,
    CycleFrequency.HALF_YEARLY: 6,
    CycleFrequency.YEARLY: 12,
}
INTEREST_BEARING = (BillStatus.ISSUED, BillStatus.PARTIALLY_PAID, BillStatus.OVERDUE)


def money(v) -> Decimal:
    return Decimal(v).quantize(CENT, rounding=ROUND_HALF_UP)


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
        gst_rate_pct=Decimal(18), gst_threshold_monthly=Decimal(7500),
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

    @property
    def total(self) -> Decimal:
        return self.amount + self.tax_amount


@dataclass
class FlatBillDraft:
    flat: Flat
    period_start: Optional[date] = None      # the days this bill charges for
    period_end: Optional[date] = None
    months: Decimal = Decimal(1)
    lines: List[LineDraft] = field(default_factory=list)
    previous_dues: Decimal = ZERO
    interest_bills: List[MaintenanceBill] = field(default_factory=list)

    @property
    def subtotal(self) -> Decimal:
        return money(sum((l.amount for l in self.lines), ZERO))

    @property
    def tax(self) -> Decimal:
        return money(sum((l.tax_amount for l in self.lines), ZERO))

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.tax


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
        self._auto_rate: Dict[UUID, Decimal] = {}
        self.flat_charges = self._flat_charges_by_flat()

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

    def _apply_expense_budgets(self, bill_date: date) -> None:
        """Charge heads set to budget from expenses: work out their rate from
        the linked expense ledgers (heads with no expenses keep the typed amount)."""
        from app.modules.billing.services.budget_suggestions import ExpenseBudgets
        self._auto_rate = {}
        auto = [c for c in self.charges if c.auto_from_expenses and c.element_id]
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

    def _parking_by_flat(self) -> Dict[UUID, List[Optional[int]]]:
        """The monthly charge of each slot a flat holds today (None: the charge head's rate applies). A slot
        whose allotment hasn't begun or whose end date has passed isn't billed, even before the sweep that
        marks it expired has run."""
        from app.modules.parking.models.parking import ParkingAllocation, AllocationStatus
        today = date.today()
        rows = self.db.query(ParkingAllocation).filter(
            ParkingAllocation.society_id == self.society_id,
            ParkingAllocation.status == AllocationStatus.ACTIVE,
            ParkingAllocation.flat_id.isnot(None),
            ParkingAllocation.is_active == True,
            ParkingAllocation.start_date <= today,
            or_(ParkingAllocation.end_date.is_(None), ParkingAllocation.end_date >= today),
        ).all()
        by_flat: Dict[UUID, List[Optional[int]]] = defaultdict(list)
        for a in rows:
            by_flat[a.flat_id].append(a.monthly_charge)
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
            slots = self.parking.get(flat.id, [])
            return sum((Decimal(c) if c is not None else rate for c in slots), ZERO) * months
        return ZERO

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

        for flat in self.flats:
            period = self._period_for(flat, cycle, through)
            if period is None:
                not_yet += 1
                continue
            start, end, months = period
            if months > Decimal(cycle_months(cycle)):
                catch_up += 1
            draft = FlatBillDraft(flat=flat, period_start=start, period_end=end, months=months)

            for charge in self.charges:
                amount = money(self._charge_amount(charge, flat, months))
                if amount <= 0:
                    continue
                line = LineDraft(
                    charge_type=charge.charge_type, description=charge.name, amount=amount,
                    gst_applicable=charge.gst_applicable, is_service=charge.is_service_charge,
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
                        charge_type=ChargeType.PENALTY if is_fine else ChargeType.OTHER,
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

            self._add_arrears(draft, open_bills.get(flat.id, []), bill_date)

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

    def _add_arrears(self, draft: FlatBillDraft, earlier: List[MaintenanceBill], bill_date: date) -> None:
        s = self.settings
        draft.previous_dues = money(sum((b.outstanding for b in earlier), ZERO))
        if not s.interest_rate_pct:
            return
        interest = ZERO
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
            interest += principal * s.interest_rate_pct / 100 * days / 365
            draft.interest_bills.append(b)
        interest = money(interest)
        if interest > 0:
            draft.lines.append(LineDraft(
                charge_type=ChargeType.PENALTY,
                description=f"Interest on arrears @ {s.interest_rate_pct.normalize():f}% p.a.",
                amount=interest,
            ))
