import secrets
from datetime import datetime, date
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.modules.parking.models.parking import (
    ParkingZone, ParkingFloor, ParkingSlot, ParkingAllocation,
    VisitorParking, ParkingViolation, ParkingAccessLog,
    SlotStatus, AllocationStatus, VisitorParkingStatus, AccessType, AccessMethod,
)
from app.modules.parking.schemas.parking import (
    ZoneCreate, FloorCreate, SlotCreate, SlotUpdate,
    AllocationCreate, VisitorParkingCreate, ViolationCreate, AccessLogCreate,
)
from app.modules.parking.repositories.parking_repo import (
    ParkingZoneRepo, ParkingFloorRepo, ParkingSlotRepo,
    ParkingAllocationRepo, VisitorParkingRepo, ParkingAccessLogRepo,
)
from app.models.user import User
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel


class ParkingService:

    def __init__(self, db: Session):
        self.db          = db
        self.zone_repo   = ParkingZoneRepo(db)
        self.floor_repo  = ParkingFloorRepo(db)
        self.slot_repo   = ParkingSlotRepo(db)
        self.alloc_repo  = ParkingAllocationRepo(db)
        self.visitor_repo= VisitorParkingRepo(db)
        self.access_repo = ParkingAccessLogRepo(db)

    def _slot_or_404(self, slot_id: UUID) -> ParkingSlot:
        s = self.slot_repo.get(slot_id)
        if not s: raise HTTPException(404, "Parking slot not found")
        return s

    def _audit(self, action, entity, entity_type, user, request=None, **kw):
        AuditService.log(db=self.db, action=action, module="parking",
                         entity_id=str(entity.id), entity_type=entity_type,
                         user=user, request=request, **kw)

    # ── Zone / Floor / Slot CRUD ──────────────────────────────────────────────

    def create_zone(self, data: ZoneCreate, user: User) -> ParkingZone:
        zone = ParkingZone(**data.model_dump())
        return self.zone_repo.create(zone)

    def list_zones(self, society_id: UUID) -> List[ParkingZone]:
        return self.zone_repo.get_by_society(society_id)

    def create_floor(self, data: FloorCreate, user: User) -> ParkingFloor:
        floor = ParkingFloor(**data.model_dump())
        return self.floor_repo.create(floor)

    def create_slot(self, data: SlotCreate, user: User) -> ParkingSlot:
        # Duplicate slot number check
        existing = self.slot_repo.get_by_number(data.society_id, data.slot_number)
        if existing:
            raise HTTPException(409, f"Slot {data.slot_number} already exists in this society")
        slot = ParkingSlot(**data.model_dump())
        self.slot_repo.create(slot)
        # Update zone total_slots
        zone = self.zone_repo.get(data.zone_id)
        if zone: zone.total_slots += 1
        self.db.commit()
        self.db.refresh(slot)
        return slot

    def update_slot(self, slot_id: UUID, data: SlotUpdate, user: User) -> ParkingSlot:
        slot = self._slot_or_404(slot_id)
        return self.slot_repo.update(slot, data.model_dump(exclude_none=True))

    def get_slot(self, slot_id: UUID) -> ParkingSlot:
        return self._slot_or_404(slot_id)

    def list_slots_by_zone(self, zone_id: UUID) -> List[ParkingSlot]:
        return self.slot_repo.get_by_zone(zone_id)

    def get_available_slots(self, society_id: UUID, slot_type=None) -> List[ParkingSlot]:
        return self.slot_repo.get_available(society_id, slot_type)

    # ── Allocation workflow ───────────────────────────────────────────────────

    def allocate_slot(self, data: AllocationCreate, user: User, request=None) -> ParkingAllocation:
        slot = self._slot_or_404(data.slot_id)

        # Validate slot is available
        if slot.status not in (SlotStatus.AVAILABLE,):
            raise HTTPException(409, f"Slot {slot.slot_number} is not available (status: {slot.status.value})")

        # Check no active allocation exists
        existing = self.alloc_repo.get_active_by_slot(data.slot_id)
        if existing:
            raise HTTPException(409, f"Slot {slot.slot_number} is already allocated")

        allocation = ParkingAllocation(**data.model_dump(), allocated_by=user.id)
        self.db.add(allocation)
        slot.status = SlotStatus.OCCUPIED
        self.db.flush()

        self._audit(AuditAction.CREATE, allocation, "ParkingAllocation", user, request,
                    new_values={"slot": slot.slot_number, "type": data.allocation_type.value})

        # Notify allocated user
        if data.allocated_to_user:
            NotificationService.send(
                db=self.db, user_id=data.allocated_to_user,
                title="Parking Slot Allocated",
                body=f"Parking slot {slot.slot_number} has been allocated to you.",
                type=NotificationType.INFO, channel=NotificationChannel.IN_APP,
                module="parking", entity_id=str(allocation.id),
            )
        self.db.commit()
        self.db.refresh(allocation)
        return allocation

    def release_slot(self, allocation_id: UUID, user: User, request=None) -> ParkingAllocation:
        alloc = self.alloc_repo.get(allocation_id)
        if not alloc: raise HTTPException(404, "Allocation not found")
        if alloc.status != AllocationStatus.ACTIVE:
            raise HTTPException(409, f"Allocation is already {alloc.status.value}")

        alloc.status      = AllocationStatus.RELEASED
        alloc.released_at = datetime.utcnow()
        alloc.released_by = user.id

        slot = self._slot_or_404(alloc.slot_id)
        slot.status = SlotStatus.AVAILABLE

        self._audit(AuditAction.UPDATE, alloc, "ParkingAllocation", user, request,
                    new_values={"status": "released"})
        self.db.commit()
        self.db.refresh(alloc)
        return alloc

    def get_allocations(self, society_id: UUID, skip=0, limit=50) -> List[ParkingAllocation]:
        return self.alloc_repo.get_by_society(society_id, skip, limit)

    def get_flat_allocations(self, flat_id: UUID) -> List[ParkingAllocation]:
        return self.alloc_repo.get_active_by_flat(flat_id)

    # ── Visitor parking ───────────────────────────────────────────────────────

    def assign_visitor_parking(self, data: VisitorParkingCreate,
                                user: User, request=None) -> VisitorParking:
        # Check duplicate active visitor parking
        existing = self.visitor_repo.get_active_by_vehicle(data.society_id, data.vehicle_number)
        if existing:
            raise HTTPException(409, f"Vehicle {data.vehicle_number} already has active visitor parking")

        # Mark slot as occupied if provided
        if data.slot_id:
            slot = self._slot_or_404(data.slot_id)
            if slot.status != SlotStatus.AVAILABLE:
                raise HTTPException(409, f"Visitor slot {slot.slot_number} is not available")
            slot.status = SlotStatus.OCCUPIED

        vp = VisitorParking(
            **data.model_dump(),
            assigned_by=user.id,
            check_in_time=datetime.utcnow(),
            temp_access_code=secrets.token_hex(4).upper(),
        )
        self.db.add(vp)
        self.db.flush()

        self._audit(AuditAction.CREATE, vp, "VisitorParking", user, request,
                    new_values={"vehicle": data.vehicle_number, "slot": str(data.slot_id)})
        # Log access entry
        self._log_access(data.society_id, data.vehicle_number, AccessType.ENTRY,
                         AccessMethod.MANUAL, user, slot_id=data.slot_id)
        self.db.commit()
        self.db.refresh(vp)
        return vp

    def checkout_visitor_parking(self, vp_id: UUID, user: User, request=None) -> VisitorParking:
        vp = self.visitor_repo.get(vp_id)
        if not vp: raise HTTPException(404, "Visitor parking not found")
        if vp.status != VisitorParkingStatus.ACTIVE:
            raise HTTPException(409, f"Visitor parking is already {vp.status.value}")

        vp.status         = VisitorParkingStatus.COMPLETED
        vp.check_out_time = datetime.utcnow()

        if vp.slot_id:
            slot = self._slot_or_404(vp.slot_id)
            slot.status = SlotStatus.AVAILABLE

        self._log_access(vp.society_id, vp.vehicle_number, AccessType.EXIT,
                         AccessMethod.MANUAL, user, slot_id=vp.slot_id)
        self.db.commit()
        self.db.refresh(vp)
        return vp

    def get_active_visitor_parking(self, society_id: UUID) -> List[VisitorParking]:
        return self.visitor_repo.get_active(society_id)

    # ── Violations ────────────────────────────────────────────────────────────

    def report_violation(self, data: ViolationCreate, user: User, request=None) -> ParkingViolation:
        violation = ParkingViolation(**data.model_dump(), reported_by=user.id)
        self.db.add(violation)
        self.db.flush()
        self._audit(AuditAction.CREATE, violation, "ParkingViolation", user, request,
                    new_values={"vehicle": data.vehicle_number, "type": data.violation_type.value})
        self.db.commit()
        self.db.refresh(violation)
        return violation

    def resolve_violation(self, violation_id: UUID, user: User) -> ParkingViolation:
        v = self.db.query(ParkingViolation).filter(ParkingViolation.id == violation_id).first()
        if not v: raise HTTPException(404, "Violation not found")
        v.is_resolved  = True
        v.resolved_at  = datetime.utcnow()
        v.resolved_by  = user.id
        self.db.commit()
        self.db.refresh(v)
        return v

    def get_violations(self, society_id: UUID, unresolved_only=False) -> List[ParkingViolation]:
        q = self.db.query(ParkingViolation).filter(ParkingViolation.society_id==society_id)
        if unresolved_only: q = q.filter(ParkingViolation.is_resolved==False)
        return q.order_by(ParkingViolation.created_at.desc()).limit(100).all()

    # ── Access logging ────────────────────────────────────────────────────────

    def _log_access(self, society_id, vehicle_number, access_type, access_method,
                    user, slot_id=None, rfid_tag=None, is_authorized=True):
        log = ParkingAccessLog(
            society_id=society_id, vehicle_number=vehicle_number,
            access_type=access_type, access_method=access_method,
            access_time=datetime.utcnow(), slot_id=slot_id,
            user_id=user.id, rfid_tag=rfid_tag, is_authorized=is_authorized,
        )
        self.db.add(log)

    def log_access(self, data: AccessLogCreate, user: User) -> ParkingAccessLog:
        log = ParkingAccessLog(**data.model_dump(), user_id=user.id, access_time=datetime.utcnow())
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_access_logs(self, society_id: UUID, skip=0, limit=100) -> List[ParkingAccessLog]:
        return self.access_repo.get_by_society(society_id, skip, limit)

    def get_vehicle_access_history(self, vehicle_number: str, skip=0, limit=50) -> List[ParkingAccessLog]:
        return self.access_repo.get_by_vehicle(vehicle_number, skip, limit)
