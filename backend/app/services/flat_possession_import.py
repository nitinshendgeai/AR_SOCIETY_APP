"""Set the possession date of many flats from a sheet. Only existing flats are touched: the date is added where
there is none and replaced where there is one. A bad row is reported and skipped; the rest go in."""
from collections import defaultdict
from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.tenant_scope import resolve_create_society_id
from app.models.audit_log import AuditAction
from app.models.user import User
from app.schemas.flat import PossessionImportResult, PossessionImportRow
from app.services.audit_service import AuditService
from app.repositories.flat_repo import FlatRepository
from app.utils.unit_fields import clean_possession_date


def _clean(v: Optional[str]) -> str:
    return " ".join(str(v).split()) if v is not None else ""


def _key(v: str) -> str:
    return v.lower()


def import_possession_dates(db: Session, society_id: Optional[UUID], rows: List[PossessionImportRow],
                            dry_run: bool, user: User, request=None) -> List[PossessionImportResult]:
    society_id = resolve_create_society_id(user, society_id)
    flats = FlatRepository(db).get_by_society(society_id)
    by_wing = {}                                   # (wing name or code, flat number) -> flat
    by_number = defaultdict(list)                  # flat number -> every flat of the society with it
    for f in flats:
        for wing_key in {_key(f.wing.name), _key(f.wing.code or f.wing.name)}:
            by_wing[(wing_key, _key(f.flat_number))] = f
        by_number[_key(f.flat_number)].append(f)

    seen = {}
    out: List[PossessionImportResult] = []
    for row in rows:
        wing, number = _clean(row.wing), _clean(row.flat_number)
        res = lambda status, **kw: out.append(PossessionImportResult(
            line=row.line, wing=wing or None, flat_number=number or None, status=status, **kw))
        try:
            if not number:
                raise ValueError("Flat number is required")
            if wing:
                flat = by_wing.get((_key(wing), _key(number)))
                if flat is None:
                    raise ValueError(f"No flat {number} in wing {wing}")
            else:
                found = by_number.get(_key(number), [])
                if not found:
                    raise ValueError(f"No flat {number}")
                if len(found) > 1:
                    raise ValueError(f"Flat {number} is in more than one wing — add the Wing column")
                flat = found[0]
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
            if old == new:
                res("unchanged", previous=old)
                continue
            if not dry_run:
                flat.possession_date = new
            res("updated", previous=old)
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
