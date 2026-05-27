"""
Shift Handover / Takeover Models — operational workforce continuity.

Workflow:
  Outgoing staff submits handover
    → Lists pending tasks, assets, keys, incidents
    → Incoming staff reviews and accepts takeover
    → Supervisor optionally verifies
    → Full audit trail maintained

This is critical for 24/7 operations: security, maintenance, etc.
"""
import enum
from sqlalchemy import Column, String, Text, Boolean, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class HandoverStatus(str, enum.Enum):
    DRAFT     = "draft"       # being filled by outgoing staff
    SUBMITTED = "submitted"   # awaiting incoming staff
    ACCEPTED  = "accepted"    # incoming staff confirmed
    DISPUTED  = "disputed"    # incoming staff raised concern
    VERIFIED  = "verified"    # supervisor verified
    CLOSED    = "closed"      # final state


class HandoverItemType(str, enum.Enum):
    PENDING_TASK = "pending_task"
    INCIDENT     = "incident"
    KEY          = "key"
    EQUIPMENT    = "equipment"
    VISITOR      = "visitor"       # visitor still on premises
    REMARK       = "remark"
    MAINTENANCE  = "maintenance"


HANDOVER_TRANSITIONS: dict = {
    HandoverStatus.DRAFT:     {HandoverStatus.SUBMITTED},
    HandoverStatus.SUBMITTED: {HandoverStatus.ACCEPTED, HandoverStatus.DISPUTED},
    HandoverStatus.DISPUTED:  {HandoverStatus.ACCEPTED, HandoverStatus.SUBMITTED},
    HandoverStatus.ACCEPTED:  {HandoverStatus.VERIFIED, HandoverStatus.CLOSED},
    HandoverStatus.VERIFIED:  {HandoverStatus.CLOSED},
    HandoverStatus.CLOSED:    set(),
}


class StaffHandover(Base, TimestampMixin):
    """
    One handover record per shift transition.
    Outgoing staff creates it; incoming staff accepts.
    """
    __tablename__ = "staff_handovers"

    society_id       = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    # Shift reference
    outgoing_staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="SET NULL"),
                                nullable=True, index=True)
    incoming_staff_id = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="SET NULL"),
                                nullable=True, index=True)
    duty_assignment_id = Column(UUID(as_uuid=True), nullable=True)  # linked duty if any
    verified_by       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
                                nullable=True)

    # Location / area being handed over
    area             = Column(String(255), nullable=True)   # "Main Gate", "Lobby", "B-Block"
    shift_start      = Column(DateTime, nullable=True)
    shift_end        = Column(DateTime, nullable=True)

    # Core handover content
    summary          = Column(Text, nullable=False)   # outgoing staff summary
    status           = Column(Enum(HandoverStatus), default=HandoverStatus.DRAFT,
                               nullable=False, index=True)

    # Takeover details
    accepted_at      = Column(DateTime, nullable=True)
    acceptance_notes = Column(Text, nullable=True)
    dispute_reason   = Column(Text, nullable=True)
    verified_at      = Column(DateTime, nullable=True)
    verification_notes = Column(Text, nullable=True)
    closed_at        = Column(DateTime, nullable=True)

    society         = relationship("Society")
    outgoing_staff  = relationship("Staff", foreign_keys=[outgoing_staff_id])
    incoming_staff  = relationship("Staff", foreign_keys=[incoming_staff_id])
    verifier        = relationship("User", foreign_keys=[verified_by])
    items           = relationship("HandoverItem", back_populates="handover",
                                   cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StaffHandover {self.area} [{self.status}]>"


class HandoverItem(Base, TimestampMixin):
    """
    Individual item in a handover — task, key, equipment, incident, visitor, etc.
    """
    __tablename__ = "handover_items"

    handover_id  = Column(UUID(as_uuid=True), ForeignKey("staff_handovers.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    item_type    = Column(Enum(HandoverItemType), nullable=False, index=True)
    title        = Column(String(255), nullable=False)
    description  = Column(Text, nullable=True)
    is_urgent    = Column(Boolean, default=False, nullable=False)
    is_resolved  = Column(Boolean, default=False, nullable=False)   # resolved during shift
    reference_id = Column(String(100), nullable=True)  # complaint/task/visitor ID ref
    quantity     = Column(Integer, nullable=True)       # for keys/equipment count

    # Acknowledgement by incoming staff
    acknowledged = Column(Boolean, default=False, nullable=False)
    ack_notes    = Column(Text, nullable=True)

    handover = relationship("StaffHandover", back_populates="items")

    def __repr__(self):
        return f"<HandoverItem {self.item_type} {self.title!r}>"
