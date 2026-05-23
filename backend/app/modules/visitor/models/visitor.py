"""
Visitor & Gate Management Models

Workflow:
  PENDING → APPROVED / REJECTED
  APPROVED → CHECKED_IN → CHECKED_OUT
"""
import enum
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Boolean, Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


# ── Enums ─────────────────────────────────────────────────────────────────────

class VisitorType(str, enum.Enum):
    GUEST       = "guest"
    DELIVERY    = "delivery"
    CAB         = "cab"
    MAINTENANCE = "maintenance"
    VENDOR      = "vendor"
    EMERGENCY   = "emergency"


class VisitorStatus(str, enum.Enum):
    PENDING   = "pending"     # guard logged, waiting resident approval
    APPROVED  = "approved"    # resident approved
    REJECTED  = "rejected"    # resident rejected
    CHECKED_IN  = "checked_in"   # guard checked in
    CHECKED_OUT = "checked_out"  # guard checked out
    EXPIRED   = "expired"     # no action within timeout


class GateType(str, enum.Enum):
    ENTRY = "entry"
    EXIT  = "exit"
    BOTH  = "both"


# ── Gate ──────────────────────────────────────────────────────────────────────

class Gate(Base, TimestampMixin):
    __tablename__ = "gates"

    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    name         = Column(String(100), nullable=False)        # "Main Gate", "East Gate"
    gate_type    = Column(Enum(GateType), default=GateType.BOTH, nullable=False)
    location     = Column(String(255), nullable=True)
    is_active    = Column(Boolean, default=True, nullable=False)

    society  = relationship("Society")
    visitors = relationship("Visitor", back_populates="gate")

    def __repr__(self):
        return f"<Gate {self.name}>"


# ── Visitor ───────────────────────────────────────────────────────────────────

class Visitor(Base, TimestampMixin):
    __tablename__ = "visitors"

    # Identity
    name         = Column(String(255), nullable=False)
    mobile       = Column(String(20), nullable=False, index=True)
    visitor_type = Column(Enum(VisitorType), default=VisitorType.GUEST, nullable=False, index=True)
    purpose      = Column(Text, nullable=True)
    photo_url    = Column(String(500), nullable=True)

    # References
    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id      = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="SET NULL"), nullable=True, index=True)
    resident_id  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    gate_id      = Column(UUID(as_uuid=True), ForeignKey("gates.id", ondelete="SET NULL"), nullable=True)

    # Workflow status
    status             = Column(Enum(VisitorStatus), default=VisitorStatus.PENDING, nullable=False, index=True)
    expected_arrival   = Column(DateTime, nullable=True)
    checked_in_at      = Column(DateTime, nullable=True)
    checked_out_at     = Column(DateTime, nullable=True)

    # Approval
    approved_by        = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at        = Column(DateTime, nullable=True)
    rejection_reason   = Column(Text, nullable=True)

    # Guard who logged
    logged_by          = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # QR pass (future)
    qr_token           = Column(String(255), nullable=True, unique=True, index=True)
    qr_expires_at      = Column(DateTime, nullable=True)

    # Relationships
    society      = relationship("Society")
    flat         = relationship("Flat")
    resident     = relationship("User", foreign_keys=[resident_id])
    approver     = relationship("User", foreign_keys=[approved_by])
    logged_by_user = relationship("User", foreign_keys=[logged_by])
    gate         = relationship("Gate", back_populates="visitors")
    vehicle      = relationship("VisitorVehicle", back_populates="visitor", uselist=False, cascade="all, delete-orphan")
    logs         = relationship("VisitorLog", back_populates="visitor", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Visitor {self.name} status={self.status}>"


# ── VisitorVehicle ────────────────────────────────────────────────────────────

class VisitorVehicle(Base, TimestampMixin):
    __tablename__ = "visitor_vehicles"

    visitor_id    = Column(UUID(as_uuid=True), ForeignKey("visitors.id", ondelete="CASCADE"), nullable=False, index=True)
    vehicle_type  = Column(String(50), nullable=True)   # car, bike, auto, truck
    vehicle_number = Column(String(30), nullable=True, index=True)
    vehicle_model = Column(String(100), nullable=True)
    vehicle_color = Column(String(50), nullable=True)

    visitor = relationship("Visitor", back_populates="vehicle")

    def __repr__(self):
        return f"<VisitorVehicle {self.vehicle_number}>"


# ── VisitorLog ────────────────────────────────────────────────────────────────

class VisitorLog(Base, TimestampMixin):
    """Immutable append-only log for every state change in visitor workflow."""

    __tablename__ = "visitor_logs"

    visitor_id   = Column(UUID(as_uuid=True), ForeignKey("visitors.id", ondelete="CASCADE"), nullable=False, index=True)
    action       = Column(String(50), nullable=False)      # CREATED, APPROVED, REJECTED, CHECKED_IN, CHECKED_OUT
    performed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes        = Column(Text, nullable=True)
    gate_id      = Column(UUID(as_uuid=True), ForeignKey("gates.id", ondelete="SET NULL"), nullable=True)

    visitor      = relationship("Visitor", back_populates="logs")
    performed_by_user = relationship("User", foreign_keys=[performed_by])

    def __repr__(self):
        return f"<VisitorLog {self.action} visitor={self.visitor_id}>"
