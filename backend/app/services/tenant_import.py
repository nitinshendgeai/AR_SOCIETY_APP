"""Bulk import of tenants from a file: each row is a tenant of a flat that is let out, with the agreement, the rent
and the channel the agreement came through (direct, agent, online app).

The app reads the file and sends the rows as text; this reads each cell the way a person typed it. Every row stands
alone: a bad row is reported and skipped, the rest go in, and a row for a tenant already in the flat is skipped, so a
corrected file can be imported again. Each tenant is made through TenantService.create(), so the move-in, the
agreement and the flat's occupancy behave exactly as when the tenant is added on the form. With `dry_run` every row
is checked and nothing is written."""
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Literal, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditAction
from app.models.flat import Flat
from app.models.tenant import Tenant
from app.models.user import User
from app.models.wing import Wing
from app.schemas.tenant import TenantCreate
from app.services.audit_service import AuditService
from app.services.occupancy_service import OccupancyService
from app.services.tenant_service import TenantService

MAX_ROWS = 2000


class TenantImportRow(BaseModel):
    """One line of the file. Everything arrives as text (or null)."""
    line:                 Optional[int] = None
    wing:                 Optional[str] = None
    flat_number:          Optional[str] = None
    full_name:            Optional[str] = None
    phone:                Optional[str] = None
    email:                Optional[str] = None
    agreement_start_date: Optional[str] = None        # ISO, or dd/mm/yyyy
    agreement_end_date:   Optional[str] = None
    monthly_rent:         Optional[str] = None
    security_deposit:     Optional[str] = None
    move_in_date:         Optional[str] = None        # the agreement's start when left out
    channel:              Optional[str] = None        # direct | agent | online app | other (or what a person writes)
    channel_name:         Optional[str] = None        # the agent's or the app's name
    id_proof_type:        Optional[str] = None
    id_proof_number:      Optional[str] = None
    remarks:              Optional[str] = None


class TenantImportRequest(BaseModel):
    rows: List[TenantImportRow] = Field(max_length=MAX_ROWS)
    dry_run: bool = False


class TenantImportResult(BaseModel):
    line: Optional[int]
    flat: Optional[str]
    full_name: Optional[str]
    status: Literal["created", "skipped", "error"]
    message: Optional[str] = None


def _clean(v) -> Optional[str]:
    v = (v or "").strip() if isinstance(v, str) else v
    return v or None


def parse_date(v) -> Optional[date]:
    """ISO (2026-04-01) or day first (01/04/2026, 1-4-26)."""
    v = _clean(v)
    if v is None:
        return None
    try:
        return date.fromisoformat(v[:10])
    except ValueError:
        pass
    m = re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2}|\d{4})", v)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + 2000 if y < 100 else y
        try:
            return date(y, mo, d)
        except ValueError:
            pass
    raise ValueError(f"'{v}' is not a date — write it as dd/mm/yyyy")


def parse_money(v) -> Optional[Decimal]:
    v = _clean(v)
    if v is None:
        return None
    cleaned = re.sub(r"[₹,\s]|rs\.?|inr", "", v, flags=re.I)
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"'{v}' is not an amount")


_CHANNEL_WORDS = (
    ("direct", ("direct", "owner", "self", "personal", "known", "reference", "walk")),
    ("agent", ("agent", "broker", "brokerage", "dealer", "consultant", "estate")),
    ("online_app", ("online", "app", "portal", "website", "web", "site", "platform", "nobroker", "magicbricks",
                    "99acres", "housing", "olx", "squareyards", "quikr", "nestaway", "airbnb")),
)


def parse_channel(v) -> Optional[str]:
    """direct / agent / online_app, from what a person writes ("Broker", "Online App", "NoBroker", "Direct");
    anything else is 'other'."""
    v = _clean(v)
    if v is None:
        return None
    low = re.sub(r"[^a-z0-9 ]", " ", v.lower())
    words = set(low.split())
    for channel, hints in _CHANNEL_WORDS:
        if low.replace(" ", "_") == channel or words & set(hints):
            return channel
    return "other"


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    where = ".".join(str(p) for p in err["loc"] if p != "body")
    msg = err["msg"].removeprefix("Value error, ")
    return f"{where}: {msg}" if where else msg


def _flat_index(db: Session, society_id: UUID) -> Tuple[Dict[Tuple[str, str], Flat], Dict[str, List[Flat]]]:
    by_wing: Dict[Tuple[str, str], Flat] = {}
    by_number: Dict[str, List[Flat]] = {}
    rows = (db.query(Flat, Wing.name).join(Wing, Wing.id == Flat.wing_id)
            .filter(Wing.society_id == society_id, Flat.is_active == True).all())     # noqa: E712
    for flat, wing_name in rows:
        by_wing[(wing_name.strip().lower(), str(flat.flat_number).strip().lower())] = flat
        by_number.setdefault(str(flat.flat_number).strip().lower(), []).append(flat)
    return by_wing, by_number


def import_tenants(db: Session, rows: List[TenantImportRow], dry_run: bool, user: User) -> List[TenantImportResult]:
    society_id = user.society_id
    if society_id is None:
        raise HTTPException(400, "Choose a society first: this login is not tied to one")
    by_wing, by_number = _flat_index(db, society_id)
    occupancy = OccupancyService(db)
    service = TenantService(db)
    seen_flats: Dict[UUID, int] = {}
    out: List[TenantImportResult] = []

    for row in rows:
        label = " ".join(x for x in (_clean(row.wing), _clean(row.flat_number)) if x) or None
        name = _clean(row.full_name)

        def result(status, message=None):
            out.append(TenantImportResult(line=row.line, flat=label, full_name=name, status=status, message=message))

        try:
            if not _clean(row.flat_number):
                raise ValueError("Flat number is required")
            if not name:
                raise ValueError("Tenant name is required")

            number = str(row.flat_number).strip().lower()
            wing = _clean(row.wing)
            if wing:
                flat = by_wing.get((wing.lower(), number))
                if flat is None:
                    raise ValueError(f"There is no flat {wing} {row.flat_number.strip()} in this society")
            else:
                found = by_number.get(number, [])
                if not found:
                    raise ValueError(f"There is no flat {row.flat_number.strip()} in this society")
                if len(found) > 1:
                    raise ValueError(f"Flat {row.flat_number.strip()} is in more than one wing: give the wing")
                flat = found[0]

            if flat.id in seen_flats:
                raise ValueError(f"This flat appears again (line {seen_flats[flat.id]} of the file)")
            seen_flats[flat.id] = row.line or 0

            already = (db.query(Tenant).filter(Tenant.flat_id == flat.id, Tenant.is_active == True,     # noqa: E712
                                               Tenant.move_out_date.is_(None)).all())
            if any(t.full_name.strip().lower() == name.lower() for t in already):
                result("skipped", f"{name} is already the tenant of this flat")
                continue

            start, end = parse_date(row.agreement_start_date), parse_date(row.agreement_end_date)
            move_in = parse_date(row.move_in_date) or start
            channel = parse_channel(row.channel)
            channel_name = _clean(row.channel_name)
            if channel == "other" and not channel_name:
                channel_name = _clean(row.channel)          # "Friend", "Society notice board": kept as written
            if channel in (None, "direct"):
                channel_name = None
            try:
                data = TenantCreate.model_validate({
                    "flat_id": flat.id, "full_name": name, "phone": _clean(row.phone), "email": _clean(row.email),
                    "agreement_start_date": start, "agreement_end_date": end,
                    "monthly_rent": parse_money(row.monthly_rent), "security_deposit": parse_money(row.security_deposit),
                    "agreement_channel": channel, "agreement_channel_name": channel_name,
                    "id_proof_type": _clean(row.id_proof_type), "id_proof_number": _clean(row.id_proof_number),
                    "remarks": _clean(row.remarks), "move_in_date": move_in})
            except ValidationError as exc:
                raise ValueError(_first_error(exc))

            if move_in is not None:
                occupancy.check_tenant_move_in(flat, agreement_start=start, agreement_end=end)
            if not dry_run:
                service.create(data, user)
            result("created", None if move_in is not None else
                   "Added without a move-in date, so the flat is not yet marked as let out")
        except HTTPException as exc:           # refused before anything is written, so nothing to undo
            result("error", str(exc.detail))
        except ValueError as exc:
            result("error", str(exc))

    if not dry_run:
        AuditService.log(db=db, action=AuditAction.CREATE, module="tenant", entity_type="Tenant", user=user,
                         new_values={"import": True, "created": sum(1 for r in out if r.status == "created"),
                                     "skipped": sum(1 for r in out if r.status == "skipped"),
                                     "errors": sum(1 for r in out if r.status == "error")})
    return out
