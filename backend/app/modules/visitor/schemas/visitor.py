from pydantic import BaseModel, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.schemas.common import OrmBase, TimestampSchema
from app.modules.visitor.models.visitor import VisitorType, VisitorStatus, GateType


# ── Gate ─────────────────────────────────────────────────────────────────────

class GateCreate(OrmBase):
    society_id: UUID
    name:       str
    gate_type:  GateType = GateType.BOTH
    location:   Optional[str] = None


class GateOut(TimestampSchema):
    society_id: UUID
    name:       str
    gate_type:  GateType
    location:   Optional[str]


# ── Vehicle ───────────────────────────────────────────────────────────────────

class VehicleIn(OrmBase):
    vehicle_type:   Optional[str] = None
    vehicle_number: Optional[str] = None
    vehicle_model:  Optional[str] = None
    vehicle_color:  Optional[str] = None


class VehicleOut(TimestampSchema):
    vehicle_type:   Optional[str]
    vehicle_number: Optional[str]
    vehicle_model:  Optional[str]
    vehicle_color:  Optional[str]


# ── Visitor ───────────────────────────────────────────────────────────────────

class VisitorCreate(OrmBase):
    name:             str
    mobile:           str
    visitor_type:     VisitorType      = VisitorType.GUEST
    purpose:          Optional[str]    = None
    society_id:       UUID
    flat_id:          Optional[UUID]   = None
    resident_id:      Optional[UUID]   = None
    gate_id:          Optional[UUID]   = None
    expected_arrival: Optional[datetime] = None
    vehicle:          Optional[VehicleIn] = None

    @field_validator("mobile")
    @classmethod
    def mobile_valid(cls, v):
        if not v.replace("+", "").replace("-", "").replace(" ", "").isdigit():
            raise ValueError("Invalid mobile number")
        return v


class VisitorApproveRequest(OrmBase):
    notes: Optional[str] = None


class VisitorRejectRequest(OrmBase):
    reason: str


class VisitorCheckInRequest(OrmBase):
    gate_id: Optional[UUID] = None
    notes:   Optional[str]  = None


class VisitorCheckOutRequest(OrmBase):
    gate_id: Optional[UUID] = None
    notes:   Optional[str]  = None


class VisitorLogOut(TimestampSchema):
    visitor_id:   UUID
    action:       str
    notes:        Optional[str]
    gate_id:      Optional[UUID]


class VisitorOut(TimestampSchema):
    name:             str
    mobile:           str
    visitor_type:     VisitorType
    purpose:          Optional[str]
    society_id:       UUID
    flat_id:          Optional[UUID]
    resident_id:      Optional[UUID]
    gate_id:          Optional[UUID]
    status:           VisitorStatus
    expected_arrival: Optional[datetime]
    checked_in_at:    Optional[datetime]
    checked_out_at:   Optional[datetime]
    approved_at:      Optional[datetime]
    rejection_reason: Optional[str]
    qr_token:         Optional[str]
    vehicle:          Optional[VehicleOut]
    logs:             List[VisitorLogOut] = []
