from typing import Optional
from uuid import UUID
from pydantic import Field, field_validator
from app.schemas.common import OrmBase, TimestampSchema

MAX_FLOORS = 200


def _name(v):
    """A name as typed: trimmed, and never blank."""
    if v is None:
        return None
    v = " ".join(str(v).split())
    if not v:
        raise ValueError("Name cannot be blank")
    return v


def _code(v):
    """A wing code, upper-cased as the form does; blank means none."""
    if v is None:
        return None
    v = str(v).strip().upper()
    return v or None


class WingCreate(OrmBase):
    name:         str = Field(max_length=100)
    code:         Optional[str] = Field(default=None, max_length=20)
    description:  Optional[str] = None
    total_floors: Optional[int] = Field(default=None, ge=1, le=MAX_FLOORS)
    society_id:   UUID

    _name = field_validator("name", mode="before")(_name)
    _code = field_validator("code", mode="before")(_code)


class WingUpdate(OrmBase):
    name:         Optional[str] = Field(default=None, max_length=100)
    code:         Optional[str] = Field(default=None, max_length=20)
    description:  Optional[str] = None
    total_floors: Optional[int] = Field(default=None, ge=1, le=MAX_FLOORS)

    _name = field_validator("name", mode="before")(_name)
    _code = field_validator("code", mode="before")(_code)


class WingOut(TimestampSchema):
    name:         str
    code:         Optional[str]
    description:  Optional[str]
    total_floors: Optional[int]
    society_id:   UUID
    flat_count:   int = 0
    floor_count:  int = 0
