import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class PasswordResetStatus(str, enum.Enum):
    PENDING   = "pending"
    COMPLETED = "completed"   # an admin reset the password
    DISMISSED = "dismissed"   # an admin decided not to


class PasswordResetRequest(Base, TimestampMixin):
    """A member who can't sign in asked for a new password from the login
    screen ("Forgot password?"). There's no email/SMS channel that reaches
    every member (residents sign in by mobile and have no real email), so the
    society's admins handle it: they reset the password and give the member
    the temporary one, which must be changed at the next sign-in."""
    __tablename__ = "password_reset_requests"

    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    society_id  = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=True, index=True)
    identifier  = Column(String(255), nullable=False)   # what the member typed
    status      = Column(Enum(PasswordResetStatus, values_callable=lambda e: [x.value for x in e]),
                         default=PasswordResetStatus.PENDING, nullable=False, index=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    resolved_at = Column(DateTime, nullable=True)

    user     = relationship("User", foreign_keys=[user_id])
    resolver = relationship("User", foreign_keys=[resolved_by])
