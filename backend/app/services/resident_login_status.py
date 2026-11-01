"""Which residents can sign in to the app: the "Residents without a login" report.

A resident can sign in when their record is linked to an active login (Resident.user_id). The statuses:

  linked          linked to an active login
  login_disabled  linked, but the login is disabled or suspended: they cannot sign in
  login_unlinked  not linked, but an active login with the resident's mobile number exists in this society: it only
                  needs linking (Edit Resident → App login → Link login)
  no_login        not linked, and no login exists for their mobile number
  no_mobile       not linked and no mobile number on record: no login can be made until one is added

Only active residents of the society are listed.
"""
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.flat import Flat
from app.models.resident import Resident
from app.models.user import User, UserStatus
from app.models.wing import Wing
from app.repositories.user_repo import login_mobile

STATUSES = ("linked", "login_disabled", "login_unlinked", "no_login", "no_mobile")
NEEDS_ATTENTION = ("login_disabled", "login_unlinked", "no_login", "no_mobile")


def _flat_label(flat: Flat) -> str:
    wing = flat.wing.name if flat.wing else ""
    return f"{wing} / {flat.flat_number}" if wing else flat.flat_number


def resident_login_status(db: Session, society_id: UUID, status: Optional[str] = None,
                          search: Optional[str] = None) -> dict:
    rows = (db.query(Resident).join(Flat, Resident.flat_id == Flat.id).join(Wing, Flat.wing_id == Wing.id)
            .filter(Wing.society_id == society_id, Resident.is_active == True)               # noqa: E712
            .order_by(Wing.name, Flat.flat_number, Resident.full_name).all())

    users = db.query(User).filter(User.society_id == society_id, User.is_active == True).all()   # noqa: E712
    by_id: Dict[UUID, User] = {u.id: u for u in users}
    by_mobile: Dict[str, User] = {}
    for u in users:
        if u.phone and u.status == UserStatus.ACTIVE:
            by_mobile.setdefault(login_mobile(u.phone), u)

    summary = {k: 0 for k in STATUSES}
    out: List[dict] = []
    q = (search or "").strip().lower()
    for r in rows:
        phone = (r.phone or "").strip()
        login: Optional[User] = None
        if r.user_id is not None:
            login = by_id.get(r.user_id)
            state = "linked" if login is not None and login.status == UserStatus.ACTIVE else "login_disabled"
        elif not phone:
            state = "no_mobile"
        else:
            login = by_mobile.get(login_mobile(phone))
            state = "login_unlinked" if login is not None else "no_login"
        summary[state] += 1
        label = _flat_label(r.flat)
        if status and state != status:
            continue
        if q and q not in f"{r.full_name} {label} {phone}".lower():
            continue
        out.append({
            "id": str(r.id), "full_name": r.full_name, "resident_type": r.resident_type.value,
            "flat_id": str(r.flat_id), "flat_label": label, "phone": phone or None, "status": state,
            "login": ({"id": str(login.id), "name": login.full_name, "phone": login.phone}
                      if login is not None else None),
        })
    return {"summary": {**summary, "total": sum(summary.values()),
                        "needs_attention": sum(summary[k] for k in NEEDS_ATTENTION)},
            "residents": out}
