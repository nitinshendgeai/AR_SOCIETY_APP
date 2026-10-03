from typing import Optional
from uuid import UUID
from pydantic import Field, field_validator
from app.schemas.common import OrmBase, TimestampSchema

# 0 = Ground, negative = basements
MIN_FLOOR, MAX_FLOOR = -10, 200


def _floor_name(v):
    if v is None:
        return None
    v = " ".join(str(v).split())
    return v or None


class FloorCreate(OrmBase):
    floor_number: int = Field(ge=MIN_FLOOR, le=MAX_FLOOR)
    floor_name:   Optional[str] = Field(default=None, max_length=50)
    wing_id:      UUID
    society_id:   UUID

    _floor_name = field_validator("floor_name", mode="before")(_floor_name)


class FloorUpdate(OrmBase):
    floor_number: Optional[int] = Field(default=None, ge=MIN_FLOOR, le=MAX_FLOOR)
    floor_name:   Optional[str] = Field(default=None, max_length=50)

    _floor_name = field_validator("floor_name", mode="before")(_floor_name)


class FloorOut(TimestampSchema):
    floor_number: int
    floor_name:   Optional[str]
    wing_id:      UUID
    society_id:   UUID
    flat_count:   int = 0
