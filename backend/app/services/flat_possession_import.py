"""Set the possession date of many flats from a sheet. Only existing flats are touched: the date is added where
there is none and replaced where there is one. A bad row is reported and skipped; the rest go in.

The date is also the move-in: each active resident of the flat who has no move-in date yet is marked as moved in on
the possession date, and the flat's occupancy follows (owner occupied instead of vacant). A move-in date already on
record is never changed, a flat that has an active tenant is left alone (the owner is not living there), and a
possession date in the future moves nobody in. This runs for every row, also where the possession date itself is
unchanged, so re-sending the sheet brings flats imported earlier up to date."""
from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.tenant_scope import resolve_create_society_id
from app.models.audit_log import AuditAction
from app.models.occupancy_log import OccupancyEventType
from app.models.resident import Resident
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.flat import PossessionImportResult, PossessionImportRow
from app.services.audit_service import AuditService
from app.services.flat_lookup import FlatLookup, clean as _clean
from app.services.occupancy_service import OccupancyService
from app.utils.unit_fields import clean_possession_date


def _move_in_residents(db: Session, occupancy: OccupancyService, flat, moved_on: date, dry_run: bool,
                       user: User) -> tuple:
    """Mark the flat's residents who have no move-in date as moved in on `moved_on`. Returns (how many, note)."""
    if moved_on > date.today():
        return 0, "possession date is in the future, so no one is marked as moved in"
    waiting = db.query(Resident).filter(
        Resident.flat_id == flat.id, Resident.is_active == True,                      # noqa: E712
        Resident.move_out_date.is_(None), Resident.move_in_date.is_(None)).all()
    if not waiting:
        return 0, None
    let_out = db.query(Tenant.id).filter(
        Tenant.flat_id == flat.id, Tenant.is_active == True,                          # noqa: E712
        Tenant.move_out_date.is_(None)).first() is not None
    if let_out:
        return 0, "the flat has a tenant, so the owner is not marked as moved in"
    if not dry_run:
        for resident in waiting:
            resident.move_in_date = moved_on
            occupancy._log_event(flat, OccupancyEventType.RESIDENT_MOVE_IN, moved_on, user, resident_id=resident.id,
                                 notes="Move-in set from the possession date import")
        occupancy._sync_status(flat)
    return len(waiting), None


def import_possession_dates(db: Session, society_id: Optional[UUID], rows: List[PossessionImportRow],
                            dry_run: bool, user: User, request=None) -> List[PossessionImportResult]:
    society_id = resolve_create_society_id(user, society_id)
    lookup = FlatLookup(db, society_id)
    occupancy = OccupancyService(db)

    seen = {}
    out: List[PossessionImportResult] = []
    for row in rows:
        wing, number = _clean(row.wing), _clean(row.flat_number)
        res = lambda status, **kw: out.append(PossessionImportResult(
            line=row.line, wing=wing or None, flat_number=number or None, status=status, **kw))
        try:
            flat = lookup.find(wing, number)
            if flat.id in seen:
                raise ValueError(f"{flat.wing.name}-{flat.flat_number} appears again (line {seen[flat.id]} of the file)")

            text = _clean(row.possession_date)
            if not text:
                raise ValueError("Possession date is empty")
            try:
                new = clean_possession_date(date.fromisoformat(text))
            except ValueError as exc:
                msg = str(exc)
                raise ValueError(msg if msg.startswith("Possession") else "Possession date must be a date (yyyy-mm-dd)")

            seen[flat.id] = row.line or 0
            old = flat.possession_date
            if not dry_run and old != new:
                flat.possession_date = new
            moved, note = _move_in_residents(db, occupancy, flat, new, dry_run, user)
            parts = []
            if moved:
                parts.append(f"{moved} resident{'s' if moved != 1 else ''} marked as moved in on {new:%d %b %Y}")
            if note:
                parts.append(note)
            message = ("; ".join(parts))[:1].upper() + ("; ".join(parts))[1:] if parts else None
            if old == new and not moved:
                res("unchanged", previous=old, message=message)
            else:
                res("updated", previous=old, message=message)
        except ValueError as exc:
            res("error", message=str(exc))

    if not dry_run:
        AuditService.log(db=db, action=AuditAction.UPDATE, module="flats", entity_type="Flat", user=user,
                         request=request,
                         new_values={"possession_date_import": True,
                                     "updated": sum(1 for r in out if r.status == "updated"),
                                     "errors": sum(1 for r in out if r.status == "error")})
        db.commit()
    return out
