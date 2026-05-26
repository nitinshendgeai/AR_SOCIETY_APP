from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import field_validator

from app.db.session import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleType
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.schemas.common import OrmBase, TimestampSchema

router = APIRouter(prefix="/vehicles", tags=["Vehicle Master"])

committee_or_admin = require_roles("Admin", "Committee")
any_member         = require_roles("Admin", "Committee", "Resident", "Staff", "Security")


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
        return v.upper().replace(" ", "").replace("-", "")


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


@router.post("/", response_model=VehicleOut, status_code=201)
def register_vehicle(data: VehicleCreate, request: Request,
                     db: Session = Depends(get_db),
                     user: User = Depends(any_member)):
    # Duplicate check
    existing = db.query(Vehicle).filter(
        Vehicle.vehicle_number == data.vehicle_number,
        Vehicle.society_id     == data.society_id,
        Vehicle.is_active      == True,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Vehicle {data.vehicle_number} already registered")

    vehicle = Vehicle(**data.model_dump(), registered_by=user.id)
    db.add(vehicle)
    db.flush()
    AuditService.log(db=db, action=AuditAction.CREATE, module="vehicle",
                     entity_id=str(vehicle.id), entity_type="Vehicle",
                     user=user, request=request,
                     new_values={"number": data.vehicle_number, "type": data.vehicle_type.value})
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.patch("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(vehicle_id: UUID, data: VehicleUpdate,
                   db: Session = Depends(get_db),
                   user: User = Depends(committee_or_admin)):
    v = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not v: raise HTTPException(status_code=404, detail="Vehicle not found")
    for k, val in data.model_dump(exclude_none=True).items():
        setattr(v, k, val)
    db.commit()
    db.refresh(v)
    return v


@router.get("/society/{society_id}", response_model=List[VehicleOut],
            dependencies=[Depends(any_member)])
def list_vehicles(society_id: UUID, db: Session = Depends(get_db)):
    return db.query(Vehicle).filter(Vehicle.society_id == society_id, Vehicle.is_active == True).all()


@router.get("/flat/{flat_id}", response_model=List[VehicleOut],
            dependencies=[Depends(any_member)])
def vehicles_by_flat(flat_id: UUID, db: Session = Depends(get_db)):
    return db.query(Vehicle).filter(Vehicle.flat_id == flat_id, Vehicle.is_active == True).all()


@router.get("/{vehicle_id}", response_model=VehicleOut,
            dependencies=[Depends(any_member)])
def get_vehicle(vehicle_id: UUID, db: Session = Depends(get_db)):
    v = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not v: raise HTTPException(status_code=404, detail="Vehicle not found")
    return v


@router.delete("/{vehicle_id}", status_code=204,
               dependencies=[Depends(committee_or_admin)])
def deregister_vehicle(vehicle_id: UUID, db: Session = Depends(get_db)):
    v = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not v: raise HTTPException(status_code=404, detail="Vehicle not found")
    v.is_active = False
    db.commit()
