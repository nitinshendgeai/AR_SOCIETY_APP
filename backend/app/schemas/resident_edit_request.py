from typing import Optional
from datetime import date, datetime
from uuid import UUID
from pydantic import Field, field_validator
from app.schemas import validators as val
from app.schemas.common import OrmBase, TimestampSchema
from app.models.resident import CommunicationPreference
from app.models.resident_edit_request import ResidentEditRequestStatus


class ResidentEditRequestCreate(OrmBase):
    full_name:               Optional[str] = Field(default=None, max_length=255)
    phone:                   Optional[str] = None
    email:                   Optional[str] = None
    date_of_birth:           Optional[date] = None
    emergency_contact_name:  Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    comm_preference:         Optional[CommunicationPreference] = None
    photo_url:               Optional[str] = None

    _name = field_validator("full_name", mode="before")(val.name)
    _phone = field_validator("phone", mode="before")(val.mobile)
    _email = field_validator("email", mode="before")(val.email)
    _dob = field_validator("date_of_birth")(val.birth_date)
    _emergency_phone = field_validator("emergency_contact_phone", mode="before")(val.contact_phone)
    _emergency_name = field_validator("emergency_contact_name", mode="before")(val.limited(255))
    _photo = field_validator("photo_url", mode="before")(val.limited(500))


class ResidentEditRequestReject(OrmBase):
    reason: str


class ResidentEditRequestOut(TimestampSchema):
    resident_id:      UUID
    requested_by:     Optional[UUID] = None
    society_id:       UUID
    changes:          dict
    status:           ResidentEditRequestStatus
    reviewed_by:      Optional[UUID] = None
    reviewed_at:      Optional[datetime] = None
    rejection_reason: Optional[str] = None
    resident_name:    Optional[str] = None
    flat_display:     Optional[str] = None
