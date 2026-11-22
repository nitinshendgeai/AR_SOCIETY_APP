"""An estimate of next month's maintenance bill, flat by flat and element by element, with a what-if.

It runs the same calculation as the real bills (`MaintenanceCalculator`), for one month, on a billing cycle that is
never saved, so every charge head, basis (fixed, per sq ft, budget...), flat type, parking slot and GST rule counts the
way it will on the bill. What an estimate leaves out: arrears and interest (they are not part of the month's charges),
fines, and each flat's own billing start date (every flat is taken as billed for the whole month).

What-if: an element can be raised or lowered by a percentage, or set to the monthly total the society wants from it;
the estimate then shows the bill each flat would get and the rate per sq ft, beside the figures as they stand. Nothing
is written: the cycle is never added to the session, no object is changed and nothing is committed.
"""
import calendar
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.flat import Flat
from app.modules.billing.models.billing import (
    BillingCycle, CycleFrequency, FlatChargeKind, MaintenanceChargeConfig, MaintenanceElement,
)
from app.modules.billing.services.maintenance_calculator import MaintenanceCalculator, money

ZERO = Decimal("0")


class _EstimateCalculator(MaintenanceCalculator):
    """The real calculation, for one month, ignoring what the bills themselves would depend on (earlier bills) and
    scaling the elements being tried out."""

    def __init__(self, db: Session, society_id: UUID, element_of: Dict[str, str], factors: Dict[str, Decimal]):
        super().__init__(db, society_id)
        self._element_of = element_of
        self._factors = factors

    def _open_bills_by_flat(self, exclude_cycle_id):
        return {}

    def _billed_through(self, exclude_cycle_id):
        return {}

    def _period_for(self, flat, cycle, through):
        return cycle.cycle_start, cycle.cycle_end, Decimal(1)

    def _add_arrears(self, draft, earlier, bill_date, waivers=None):
        return None

    @staticmethod
    def _applies(fc, cycle):
        return fc.kind != FlatChargeKind.FINE and MaintenanceCalculator._applies(fc, cycle)

    def _charge_lines(self, charge: MaintenanceChargeConfig, flat: Flat, months: Decimal, service_base=None):
        lines = super()._charge_lines(charge, flat, months, service_base)
        factor = self._factors.get(self._element_of.get(charge.name, charge.name))
        return lines if factor is None else [(description, money(amount * factor)) for description, amount in lines]


def month_bounds(month: Optional[str], today: date) -> tuple:
    """(first day, last day) of `month` ("2026-12"); with none, the month after `today`."""
    if month:
        year, mon = (int(x) for x in month.split("-"))
    else:
        year, mon = (today.year + (today.month == 12), today.month % 12 + 1)
    return date(year, mon, 1), date(year, mon, calendar.monthrange(year, mon)[1])


class BillEstimateService:
    def __init__(self, db: Session):
        self.db = db

    def _element_names(self, society_id: UUID) -> Dict[str, str]:
        """{charge head name: the name of the maintenance element it was made from}."""
        rows = (self.db.query(MaintenanceChargeConfig.name, MaintenanceElement.name)
                .join(MaintenanceElement, MaintenanceElement.id == MaintenanceChargeConfig.element_id)
                .filter(MaintenanceChargeConfig.society_id == society_id).all())
        return {head: element for head, element in rows}

    def _run(self, society_id: UUID, start: date, end: date, element_of: Dict[str, str],
             factors: Dict[str, Decimal]) -> list:
        cycle = BillingCycle(id=uuid4(), society_id=society_id, name="Estimate", cycle_start=start, cycle_end=end,
                             due_date=end, frequency=CycleFrequency.MONTHLY)
        calc = _EstimateCalculator(self.db, society_id, element_of, factors)
        return calc.calculate(cycle, start)

    @staticmethod
    def _by_element(draft, element_of: Dict[str, str]) -> Dict[str, Decimal]:
        out: Dict[str, Decimal] = {}
        for line in draft.lines:
            name = element_of.get(line.description, line.description)
            out[name] = out.get(name, ZERO) + line.amount
        return out

    def estimate(self, society_id: UUID, month: Optional[str], adjustments: List[dict], today: date) -> dict:
        with self.db.no_autoflush:                      # nothing the calculation touches is ever written
            return self._estimate(society_id, month, adjustments, today)

    def _estimate(self, society_id: UUID, month: Optional[str], adjustments: List[dict], today: date) -> dict:
        start, end = month_bounds(month, today)
        element_of = self._element_names(society_id)
        base = self._run(society_id, start, end, element_of, {})
        base_totals: Dict[str, Decimal] = {}
        for d in base:
            for name, amount in self._by_element(d, element_of).items():
                base_totals[name] = base_totals.get(name, ZERO) + amount

        factors: Dict[str, Decimal] = {}
        for a in adjustments:
            name = a["element"]
            if a.get("target_total") is not None:
                current = base_totals.get(name, ZERO)
                if current <= 0:
                    raise ValueError(f"{name} has nothing billed in this month to set a total against")
                factors[name] = Decimal(a["target_total"]) / current
            else:
                factors[name] = Decimal(1) + Decimal(a.get("percent") or 0) / Decimal(100)
            if factors[name] < 0:
                raise ValueError(f"{name} can't go below nothing")
        est = self._run(society_id, start, end, element_of, factors) if factors else base

        by_flat_base = {d.flat.id: d for d in base}
        flats, est_totals = [], {}
        total_base = total_est = area_base = area_est = ZERO
        for d in sorted(est, key=lambda d: (d.flat.wing.name if d.flat.wing else "", d.flat.flat_number)):
            b = by_flat_base.get(d.flat.id)
            est_lines = self._by_element(d, element_of)
            base_lines = self._by_element(b, element_of) if b else {}
            for name, amount in est_lines.items():
                est_totals[name] = est_totals.get(name, ZERO) + amount
            area = Decimal(str(d.flat.area_sqft)) if d.flat.area_sqft else ZERO
            cur_total = b.total if b else ZERO
            total_base += cur_total
            total_est += d.total
            if area:
                area_base += area if b else ZERO
                area_est += area
            names = sorted(set(est_lines) | set(base_lines), key=lambda n: (-est_lines.get(n, ZERO), n))
            flats.append({
                "flat_id": str(d.flat.id),
                "flat_label": f"{d.flat.wing.name if d.flat.wing else ''} / {d.flat.flat_number}".strip(" /"),
                "area_sqft": float(area) if area else None,
                "lines": [{"element": n, "current": str(money(base_lines.get(n, ZERO))),
                           "estimate": str(money(est_lines.get(n, ZERO)))} for n in names],
                "tax": str(d.tax), "round_off": str(d.round_off),
                "current_total": str(money(cur_total)), "estimate_total": str(money(d.total)),
                "change": str(money(d.total - cur_total)),
                "current_per_sqft": str(self._per(cur_total, area)) if area else None,
                "estimate_per_sqft": str(self._per(d.total, area)) if area else None,
            })

        elements = []
        for name in sorted(set(base_totals) | set(est_totals), key=lambda n: (-est_totals.get(n, ZERO), n)):
            cur, new = base_totals.get(name, ZERO), est_totals.get(name, ZERO)
            elements.append({
                "element": name, "current_total": str(money(cur)), "estimate_total": str(money(new)),
                "change": str(money(new - cur)),
                "change_pct": str(((new - cur) / cur * 100).quantize(Decimal("0.01"))) if cur else None,
                "current_per_sqft": str(self._per(cur, area_base)) if area_base else None,
                "estimate_per_sqft": str(self._per(new, area_est)) if area_est else None,
                "adjusted": name in factors,
            })
        return {
            "month": f"{start:%Y-%m}", "month_label": f"{start:%B %Y}", "adjusted": bool(factors),
            "flats_count": len(flats), "total_area_sqft": float(area_est),
            "elements": elements, "flats": flats,
            "totals": {
                "current": str(money(total_base)), "estimate": str(money(total_est)),
                "change": str(money(total_est - total_base)),
                "current_per_sqft": str(self._per(total_base, area_base)) if area_base else None,
                "estimate_per_sqft": str(self._per(total_est, area_est)) if area_est else None,
            },
            "notes": ["Arrears, interest and fines are not part of an estimate.",
                      "Heads billed from actual expenses show what the books hold for this month."],
        }

    @staticmethod
    def _per(total: Decimal, area: Decimal) -> Decimal:
        return (Decimal(total) / Decimal(area)).quantize(Decimal("0.01"))
