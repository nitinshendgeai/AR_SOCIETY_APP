from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class UserSession(Base, TimestampMixin):
    """One signed-in device. Both tokens issued at login carry this row's id (`sid`), so the
    server can sign a device out: a revoked session's tokens stop working at once, instead of
    living on until they expire. `created_at` is when the device signed in."""
    __tablename__ = "user_sessions"

    user_id        = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device         = Column(String(120), nullable=True)      # "Chrome on Windows"
    ip_address     = Column(String(64), nullable=True)
    last_seen_at   = Column(DateTime, nullable=True)
    revoked_at     = Column(DateTime, nullable=True, index=True)
    revoked_reason = Column(String(40), nullable=True)       # logout | signed_out | password_changed | password_reset | ...

    user = relationship("User")

    def __repr__(self):
        return f"<UserSession {self.id} user={self.user_id} revoked={self.revoked_at is not None}>"
