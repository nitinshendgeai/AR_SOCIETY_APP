"""
Amenity Management Models — rule-driven booking governance system.

Booking FSM:
  PENDING → APPROVED → COMPLETED
          → REJECTED
  PENDING | APPROVED → CANCELLED
"""
import enum
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean,
    DateTime, Date, Time, Enum, ForeignKey, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


# ── Enums ─────────────────────────────────────────────────────────────────────

class AmenityType(str, enum.Enum):
    CLUBHOUSE    = "clubhouse"
    GYM          = "gym"
    POOL         = "pool"
    PARTY_HALL   = "party_hall"
    GUEST_ROOM   = "guest_room"
    SPORTS_COURT = "sports_court"
    TERRACE      = "terrace"
    CONFERENCE   = "conference"
    OTHER        = "other"


class BookingStatus(str, enum.Enum):
    PENDING   = "pending"
    APPROVED  = "approved"
    REJECTED  = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class RuleType(str, enum.Enum):
    # Eligibility
    OWNERS_ONLY          = "owners_only"
    TENANTS_RESTRICTED   = "tenants_restricted"
    NO_DUES_REQUIRED     = "no_dues_required"
    # Booking limits
    MAX_DURATION_HOURS   = "max_duration_hours"
    MAX_BOOKINGS_PER_WEEK = "max_bookings_per_week"
    MAX_BOOKINGS_PER_MONTH = "max_bookings_per_month"
    MIN_ADVANCE_HOURS    = "min_advance_hours"
    MAX_ADVANCE_DAYS     = "max_advance_days"
    # Financial
    DEPOSIT_REQUIRED     = "deposit_required"
    CHARGE_PER_HOUR      = "charge_per_hour"
    # Approval
    APPROVAL_REQUIRED    = "approval_required"
    # Capacity
    MAX_GUESTS           = "max_guests"


# Valid booking transitions
BOOKING_TRANSITIONS: dict = {
    BookingStatus.PENDING:   {BookingStatus.APPROVED, BookingStatus.REJECTED, BookingStatus.CANCELLED},
    BookingStatus.APPROVED:  {BookingStatus.COMPLETED, BookingStatus.CANCELLED},
    BookingStatus.REJECTED:  set(),
    BookingStatus.CANCELLED: set(),
    BookingStatus.COMPLETED: set(),
}


# ── Amenity ───────────────────────────────────────────────────────────────────

class Amenity(Base, TimestampMixin):
    __tablename__ = "amenities"

    society_id        = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    name              = Column(String(150), nullable=False)
    amenity_type      = Column(Enum(AmenityType, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    description       = Column(Text, nullable=True)
    location          = Column(String(255), nullable=True)
    capacity          = Column(Integer, nullable=True)       # max people
    open_time         = Column(Time, nullable=True)          # e.g. 06:00
    close_time        = Column(Time, nullable=True)          # e.g. 22:00
    booking_required  = Column(Boolean, default=True,  nullable=False)
    approval_required = Column(Boolean, default=False, nullable=False)
    is_chargeable     = Column(Boolean, default=False, nullable=False)
    image_url         = Column(String(500), nullable=True)

    society    = relationship("Society")
    rules      = relationship("AmenityRule",         back_populates="amenity", cascade="all, delete-orphan")
    pricing    = relationship("AmenityPricing",      back_populates="amenity", cascade="all, delete-orphan")
    blackouts  = relationship("AmenityBlackoutDate", back_populates="amenity", cascade="all, delete-orphan")
    bookings   = relationship("AmenityBooking",      back_populates="amenity", cascade="all, delete-orphan")
    slots      = relationship("AmenitySlot",         back_populates="amenity", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Amenity {self.name} ({self.amenity_type})>"


# ── AmenityRule (database-driven rule engine) ─────────────────────────────────

class AmenityRule(Base, TimestampMixin):
    __tablename__ = "amenity_rules"

    amenity_id  = Column(UUID(as_uuid=True), ForeignKey("amenities.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_type   = Column(Enum(RuleType, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    rule_value  = Column(String(255), nullable=True)   # "true", "48", "2", "500.00"
    description = Column(String(500), nullable=True)
    is_active   = Column(Boolean, default=True, nullable=False)

    amenity = relationship("Amenity", back_populates="rules")

    def get_value(self):
        """Return typed value based on rule_type."""
        v = self.rule_value
        if v is None:
            return True
        try:
            return float(v) if '.' in v else int(v)
        except (ValueError, TypeError):
            return v.lower() in ('true', '1', 'yes') if v.lower() in ('true','false','1','0','yes','no') else v


# ── AmenitySlot (time-slot availability grid) ─────────────────────────────────

class AmenitySlot(Base, TimestampMixin):
    __tablename__ = "amenity_slots"

    amenity_id   = Column(UUID(as_uuid=True), ForeignKey("amenities.id", ondelete="CASCADE"), nullable=False, index=True)
    slot_date    = Column(Date, nullable=False, index=True)
    start_time   = Column(Time, nullable=False)
    end_time     = Column(Time, nullable=False)
    max_capacity = Column(Integer, nullable=True)
    booked_count = Column(Integer, default=0, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)

    amenity  = relationship("Amenity", back_populates="slots")
    bookings = relationship("AmenityBooking", back_populates="slot")

    def __repr__(self):
        return f"<AmenitySlot {self.slot_date} {self.start_time}-{self.end_time}>"


# ── AmenityPricing ────────────────────────────────────────────────────────────

class AmenityPricing(Base, TimestampMixin):
    __tablename__ = "amenity_pricing"

    amenity_id       = Column(UUID(as_uuid=True), ForeignKey("amenities.id", ondelete="CASCADE"), nullable=False, index=True)
    label            = Column(String(100), nullable=False)   # "Weekend Rate", "Peak Hours"
    price_per_hour   = Column(Float, nullable=True)
    flat_price       = Column(Float, nullable=True)          # fixed price regardless of duration
    deposit_amount   = Column(Float, nullable=True)
    is_default       = Column(Boolean, default=False, nullable=False)

    amenity = relationship("Amenity", back_populates="pricing")


# ── AmenityBlackoutDate ───────────────────────────────────────────────────────

class AmenityBlackoutDate(Base, TimestampMixin):
    __tablename__ = "amenity_blackout_dates"

    amenity_id  = Column(UUID(as_uuid=True), ForeignKey("amenities.id", ondelete="CASCADE"), nullable=False, index=True)
    blackout_date = Column(Date, nullable=False, index=True)
    reason        = Column(String(255), nullable=True)
    created_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    amenity = relationship("Amenity", back_populates="blackouts")


# ── AmenityBooking ────────────────────────────────────────────────────────────

class AmenityBooking(Base, TimestampMixin):
    __tablename__ = "amenity_bookings"

    # References
    amenity_id    = Column(UUID(as_uuid=True), ForeignKey("amenities.id", ondelete="CASCADE"), nullable=False, index=True)
    slot_id       = Column(UUID(as_uuid=True), ForeignKey("amenity_slots.id", ondelete="SET NULL"), nullable=True)
    booked_by     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False, index=True)
    society_id    = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id       = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="SET NULL"), nullable=True)

    # Booking details
    booking_date  = Column(Date, nullable=False, index=True)
    start_time    = Column(Time, nullable=False)
    end_time      = Column(Time, nullable=False)
    guest_count   = Column(Integer, default=1, nullable=False)
    purpose       = Column(Text, nullable=True)
    special_notes = Column(Text, nullable=True)

    # Status
    status        = Column(Enum(BookingStatus, values_callable=lambda e: [x.value for x in e]), default=BookingStatus.PENDING, nullable=False, index=True)

    # Approval
    approved_by   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at   = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    cancelled_at  = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)

    # Financial (future)
    charge_amount = Column(Float, nullable=True)
    deposit_amount = Column(Float, nullable=True)
    deposit_paid  = Column(Boolean, default=False, nullable=False)
    deposit_refunded = Column(Boolean, default=False, nullable=False)

    # Relationships
    amenity   = relationship("Amenity", back_populates="bookings")
    slot      = relationship("AmenitySlot", back_populates="bookings")
    booker    = relationship("User", foreign_keys=[booked_by])
    approver  = relationship("User", foreign_keys=[approved_by])
    society   = relationship("Society")
    flat      = relationship("Flat")
    usage_log = relationship("AmenityUsageLog", back_populates="booking", uselist=False)

    def __repr__(self):
        return f"<AmenityBooking {self.booking_date} status={self.status}>"


# ── AmenityUsageLog ───────────────────────────────────────────────────────────

class AmenityUsageLog(Base, TimestampMixin):
    __tablename__ = "amenity_usage_logs"

    booking_id    = Column(UUID(as_uuid=True), ForeignKey("amenity_bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    amenity_id    = Column(UUID(as_uuid=True), ForeignKey("amenities.id", ondelete="CASCADE"), nullable=False, index=True)
    society_id    = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    used_by       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actual_start  = Column(DateTime, nullable=True)
    actual_end    = Column(DateTime, nullable=True)
    guest_count   = Column(Integer, nullable=True)
    damage_noted  = Column(Boolean, default=False, nullable=False)
    damage_notes  = Column(Text, nullable=True)
    extra_charges = Column(Float, nullable=True)

    booking = relationship("AmenityBooking", back_populates="usage_log")
