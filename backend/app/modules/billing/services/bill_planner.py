"""A budget planner for the maintenance: list what the society needs (its elements and common areas: Refuse Area, Gym,
Podium, Club house, Office...), each with an amount per month, quarter or year, and see the total for a month, a
quarter and a year, the rate per sq ft for each, and what every flat would pay, by its own area.

Each line is shared out either **by area** (a flat pays its area x the line's amount / the society's total area) or
**equally** (every flat pays the same). The total area is the flats' areas added up, or a figure the caller types: when
that is more than the flats add up to, the flats pay less than the budget and the shortfall is reported. Nothing is
saved; it is arithmetic over the society's flats, with the bill each flat would get from the charge heads as they
stand (the estimate) beside it, to compare.
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.flat import Flat
from app.models.wing import Wing
from app.modules.billing.services.bill_estimate import BillEstimateService, month_bounds
from app.modules.billing.services.maintenance_calculator import money

ZERO = Decimal("0")
PERIOD_MONTHS = {"month": 1, "quarter": 3, "year": 12}        # what an entered amount covers
PERIODS = (("monthly", 1), ("quarterly", 3), ("yearly", 12))   # what the plan reports, in months


def _per(total: Decimal, area: Decimal) -> str:
    return str((Decimal(total) / Decimal(area)).quantize(Decimal("0.01")))


class BillPlannerService:
    def __init__(self, db: Session):
        self.db = db

    def _flats(self, society_id: UUID) -> List[Flat]:
        flats = (self.db.query(Flat).join(Wing, Wing.id == Flat.wing_id)
                 .filter(Wing.society_id == society_id, Flat.is_active == True)  # noqa: E712
                 .all())
        return sorted(flats, key=lambda f: (f.wing.name if f.wing else "", f.flat_number))

    def plan(self, society_id: UUID, lines: List[dict], month: Optional[str], compare: bool, today: date,
             total_area: Optional[Decimal] = None) -> dict:
        with self.db.no_autoflush:
            return self._plan(society_id, lines, month, compare, today, total_area)

    def _plan(self, society_id: UUID, lines: List[dict], month: Optional[str], compare: bool, today: date,
              typed_area: Optional[Decimal]) -> dict:
        flats = self._flats(society_id)
        if not flats:
            raise ValueError("The society has no flats to share the maintenance over")
        n = len(flats)
        areas = {f.id: (Decimal(str(f.area_sqft)) if f.area_sqft else ZERO) for f in flats}
        flats_area = sum(areas.values(), ZERO)
        total_area = Decimal(typed_area) if typed_area else flats_area
        no_area = sum(1 for f in flats if not areas[f.id])
        # each line as an amount a month, exactly (a yearly 3,60,000 is 30,000 a month)
        monthly = [Decimal(l["amount"]) / PERIOD_MONTHS[l.get("period", "month")] for l in lines]
        by_area = [l["split"] == "area" for l in lines]
        area_monthly = sum((m for m, a in zip(monthly, by_area) if a), ZERO)
        equal_monthly = sum((m for m, a in zip(monthly, by_area) if not a), ZERO)
        if area_monthly > 0 and total_area <= 0:
            raise ValueError("No flat has an area recorded, so nothing can be shared by area")
        total_monthly = area_monthly + equal_monthly

        out_lines = []
        for l, m, a in zip(lines, monthly, by_area):
            out_lines.append({
                "name": l["name"], "amount": str(money(Decimal(l["amount"]))), "period": l.get("period", "month"),
                "split": l["split"],
                "rate_per_sqft": str((m / total_area).quantize(Decimal("0.0001"))) if a and total_area else None,
                "per_flat": None if a else str(money(m / n)),
                "by_period": {name: str(money(m * k)) for name, k in PERIODS},
                "rate_by_period": ({name: str((m * k / total_area).quantize(Decimal("0.0001"))) for name, k in PERIODS}
                                   if a and total_area else None),
            })

        current = {}
        if compare:
            start, end = month_bounds(month, today)
            svc = BillEstimateService(self.db)
            element_of = svc._element_names(society_id)
            current = {d.flat.id: d.total for d in svc._run(society_id, start, end, element_of, {}, {})}

        rows = []
        collected = {name: ZERO for name, _ in PERIODS}
        current_total = ZERO
        for f in flats:
            area = areas[f.id]
            per_period = {}
            for name, k in PERIODS:
                shares, flat_total = [], ZERO
                for l, m, a in zip(lines, monthly, by_area):
                    share = (money(m * k * area / total_area) if area and total_area else ZERO) if a \
                        else money(m * k / n)
                    shares.append({"name": l["name"], "amount": str(share)})
                    flat_total += share
                collected[name] += flat_total
                entry = {"total": str(money(flat_total)), "per_sqft": _per(flat_total, area) if area else None,
                         "shares": shares}
                if compare:
                    cur = money(current.get(f.id, ZERO) * k)
                    entry.update({"current": str(cur), "change": str(money(flat_total - cur))})
                per_period[name] = entry
            monthly_entry = per_period["monthly"]
            row = {
                "flat_id": str(f.id),
                "flat_label": f"{f.wing.name if f.wing else ''} / {f.flat_number}".strip(" /"),
                "area_sqft": float(area) if area else None,
                "shares": monthly_entry["shares"], "total": monthly_entry["total"], "per_sqft": monthly_entry["per_sqft"],
                "by_period": per_period,
            }
            if compare:
                current_total += current.get(f.id, ZERO)
                row.update({"current": monthly_entry["current"], "change": monthly_entry["change"]})
            rows.append(row)

        periods = {}
        for name, k in PERIODS:
            total = money(total_monthly * k)
            periods[name] = {
                "total": str(total),
                "rate_per_sqft": _per(area_monthly * k, total_area) if total_area else None,
                "per_flat_equal": str(money(equal_monthly * k / n)),
                "average_per_sqft": _per(total_monthly * k, total_area) if total_area else None,
                "collected": str(money(collected[name])),
                "shortfall": str(money(total - collected[name])),
            }

        notes = ["Rounded to the paisa for each flat, so what the flats add up to can differ from the total by a few paise."]
        if typed_area and abs(typed_area - flats_area) > Decimal("0.5"):
            notes.append(f"You typed a total area of {typed_area:,.0f} sq ft; the flats add up to {flats_area:,.0f} sq ft. "
                         "Each flat pays its own area at the rate for the typed area, so the flats together pay "
                         f"{'less' if typed_area > flats_area else 'more'} than the budget "
                         f"(monthly {periods['monthly']['collected']} against {periods['monthly']['total']}).")
        if no_area and area_monthly > 0:
            notes.append(f"{no_area} flat(s) have no area recorded and would pay nothing for the lines shared by area.")
        if compare:
            notes.append("'Current' is the bill each flat would get from the charge heads as they stand "
                         "(without arrears, interest or fines); quarterly and yearly are that figure x 3 and x 12.")
        return {
            "lines": out_lines, "total": periods["monthly"]["total"], "area_total_sqft": float(total_area),
            "area_source": "typed" if typed_area else "flats", "flats_area_sqft": float(flats_area),
            "flats_count": n, "rate_per_sqft": periods["monthly"]["rate_per_sqft"],
            "per_flat_equal": periods["monthly"]["per_flat_equal"],
            "average_per_sqft": periods["monthly"]["average_per_sqft"],
            "collected": periods["monthly"]["collected"], "periods": periods, "flats": rows,
            "compared": compare, "month_label": month_bounds(month, today)[0].strftime("%B %Y") if compare else None,
            "totals": ({"current": str(money(current_total)), "change": str(money(collected["monthly"] - current_total))}
                       if compare else None),
            "notes": notes,
        }
