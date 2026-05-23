from pydantic import BaseModel, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import date, time, datetime
from app.schemas.common import OrmBase, TimestampSchema
from app.modules.amenity.models.amenity import AmenityType, BookingStatus, RuleType


# ── Amenity ───────────────────────────────────────────────────────────────────

class AmenityCreate(OrmBase):
    society_id:        UUID
    name:              str
    amenity_type:      AmenityType
    description:       Optional[str]  = None
    location:          Optional[str]  = None
    capacity:          Optional[int]  = None
    open_time:         Optional[time] = None
    close_time:        Optional[time] = None
    booking_required:  bool           = True
    approval_required: bool           = False
    is_chargeable:     bool           = False
    image_url:         Optional[str]  = None


class AmenityUpdate(OrmBase):
    name:              Optional[str]  = None
    description:       Optional[str]  = None
    location:          Optional[str]  = None
    capacity:          Optional[int]  = None
    open_time:         Optional[time] = None
    close_time:        Optional[time] = None
    booking_required:  Optional[bool] = None
    approval_required: Optional[bool] = None
    is_chargeable:     Optional[bool] = None
    image_url:         Optional[str]  = None


class AmenityOut(TimestampSchema):
    society_id:        UUID
    name:              str
    amenity_type:      AmenityType
    description:       Optional[str]
    location:          Optional[str]
    capacity:          Optional[int]
    open_time:         Optional[time]
    close_time:        Optional[time]
    booking_required:  bool
    approval_required: bool
    is_chargeable:     bool
    image_url:         Optional[str]


# ── Rules ─────────────────────────────────────────────────────────────────────

class RuleCreate(OrmBase):
    rule_type:   RuleType
    rule_value:  Optional[str] = None
    description: Optional[str] = None


class RuleOut(TimestampSchema):
    amenity_id:  UUID
    rule_type:   RuleType
    rule_value:  Optional[str]
    description: Optional[str]


# ── Pricing ───────────────────────────────────────────────────────────────────

class PricingCreate(OrmBase):
    label:          str
    price_per_hour: Optional[float] = None
    flat_price:     Optional[float] = None
    deposit_amount: Optional[float] = None
    is_default:     bool            = False


class PricingOut(TimestampSchema):
    amenity_id:     UUID
    label:          str
    price_per_hour: Optional[float]
    flat_price:     Optional[float]
    deposit_amount: Optional[float]
    is_default:     bool


# ── Blackout ──────────────────────────────────────────────────────────────────

class BlackoutCreate(OrmBase):
    blackout_date: date
    reason:        Optional[str] = None


class BlackoutOut(TimestampSchema):
    amenity_id:    UUID
    blackout_date: date
    reason:        Optional[str]


# ── Slot ──────────────────────────────────────────────────────────────────────

class SlotCreate(OrmBase):
    slot_date:    date
    start_time:   time
    end_time:     time
    max_capacity: Optional[int] = None


class SlotOut(TimestampSchema):
    amenity_id:   UUID
    slot_date:    date
    start_time:   time
    end_time:     time
    max_capacity: Optional[int]
    booked_count: int
    is_available: bool


# ── Booking ───────────────────────────────────────────────────────────────────

class BookingCreate(OrmBase):
    amenity_id:    UUID
    society_id:    UUID
    flat_id:       Optional[UUID] = None
    booking_date:  date
    start_time:    time
    end_time:      time
    guest_count:   int            = 1
    purpose:       Optional[str]  = None
    special_notes: Optional[str]  = None

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v, info):
        if "start_time" in info.data and v <= info.data["start_time"]:
            raise ValueError("end_time must be after start_time")
        return v


class BookingApproveRequest(OrmBase):
    notes: Optional[str] = None


class BookingRejectRequest(OrmBase):
    reason: str


class BookingCancelRequest(OrmBase):
    reason: Optional[str] = None


class UsageLogCreate(OrmBase):
    actual_start:  Optional[datetime] = None
    actual_end:    Optional[datetime] = None
    guest_count:   Optional[int]      = None
    damage_noted:  bool               = False
    damage_notes:  Optional[str]      = None
    extra_charges: Optional[float]    = None


class BookingOut(TimestampSchema):
    amenity_id:      UUID
    society_id:      UUID
    flat_id:         Optional[UUID]
    booked_by:       UUID
    booking_date:    date
    start_time:      time
    end_time:        time
    guest_count:     int
    purpose:         Optional[str]
    status:          BookingStatus
    approved_by:     Optional[UUID]
    approved_at:     Optional[datetime]
    rejection_reason: Optional[str]
    cancelled_at:    Optional[datetime]
    charge_amount:   Optional[float]
    deposit_amount:  Optional[float]
    deposit_paid:    bool
