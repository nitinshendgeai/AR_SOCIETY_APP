import secrets
from datetime import datetime, date
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy import func, or_
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
from app.models.vehicle import Vehicle
from app.models.resident import Resident
from app.models.tenant import Tenant
from app.models.flat import Flat
from app.models.wing import Wing
from app.models.society import Society
from app.core.tenant_scope import assert_society_access, resolve_create_society_id
from app.utils.local_time import zone, local_today
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel
from app.utils.vehicle_number import normalize_vehicle_number


from app.utils.auto_code import short_code


class ParkingService:

    def __init__(self, db: Session):
        self.db          = db
        self.zone_repo   = ParkingZoneRepo(db)
        self.floor_repo  = ParkingFloorRepo(db)
        self.slot_repo   = ParkingSlotRepo(db)
        self.alloc_repo  = ParkingAllocationRepo(db)
        self.visitor_repo= VisitorParkingRepo(db)
        self.access_repo = ParkingAccessLogRepo(db)

    # ── Society scope ─────────────────────────────────────────────────────────
    # Role checks say what a caller may do; these say which society's data it may
    # touch. A society-scoped caller is confined to its own society; a platform
    # admin (society_id None) may work in any. Something that belongs to another
    # society is reported as not found, so ids can't be probed.

    @staticmethod
    def _in_scope(user: Optional[User], society_id) -> bool:
        return user is None or user.society_id is None or user.society_id == society_id

    def _scoped_or_404(self, row, user: Optional[User], what: str):
        if row is None or not self._in_scope(user, row.society_id):
            raise HTTPException(404, f"{what} not found")
        return row

    def _today(self, society_id: UUID) -> date:
        society = self.db.query(Society).filter(Society.id == society_id).first()
        return local_today(zone(society.timezone if society else None))

    def _slot_or_404(self, slot_id: UUID, user: Optional[User] = None) -> ParkingSlot:
        return self._scoped_or_404(self.slot_repo.get(slot_id), user, "Parking slot")

    def _zone_or_404(self, zone_id: UUID, user: Optional[User], society_id: UUID) -> ParkingZone:
        z = self.zone_repo.get(zone_id)
        if z is None or z.society_id != society_id or not self._in_scope(user, z.society_id):
            raise HTTPException(404, "Parking zone not found")
        return z

    def _same_society_slot(self, slot_id: Optional[UUID], society_id: UUID, user: Optional[User]):
        if slot_id is None:
            return None
        slot = self._slot_or_404(slot_id, user)
        if slot.society_id != society_id:
            raise HTTPException(404, "Parking slot not found")
        return slot

    def _flat_in_society(self, flat_id: Optional[UUID], society_id: UUID) -> Optional[Flat]:
        if flat_id is None:
            return None
        flat = self.db.query(Flat).join(Wing, Flat.wing_id == Wing.id).filter(
            Flat.id == flat_id, Wing.society_id == society_id).first()
        if flat is None:
            raise HTTPException(404, "Flat not found")
        return flat

    def _audit(self, action, entity, entity_type, user, request=None, **kw):
        AuditService.log(db=self.db, action=action, module="parking",
                         entity_id=str(entity.id), entity_type=entity_type,
                         user=user, request=request, **kw)

    # ── Zone / Floor / Slot CRUD ──────────────────────────────────────────────

    def create_zone(self, data: ZoneCreate, user: User) -> ParkingZone:
        society_id = resolve_create_society_id(user, data.society_id)
        payload = {**data.model_dump(), "society_id": society_id}
        if not (payload.get("code") or "").strip():
            # No code given: the app makes one from the name ("Basement" -> "BAS").
            payload["code"] = short_code(data.name, [z.code for z in self.zone_repo.get_by_society(society_id)])
        zone_row = ParkingZone(**payload)
        return self.zone_repo.create(zone_row)

    def list_zones(self, society_id: UUID, user: User) -> List[ParkingZone]:
        assert_society_access(user, society_id)
        return self.zone_repo.get_by_society(society_id)

    def create_floor(self, data: FloorCreate, user: User) -> ParkingFloor:
        society_id = resolve_create_society_id(user, data.society_id)
        self._zone_or_404(data.zone_id, user, society_id)
        floor = ParkingFloor(**{**data.model_dump(), "society_id": society_id})
        return self.floor_repo.create(floor)

    def create_slot(self, data: SlotCreate, user: User) -> ParkingSlot:
        society_id = resolve_create_society_id(user, data.society_id)
        zone_row = self._zone_or_404(data.zone_id, user, society_id)
        if data.floor_id is not None:
            floor = self.floor_repo.get(data.floor_id)
            if floor is None or floor.society_id != society_id or floor.zone_id != zone_row.id:
                raise HTTPException(404, "Parking floor not found")
        # Duplicate slot number check
        existing = self.slot_repo.get_by_number(society_id, data.slot_number)
        if existing:
            raise HTTPException(409, f"Slot {data.slot_number} already exists in this society")
        slot = ParkingSlot(**{**data.model_dump(), "society_id": society_id})
        self.slot_repo.create(slot)
        zone_row.total_slots += 1
        self.db.commit()
        self.db.refresh(slot)
        return slot

    def update_slot(self, slot_id: UUID, data: SlotUpdate, user: User) -> ParkingSlot:
        slot = self._slot_or_404(slot_id, user)
        return self.slot_repo.update(slot, data.model_dump(exclude_none=True))

    def get_slot(self, slot_id: UUID, user: User) -> ParkingSlot:
        return self._slot_or_404(slot_id, user)

    def list_slots_by_zone(self, zone_id: UUID, user: User) -> List[ParkingSlot]:
        z = self.zone_repo.get(zone_id)
        self._scoped_or_404(z, user, "Parking zone")
        return self.slot_repo.get_by_zone(zone_id)

    def get_available_slots(self, society_id: UUID, user: User, slot_type=None) -> List[ParkingSlot]:
        assert_society_access(user, society_id)
        self.expire_due_allocations(society_id)
        return self.slot_repo.get_available(society_id, slot_type)

    def list_slots_by_society(self, society_id: UUID, user: User) -> List[ParkingSlot]:
        assert_society_access(user, society_id)
        self.expire_due_allocations(society_id)
        return self.slot_repo.get_by_society(society_id)

    # ── Allocation workflow ───────────────────────────────────────────────────

    def expire_due_allocations(self, society_id: UUID) -> int:
        """Allocations whose end date has passed stop counting: mark them expired and
        free their slot. There is no background job, so this runs whenever slots or
        allocations are read or a slot is allotted; the gate check also ignores a
        lapsed allocation on its own, so it never depends on this having run."""
        today = self._today(society_id)
        due = self.db.query(ParkingAllocation).filter(
            ParkingAllocation.society_id == society_id, ParkingAllocation.is_active == True,
            ParkingAllocation.status == AllocationStatus.ACTIVE,
            ParkingAllocation.end_date != None, ParkingAllocation.end_date < today).all()
        for alloc in due:
            alloc.status = AllocationStatus.EXPIRED
            alloc.released_at = datetime.utcnow()
            slot = self.slot_repo.get(alloc.slot_id)
            if slot is not None and slot.status == SlotStatus.OCCUPIED:
                slot.status = SlotStatus.AVAILABLE
            self._clear_vehicle_slot_field(alloc, slot)
        if due:
            self.db.commit()
        return len(due)

    def _clear_vehicle_slot_field(self, alloc: ParkingAllocation, slot: Optional[ParkingSlot]) -> None:
        """Vehicle.parking_slot mirrors an allotment so the resident sees it on their
        vehicle; take it back when that allotment ends."""
        if alloc.vehicle_id and slot is not None:
            vehicle = self.db.query(Vehicle).filter(Vehicle.id == alloc.vehicle_id).first()
            if vehicle is not None and vehicle.parking_slot == slot.slot_number:
                vehicle.parking_slot = None

    def allocate_slot(self, data: AllocationCreate, user: User, request=None) -> ParkingAllocation:
        society_id = resolve_create_society_id(user, data.society_id)
        self.expire_due_allocations(society_id)
        slot = self._same_society_slot(data.slot_id, society_id, user)
        self._flat_in_society(data.flat_id, society_id)
        if data.end_date is not None and data.end_date < data.start_date:
            raise HTTPException(422, "The end date can't be before the start date")
        today = self._today(society_id)
        if data.end_date is not None and data.end_date < today:
            raise HTTPException(422, "That parking has already ended — choose an end date from today on")

        vehicle = None
        if data.vehicle_id is not None:
            vehicle = self.db.query(Vehicle).filter(
                Vehicle.id == data.vehicle_id, Vehicle.society_id == society_id,
                Vehicle.is_active == True).first()
            if vehicle is None:
                raise HTTPException(404, "Vehicle not found")
            if data.flat_id is not None and vehicle.flat_id not in (None, data.flat_id):
                raise HTTPException(422, "That vehicle is registered to a different flat")
            held = self.alloc_repo.get_active_by_vehicle(vehicle.id)
            if held is not None:
                raise HTTPException(409, f"{vehicle.vehicle_number} already has parking "
                                         f"(slot {held.slot_number}). Release it first.")

        # Validate slot is available
        if slot.status not in (SlotStatus.AVAILABLE,):
            raise HTTPException(409, f"Slot {slot.slot_number} is not available (status: {slot.status.value})")

        # Check no active allocation exists
        existing = self.alloc_repo.get_active_by_slot(data.slot_id)
        if existing:
            raise HTTPException(409, f"Slot {slot.slot_number} is already allocated")

        allocation = ParkingAllocation(**{**data.model_dump(), "society_id": society_id}, allocated_by=user.id)
        self.db.add(allocation)
        slot.status = SlotStatus.OCCUPIED
        if vehicle is not None and not vehicle.parking_slot and data.start_date <= today:
            vehicle.parking_slot = slot.slot_number
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
        alloc = self._scoped_or_404(self.alloc_repo.get(allocation_id), user, "Allocation")
        if alloc.status != AllocationStatus.ACTIVE:
            raise HTTPException(409, f"Allocation is already {alloc.status.value}")

        alloc.status      = AllocationStatus.RELEASED
        alloc.released_at = datetime.utcnow()
        alloc.released_by = user.id

        slot = self._slot_or_404(alloc.slot_id)
        slot.status = SlotStatus.AVAILABLE
        self._clear_vehicle_slot_field(alloc, slot)

        self._audit(AuditAction.UPDATE, alloc, "ParkingAllocation", user, request,
                    new_values={"status": "released"})
        self.db.commit()
        self.db.refresh(alloc)
        return alloc

    @staticmethod
    def release_for_vehicles(db: Session, vehicle_ids: List[UUID], user: Optional[User] = None) -> int:
        """End the parking of vehicles that are leaving the society's books: a resident
        or tenant moving out, or a vehicle being deregistered. Their allocations are
        released, the slots freed, and the vehicle's own slot field cleared, so a car
        that no longer belongs here is not waved through the gate and its slot is
        not locked up forever. Caller commits."""
        if not vehicle_ids:
            return 0
        allocations = db.query(ParkingAllocation).filter(
            ParkingAllocation.vehicle_id.in_(vehicle_ids), ParkingAllocation.is_active == True,
            ParkingAllocation.status == AllocationStatus.ACTIVE).all()
        for alloc in allocations:
            alloc.status = AllocationStatus.RELEASED
            alloc.released_at = datetime.utcnow()
            alloc.released_by = user.id if user else None
            slot = db.query(ParkingSlot).filter(ParkingSlot.id == alloc.slot_id).first()
            if slot is not None and slot.status == SlotStatus.OCCUPIED:
                slot.status = SlotStatus.AVAILABLE
        db.query(Vehicle).filter(Vehicle.id.in_(vehicle_ids)).update(
            {"parking_slot": None}, synchronize_session=False)
        return len(allocations)

    def get_allocations(self, society_id: UUID, user: User, skip=0, limit=50) -> List[ParkingAllocation]:
        assert_society_access(user, society_id)
        self.expire_due_allocations(society_id)
        return self.alloc_repo.get_by_society(society_id, skip, limit)

    def get_flat_allocations(self, flat_id: UUID, user: User) -> List[ParkingAllocation]:
        flat = self.db.query(Flat).join(Wing, Flat.wing_id == Wing.id).filter(Flat.id == flat_id)
        if user.society_id is not None:
            flat = flat.filter(Wing.society_id == user.society_id)
        if flat.first() is None:
            raise HTTPException(404, "Flat not found")
        return self.alloc_repo.get_active_by_flat(flat_id)

    # ── Visitor parking ───────────────────────────────────────────────────────

    def assign_visitor_parking(self, data: VisitorParkingCreate,
                                user: User, request=None) -> VisitorParking:
        society_id = resolve_create_society_id(user, data.society_id)
        self._flat_in_society(data.host_flat_id, society_id)
        # Check duplicate active visitor parking
        existing = self.visitor_repo.get_active_by_vehicle(society_id, data.vehicle_number)
        if existing:
            raise HTTPException(409, f"Vehicle {data.vehicle_number} already has active visitor parking")

        # Mark slot as occupied if provided
        if data.slot_id:
            slot = self._same_society_slot(data.slot_id, society_id, user)
            if slot.status != SlotStatus.AVAILABLE:
                raise HTTPException(409, f"Visitor slot {slot.slot_number} is not available")
            slot.status = SlotStatus.OCCUPIED

        vp = VisitorParking(
            **{**data.model_dump(), "society_id": society_id},
            assigned_by=user.id,
            check_in_time=datetime.utcnow(),
            temp_access_code=secrets.token_hex(4).upper(),
        )
        self.db.add(vp)
        self.db.flush()

        self._audit(AuditAction.CREATE, vp, "VisitorParking", user, request,
                    new_values={"vehicle": data.vehicle_number, "slot": str(data.slot_id)})
        # Log access entry
        self._log_access(society_id, data.vehicle_number, AccessType.ENTRY,
                         AccessMethod.MANUAL, user, slot_id=data.slot_id)
        self.db.commit()
        self.db.refresh(vp)
        return vp

    def checkout_visitor_parking(self, vp_id: UUID, user: User, request=None) -> VisitorParking:
        vp = self._scoped_or_404(self.visitor_repo.get(vp_id), user, "Visitor parking")
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

    def get_active_visitor_parking(self, society_id: UUID, user: User) -> List[VisitorParking]:
        assert_society_access(user, society_id)
        return self.visitor_repo.get_active(society_id)

    # ── Violations ────────────────────────────────────────────────────────────

    def report_violation(self, data: ViolationCreate, user: User, request=None) -> ParkingViolation:
        society_id = resolve_create_society_id(user, data.society_id)
        self._same_society_slot(data.slot_id, society_id, user)
        if data.vehicle_id is not None:
            if self.db.query(Vehicle.id).filter(Vehicle.id == data.vehicle_id,
                                                Vehicle.society_id == society_id).first() is None:
                raise HTTPException(404, "Vehicle not found")
        violation = ParkingViolation(**{**data.model_dump(), "society_id": society_id}, reported_by=user.id)
        self.db.add(violation)
        self.db.flush()
        self._audit(AuditAction.CREATE, violation, "ParkingViolation", user, request,
                    new_values={"vehicle": data.vehicle_number, "type": data.violation_type.value})
        self.db.commit()
        self.db.refresh(violation)
        return violation

    def resolve_violation(self, violation_id: UUID, user: User) -> ParkingViolation:
        v = self.db.query(ParkingViolation).filter(ParkingViolation.id == violation_id).first()
        self._scoped_or_404(v, user, "Violation")
        v.is_resolved  = True
        v.resolved_at  = datetime.utcnow()
        v.resolved_by  = user.id
        self.db.commit()
        self.db.refresh(v)
        return v

    def get_violations(self, society_id: UUID, user: User, unresolved_only=False) -> List[ParkingViolation]:
        assert_society_access(user, society_id)
        q = self.db.query(ParkingViolation).filter(ParkingViolation.society_id==society_id)
        if unresolved_only: q = q.filter(ParkingViolation.is_resolved==False)
        return q.order_by(ParkingViolation.created_at.desc()).limit(100).all()

    # ── Gate validation ───────────────────────────────────────────────────────

    @staticmethod
    def _plate_matches(column, normalized: str):
        """Compare a stored plate to a normalised one the way the unique index on
        vehicles does (spaces and dashes dropped, upper-case), so a plate saved as
        'MH 12 AB 1234' is still found by 'MH12AB1234'."""
        return func.upper(func.replace(func.replace(column, " ", ""), "-", "")) == normalized

    def _resolve_parking_slot(self, vehicle: Vehicle, today: date) -> Optional[str]:
        """A vehicle counts as having parking allotted/rented either way this
        society manages it: the simple Vehicle.parking_slot field some
        societies set directly, or a formal ParkingAllocation that is active
        today (started, not yet ended). Returns the slot number, else None."""
        if vehicle.parking_slot:
            return vehicle.parking_slot
        alloc = self.alloc_repo.get_active_by_vehicle(vehicle.id, on=today)
        if alloc:
            slot = self.slot_repo.get(alloc.slot_id)
            return slot.slot_number if slot else None
        return None

    def _visitor_vehicle(self, society_id: UUID, normalized: str):
        """A visitor whose vehicle the guard logged in the Visitors module and whom a
        resident has approved (or who is already inside). Returns the Visitor."""
        from app.modules.visitor.models.visitor import Visitor, VisitorVehicle, VisitorStatus
        return self.db.query(Visitor).join(VisitorVehicle, VisitorVehicle.visitor_id == Visitor.id).filter(
            Visitor.society_id == society_id, Visitor.is_active == True,
            Visitor.status.in_([VisitorStatus.APPROVED, VisitorStatus.CHECKED_IN]),
            self._plate_matches(VisitorVehicle.vehicle_number, normalized),
        ).order_by(Visitor.created_at.desc()).first()

    def _lookup_gate_status(self, society_id: UUID, normalized_number: str):
        """The single source of truth for "is this vehicle allowed in" —
        shared by the read-only pre-entry check (validate_vehicle_at_gate)
        and log_access, so a client can never talk the access log into
        recording an authorization the lookup itself didn't grant.

        A resident/tenant vehicle is only authorized if it has parking
        actually allotted or rented (see _resolve_parking_slot) — being
        registered to a flat is not, on its own, permission to park; a
        household's un-allotted second/third car should be flagged so the
        guard can send it elsewhere, not waved through.

        A visitor's vehicle is allowed while the visitor has active visitor
        parking, or has been approved by a resident / checked in.

        Returns (authorized, vehicle_or_None, visitor_parking_or_None,
        parking_slot_or_None, visitor_or_None)."""
        # Parking whose end date has passed stops counting right now, not whenever the
        # committee next opens the allocations list.
        self.expire_due_allocations(society_id)
        vehicle = self.db.query(Vehicle).filter(
            Vehicle.society_id == society_id,
            self._plate_matches(Vehicle.vehicle_number, normalized_number),
            Vehicle.is_active == True,
        ).first()
        if vehicle:
            parking_slot = self._resolve_parking_slot(vehicle, self._today(society_id))
            return bool(parking_slot), vehicle, None, parking_slot, None

        visitor_parking = self.visitor_repo.get_active_by_vehicle(society_id, normalized_number)
        if visitor_parking:
            return True, None, visitor_parking, None, None

        visitor = self._visitor_vehicle(society_id, normalized_number)
        if visitor:
            return True, None, None, None, visitor

        return False, None, None, None, None

    def validate_vehicle_at_gate(self, society_id: UUID, vehicle_number: str) -> dict:
        normalized = normalize_vehicle_number(vehicle_number)
        authorized, vehicle, visitor_parking, parking_slot, visitor = self._lookup_gate_status(society_id, normalized)

        if vehicle:
            owner_name, category = None, "resident"
            if vehicle.resident_id:
                resident = self.db.query(Resident).filter(Resident.id == vehicle.resident_id).first()
                owner_name, category = (resident.full_name if resident else None), "resident"
            elif vehicle.tenant_id:
                tenant = self.db.query(Tenant).filter(Tenant.id == vehicle.tenant_id).first()
                owner_name, category = (tenant.full_name if tenant else None), "tenant"

            flat = self.db.query(Flat).filter(Flat.id == vehicle.flat_id).first() if vehicle.flat_id else None
            message = (
                "Registered vehicle with allotted parking — access granted" if authorized
                else "Registered vehicle has no allotted/rented parking — access not authorized"
            )

            return {
                "vehicle_number": normalized,
                "authorized":     authorized,
                "status":         "allowed" if authorized else "no_parking",
                "category":       category,
                "vehicle_type":   vehicle.vehicle_type.value,
                "flat_number":    flat.flat_number if flat else None,
                "wing_name":      flat.wing.name if flat and flat.wing else None,
                "owner_name":     owner_name,
                "parking_slot":   parking_slot,
                "message":        message,
            }

        if visitor_parking:
            host_flat = self.db.query(Flat).filter(Flat.id == visitor_parking.host_flat_id).first() \
                if visitor_parking.host_flat_id else None
            return {
                "vehicle_number":         normalized,
                "authorized":             True,
                "status":                 "allowed",
                "category":               "visitor",
                "vehicle_type":           visitor_parking.vehicle_type,
                "flat_number":            host_flat.flat_number if host_flat else None,
                "wing_name":              host_flat.wing.name if host_flat and host_flat.wing else None,
                "visitor_purpose":        visitor_parking.purpose,
                "visitor_check_in_time":  visitor_parking.check_in_time,
                "message":                "Active visitor parking — access granted",
            }

        if visitor:
            flat = self.db.query(Flat).filter(Flat.id == visitor.flat_id).first() if visitor.flat_id else None
            return {
                "vehicle_number":         normalized,
                "authorized":             True,
                "status":                 "allowed",
                "category":               "visitor",
                "vehicle_type":           visitor.vehicle.vehicle_type if visitor.vehicle else None,
                "flat_number":            flat.flat_number if flat else None,
                "wing_name":              flat.wing.name if flat and flat.wing else None,
                "owner_name":             visitor.name,
                "visitor_purpose":        visitor.purpose,
                "visitor_check_in_time":  visitor.checked_in_at,
                "message":                ("Visitor already inside — access granted" if visitor.checked_in_at
                                           else "Visitor approved by the resident — access granted"),
            }

        return {
            "vehicle_number": normalized,
            "authorized":     False,
            "status":         "unregistered",
            "category":       "unregistered",
            "message":        "Vehicle not registered — verify manually before allowing entry",
        }

    # ── Registered vehicles and their parking ─────────────────────────────────

    def vehicles_overview(self, society_id: UUID, user: User, parking: Optional[str] = None) -> List[dict]:
        """Every vehicle a resident or tenant has registered, with whether it has
        parking — the list the committee works from to allot parking. `parking` is
        'none' for vehicles still without parking, 'allotted' for those with it."""
        assert_society_access(user, society_id)
        self.expire_due_allocations(society_id)
        today = self._today(society_id)
        vehicles = self.db.query(Vehicle).filter(
            Vehicle.society_id == society_id, Vehicle.is_active == True
        ).order_by(Vehicle.vehicle_number).all()

        allocations = {}
        for alloc in self.db.query(ParkingAllocation).filter(
                ParkingAllocation.society_id == society_id, ParkingAllocation.is_active == True,
                ParkingAllocation.status == AllocationStatus.ACTIVE,
                ParkingAllocation.vehicle_id != None, ParkingAllocation.start_date <= today).all():
            allocations[alloc.vehicle_id] = alloc

        rows = []
        for v in vehicles:
            alloc = allocations.get(v.id)
            slot = alloc.slot_number if alloc else v.parking_slot
            has = bool(slot)
            if parking == "none" and has:
                continue
            if parking == "allotted" and not has:
                continue
            owner = (v.resident.full_name if v.resident else (v.tenant.full_name if v.tenant else None))
            rows.append({
                "id": v.id, "vehicle_number": v.vehicle_number, "vehicle_type": v.vehicle_type.value,
                "make": v.make, "model": v.model, "color": v.color,
                "flat_id": v.flat_id, "flat_number": v.flat.flat_number if v.flat else None,
                "wing_name": v.flat.wing.name if v.flat and v.flat.wing else None,
                "owner_name": owner,
                "category": "tenant" if v.tenant_id else "resident",
                "has_parking": has, "parking_slot": slot,
                "allocation_id": alloc.id if alloc else None,
                "allocation_type": alloc.allocation_type.value if alloc else None,
                "end_date": alloc.end_date if alloc else None,
                "monthly_charge": alloc.monthly_charge if alloc else None,
            })
        return rows

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
        society_id = resolve_create_society_id(user, data.society_id)
        self._same_society_slot(data.slot_id, society_id, user)
        normalized = normalize_vehicle_number(data.vehicle_number)
        authorized, vehicle, _, _, _ = self._lookup_gate_status(society_id, normalized)
        log = ParkingAccessLog(
            society_id=society_id, vehicle_number=normalized,
            access_type=data.access_type, access_method=data.access_method,
            slot_id=data.slot_id, gate_id=data.gate_id, rfid_tag=data.rfid_tag,
            notes=data.notes, vehicle_id=vehicle.id if vehicle else None,
            is_authorized=authorized, user_id=user.id, access_time=datetime.utcnow(),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_access_logs(self, society_id: UUID, user: User, skip=0, limit=100) -> List[ParkingAccessLog]:
        assert_society_access(user, society_id)
        return self.access_repo.get_by_society(society_id, skip, limit)

    def get_vehicle_access_history(self, vehicle_number: str, user: User,
                                   society_id: Optional[UUID] = None, skip=0, limit=50) -> List[ParkingAccessLog]:
        """A plate's gate history within one society: the caller's own, or — for a
        platform admin — the one named."""
        scope = user.society_id if user.society_id is not None else society_id
        if scope is None:
            raise HTTPException(400, "society_id is required")
        return self.access_repo.get_by_vehicle(normalize_vehicle_number(vehicle_number), scope, skip, limit)
