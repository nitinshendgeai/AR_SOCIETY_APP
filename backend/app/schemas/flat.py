import re
from typing import Optional
from uuid import UUID
from datetime import date
from pydantic import Field, field_validator
from app.schemas.common import OrmBase, TimestampSchema
from app.models.flat import FlatType, OccupancyStatus
from app.schemas.floor import MAX_FLOOR, MIN_FLOOR
from app.utils.unit_fields import clean_possession_date, clean_ref

_VAN = re.compile(r"^[A-Z0-9]{4,30}$")


def _clean_van(v: Optional[str]) -> Optional[str]:
    """Virtual account number: spaces and dashes dropped, upper-cased;
    blank means none."""
    if v is None:
        return None
    v = re.sub(r"[\s-]", "", v).upper()
    if not v:
        return None
    if not _VAN.match(v):
        raise ValueError("Virtual account number must be 4-30 letters or digits")
    return v


def _flat_number(v):
    """A flat number as typed: trimmed, never blank."""
    if v is None:
        return None
    v = str(v).strip()
    if not v:
        raise ValueError("Flat number cannot be blank")
    return v


class FlatCreate(OrmBase):
    flat_number:      str = Field(max_length=20)
    floor:            Optional[int] = Field(default=None, ge=MIN_FLOOR, le=MAX_FLOOR)
    flat_type:        Optional[FlatType] = None
    area_sqft:        Optional[float] = Field(default=None, gt=0, le=1_000_000)
    occupancy_status: Optional[OccupancyStatus] = None
    remarks:          Optional[str] = None
    virtual_account_number: Optional[str] = None
    possession_date:  Optional[date] = None
    electric_meter_no: Optional[str] = Field(default=None, max_length=40)
    electric_consumer_no: Optional[str] = Field(default=None, max_length=40)
    wing_id:          UUID

    _van = field_validator("virtual_account_number")(_clean_van)
    _possession = field_validator("possession_date")(clean_possession_date)
    _meter = field_validator("electric_meter_no", "electric_consumer_no")(clean_ref)
    _number = field_validator("flat_number", mode="before")(_flat_number)


class FlatUpdate(OrmBase):
    # Phase M1.3: occupancy_status is deliberately NOT a field here.
    # FlatCreate may still set an initial value (a brand-new flat has no
    # occupancy history to bypass), but once a flat exists, OccupancyService
    # (resident/tenant move-in/move-out) must be the only writer — a generic
    # PATCH here previously let a caller change this field directly with no
    # duplicate-active-tenant check, no OccupancyLog entry, and no audit
    # trail, creating a second, uncontrolled source of truth. Because OrmBase
    # doesn't set extra="forbid", a client that still sends this field in a
    # PATCH body gets no error — the key is just silently dropped, matching
    # every other field this schema has never declared. See the M1.3 report
    # for the one known caller this affects (the Flutter flat-edit form's
    # occupancy dropdown), which is an accepted, documented no-op until a
    # coordinated Flutter change repoints it at the Occupancy endpoints.
    flat_number:      Optional[str] = Field(default=None, max_length=20)
    floor:            Optional[int] = Field(default=None, ge=MIN_FLOOR, le=MAX_FLOOR)
    flat_type:        Optional[FlatType] = None
    area_sqft:        Optional[float] = Field(default=None, gt=0, le=1_000_000)
    remarks:          Optional[str] = None
    # Sent as null or "" to clear it (see FlatService.update)
    virtual_account_number: Optional[str] = None
    # These three can be cleared the same way
    possession_date:  Optional[date] = None
    electric_meter_no: Optional[str] = Field(default=None, max_length=40)
    electric_consumer_no: Optional[str] = Field(default=None, max_length=40)

    _van = field_validator("virtual_account_number")(_clean_van)
    _possession = field_validator("possession_date")(clean_possession_date)
    _meter = field_validator("electric_meter_no", "electric_consumer_no")(clean_ref)
    _number = field_validator("flat_number", mode="before")(_flat_number)


class FlatOut(TimestampSchema):
    flat_number:      str
    floor:            Optional[int]
    flat_type:        Optional[FlatType]
    area_sqft:        Optional[float]
    occupancy_status: Optional[OccupancyStatus]
    remarks:          Optional[str]
    virtual_account_number: Optional[str] = None
    possession_date:  Optional[date] = None
    electric_meter_no: Optional[str] = None
    electric_consumer_no: Optional[str] = None
    wing_id:          UUID
    wing_name:        Optional[str] = None   # populated by service helper
