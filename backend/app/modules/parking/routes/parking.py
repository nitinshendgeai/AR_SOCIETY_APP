from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import (
    get_current_user, require_roles,
    require_admin_committee, require_security, require_any_member,
)
from app.models.user import User
from app.modules.parking.schemas.parking import (
    ZoneCreate, ZoneOut, FloorCreate, FloorOut,
    SlotCreate, SlotUpdate, SlotOut,
    AllocationCreate, AllocationOut,
    VisitorParkingCreate, VisitorParkingOut,
    ViolationCreate, ViolationOut,
    AccessLogCreate, AccessLogOut,
)
from app.modules.parking.models.parking import SlotType
from app.modules.parking.services.parking_service import ParkingService

router = APIRouter(prefix="/parking", tags=["Parking Management"])

admin_committee = require_admin_committee
security_above  = require_security
any_member      = require_any_member


# ── Zones ─────────────────────────────────────────────────────────────────────
@router.post("/zones", response_model=ZoneOut, status_code=201, dependencies=[Depends(admin_committee)])
def create_zone(data: ZoneCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ParkingService(db).create_zone(data, user)

@router.get("/zones/{society_id}", response_model=List[ZoneOut], dependencies=[Depends(any_member)])
def list_zones(society_id: UUID, db: Session = Depends(get_db)):
    return ParkingService(db).list_zones(society_id)


# ── Floors ────────────────────────────────────────────────────────────────────
@router.post("/floors", response_model=FloorOut, status_code=201, dependencies=[Depends(admin_committee)])
def create_floor(data: FloorCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ParkingService(db).create_floor(data, user)


# ── Slots ─────────────────────────────────────────────────────────────────────
@router.post("/slots", response_model=SlotOut, status_code=201, dependencies=[Depends(admin_committee)])
def create_slot(data: SlotCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ParkingService(db).create_slot(data, user)

@router.patch("/slots/{slot_id}", response_model=SlotOut, dependencies=[Depends(admin_committee)])
def update_slot(slot_id: UUID, data: SlotUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ParkingService(db).update_slot(slot_id, data, user)

@router.get("/slots/{slot_id}", response_model=SlotOut, dependencies=[Depends(any_member)])
def get_slot(slot_id: UUID, db: Session = Depends(get_db)):
    return ParkingService(db).get_slot(slot_id)

@router.get("/slots/zone/{zone_id}", response_model=List[SlotOut], dependencies=[Depends(any_member)])
def slots_by_zone(zone_id: UUID, db: Session = Depends(get_db)):
    return ParkingService(db).list_slots_by_zone(zone_id)

@router.get("/slots/available/{society_id}", response_model=List[SlotOut], dependencies=[Depends(any_member)])
def available_slots(society_id: UUID, slot_type: Optional[SlotType] = None, db: Session = Depends(get_db)):
    return ParkingService(db).get_available_slots(society_id, slot_type)


# ── Allocations ───────────────────────────────────────────────────────────────
@router.post("/allocations", response_model=AllocationOut, status_code=201)
def allocate_slot(data: AllocationCreate, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(admin_committee)):
    return ParkingService(db).allocate_slot(data, user, request)

@router.post("/allocations/{allocation_id}/release", response_model=AllocationOut)
def release_slot(allocation_id: UUID, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(admin_committee)):
    return ParkingService(db).release_slot(allocation_id, user, request)

@router.get("/allocations/society/{society_id}", response_model=List[AllocationOut],
            dependencies=[Depends(admin_committee)])
def list_allocations(society_id: UUID, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return ParkingService(db).get_allocations(society_id, skip, limit)

@router.get("/allocations/flat/{flat_id}", response_model=List[AllocationOut],
            dependencies=[Depends(any_member)])
def flat_allocations(flat_id: UUID, db: Session = Depends(get_db)):
    return ParkingService(db).get_flat_allocations(flat_id)


# ── Visitor parking ───────────────────────────────────────────────────────────
@router.post("/visitor", response_model=VisitorParkingOut, status_code=201)
def assign_visitor_parking(data: VisitorParkingCreate, request: Request,
                            db: Session = Depends(get_db), user: User = Depends(security_above)):
    return ParkingService(db).assign_visitor_parking(data, user, request)

@router.post("/visitor/{vp_id}/checkout", response_model=VisitorParkingOut)
def checkout_visitor(vp_id: UUID, request: Request, db: Session = Depends(get_db),
                     user: User = Depends(security_above)):
    return ParkingService(db).checkout_visitor_parking(vp_id, user, request)

@router.get("/visitor/active/{society_id}", response_model=List[VisitorParkingOut],
            dependencies=[Depends(security_above)])
def active_visitor_parking(society_id: UUID, db: Session = Depends(get_db)):
    return ParkingService(db).get_active_visitor_parking(society_id)


# ── Violations ────────────────────────────────────────────────────────────────
@router.post("/violations", response_model=ViolationOut, status_code=201)
def report_violation(data: ViolationCreate, request: Request, db: Session = Depends(get_db),
                     user: User = Depends(security_above)):
    return ParkingService(db).report_violation(data, user, request)

@router.post("/violations/{violation_id}/resolve", response_model=ViolationOut)
def resolve_violation(violation_id: UUID, db: Session = Depends(get_db),
                      user: User = Depends(security_above)):
    return ParkingService(db).resolve_violation(violation_id, user)

@router.get("/violations/society/{society_id}", response_model=List[ViolationOut],
            dependencies=[Depends(security_above)])
def list_violations(society_id: UUID, unresolved_only: bool = False, db: Session = Depends(get_db)):
    return ParkingService(db).get_violations(society_id, unresolved_only)


# ── Access logs ───────────────────────────────────────────────────────────────
@router.post("/access-log", response_model=AccessLogOut, status_code=201)
def log_access(data: AccessLogCreate, db: Session = Depends(get_db),
               user: User = Depends(security_above)):
    return ParkingService(db).log_access(data, user)

@router.get("/access-log/society/{society_id}", response_model=List[AccessLogOut],
            dependencies=[Depends(security_above)])
def society_access_logs(society_id: UUID, skip: int = 0, limit: int = 100,
                         db: Session = Depends(get_db)):
    return ParkingService(db).get_access_logs(society_id, skip, limit)

@router.get("/access-log/vehicle/{vehicle_number}", response_model=List[AccessLogOut],
            dependencies=[Depends(security_above)])
def vehicle_access_history(vehicle_number: str, db: Session = Depends(get_db)):
    return ParkingService(db).get_vehicle_access_history(vehicle_number)
