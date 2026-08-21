from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import field_validator, model_validator

from app.db.session import get_db
from app.core.dependencies import get_current_user, require_roles, require_admin_committee, require_any_member
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


class VehicleCreate(OrmBase):
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

    @field_validator("vehicle_number")
    @classmethod
    def normalize(cls, v):
        return normalize_vehicle_number(v)

    @model_validator(mode="after")
    def check_owner_xor(self):
        # A vehicle may belong to a resident, a tenant, or neither — never both
        # (a car can't simultaneously be "the tenant's" and "the owner's").
        if self.resident_id is not None and self.tenant_id is not None:
            raise ValueError("A vehicle cannot have both resident_id and tenant_id set")
        return self


class VehicleUpdate(OrmBase):
    vehicle_type:   Optional[VehicleType] = None
    make:           Optional[str] = None
    model:          Optional[str] = None
    color:          Optional[str] = None
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
    db.flush()
    AuditService.log(db=db, action=AuditAction.CREATE, module="vehicle",
                     entity_id=str(vehicle.id), entity_type="Vehicle",
                     user=user, request=request,
                     new_values={"number": data.vehicle_number, "type": data.vehicle_type.value})
    db.commit()
    db.refresh(vehicle)
    return vehicle


def _vehicle_query(db: Session, user: User):
    """Base query for a single vehicle, scoped to the caller's own society
    unless they're a platform admin (user.society_id is None)."""
    q = db.query(Vehicle).filter(Vehicle.is_active == True)
    if user.society_id is not None:
        q = q.filter(Vehicle.society_id == user.society_id)
    return q


@router.patch("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(vehicle_id: UUID, data: VehicleUpdate,
                   db: Session = Depends(get_db),
                   user: User = Depends(committee_or_admin)):
    v = _vehicle_query(db, user).filter(Vehicle.id == vehicle_id).first()
    if not v: raise HTTPException(status_code=404, detail="Vehicle not found")
    for k, val in data.model_dump(exclude_none=True).items():
        setattr(v, k, val)
    db.commit()
    db.refresh(v)
    return v


@router.get("/society/{society_id}", response_model=List[VehicleOut])
def list_vehicles(society_id: UUID, db: Session = Depends(get_db),
                   user: User = Depends(any_member)):
    assert_society_access(user, society_id)
    return db.query(Vehicle).filter(Vehicle.society_id == society_id, Vehicle.is_active == True).all()


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
def deregister_vehicle(vehicle_id: UUID, request: Request, db: Session = Depends(get_db),
                        user: User = Depends(committee_or_admin)):
    v = _vehicle_query(db, user).filter(Vehicle.id == vehicle_id).first()
    if not v: raise HTTPException(status_code=404, detail="Vehicle not found")
    v.is_active = False
    AuditService.log(db=db, action=AuditAction.DELETE, module="vehicle",
                     entity_id=str(v.id), entity_type="Vehicle",
                     user=user, request=request,
                     old_values={"number": v.vehicle_number, "is_active": True})
    db.commit()
