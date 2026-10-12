"""Which services (modules) a society has switched on.

The platform owner can switch any optional service on or off for one society from the Platform Console, by hand.
Everything not listed here is core and always on: sign-in, the society's structure (wings, floors, flats), residents,
tenants and vehicles, users and roles, maintenance billing and payments, notifications and the dashboard.

Every society has every service until the owner switches one off. Only the switched-off ones are stored
(`SocietyService` rows); switching it back on removes the row. A service that is off is closed in two places: the API
refuses its calls (see society_gate.service_block_reason) and the app hides its menu items (the form codes below are
dropped from /roles/forms/mine).
"""
from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional, Set, Tuple

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Service:
    key: str
    label: str
    description: str
    prefixes: Tuple[str, ...]          # first path segment(s) under /api/v1 that belong to it
    form_codes: Tuple[str, ...]        # menu items (rbac_seed form codes) that belong to it


SERVICES: Tuple[Service, ...] = (
    Service("visitors", "Visitors & gate", "Visitor entry, approvals, pre-approvals and the gate log", ("visitors",), ("visitors",)),
    Service("complaints", "Complaints", "Raise, assign and resolve complaints", ("complaints",), ("complaints",)),
    Service("notices", "Notices", "Notices and announcements to members", ("notices",), ("notices",)),
    Service("amenities", "Amenity booking", "Club house, hall and other bookable amenities", ("amenities",), ("amenities",)),
    Service("parking", "Parking", "Slots, allotments, the gate vehicle check and parking charges", ("parking",), ("parking_management",)),
    Service("staff", "Staff & duty", "Staff, duty plans, attendance and shift handover", ("staff", "handovers", "payroll", "workload"),
            ("staff", "checklist_templates")),
    Service("vendors", "Vendors & work orders", "Vendors, AMC, work orders and vendor bills", ("vendors",), ("vendors", "vendor_bills")),
    Service("inventory", "Stores & assets", "Stock register and the assets register", ("inventory",), ("assets", "inventory")),
    Service("governance", "Meetings, polls & documents", "Meetings and minutes, polls and voting, the documents library",
            ("governance",), ("meetings", "polls", "documents")),
    Service("certificates", "Certificates & NOC", "NOC and certificate requests with approval", ("certificates",), ("certificates",)),
    Service("gate_extras", "Parcels & domestic help", "Parcel register and domestic help passes", ("gate",), ("parcels", "domestic_help")),
    Service("shops", "Shops", "Shops master and shop tenants", ("shops",), ("shops",)),
    Service("checklist", "Manager's checklist", "The manager's daily checklist and compliance calendar", ("manager-checklist",),
            ("manager_checklist",)),
    Service("accounts", "Accounts (books)", "Vouchers, ledgers, registers and financial statements", ("accounts",), ("accounts",)),
)

BY_KEY: Dict[str, Service] = {s.key: s for s in SERVICES}
BY_PREFIX: Dict[str, Service] = {p: s for s in SERVICES for p in s.prefixes}
ALL_KEYS: FrozenSet[str] = frozenset(BY_KEY)

def off_services(db: Session, society_id) -> Set[str]:
    """The services the owner has switched off for this society."""
    from app.models.society_service import SocietyService
    rows = db.query(SocietyService.service_key).filter(SocietyService.society_id == society_id,
                                                       SocietyService.enabled == False)  # noqa: E712
    return {k for (k,) in rows if k in ALL_KEYS}


def effective_services(db: Session, society_id) -> Set[str]:
    """The services this society can use: all of them, less the ones switched off."""
    return set(ALL_KEYS) - off_services(db, society_id)


def service_for_path(path: str) -> Optional[Service]:
    """The optional service an API path belongs to, or None for the core."""
    p = path[len("/api/v1"):] if path.startswith("/api/v1") else path
    first = p.lstrip("/").split("/", 1)[0]
    return BY_PREFIX.get(first)
