from sqlalchemy import Boolean, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin


class SocietyService(Base, TimestampMixin):
    """The platform owner's switch for one service of one society (see app.core.services_catalog). Only switched-off
    services are kept: a row with enabled False closes the service; switching it back on deletes the row."""
    __tablename__ = "society_services"
    __table_args__ = (UniqueConstraint("society_id", "service_key", name="uq_society_services_key"),)

    society_id  = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    service_key = Column(String(40), nullable=False)
    enabled     = Column(Boolean, nullable=False)
    changed_by  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
