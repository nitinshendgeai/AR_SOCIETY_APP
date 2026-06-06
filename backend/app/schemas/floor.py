from typing import Optional
from uuid import UUID
from app.schemas.common import OrmBase, TimestampSchema


class FloorCreate(OrmBase):
    floor_number: int
    floor_name:   Optional[str] = None
    wing_id:      UUID
    society_id:   UUID


class FloorUpdate(OrmBase):
    floor_number: Optional[int] = None
    floor_name:   Optional[str] = None


class FloorOut(TimestampSchema):
    floor_number: int
    floor_name:   Optional[str]
    wing_id:      UUID
    society_id:   UUID
    flat_count:   int = 0
