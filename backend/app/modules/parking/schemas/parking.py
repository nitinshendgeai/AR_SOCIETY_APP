from pydantic import BaseModel, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from app.schemas.common import OrmBase, TimestampSchema
from app.modules.parking.models.parking import (
    SlotType, SlotStatus, AllocationStatus, VisitorParkingStatus,
    ViolationType, AccessType, AccessMethod,
)


class ZoneCreate(OrmBase):
    society_id: UUID; name: str; code: Optional[str] = None
    description: Optional[str] = None

class ZoneOut(TimestampSchema):
    society_id: UUID; name: str; code: Optional[str]
    description: Optional[str]; total_slots: int


class FloorCreate(OrmBase):
    zone_id: UUID; society_id: UUID; name: str; level: Optional[int] = None

class FloorOut(TimestampSchema):
    zone_id: UUID; society_id: UUID; name: str; level: Optional[int]; total_slots: int


class SlotCreate(OrmBase):
    society_id: UUID; zone_id: UUID; floor_id: Optional[UUID] = None
    slot_number: str; slot_type: SlotType = SlotType.RESIDENT
    is_covered: bool = False; is_ev_charging: bool = False
    length_ft: Optional[int] = None; width_ft: Optional[int] = None
    notes: Optional[str] = None

class SlotUpdate(OrmBase):
    slot_type: Optional[SlotType]   = None
    status:    Optional[SlotStatus] = None
    is_covered: Optional[bool]      = None
    is_ev_charging: Optional[bool]  = None
    rfid_reader_id: Optional[str]   = None
    camera_id:      Optional[str]   = None
    barrier_id:     Optional[str]   = None
    notes:          Optional[str]   = None

class SlotOut(TimestampSchema):
    society_id: UUID; zone_id: UUID; floor_id: Optional[UUID]
    slot_number: str; slot_type: SlotType; status: SlotStatus
    is_covered: bool; is_ev_charging: bool
    rfid_reader_id: Optional[str]; camera_id: Optional[str]


class AllocationCreate(OrmBase):
    society_id: UUID; slot_id: UUID
    flat_id:    Optional[UUID]  = None
    vehicle_id: Optional[UUID]  = None
    allocated_to_user: Optional[UUID] = None
    allocation_type: SlotType   = SlotType.RESIDENT
    start_date: date
    end_date:   Optional[date]  = None
    monthly_charge: Optional[int] = None
    notes: Optional[str]        = None

class AllocationOut(TimestampSchema):
    society_id: UUID; slot_id: UUID; flat_id: Optional[UUID]
    vehicle_id: Optional[UUID]; allocation_type: SlotType
    status: AllocationStatus; start_date: date; end_date: Optional[date]
    monthly_charge: Optional[int]; released_at: Optional[datetime]


class VisitorParkingCreate(OrmBase):
    society_id:     UUID
    slot_id:        Optional[UUID] = None
    visitor_id:     Optional[UUID] = None
    vehicle_number: str
    vehicle_type:   Optional[str] = None
    host_flat_id:   Optional[UUID] = None
    expected_duration_hours: int = 4
    purpose: Optional[str] = None

    @field_validator("vehicle_number")
    @classmethod
    def normalize(cls, v): return v.upper().replace(" ", "").replace("-", "")

class VisitorParkingOut(TimestampSchema):
    society_id: UUID; slot_id: Optional[UUID]; vehicle_number: str
    vehicle_type: Optional[str]; status: VisitorParkingStatus
    check_in_time: Optional[datetime]; check_out_time: Optional[datetime]
    expected_duration_hours: int; temp_access_code: Optional[str]
    host_flat_id: Optional[UUID]


class ViolationCreate(OrmBase):
    society_id: UUID; slot_id: Optional[UUID] = None
    vehicle_number: str; vehicle_id: Optional[UUID] = None
    violation_type: ViolationType
    description: Optional[str] = None
    photo_url: Optional[str]   = None
    fine_amount: Optional[int] = None

class ViolationOut(TimestampSchema):
    society_id: UUID; slot_id: Optional[UUID]; vehicle_number: str
    violation_type: ViolationType; description: Optional[str]
    is_resolved: bool; resolved_at: Optional[datetime]; fine_amount: Optional[int]


class AccessLogCreate(OrmBase):
    society_id:    UUID
    vehicle_number: str
    access_type:   AccessType
    access_method: AccessMethod = AccessMethod.MANUAL
    slot_id:       Optional[UUID] = None
    vehicle_id:    Optional[UUID] = None
    gate_id:       Optional[UUID] = None
    rfid_tag:      Optional[str]  = None
    is_authorized: bool           = True
    notes:         Optional[str]  = None

class AccessLogOut(TimestampSchema):
    society_id: UUID; vehicle_number: str; access_type: AccessType
    access_method: AccessMethod; access_time: datetime
    slot_id: Optional[UUID]; is_authorized: bool; rfid_tag: Optional[str]
