"""Suggested charge-head amounts from what the society actually spent.

Maintenance is billed from a budget set in advance (bye-law 67), usually
last year's spend on each head plus an allowance for increases. This works
out that starting point from Vendor Bills: the last N months of invoices,
grouped by the vendor's category, mapped onto the standard maintenance
element each category pays for, annualised, and converted into the unit of
the charge head's basis (annual budget, ₹ per flat per month, ₹ per sq ft
per month). Nothing is changed here — the committee reviews the figures and
applies the ones it wants.
"""
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.flat import Flat
from app.modules.billing.models.billing import ChargeBasis, MaintenanceChargeConfig
from app.modules.billing.services.maintenance_calculator import ZERO, money
from app.modules.vendor.models.vendor import Vendor, VendorInvoice

# Vendor categories whose bills pay for each standard element (by element
# code). Categories not listed here — plumbing and civil repairs (met from the
# repairs fund), IT, "other" — are reported as not linked to a charge head.
EXPENSE_SOURCES: Dict[str, List[str]] = {
    "security":           ["security", "cctv"],
    "housekeeping":       ["housekeeping", "pest_control", "gardening"],
    "lift_maintenance":   ["lift"],
    "common_electricity": ["electrical", "generator"],
    "water_charges":      ["water_supply"],
}

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


def suggest_budgets(db: Session, society_id: UUID, months: int = 12,
                    today: Optional[date] = None) -> dict:
    end = today or date.today()
    start = months_back(end, months)

    rows = (
        db.query(Vendor.category, VendorInvoice.total_amount, VendorInvoice.invoice_date)
        .join(Vendor, Vendor.id == VendorInvoice.vendor_id)
        .filter(VendorInvoice.society_id == society_id,
                VendorInvoice.invoice_date >= start,
                VendorInvoice.invoice_date <= end)
        .all()
    )
    spent: Dict[str, Decimal] = {}
    for category, total, _ in rows:
        key = category.value if hasattr(category, "value") else str(category)
        spent[key] = spent.get(key, ZERO) + Decimal(str(total or 0))

    # A society with only a few months of bills gets those months scaled up
    # to a year, rather than a year's budget built from a partial year.
    first_bill = min((r[2] for r in rows), default=None)
    months_covered = min(months, _months_between(first_bill, end)) if first_bill else 0

    flats = db.query(Flat).filter(Flat.wing.has(society_id=society_id), Flat.is_active == True).all()
    flat_count = len(flats)
    total_area = sum((Decimal(str(f.area_sqft)) for f in flats if f.area_sqft), ZERO)

    charges = (
        db.query(MaintenanceChargeConfig)
        .filter(MaintenanceChargeConfig.society_id == society_id,
                MaintenanceChargeConfig.is_active == True)
        .all()
    )

    suggestions, linked = [], set()
    for charge in charges:
        code = charge.element.code if charge.element else None
        sources = EXPENSE_SOURCES.get(code or "")
        basis = charge.basis or ChargeBasis.FIXED
        if not sources or basis not in SUGGESTIBLE_BASES:
            continue
        linked.update(sources)
        total = sum((spent.get(c, ZERO) for c in sources), ZERO)
        annual = money(total * 12 / months_covered) if months_covered else ZERO

        suggested: Optional[Decimal] = None
        if total > 0:
            if basis in (ChargeBasis.BUDGET_EQUAL, ChargeBasis.BUDGET_AREA):
                suggested = annual
            elif basis == ChargeBasis.FIXED and flat_count:
                suggested = money(annual / flat_count / 12)
            elif basis == ChargeBasis.PER_SQFT and total_area:
                suggested = money(annual / total_area / 12)

        suggestions.append({
            "charge_id": str(charge.id),
            "charge_name": charge.name,
            "basis": basis.value,
            "current_amount": str(charge.default_amount) if charge.default_amount is not None else None,
            "vendor_categories": sources,
            "spent": str(money(total)),
            "annual_estimate": str(annual),
            "suggested_amount": str(suggested) if suggested is not None else None,
        })

    unlinked = [
        {"category": c, "spent": str(money(v))}
        for c, v in sorted(spent.items()) if c not in linked and v > 0
    ]
    return {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "months_covered": months_covered,
        "flat_count": flat_count,
        "total_area": str(total_area),
        "suggestions": suggestions,
        "unlinked": unlinked,
    }
