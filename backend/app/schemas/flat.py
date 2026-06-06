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
    flat_number:      Optional[str] = None
    floor:            Optional[int] = None
    flat_type:        Optional[FlatType] = None
    area_sqft:        Optional[float] = None
    occupancy_status: Optional[OccupancyStatus] = None
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
