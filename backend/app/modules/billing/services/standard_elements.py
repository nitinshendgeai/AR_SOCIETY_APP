"""
Standard maintenance elements a society's master starts with — the charge
heads the Maharashtra model bye-laws (65-71, 13(c)) let a co-operative
housing society levy, each with its customary way of being shared.

Default amounts are set only where the bye-laws fix a rate (sinking and
repair fund); everything else is decided by each society's general body,
so the committee fills it in when creating the charge head.
"""
from decimal import Decimal
from typing import List

from sqlalchemy.orm import Session

from app.modules.billing.models.billing import ChargeBasis, ChargeType, MaintenanceElement

STANDARD_ELEMENTS = [
    # code, name, category, basis, default amount, service charge?, bye-law ref, description
    ("service_charges", "Service Charges", ChargeType.MAINTENANCE, ChargeBasis.FIXED, None, True,
     "Bye-laws 66–67",
     "Office, staff salaries, stationery, audit fees and similar running costs. "
     "Shared equally by all flats irrespective of size."),
    ("property_tax", "Property Tax", ChargeType.OTHER, ChargeBasis.PER_SQFT, None, False,
     "Bye-laws 66–67",
     "Municipal property tax, recovered per flat as levied by the local authority "
     "(on rateable value or area)."),
    ("water_charges", "Water Charges", ChargeType.WATER, ChargeBasis.BUDGET_AREA, None, False,
     "Bye-laws 66–67",
     "Water bill of the society. Bye-laws share it by the number and size of inlets; "
     "by area is the usual approximation."),
    ("common_electricity", "Common Electricity", ChargeType.MAINTENANCE, ChargeBasis.BUDGET_EQUAL, None, True,
     "Bye-laws 66–67",
     "Electricity for common areas — passages, pumps, lights, CCTV. Shared equally."),
    ("repair_fund", "Repairs & Maintenance Fund", ChargeType.REPAIR_FUND,
     ChargeBasis.SERVICE_CHARGE_PCT, Decimal("0.75"), False,
     "Bye-law 67(a)(iii)",
     "0.75% of each flat's monthly service charges, for repairs and maintenance of the buildings. A society that "
     "levies it on construction cost instead (0.75% a year) switches the basis to % of construction cost."),
    ("sinking_fund", "Sinking Fund", ChargeType.SINKING_FUND,
     ChargeBasis.SERVICE_CHARGE_PCT, Decimal("0.25"), False,
     "Bye-laws 13(c), 67(a)(v)",
     "0.25% of each flat's monthly service charges, kept for major structural repairs or reconstruction. The bye-law "
     "minimum is 0.25% a year of the architect-certified construction cost (excluding land); a society that levies "
     "it that way switches the basis to % of construction cost."),
    ("lift_maintenance", "Lift Maintenance", ChargeType.MAINTENANCE, ChargeBasis.BUDGET_EQUAL, None, True,
     "Bye-laws 66–67",
     "Lift running and AMC costs, borne equally by every flat in a building with a lift — "
     "whether or not they use it."),
    ("fire_safety", "Fire Safety", ChargeType.MAINTENANCE, ChargeBasis.BUDGET_EQUAL, None, True,
     "Bye-laws 66–67",
     "Fire-fighting equipment, fire alarm and sprinkler AMC and refilling, usually paid yearly. "
     "Billed as a monthly share: pick the recent 12-month average so the yearly cost is spread over the year."),
    ("pest_control", "Pest Control", ChargeType.MAINTENANCE, ChargeBasis.BUDGET_EQUAL, None, True,
     "Bye-laws 66–67",
     "Pest control AMC / treatments, usually paid yearly or quarterly. Shared equally; "
     "use the recent 12-month average to spread it monthly."),
    ("cctv", "CCTV & Security Systems", ChargeType.MAINTENANCE, ChargeBasis.BUDGET_EQUAL, None, True,
     "Bye-laws 66–67",
     "CCTV, access control and intercom AMC, usually paid yearly. Shared equally; "
     "use the recent 12-month average to spread it monthly."),
    ("security", "Security Services", ChargeType.MAINTENANCE, ChargeBasis.BUDGET_EQUAL, None, True,
     "Bye-laws 66–67", "Security agency charges. Shared equally."),
    ("housekeeping", "Housekeeping", ChargeType.MAINTENANCE, ChargeBasis.BUDGET_EQUAL, None, True,
     "Bye-laws 66–67", "Cleaning and gardening staff. Shared equally."),
    ("parking", "Parking Charges", ChargeType.PARKING, ChargeBasis.PARKING, None, False,
     "Bye-laws 66–67",
     "Per allotted parking slot, at the rate fixed by the general body."),
    ("insurance", "Building Insurance", ChargeType.OTHER, ChargeBasis.BUDGET_AREA, None, False,
     "Bye-laws 66–67", "Insurance premium for the society's buildings."),
    ("lease_rent_na_tax", "Lease Rent / NA Tax", ChargeType.OTHER, ChargeBasis.BUDGET_AREA, None, False,
     "Bye-laws 66–67", "Lease rent and non-agricultural tax payable on the land."),
    ("education_fund", "Education & Training Fund", ChargeType.OTHER, ChargeBasis.BUDGET_EQUAL, None, False,
     "Bye-laws 66–67", "Contribution to the co-operative education and training fund."),
    ("amenities", "Amenities / Clubhouse", ChargeType.AMENITIES, ChargeBasis.FIXED, None, False,
     None, "Clubhouse, gym, pool or other amenity charges."),
]


def seed_standard_elements(db: Session, society_id) -> List[MaintenanceElement]:
    """Create the standard elements a society does not have yet (matched by
    code, so a society seeded earlier gains newly added standard elements
    without touching its existing ones). Caller commits."""
    have = {c for (c,) in db.query(MaintenanceElement.code).filter(MaintenanceElement.society_id == society_id)}
    rows = []
    for order, (code, name, category, basis, amount, service, ref, desc) in enumerate(STANDARD_ELEMENTS):
        if code in have:
            continue
        el = MaintenanceElement(
            society_id=society_id, code=code, name=name, category=category,
            default_basis=basis, default_amount=amount, is_service_charge=service,
            gst_applicable=True, bye_law_ref=ref, description=desc,
            sort_order=(order + 1) * 10, is_system=True,
        )
        db.add(el)
        rows.append(el)
    db.flush()
    # A society whose books already exist: its standard expense ledgers now have elements to count towards.
    from app.modules.accounts.services.chart_of_accounts import link_default_elements
    link_default_elements(db, society_id)
    db.flush()
    return rows
