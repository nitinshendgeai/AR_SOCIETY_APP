"""Gate extras: parcels left at the gate, and the register of domestic help (maids, cooks, drivers) with passes."""
from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin

PARCEL_STATUSES = ("at_gate", "collected", "returned")
HELP_KINDS = ("maid", "cook", "driver", "nanny", "cleaner", "gardener", "other")
HELP_STATUSES = ("pending", "active", "suspended", "ended")


class Parcel(Base, TimestampMixin):
    __tablename__ = "gate_parcels"

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    courier = Column(String(120), nullable=True)               # Amazon, Swiggy, India Post ...
    description = Column(String(255), nullable=True)
    recipient_name = Column(String(120), nullable=True)
    status = Column(String(12), nullable=False, default="at_gate", index=True)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    logged_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    collected_at = Column(DateTime, nullable=True)
    collected_by_name = Column(String(120), nullable=True)
    closed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, nullable=True)

    flat = relationship("Flat")


class DomesticHelp(Base, TimestampMixin):
    __tablename__ = "domestic_help"
    __table_args__ = (UniqueConstraint("society_id", "pass_no", name="uq_domestic_help_pass"),)

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    mobile = Column(String(20), nullable=False, index=True)
    kind = Column(String(12), nullable=False, default="maid")
    id_proof = Column(String(120), nullable=True)               # "Aadhaar ending 4821", "Voter ID ..."
    police_verified = Column(Boolean, nullable=False, default=False)
    pass_no = Column(String(20), nullable=True)
    status = Column(String(12), nullable=False, default="pending", index=True)
    valid_until = Column(Date, nullable=True)
    registered_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, nullable=True)

    flats = relationship("DomesticHelpFlat", cascade="all, delete-orphan")
    entries = relationship("DomesticHelpEntry", cascade="all, delete-orphan", order_by="DomesticHelpEntry.in_at.desc()")


class DomesticHelpFlat(Base, TimestampMixin):
    __tablename__ = "domestic_help_flats"
    __table_args__ = (UniqueConstraint("help_id", "flat_id", name="uq_domestic_help_flat"),)

    help_id = Column(UUID(as_uuid=True), ForeignKey("domestic_help.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)

    flat = relationship("Flat")


class DomesticHelpEntry(Base, TimestampMixin):
    __tablename__ = "domestic_help_entries"

    help_id = Column(UUID(as_uuid=True), ForeignKey("domestic_help.id", ondelete="CASCADE"), nullable=False, index=True)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    in_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    out_at = Column(DateTime, nullable=True)
    logged_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
