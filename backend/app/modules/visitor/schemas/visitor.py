import re
from pydantic import BaseModel, Field, field_validator
from app.schemas import validators as val
from app.utils.vehicle_number import normalize_vehicle_number
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.schemas.common import OrmBase, TimestampSchema
from app.modules.visitor.models.visitor import VisitorType, VisitorStatus, GateType


# ── Gate ─────────────────────────────────────────────────────────────────────

class GateCreate(OrmBase):
    society_id: UUID
    name:       str = Field(max_length=100)
    gate_type:  GateType = GateType.BOTH
    location:   Optional[str] = Field(default=None, max_length=255)

    _name = field_validator("name", mode="before")(val.name)
    _location = field_validator("location", mode="before")(val.limited(255))


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

    @field_validator("vehicle_number", mode="before")
    @classmethod
    def _normalise_plate(cls, v):
        """Kept the way the gate looks plates up: spaces and dashes dropped, upper-case."""
        v = val.text(v) if isinstance(v, str) else v
        return normalize_vehicle_number(v) if v else None

    _type = field_validator("vehicle_type", mode="before")(val.limited(50))
    _model = field_validator("vehicle_model", mode="before")(val.limited(100))
    _color = field_validator("vehicle_color", mode="before")(val.limited(50))

    @field_validator("vehicle_number", mode="before")
    @classmethod
    def _plate(cls, v):
        v = val.text(v)
        if v is None:
            return None
        v = normalize_vehicle_number(v)
        if not re.fullmatch(r"[A-Z0-9]{4,20}", v):
            raise ValueError("Enter a valid vehicle number, e.g. MH12AB1234")
        return v


class VehicleOut(TimestampSchema):
    vehicle_type:   Optional[str]
    vehicle_number: Optional[str]
    vehicle_model:  Optional[str]
    vehicle_color:  Optional[str]


# ── Visitor ───────────────────────────────────────────────────────────────────

class VisitorCreate(OrmBase):
    name:             str = Field(max_length=255)
    mobile:           str
    visitor_type:     VisitorType      = VisitorType.GUEST
    purpose:          Optional[str]    = None
    society_id:       UUID
    flat_id:          Optional[UUID]   = None
    resident_id:      Optional[UUID]   = None
    gate_id:          Optional[UUID]   = None
    expected_arrival: Optional[datetime] = None
    vehicle:          Optional[VehicleIn] = None

    _name = field_validator("name", mode="before")(val.name)
    _mobile = field_validator("mobile", mode="before")(val.mobile_any)
    _purpose = field_validator("purpose", mode="before")(val.limited(500))

    @field_validator("vehicle")
    @classmethod
    def _no_empty_vehicle(cls, v):
        if v is not None and not any([v.vehicle_type, v.vehicle_number, v.vehicle_model, v.vehicle_color]):
            return None
        return v


class VisitorApproveRequest(OrmBase):
    notes: Optional[str] = None

    _notes = field_validator("notes", mode="before")(val.note_max(1000))


class VisitorRejectRequest(OrmBase):
    reason: str

    _reason = field_validator("reason", mode="before")(val.note_max(1000, required=True))


class VisitorCheckInRequest(OrmBase):
    gate_id: Optional[UUID] = None
    notes:   Optional[str]  = None

    _notes = field_validator("notes", mode="before")(val.note_max(1000))


class VisitorCheckOutRequest(OrmBase):
    gate_id: Optional[UUID] = None
    notes:   Optional[str]  = None

    _notes = field_validator("notes", mode="before")(val.note_max(1000))


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
    flat_number:      Optional[str] = None
    wing_name:        Optional[str] = None
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
