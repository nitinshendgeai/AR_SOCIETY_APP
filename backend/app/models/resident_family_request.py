from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin

PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"
FAMILY_TYPES = ("family", "dependent")


class ResidentFamilyRequest(Base, TimestampMixin):
    """A resident's request to add a member of their family to their flat's Family list.

    The person does not exist as a resident until the Admin or a committee member approves: only then is a row added to the
    Residents list (as Family or Dependent). Until then nothing that reads the Residents list, such as the gym's attendance
    book, can see the person."""
    __tablename__ = "resident_family_requests"
    __table_args__ = (
        Index("ix_family_requests_soc_status", "society_id", "status"),
    )

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    requester_name = Column(String(255), nullable=True)               # as it was when asked

    full_name = Column(String(255), nullable=False)
    resident_type = Column(String(20), nullable=False)               # family or dependent
    phone = Column(String(20), nullable=True)
    date_of_birth = Column(Date, nullable=True)

    status = Column(String(10), nullable=False, default=PENDING, index=True)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    resident_id = Column(UUID(as_uuid=True), ForeignKey("residents.id", ondelete="SET NULL"), nullable=True)   # the row approval made
