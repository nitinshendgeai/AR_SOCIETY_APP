"""Bulk import of each flat's vehicles and family members from a sheet.

The app reads the file and sends the rows as text; this reads each cell the way a person typed it. Every row stands
alone: a bad row is reported and skipped, the rest go in, and a row for a vehicle or person already on the flat is
skipped, so a corrected file can be imported again. With `dry_run` every row is checked and nothing is written.

- **Vehicles**: one row per vehicle (Wing, Flat, Vehicle Number, Type, Make, Model, Colour, Parking Slot, Owner Name,
  Remarks). Checked with the same rules as registering a vehicle on the form (number format, one active vehicle per
  number in the society). The owner name links the vehicle to that resident or tenant of the flat when it matches.
- **Family members**: one row per person (Wing, Flat, Name, Relationship, Mobile, Email, Date of Birth), added to the
  flat's Residents list as Family or Dependent. No app login is made for them (the office can give one later), and nobody
  is added twice: a name already on the flat is skipped.
"""
import re
from datetime import date, datetime
from typing import Dict, List, Literal, Optional
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditAction
from app.models.resident import Resident, ResidentType
from app.models.tenant import Tenant
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleType
from app.repositories.resident_repo import ResidentRepository
from app.schemas.resident import ResidentCreate
from app.services.audit_service import AuditService
from app.services.flat_lookup import FlatLookup, clean
from app.utils.vehicle_number import normalize_vehicle_number

MAX_ROWS = 2000


class _Row(BaseModel):
    line: Optional[int] = None
    wing: Optional[str] = None
    flat_number: Optional[str] = None


class VehicleImportRow(_Row):
    vehicle_number: Optional[str] = None
    vehicle_type: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    color: Optional[str] = None
    parking_slot: Optional[str] = None
    owner_name: Optional[str] = None
    remarks: Optional[str] = None


class FamilyImportRow(_Row):
    full_name: Optional[str] = None
    relationship: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    date_of_birth: Optional[str] = None


class VehicleImportRequest(BaseModel):
    rows: List[VehicleImportRow] = Field(max_length=MAX_ROWS)
    dry_run: bool = True


class FamilyImportRequest(BaseModel):
    rows: List[FamilyImportRow] = Field(max_length=MAX_ROWS)
    dry_run: bool = True


class ImportResult(BaseModel):
    line: Optional[int] = None
    flat: Optional[str] = None
    item: Optional[str] = None              # the vehicle number, or the person's name
    status: Literal["created", "skipped", "error"]
    message: Optional[str] = None


# ── Reading cells ─────────────────────────────────────────────────────────────────────────────────────────────────────

_VEHICLE_WORDS = [
    # Order matters: the more specific words first ("motorcycle" contains "cycle", "bicycle" contains "cycle").
    (("scooter", "scooty", "moped", "activa"), VehicleType.SCOOTER),
    (("motorcycle", "motor cycle", "bike", "two wheeler", "2 wheeler", "2wheeler", "2w", "two wheel", "2 wheel"), VehicleType.MOTORCYCLE),
    (("bicycle", "cycle", "bi cycle"), VehicleType.BICYCLE),
    (("rickshaw", "auto"), VehicleType.AUTO),
    (("truck", "lorry", "pickup", "pick up"), VehicleType.TRUCK),
    (("van", "minivan", "mini van", "tempo"), VehicleType.VAN),
    (("car", "four wheeler", "4 wheeler", "4wheeler", "4w", "four wheel", "4 wheel", "suv", "sedan", "hatchback", "jeep", "muv"),
     VehicleType.CAR),
]


def parse_vehicle_type(text: Optional[str]) -> tuple:
    """(VehicleType, note). A blank type is a car; words people use ("two wheeler", "bike", "4W") are understood; anything
    else becomes Other, with a note saying so."""
    t = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    t = " ".join(t.split())
    if not t:
        return VehicleType.CAR, None
    for value in VehicleType:
        if t == value.value:
            return value, None
    for words, vtype in _VEHICLE_WORDS:
        if any(t == w or t.startswith(w + " ") or t.endswith(" " + w) or f" {w} " in f" {t} " for w in words):
            return vtype, None
    return VehicleType.OTHER, f'Type "{text.strip()}" was not recognised: saved as Other'


# A relationship written as a child, or a minor, is a Dependent; every other one is Family.
_DEPENDENT_WORDS = {"dependent", "child", "kid", "son", "daughter", "minor", "baby", "grandson", "granddaughter",
                    "grandchild", "ward"}


def parse_relationship(text: Optional[str]) -> ResidentType:
    words = set(re.sub(r"[^a-z ]", " ", (text or "").lower()).split())
    return ResidentType.DEPENDENT if words & _DEPENDENT_WORDS else ResidentType.FAMILY


def parse_birth_date(text: Optional[str]) -> Optional[date]:
    """dd/mm/yyyy or dd-mm-yyyy (the way it is written in India), or yyyy-mm-dd. Blank: no date."""
    t = clean(text)
    if not t:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d-%b-%Y", "%d %b %Y",
                "%d-%B-%Y", "%d %B %Y"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    raise ValueError(f'Date of birth "{t}" is not a date (use dd/mm/yyyy)')


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    where = ".".join(str(p) for p in err["loc"] if p != "body")
    msg = err["msg"].removeprefix("Value error, ")
    return f"{where}: {msg}" if where else msg


def _norm_name(v: Optional[str]) -> str:
    return " ".join((v or "").lower().split())


# ── Vehicles ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def import_vehicles(db: Session, rows: List[VehicleImportRow], dry_run: bool, user: User) -> List[ImportResult]:
    from app.api.routes.vehicle import VehicleCreate           # the form's own rules (number format, year, lengths)

    society_id = user.society_id
    if society_id is None:
        raise HTTPException(400, "Choose a society first: this login is not tied to one")
    lookup = FlatLookup(db, society_id)
    # Every active vehicle of the society by its number, so a repeat is found whatever spaces or dashes it was typed with.
    on_file: Dict[str, Vehicle] = {normalize_vehicle_number(v.vehicle_number): v for v in db.query(Vehicle).filter(
        Vehicle.society_id == society_id, Vehicle.is_active == True).all()}               # noqa: E712
    in_file: Dict[str, int] = {}
    out: List[ImportResult] = []

    for row in rows:
        label = " ".join(x for x in (clean(row.wing), clean(row.flat_number)) if x) or None
        number_text = clean(row.vehicle_number)

        def result(status, message=None, item=number_text or None):
            out.append(ImportResult(line=row.line, flat=label, item=item, status=status, message=message))

        try:
            flat = lookup.find(row.wing or "", row.flat_number or "")
            if not number_text:
                raise ValueError("Vehicle number is required")
            number = normalize_vehicle_number(number_text)
            if number in in_file:
                raise ValueError(f"This vehicle number appears again (line {in_file[number]} of the file)")
            in_file[number] = row.line or 0

            existing = on_file.get(number)
            if existing is not None:
                if existing.flat_id == flat.id:
                    result("skipped", f"{number} is already registered to this flat", item=number)
                    continue
                other = lookup_label(db, existing.flat_id)
                raise ValueError(f"{number} is already registered to {other or 'another flat'}")

            vtype, type_note = parse_vehicle_type(row.vehicle_type)
            owner_note, resident_id, tenant_id = None, None, None
            wanted = _norm_name(row.owner_name)
            if wanted:
                resident = next((r for r in db.query(Resident).filter(Resident.flat_id == flat.id, Resident.is_active == True)  # noqa: E712
                                 if _norm_name(r.full_name) == wanted), None)
                if resident:
                    resident_id = resident.id
                else:
                    tenant = next((t for t in db.query(Tenant).filter(Tenant.flat_id == flat.id, Tenant.is_active == True)      # noqa: E712
                                   if _norm_name(t.full_name) == wanted), None)
                    if tenant:
                        tenant_id = tenant.id
                    else:
                        owner_note = f'"{clean(row.owner_name)}" is not a resident or tenant of this flat: saved without an owner'
            try:
                data = VehicleCreate.model_validate({
                    "society_id": society_id, "flat_id": flat.id, "resident_id": resident_id, "tenant_id": tenant_id,
                    "vehicle_number": number_text, "vehicle_type": vtype, "make": clean(row.make) or None,
                    "model": clean(row.model) or None, "color": clean(row.color) or None,
                    "parking_slot": clean(row.parking_slot) or None, "remarks": clean(row.remarks) or None})
            except ValidationError as exc:
                raise ValueError(_first_error(exc))

            notes = " · ".join(n for n in (type_note, owner_note) if n) or None
            if not dry_run:
                vehicle = Vehicle(**data.model_dump(), registered_by=user.id)
                try:
                    with db.begin_nested():
                        db.add(vehicle)
                        db.flush()
                except IntegrityError:
                    raise ValueError(f"{number} is already registered")
                on_file[number] = vehicle
            result("created", notes, item=data.vehicle_number)
        except HTTPException as exc:
            result("error", str(exc.detail))
        except ValueError as exc:
            result("error", str(exc))

    if not dry_run:
        AuditService.log(db=db, action=AuditAction.CREATE, module="vehicle", entity_type="Vehicle", user=user,
                         new_values={"import": True, "created": sum(1 for r in out if r.status == "created"),
                                     "skipped": sum(1 for r in out if r.status == "skipped"),
                                     "errors": sum(1 for r in out if r.status == "error")})
        db.commit()
    return out


def lookup_label(db: Session, flat_id: Optional[UUID]) -> Optional[str]:
    """'A-101' for a flat, for a message."""
    from app.models.flat import Flat
    from app.modules.billing.services.bill_pdf import flat_label
    flat = db.query(Flat).filter(Flat.id == flat_id).first() if flat_id else None
    return f"flat {flat_label(flat)}" if flat else None


# ── Family members ────────────────────────────────────────────────────────────────────────────────────────────────────

def import_family(db: Session, rows: List[FamilyImportRow], dry_run: bool, user: User) -> List[ImportResult]:
    society_id = user.society_id
    if society_id is None:
        raise HTTPException(400, "Choose a society first: this login is not tied to one")
    lookup = FlatLookup(db, society_id)
    repo = ResidentRepository(db)
    seen: Dict[tuple, int] = {}
    out: List[ImportResult] = []

    for row in rows:
        label = " ".join(x for x in (clean(row.wing), clean(row.flat_number)) if x) or None
        name = clean(row.full_name)

        def result(status, message=None):
            out.append(ImportResult(line=row.line, flat=label, item=name or None, status=status, message=message))

        try:
            flat = lookup.find(row.wing or "", row.flat_number or "")
            if not name:
                raise ValueError("Name is required")
            key = (flat.id, _norm_name(name))
            if key in seen:
                raise ValueError(f"This person appears again for this flat (line {seen[key]} of the file)")
            seen[key] = row.line or 0

            # Anyone of that name already on the flat, whatever their type: a repeat, not a new person.
            if db.query(Resident.id).filter(
                    Resident.flat_id == flat.id, Resident.is_active == True,                          # noqa: E712
                    func.lower(func.trim(Resident.full_name)) == _norm_name(name)).first():
                result("skipped", f"{name} is already on the list for this flat")
                continue

            rtype = parse_relationship(row.relationship)
            try:
                data = ResidentCreate.model_validate({
                    "flat_id": flat.id, "full_name": name, "resident_type": rtype, "is_primary": False,
                    "phone": clean(row.phone) or None, "email": clean(row.email) or None,
                    "date_of_birth": parse_birth_date(row.date_of_birth)})
            except ValidationError as exc:
                raise ValueError(_first_error(exc))

            if not dry_run:
                member = repo.create(Resident(
                    flat_id=flat.id, full_name=data.full_name, resident_type=rtype, is_primary=False,
                    phone=data.phone, email=data.email, date_of_birth=data.date_of_birth))
                AuditService.log(
                    db=db, action=AuditAction.CREATE, module="resident", entity_id=str(member.id), entity_type="Resident",
                    user=user, new_values={"full_name": member.full_name, "resident_type": rtype.value,
                                           "flat_id": str(flat.id), "is_primary": False, "import": True})
            result("created", f"Added as {'Dependent' if rtype == ResidentType.DEPENDENT else 'Family'}")
        except HTTPException as exc:
            result("error", str(exc.detail))
        except ValueError as exc:
            result("error", str(exc))

    if not dry_run:
        AuditService.log(db=db, action=AuditAction.CREATE, module="resident", entity_type="Resident", user=user,
                         new_values={"import": "family", "created": sum(1 for r in out if r.status == "created"),
                                     "skipped": sum(1 for r in out if r.status == "skipped"),
                                     "errors": sum(1 for r in out if r.status == "error")})
        db.commit()
    return out
