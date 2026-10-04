import re
from datetime import date
from typing import List, Optional, Set
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import Field, field_validator, model_validator

from app.db.session import get_db
from app.core.dependencies import (
    get_current_user, require_roles, require_admin_committee, require_any_member, _user_has_permission,
)
from app.schemas import validators as val
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleType
from app.models.resident import Resident
from app.models.tenant import Tenant
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.schemas.common import OrmBase, TimestampSchema
from app.core.tenant_scope import assert_society_access, resolve_create_society_id
from app.utils.vehicle_number import normalize_vehicle_number
from app.repositories.flat_repo import FlatRepository

router = APIRouter(prefix="/vehicles", tags=["Vehicle Master"])

committee_or_admin = require_admin_committee
any_member         = require_any_member


_PLATE = re.compile(r"^[A-Z0-9]{4,20}$")
# Required on the row: null for these leaves them as they are; every other
# field in a PATCH, sent as null, is cleared.
_NOT_CLEARABLE = {"vehicle_type", "is_active"}


def _plate(v):
    """A registration number as the gate would see it: spaces and dashes
    dropped, upper-cased, letters and digits only."""
    v = normalize_vehicle_number(v) if v is not None else v
    if not v or not _PLATE.match(v):
        raise ValueError("Enter a valid vehicle number, e.g. MH12AB1234")
    return v


def _year(v):
    v = val.text(v)
    if v is None:
        return None
    if not re.fullmatch(r"\d{4}", v) or not (1900 <= int(v) <= date.today().year + 1):
        raise ValueError("Enter a valid 4-digit year")
    return v


def _expiry(v):
    v = val.text(v)
    if v is None:
        return None
    try:
        return date.fromisoformat(v).isoformat()
    except ValueError:
        raise ValueError("Enter the date as YYYY-MM-DD")


class _VehicleFields(OrmBase):
    """Checks shared by registering and editing a vehicle."""
    _year_ok = field_validator("year", mode="before", check_fields=False)(_year)
    _expiry_ok = field_validator("insurance_expiry", mode="before", check_fields=False)(_expiry)
    _make = field_validator("make", "model", mode="before", check_fields=False)(val.limited(100))
    _color = field_validator("color", mode="before", check_fields=False)(val.limited(50))
    _slot = field_validator("parking_slot", mode="before", check_fields=False)(val.limited(20))
    _rfid = field_validator("rfid_tag", mode="before", check_fields=False)(val.limited(100))
    _fast = field_validator("fasttag_number", "rc_number", mode="before", check_fields=False)(val.limited(50))
    _remarks = field_validator("remarks", mode="before", check_fields=False)(val.note)


class VehicleCreate(_VehicleFields):
    society_id:     UUID
    flat_id:        Optional[UUID] = None
    resident_id:    Optional[UUID] = None
    tenant_id:      Optional[UUID] = None
    vehicle_number: str
    vehicle_type:   VehicleType = VehicleType.CAR
    make:           Optional[str] = None
    model:          Optional[str] = None
    color:          Optional[str] = None
    year:           Optional[str] = None
    parking_slot:   Optional[str] = None
    rfid_tag:       Optional[str] = None
    fasttag_number: Optional[str] = None
    insurance_expiry: Optional[str] = None
    rc_number:      Optional[str] = None
    remarks:        Optional[str] = None

    _plate_ok = field_validator("vehicle_number", mode="before")(_plate)

    @model_validator(mode="after")
    def check_owner_xor(self):
        # A vehicle may belong to a resident, a tenant, or neither — never both
        # (a car can't simultaneously be "the tenant's" and "the owner's").
        if self.resident_id is not None and self.tenant_id is not None:
            raise ValueError("A vehicle cannot have both resident_id and tenant_id set")
        return self


class VehicleUpdate(_VehicleFields):
    vehicle_type:   Optional[VehicleType] = None
    make:           Optional[str] = None
    model:          Optional[str] = None
    color:          Optional[str] = None
    year:           Optional[str] = None
    parking_slot:   Optional[str] = None
    rfid_tag:       Optional[str] = None
    fasttag_number: Optional[str] = None
    insurance_expiry: Optional[str] = None
    rc_number:      Optional[str] = None
    remarks:        Optional[str] = None
    is_active:      Optional[bool] = None


class VehicleOut(TimestampSchema):
    society_id:     UUID
    flat_id:        Optional[UUID]
    resident_id:    Optional[UUID]
    tenant_id:      Optional[UUID]
    vehicle_number: str
    vehicle_type:   VehicleType
    make:           Optional[str]
    model:          Optional[str]
    color:          Optional[str]
    year:           Optional[str]
    parking_slot:   Optional[str]
    rfid_tag:       Optional[str]
    insurance_expiry: Optional[str]
    rc_number:      Optional[str]
    fasttag_number: Optional[str]
    remarks:        Optional[str]


def _own_flat_ids(db: Session, user: User) -> Optional[Set[UUID]]:
    """The flats a plain resident or tenant may see and register vehicles
    for: the ones they live in. None for staff and committee, who see the
    whole society."""
    if _user_has_permission(user, "any_staff"):
        return None
    flats = {r.flat_id for r in db.query(Resident).filter(Resident.user_id == user.id, Resident.is_active == True)}  # noqa: E712
    flats |= {t.flat_id for t in db.query(Tenant).filter(Tenant.user_id == user.id, Tenant.is_active == True)}  # noqa: E712
    return flats


def _assert_rfid_free(db: Session, rfid_tag: Optional[str], exclude_id: Optional[UUID] = None) -> None:
    """RFID tags are unique across the platform; say so instead of failing
    on the database constraint."""
    if not rfid_tag:
        return
    q = db.query(Vehicle).filter(Vehicle.rfid_tag == rfid_tag)
    if exclude_id is not None:
        q = q.filter(Vehicle.id != exclude_id)
    if q.first() is not None:
        raise HTTPException(status_code=409, detail="This RFID tag is already assigned to another vehicle")


def _validate_vehicle_links(db: Session, society_id: UUID, flat_id: Optional[UUID],
                             resident_id: Optional[UUID], tenant_id: Optional[UUID]) -> None:
    """A vehicle's society_id can be resolved/enforced correctly (tenant_scope)
    while flat_id/resident_id/tenant_id still point at a different society's
    records — nothing upstream checks that. Confine every supplied reference
    to the same society (and, where both are given, to the same flat)."""
    flat = None
    if flat_id is not None:
        flat = FlatRepository(db).get(flat_id, society_id=society_id)
        if not flat:
            raise HTTPException(status_code=404, detail="Flat not found")

    if resident_id is not None:
        resident = db.query(Resident).filter(Resident.id == resident_id).first()
        if not resident:
            raise HTTPException(status_code=404, detail="Resident not found")
        if flat_id is not None and resident.flat_id != flat_id:
            raise HTTPException(status_code=422, detail="resident_id does not belong to flat_id")
        if flat_id is None and not FlatRepository(db).get(resident.flat_id, society_id=society_id):
            raise HTTPException(status_code=404, detail="Resident not found")

    if tenant_id is not None:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        if flat_id is not None and tenant.flat_id != flat_id:
            raise HTTPException(status_code=422, detail="tenant_id does not belong to flat_id")
        if flat_id is None and not FlatRepository(db).get(tenant.flat_id, society_id=society_id):
            raise HTTPException(status_code=404, detail="Tenant not found")


@router.post("/", response_model=VehicleOut, status_code=201)
def register_vehicle(data: VehicleCreate, request: Request,
                     db: Session = Depends(get_db),
                     user: User = Depends(any_member)):
    society_id = resolve_create_society_id(user, data.society_id)
    _validate_vehicle_links(db, society_id, data.flat_id, data.resident_id, data.tenant_id)
    own = _own_flat_ids(db, user)
    if own is not None and data.flat_id not in own:
        raise HTTPException(status_code=403, detail="You can register vehicles only for your own flat")
    _assert_rfid_free(db, data.rfid_tag)

    # Duplicate check
    existing = db.query(Vehicle).filter(
        Vehicle.vehicle_number == data.vehicle_number,
        Vehicle.society_id     == society_id,
        Vehicle.is_active      == True,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Vehicle {data.vehicle_number} already registered")

    payload = data.model_dump()
    payload["society_id"] = society_id
    vehicle = Vehicle(**payload, registered_by=user.id)
    db.add(vehicle)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Vehicle {data.vehicle_number} already registered")
    AuditService.log(db=db, action=AuditAction.CREATE, module="vehicle",
                     entity_id=str(vehicle.id), entity_type="Vehicle",
                     user=user, request=request,
                     new_values={"number": data.vehicle_number, "type": data.vehicle_type.value})
    db.commit()
    db.refresh(vehicle)
    return vehicle


def _vehicle_query(db: Session, user: User):
    """Base query for a single vehicle, scoped to the caller's own society
    unless they're a platform admin (user.society_id is None) — and, for a
    plain resident or tenant, to the vehicles of their own flat."""
    q = db.query(Vehicle).filter(Vehicle.is_active == True)
    if user.society_id is not None:
        q = q.filter(Vehicle.society_id == user.society_id)
    own = _own_flat_ids(db, user)
    if own is not None:
        q = q.filter(Vehicle.flat_id.in_(own))
    return q


@router.patch("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(vehicle_id: UUID, data: VehicleUpdate,
                   db: Session = Depends(get_db),
                   user: User = Depends(committee_or_admin)):
    v = _vehicle_query(db, user).filter(Vehicle.id == vehicle_id).first()
    if not v: raise HTTPException(status_code=404, detail="Vehicle not found")
    patch = {k: getattr(data, k) for k in data.model_fields_set
             if getattr(data, k) is not None or k not in _NOT_CLEARABLE}
    _assert_rfid_free(db, patch.get("rfid_tag"), exclude_id=v.id)
    for k, value in patch.items():
        setattr(v, k, value)
    db.commit()
    db.refresh(v)
    return v


@router.get("/society/{society_id}", response_model=List[VehicleOut])
def list_vehicles(society_id: UUID, db: Session = Depends(get_db),
                   user: User = Depends(any_member)):
    assert_society_access(user, society_id)
    q = db.query(Vehicle).filter(Vehicle.society_id == society_id, Vehicle.is_active == True)
    own = _own_flat_ids(db, user)
    if own is not None:
        q = q.filter(Vehicle.flat_id.in_(own))
    return q.order_by(Vehicle.vehicle_number).all()


@router.get("/flat/{flat_id}", response_model=List[VehicleOut])
def vehicles_by_flat(flat_id: UUID, db: Session = Depends(get_db),
                      user: User = Depends(any_member)):
    return _vehicle_query(db, user).filter(Vehicle.flat_id == flat_id).all()


@router.get("/{vehicle_id}", response_model=VehicleOut)
def get_vehicle(vehicle_id: UUID, db: Session = Depends(get_db),
                 user: User = Depends(any_member)):
    v = _vehicle_query(db, user).filter(Vehicle.id == vehicle_id).first()
    if not v: raise HTTPException(status_code=404, detail="Vehicle not found")
    return v


@router.delete("/{vehicle_id}", status_code=204)
def deregister_vehicle(vehicle_id: UUID, db: Session = Depends(get_db),
                        user: User = Depends(committee_or_admin)):
    v = _vehicle_query(db, user).filter(Vehicle.id == vehicle_id).first()
    if not v: raise HTTPException(status_code=404, detail="Vehicle not found")
    v.is_active = False
    v.rfid_tag = None   # a deregistered vehicle no longer holds its tag
    # ...nor its parking: free the slot instead of leaving it allotted to a car that's gone
    from app.modules.parking.services.parking_service import ParkingService
    ParkingService.release_for_vehicles(db, [v.id], user)
    db.commit()
