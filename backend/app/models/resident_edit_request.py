from sqlalchemy import Column, String, Text, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base, TimestampMixin


class ResidentEditRequestStatus(str, enum.Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ResidentEditRequest(Base, TimestampMixin):
    """A Resident's self-service request to change their own profile fields
    (see _EDITABLE_FIELDS in resident_edit_request_service.py) — takes
    effect only once an Admin or Committee member approves it, mirroring
    the existing require_admin_committee gate on a direct Resident PATCH."""
    __tablename__ = "resident_edit_requests"

    resident_id  = Column(UUID(as_uuid=True), ForeignKey("residents.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)

    changes = Column(JSON, nullable=False)  # {"field_name": new_value, ...}
    status  = Column(Enum(ResidentEditRequestStatus, values_callable=lambda e: [x.value for x in e]),
                      default=ResidentEditRequestStatus.PENDING, nullable=False, index=True)

    reviewed_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at      = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    resident = relationship("Resident")

    def __repr__(self):
        return f"<ResidentEditRequest resident={self.resident_id} status={self.status}>"
