from sqlalchemy import Column, String, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base, TimestampMixin


class AuditAction(str, enum.Enum):
    CREATE  = "CREATE"
    UPDATE  = "UPDATE"
    DELETE  = "DELETE"
    LOGIN   = "LOGIN"
    LOGOUT  = "LOGOUT"
    ACCESS  = "ACCESS"
    APPROVE = "APPROVE"
    REJECT  = "REJECT"
    EXPORT  = "EXPORT"


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    # Who
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_email  = Column(String(255), nullable=True)   # denormalized for fast reads

    # What
    action      = Column(Enum(AuditAction), nullable=False, index=True)
    module      = Column(String(100), nullable=False, index=True)   # e.g. "society", "visitor"
    entity_id   = Column(String(100), nullable=True, index=True)    # UUID of affected record
    entity_type = Column(String(100), nullable=True)                # e.g. "Society"

    # Change data
    old_values  = Column(JSONB, nullable=True)
    new_values  = Column(JSONB, nullable=True)

    # Context
    ip_address  = Column(String(50), nullable=True)
    user_agent  = Column(String(500), nullable=True)
    notes       = Column(Text, nullable=True)

    # Relationship (optional — avoids join when user is deleted)
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<AuditLog {self.action} {self.module}/{self.entity_id} by {self.user_email}>"
