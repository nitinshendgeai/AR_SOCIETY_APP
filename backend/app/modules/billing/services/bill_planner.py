"""A budget planner for the monthly maintenance: list what the society needs each month (its elements and common
areas: Refuse Area, Gym, Podium, Club house, Office...), and see the total, the rate per sq ft, and what every flat
would pay, by its own area.

Each line is shared out either **by area** (a flat pays its area x the line's amount / the society's total area) or
**equally** (every flat pays the same). Nothing is saved; it is arithmetic over the society's flats, with the bill each
flat would get from the charge heads as they stand (the estimate) beside it, to compare.
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

    def plan(self, society_id: UUID, lines: List[dict], month: Optional[str], compare: bool, today: date) -> dict:
        with self.db.no_autoflush:
            return self._plan(society_id, lines, month, compare, today)

    def _plan(self, society_id: UUID, lines: List[dict], month: Optional[str], compare: bool, today: date) -> dict:
        flats = self._flats(society_id)
        if not flats:
            raise ValueError("The society has no flats to share the maintenance over")
        areas = {f.id: (Decimal(str(f.area_sqft)) if f.area_sqft else ZERO) for f in flats}
        total_area = sum(areas.values(), ZERO)
        no_area = sum(1 for f in flats if not areas[f.id])
        area_amount = sum((Decimal(l["amount"]) for l in lines if l["split"] == "area"), ZERO)
        equal_amount = sum((Decimal(l["amount"]) for l in lines if l["split"] == "equal"), ZERO)
        if area_amount > 0 and total_area <= 0:
            raise ValueError("No flat has an area recorded, so nothing can be shared by area")
        total = area_amount + equal_amount

        out_lines = []
        for l in lines:
            amount = Decimal(l["amount"])
            by_area = l["split"] == "area"
            out_lines.append({
                "name": l["name"], "amount": str(money(amount)), "split": l["split"],
                "rate_per_sqft": (str((amount / total_area).quantize(Decimal("0.0001"))) if by_area and total_area else None),
                "per_flat": None if by_area else str(money(amount / len(flats))),
            })

        current = {}
        if compare:
            start, end = month_bounds(month, today)
            svc = BillEstimateService(self.db)
            element_of = svc._element_names(society_id)
            current = {d.flat.id: d.total for d in svc._run(society_id, start, end, element_of, {}, {})}

        rows, collected, current_total = [], ZERO, ZERO
        for f in flats:
            area = areas[f.id]
            shares = []
            flat_total = ZERO
            for l in lines:
                amount = Decimal(l["amount"])
                share = (money(amount * area / total_area) if area and total_area else ZERO) if l["split"] == "area" \
                    else money(amount / len(flats))
                shares.append({"name": l["name"], "amount": str(share)})
                flat_total += share
            collected += flat_total
            row = {
                "flat_id": str(f.id),
                "flat_label": f"{f.wing.name if f.wing else ''} / {f.flat_number}".strip(" /"),
                "area_sqft": float(area) if area else None,
                "shares": shares, "total": str(money(flat_total)),
                "per_sqft": _per(flat_total, area) if area else None,
            }
            if compare:
                cur = current.get(f.id, ZERO)
                current_total += cur
                row.update({"current": str(money(cur)), "change": str(money(flat_total - cur))})
            rows.append(row)

        notes = ["Rounded to the paisa for each flat, so what the flats add up to can differ from the total by a few paise."]
        if no_area and area_amount > 0:
            notes.append(f"{no_area} flat(s) have no area recorded and would pay nothing for the lines shared by area.")
        if compare:
            notes.append("'Current' is the bill each flat would get from the charge heads as they stand "
                         "(without arrears, interest or fines).")
        return {
            "lines": out_lines, "total": str(money(total)), "area_total_sqft": float(total_area),
            "flats_count": len(flats), "rate_per_sqft": _per(area_amount, total_area) if total_area else None,
            "per_flat_equal": str(money(equal_amount / len(flats))),
            "average_per_sqft": _per(total, total_area) if total_area else None,
            "collected": str(money(collected)), "flats": rows,
            "compared": compare, "month_label": month_bounds(month, today)[0].strftime("%B %Y") if compare else None,
            "totals": ({"current": str(money(current_total)), "change": str(money(collected - current_total))}
                       if compare else None),
            "notes": notes,
        }
