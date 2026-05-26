"""
OccupancyLog — tracks every flat occupancy change event.
Provides full history: who moved in/out, when, as owner or tenant.
Used for analytics, reporting, and future finance integration.
"""
import enum
from sqlalchemy import Column, String, Date, Enum, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class OccupancyEventType(str, enum.Enum):
    RESIDENT_MOVE_IN  = "resident_move_in"
    RESIDENT_MOVE_OUT = "resident_move_out"
    TENANT_MOVE_IN    = "tenant_move_in"
    TENANT_MOVE_OUT   = "tenant_move_out"
    FLAT_VACANT       = "flat_vacant"
    OWNERSHIP_TRANSFER = "ownership_transfer"


class OccupancyLog(Base, TimestampMixin):
    __tablename__ = "occupancy_logs"

    society_id    = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id       = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    wing_id       = Column(UUID(as_uuid=True), ForeignKey("wings.id", ondelete="SET NULL"), nullable=True)
    resident_id   = Column(UUID(as_uuid=True), ForeignKey("residents.id", ondelete="SET NULL"), nullable=True, index=True)
    tenant_id     = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type    = Column(Enum(OccupancyEventType), nullable=False, index=True)
    event_date    = Column(Date, nullable=False, index=True)
    logged_by     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes         = Column(Text, nullable=True)

    society  = relationship("Society")
    flat     = relationship("Flat")
    wing     = relationship("Wing")
    resident = relationship("Resident", foreign_keys=[resident_id])
    tenant   = relationship("Tenant",   foreign_keys=[tenant_id])
    logger   = relationship("User",     foreign_keys=[logged_by])

    def __repr__(self):
        return f"<OccupancyLog flat={self.flat_id} {self.event_type} {self.event_date}>"
