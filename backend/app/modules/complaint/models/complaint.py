"""
Complaint Management Models

Status FSM:
  OPEN → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED
                                            → REOPENED → ASSIGNED
  Any state → REJECTED (admin only)
"""
import enum
from sqlalchemy import Column, String, Text, DateTime, Integer, Enum, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class ComplaintPriority(str, enum.Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class ComplaintStatus(str, enum.Enum):
    OPEN        = "open"
    ASSIGNED    = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED    = "resolved"
    REOPENED    = "reopened"
    CLOSED      = "closed"
    REJECTED    = "rejected"


class ComplaintCategory(str, enum.Enum):
    PLUMBING     = "plumbing"
    ELECTRICAL   = "electrical"
    SECURITY     = "security"
    HOUSEKEEPING = "housekeeping"
    PARKING      = "parking"
    LIFT         = "lift"
    WATER        = "water"
    AMENITIES    = "amenities"
    OTHER        = "other"


# ── Valid status transitions ──────────────────────────────────────────────────
VALID_TRANSITIONS: dict = {
    ComplaintStatus.OPEN:        {ComplaintStatus.ASSIGNED, ComplaintStatus.REJECTED},
    ComplaintStatus.ASSIGNED:    {ComplaintStatus.IN_PROGRESS, ComplaintStatus.REJECTED},
    ComplaintStatus.IN_PROGRESS: {ComplaintStatus.RESOLVED, ComplaintStatus.REJECTED},
    ComplaintStatus.RESOLVED:    {ComplaintStatus.CLOSED, ComplaintStatus.REOPENED},
    ComplaintStatus.REOPENED:    {ComplaintStatus.ASSIGNED, ComplaintStatus.REJECTED},
    ComplaintStatus.CLOSED:      set(),
    ComplaintStatus.REJECTED:    set(),
}


class Complaint(Base, TimestampMixin):
    __tablename__ = "complaints"

    # Identity
    complaint_number = Column(String(20), nullable=False, unique=True, index=True)
    title            = Column(String(255), nullable=False)
    description      = Column(Text, nullable=False)
    category         = Column(Enum(ComplaintCategory, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    priority         = Column(Enum(ComplaintPriority, values_callable=lambda e: [x.value for x in e]), default=ComplaintPriority.MEDIUM, nullable=False, index=True)
    status           = Column(Enum(ComplaintStatus, values_callable=lambda e: [x.value for x in e]), default=ComplaintStatus.OPEN, nullable=False, index=True)

    # References
    society_id       = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id          = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="SET NULL"), nullable=True, index=True)
    raised_by        = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False, index=True)
    assigned_to         = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_department = Column(String(50), nullable=True, index=True)   # security|housekeeping|technical
    assigned_by         = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Timestamps
    assigned_at      = Column(DateTime, nullable=True)
    resolved_at      = Column(DateTime, nullable=True)
    closed_at        = Column(DateTime, nullable=True)
    due_date         = Column(DateTime, nullable=True)   # future SLA engine

    # Resolution
    resolution_notes = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    reopen_count     = Column(Integer, default=0, nullable=False)

    # Relationships
    society        = relationship("Society")
    flat           = relationship("Flat")
    reporter       = relationship("User", foreign_keys=[raised_by])
    assignee       = relationship("User", foreign_keys=[assigned_to])
    assigner       = relationship("User", foreign_keys=[assigned_by])
    comments       = relationship("ComplaintComment",    back_populates="complaint", cascade="all, delete-orphan", order_by="ComplaintComment.created_at")
    attachments    = relationship("ComplaintAttachment", back_populates="complaint", cascade="all, delete-orphan")
    status_history = relationship("ComplaintStatusHistory", back_populates="complaint", cascade="all, delete-orphan", order_by="ComplaintStatusHistory.created_at")

    def __repr__(self):
        return f"<Complaint #{self.complaint_number} [{self.status}]>"


class ComplaintComment(Base, TimestampMixin):
    __tablename__ = "complaint_comments"

    complaint_id  = Column(UUID(as_uuid=True), ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    body          = Column(Text, nullable=False)
    is_internal   = Column(Boolean, default=False, nullable=False)  # staff-only notes

    complaint = relationship("Complaint", back_populates="comments")
    author    = relationship("User", foreign_keys=[author_id])


class ComplaintAttachment(Base, TimestampMixin):
    __tablename__ = "complaint_attachments"

    complaint_id  = Column(UUID(as_uuid=True), ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    file_name     = Column(String(255), nullable=False)
    file_url      = Column(String(500), nullable=False)   # S3/cloud URL
    file_size     = Column(Integer, nullable=True)        # bytes
    mime_type     = Column(String(100), nullable=True)

    complaint = relationship("Complaint", back_populates="attachments")
    uploader  = relationship("User", foreign_keys=[uploaded_by])


class ComplaintStatusHistory(Base, TimestampMixin):
    """Immutable append-only log for every status transition."""
    __tablename__ = "complaint_status_history"

    complaint_id  = Column(UUID(as_uuid=True), ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status   = Column(Enum(ComplaintStatus, values_callable=lambda e: [x.value for x in e]), nullable=True)
    to_status     = Column(Enum(ComplaintStatus, values_callable=lambda e: [x.value for x in e]), nullable=False)
    changed_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes         = Column(Text, nullable=True)

    complaint  = relationship("Complaint", back_populates="status_history")
    changed_by_user = relationship("User", foreign_keys=[changed_by])
