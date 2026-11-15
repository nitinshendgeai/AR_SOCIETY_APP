from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas import validators as val
from app.schemas.common import OrmBase


class FamilyRequestCreate(OrmBase):
    full_name: str = Field(min_length=2, max_length=255)
    resident_type: Literal["family", "dependent"]
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    flat_id: Optional[UUID] = None             # needed only when the resident lives in more than one flat

    _name = field_validator("full_name", mode="before")(val.name)
    _phone = field_validator("phone", mode="before")(val.mobile)
    _dob = field_validator("date_of_birth")(val.birth_date)


class FamilyRequestReject(OrmBase):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Say why")
        return v.strip()


class FamilyRequestOut(OrmBase):
    id: UUID
    flat_id: UUID
    flat_display: Optional[str] = None
    full_name: str
    resident_type: str
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    requester_name: Optional[str] = None
    status: str
    rejection_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
