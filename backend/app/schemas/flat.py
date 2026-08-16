from typing import Optional
from uuid import UUID
from app.schemas.common import OrmBase, TimestampSchema
from app.models.flat import FlatType, OccupancyStatus


class FlatCreate(OrmBase):
    flat_number:      str
    floor:            Optional[int] = None
    flat_type:        Optional[FlatType] = None
    area_sqft:        Optional[float] = None
    occupancy_status: Optional[OccupancyStatus] = None
    remarks:          Optional[str] = None
    wing_id:          UUID


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
    flat_number:      Optional[str] = None
    floor:            Optional[int] = None
    flat_type:        Optional[FlatType] = None
    area_sqft:        Optional[float] = None
    remarks:          Optional[str] = None


class FlatOut(TimestampSchema):
    flat_number:      str
    floor:            Optional[int]
    flat_type:        Optional[FlatType]
    area_sqft:        Optional[float]
    occupancy_status: Optional[OccupancyStatus]
    remarks:          Optional[str]
    wing_id:          UUID
    wing_name:        Optional[str] = None   # populated by service helper
