import re
from pydantic import BaseModel, Field, field_validator, model_validator
from app.schemas import validators as val
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.schemas.common import OrmBase, TimestampSchema
from app.modules.complaint.models.complaint import (
    ComplaintCategory, ComplaintPriority, ComplaintStatus,
)


class ComplaintCreate(OrmBase):
    title:       str = Field(max_length=255)
    description: str = Field(max_length=5000)
    category:    ComplaintCategory
    priority:    ComplaintPriority  = ComplaintPriority.MEDIUM
    society_id:  UUID
    flat_id:     Optional[UUID]     = None

    _title = field_validator("title", mode="before")(val.line_max(255, required=True))
    _description = field_validator("description", mode="before")(val.note_max(5000, required=True))


class ComplaintAssignRequest(OrmBase):
    assigned_to: UUID
    notes:       Optional[str] = None
    due_date:    Optional[datetime] = None

    _notes = field_validator("notes", mode="before")(val.note_max(1000))


class ComplaintStatusUpdateRequest(OrmBase):
    status:           ComplaintStatus
    notes:            Optional[str] = None
    resolution_notes: Optional[str] = None
    rejection_reason: Optional[str] = None

    _text = field_validator("notes", "resolution_notes", "rejection_reason", mode="before")(val.note_max(1000))

    @model_validator(mode="after")
    def _reason_needed(self):
        if self.status == ComplaintStatus.RESOLVED and not self.resolution_notes:
            raise ValueError("Say what was done to resolve it (resolution_notes)")
        if self.status == ComplaintStatus.REJECTED and not self.rejection_reason:
            raise ValueError("Give the reason for rejecting it (rejection_reason)")
        return self


class ComplaintReopenRequest(OrmBase):
    reason: str

    _reason = field_validator("reason", mode="before")(val.note_max(1000, required=True))


class CommentCreate(OrmBase):
    body:        str
    is_internal: bool = False

    _body = field_validator("body", mode="before")(val.note_max(2000, required=True))


class AttachmentCreate(OrmBase):
    file_name: str = Field(max_length=255)
    file_url:  str = Field(max_length=500)
    file_size: Optional[int] = Field(default=None, ge=0, le=2_000_000_000)
    mime_type: Optional[str] = Field(default=None, max_length=100)

    _name = field_validator("file_name", mode="before")(val.line_max(255, required=True))
    _mime = field_validator("mime_type", mode="before")(val.line_max(100))

    @field_validator("file_url", mode="before")
    @classmethod
    def _url(cls, v):
        v = val.text(v)
        if v is None or not re.match(r"^https?://\S+$", v):
            raise ValueError("Enter a valid link starting with http:// or https://")
        return v


# ── Output schemas ────────────────────────────────────────────────────────────

class CommentOut(TimestampSchema):
    complaint_id: UUID
    author_id:    UUID
    author_name:  Optional[str] = None
    body:         str
    is_internal:  bool


class AttachmentOut(TimestampSchema):
    complaint_id: UUID
    file_name:    str
    file_url:     str
    file_size:    Optional[int]
    mime_type:    Optional[str]


class StatusHistoryOut(TimestampSchema):
    from_status: Optional[ComplaintStatus]
    to_status:   ComplaintStatus
    changed_by:  Optional[UUID]
    notes:       Optional[str]


class ComplaintOut(TimestampSchema):
    complaint_number: str
    title:            str
    description:      str
    category:         ComplaintCategory
    priority:         ComplaintPriority
    status:           ComplaintStatus
    society_id:       UUID
    flat_id:          Optional[UUID]
    flat_number:      Optional[str]        = None
    wing_name:        Optional[str]        = None
    raised_by:        UUID
    raised_by_name:   Optional[str]      = None
    assigned_to:      Optional[UUID]
    assigned_to_name: Optional[str]      = None
    assigned_at:      Optional[datetime]
    resolved_at:      Optional[datetime]
    closed_at:        Optional[datetime]
    due_date:         Optional[datetime]
    resolution_notes: Optional[str]
    rejection_reason: Optional[str]
    reopen_count:     int
    comments:         List[CommentOut]      = []
    attachments:      List[AttachmentOut]   = []
    status_history:   List[StatusHistoryOut] = []


class ComplaintListOut(TimestampSchema):
    """Lightweight schema for list views — no nested collections."""
    complaint_number: str
    title:            str
    category:         ComplaintCategory
    priority:         ComplaintPriority
    status:           ComplaintStatus
    society_id:       UUID
    flat_number:      Optional[str]        = None
    wing_name:        Optional[str]        = None
    raised_by:        UUID
    assigned_to:      Optional[UUID]
    assigned_to_name: Optional[str]      = None
    resolved_at:      Optional[datetime]
    closed_at:        Optional[datetime]
