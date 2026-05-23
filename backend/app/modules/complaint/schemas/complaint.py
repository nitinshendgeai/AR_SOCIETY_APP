from pydantic import BaseModel, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.schemas.common import OrmBase, TimestampSchema
from app.modules.complaint.models.complaint import (
    ComplaintCategory, ComplaintPriority, ComplaintStatus,
)


class ComplaintCreate(OrmBase):
    title:       str
    description: str
    category:    ComplaintCategory
    priority:    ComplaintPriority  = ComplaintPriority.MEDIUM
    society_id:  UUID
    flat_id:     Optional[UUID]     = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()


class ComplaintAssignRequest(OrmBase):
    assigned_to: UUID
    notes:       Optional[str] = None
    due_date:    Optional[datetime] = None


class ComplaintStatusUpdateRequest(OrmBase):
    status:           ComplaintStatus
    notes:            Optional[str] = None
    resolution_notes: Optional[str] = None
    rejection_reason: Optional[str] = None


class ComplaintReopenRequest(OrmBase):
    reason: str


class CommentCreate(OrmBase):
    body:        str
    is_internal: bool = False


class AttachmentCreate(OrmBase):
    file_name: str
    file_url:  str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None


# ── Output schemas ────────────────────────────────────────────────────────────

class CommentOut(TimestampSchema):
    complaint_id: UUID
    author_id:    UUID
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
    raised_by:        UUID
    assigned_to:      Optional[UUID]
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
    raised_by:        UUID
    assigned_to:      Optional[UUID]
    resolved_at:      Optional[datetime]
    closed_at:        Optional[datetime]
