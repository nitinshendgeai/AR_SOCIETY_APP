"""A starting password for resident logins that have never been used.

When a society's residents are set up in bulk, an admin may want every resident to begin with the same starting password
(handed out with the app link) and choose their own at first sign-in. This sets it, and ONLY for logins that are safe
to hand over like that:

  - the login belongs to this society, is active, and is linked to an active resident;
  - it has NEVER been signed in to (last_login is empty): nobody has chosen a password of their own yet;
  - its only roles are Resident or Tenant: admins, committee, managers, guards, staff and platform admins are left
    exactly as they are.

Every login set is forced to change the password at first sign-in. A shared starting password is guessable, so until a
resident signs in, anyone who knows it and their mobile number could sign in as them: hand it out with that in mind.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.audit_log import AuditAction
from app.models.flat import Flat
from app.models.resident import Resident
from app.models.user import User, UserStatus
from app.models.wing import Wing
from app.services.audit_service import AuditService

RESIDENT_ROLES = {"Resident", "Tenant"}
MIN_LENGTH = 8


def set_starting_password(db: Session, society_id: UUID, password: str, dry_run: bool, by: User,
                          request=None) -> dict:
    """Returns {dry_run, set, skipped_signed_in, skipped_other_roles, people:[{name, flat, mobile}]}."""
    if len(password) < MIN_LENGTH:
        raise ValueError(f"The password must be at least {MIN_LENGTH} characters")
    rows = (db.query(User, Resident, Flat, Wing)
            .join(Resident, Resident.user_id == User.id).join(Flat, Resident.flat_id == Flat.id)
            .join(Wing, Flat.wing_id == Wing.id)
            .filter(User.society_id == society_id, Wing.society_id == society_id, User.is_active == True,   # noqa: E712
                    User.status == UserStatus.ACTIVE, Resident.is_active == True)                          # noqa: E712
            .order_by(Wing.name, Flat.flat_number).all())

    chosen: dict = {}                     # user id -> (user, [flat labels])
    skipped_signed_in = skipped_roles = 0
    seen_skipped = set()
    for user, _resident, flat, wing in rows:
        if user.id in seen_skipped:
            continue
        roles = {ur.role.name for ur in user.user_roles if ur.role is not None}
        if user.is_superadmin or not roles or not roles <= RESIDENT_ROLES:
            seen_skipped.add(user.id)
            skipped_roles += 1
            continue
        if user.last_login is not None:
            seen_skipped.add(user.id)
            skipped_signed_in += 1
            continue
        entry = chosen.setdefault(user.id, (user, []))
        entry[1].append(f"{wing.name} / {flat.flat_number}")

    people = [{"name": u.full_name, "flat": ", ".join(flats), "mobile": u.phone} for u, flats in chosen.values()]
    if not dry_run and chosen:
        hashed = hash_password(password)             # one hash for all: hashing hundreds of passwords one by one is slow
        for user, _ in chosen.values():
            user.hashed_password = hashed
            user.must_change_password = True
        AuditService.log(db=db, action=AuditAction.UPDATE, module="users", entity_type="User", user=by,
                         request=request, notes="Starting password set for residents who have never signed in",
                         new_values={"logins": len(chosen), "must_change_password": True})
        db.commit()
    return {"dry_run": dry_run, "set": len(chosen), "skipped_signed_in": skipped_signed_in,
            "skipped_other_roles": skipped_roles, "people": people}
