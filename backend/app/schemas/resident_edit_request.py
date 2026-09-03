from typing import Optional
from datetime import date, datetime
from uuid import UUID
from pydantic import field_validator
from app.schemas.common import OrmBase, TimestampSchema
from app.models.resident import CommunicationPreference
from app.models.resident_edit_request import ResidentEditRequestStatus


class ResidentEditRequestCreate(OrmBase):
    full_name:               Optional[str] = None
    phone:                   Optional[str] = None
    email:                   Optional[str] = None
    date_of_birth:           Optional[date] = None
    emergency_contact_name:  Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    comm_preference:         Optional[CommunicationPreference] = None
    photo_url:               Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def name_not_blank(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Full name cannot be blank")
        return v.strip() if v else v


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
