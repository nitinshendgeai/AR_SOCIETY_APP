from sqlalchemy import Column, String, Text, Boolean, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base, TimestampMixin


class NotificationChannel(str, enum.Enum):
    IN_APP = "in_app"
    EMAIL  = "email"
    SMS    = "sms"
    PUSH   = "push"


class NotificationStatus(str, enum.Enum):
    PENDING   = "pending"
    SENT      = "sent"
    FAILED    = "failed"
    READ      = "read"


class NotificationType(str, enum.Enum):
    INFO     = "info"
    WARNING  = "warning"
    ALERT    = "alert"
    APPROVAL = "approval"
    REMINDER = "reminder"


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    # Recipient
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Content
    title       = Column(String(255), nullable=False)
    body        = Column(Text, nullable=False)
    type        = Column(Enum(NotificationType, values_callable=lambda e: [x.value for x in e]), default=NotificationType.INFO, nullable=False)
    channel     = Column(Enum(NotificationChannel, values_callable=lambda e: [x.value for x in e]), default=NotificationChannel.IN_APP, nullable=False)
    status      = Column(Enum(NotificationStatus, values_callable=lambda e: [x.value for x in e]), default=NotificationStatus.PENDING, nullable=False, index=True)

    # Reference (which module/entity triggered this)
    module      = Column(String(100), nullable=True)   # e.g. "visitor", "complaint"
    entity_id   = Column(String(100), nullable=True)
    action_url  = Column(String(500), nullable=True)   # deep link for mobile

    # Delivery metadata
    is_read     = Column(Boolean, default=False, nullable=False)
    extra_data  = Column(JSONB, nullable=True)          # provider-specific payload

    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<Notification {self.type} to user={self.user_id} status={self.status}>"
