from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class DeviceToken(Base, TimestampMixin):
    """A browser or phone that receives push notifications for a user.

    `token` is the Firebase Cloud Messaging registration token the app gets
    after the user allows notifications. One user can have several (phone +
    laptop); a token moves to whoever signs in on that device last."""
    __tablename__ = "device_tokens"

    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token        = Column(String(512), nullable=False, unique=True, index=True)
    platform     = Column(String(20), nullable=False)   # web | android | ios
    last_seen_at = Column(DateTime, nullable=True)

    user = relationship("User")
