"""
Parking Management Models — operational ERP architecture.

Hierarchy:  Society → ParkingZone → ParkingFloor → ParkingSlot
Workflows:  Slot Allocation, Visitor Parking, Violation Tracking, Access Logs
"""
import enum
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, Date, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


# ── Enums ─────────────────────────────────────────────────────────────────────

class SlotType(str, enum.Enum):
    RESIDENT  = "resident"
    TENANT    = "tenant"
    VISITOR   = "visitor"
    STAFF     = "staff"
    RESERVED  = "reserved"
    DISABLED  = "disabled"


class SlotStatus(str, enum.Enum):
    AVAILABLE = "available"
    OCCUPIED  = "occupied"
    RESERVED  = "reserved"
    BLOCKED   = "blocked"
    UNDER_MAINTENANCE = "under_maintenance"


class AllocationStatus(str, enum.Enum):
    ACTIVE    = "active"
    RELEASED  = "released"
    EXPIRED   = "expired"
    SUSPENDED = "suspended"


class VisitorParkingStatus(str, enum.Enum):
    ACTIVE    = "active"
    COMPLETED = "completed"
    EXPIRED   = "expired"
    CANCELLED = "cancelled"


class ViolationType(str, enum.Enum):
    UNAUTHORIZED     = "unauthorized"
    EXPIRED_PERMIT   = "expired_permit"
    WRONG_SLOT       = "wrong_slot"
    DOUBLE_PARKING   = "double_parking"
    BLOCKED_ACCESS   = "blocked_access"
    RESTRICTED_ZONE  = "restricted_zone"
    NO_PARKING       = "no_parking"


class AccessType(str, enum.Enum):
    ENTRY = "entry"
    EXIT  = "exit"


class AccessMethod(str, enum.Enum):
    MANUAL   = "manual"
    RFID     = "rfid"
    ANPR     = "anpr"       # future: camera plate recognition
    APP      = "app"
    BIOMETRIC= "biometric"


# ── ParkingZone ───────────────────────────────────────────────────────────────

class ParkingZone(Base, TimestampMixin):
    __tablename__ = "parking_zones"

    society_id  = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    name        = Column(String(100), nullable=False)      # "Basement", "Open", "Covered"
    code        = Column(String(20), nullable=True)        # "B1", "OA"
    description = Column(Text, nullable=True)
    total_slots = Column(Integer, default=0, nullable=False)

    society = relationship("Society")
    floors  = relationship("ParkingFloor", back_populates="zone", cascade="all, delete-orphan")
    slots   = relationship("ParkingSlot",  back_populates="zone")

    def __repr__(self):
        return f"<ParkingZone {self.name}>"


# ── ParkingFloor ──────────────────────────────────────────────────────────────

class ParkingFloor(Base, TimestampMixin):
    __tablename__ = "parking_floors"

    zone_id    = Column(UUID(as_uuid=True), ForeignKey("parking_zones.id", ondelete="CASCADE"), nullable=False, index=True)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    name       = Column(String(50), nullable=False)   # "B1", "B2", "Ground"
    level      = Column(Integer, nullable=True)       # -1, 0, 1 (negative = basement)
    total_slots = Column(Integer, default=0, nullable=False)

    zone    = relationship("ParkingZone", back_populates="floors")
    society = relationship("Society")
    slots   = relationship("ParkingSlot", back_populates="floor")


# ── ParkingSlot ───────────────────────────────────────────────────────────────

class ParkingSlot(Base, TimestampMixin):
    __tablename__ = "parking_slots"

    society_id  = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_id     = Column(UUID(as_uuid=True), ForeignKey("parking_zones.id", ondelete="CASCADE"), nullable=False, index=True)
    floor_id    = Column(UUID(as_uuid=True), ForeignKey("parking_floors.id", ondelete="SET NULL"), nullable=True, index=True)

    slot_number = Column(String(20), nullable=False, index=True)
    slot_type   = Column(Enum(SlotType), default=SlotType.RESIDENT, nullable=False, index=True)
    status      = Column(Enum(SlotStatus), default=SlotStatus.AVAILABLE, nullable=False, index=True)

    # Physical attributes
    length_ft   = Column(Integer, nullable=True)
    width_ft    = Column(Integer, nullable=True)
    is_covered  = Column(Boolean, default=False, nullable=False)
    is_ev_charging = Column(Boolean, default=False, nullable=False)   # EV-ready

    # RFID / smart access readiness
    rfid_reader_id  = Column(String(100), nullable=True)
    camera_id       = Column(String(100), nullable=True)   # ANPR readiness
    barrier_id      = Column(String(100), nullable=True)   # boom barrier

    notes       = Column(Text, nullable=True)

    society  = relationship("Society")
    zone     = relationship("ParkingZone", back_populates="slots")
    floor    = relationship("ParkingFloor", back_populates="slots")
    allocations = relationship("ParkingAllocation", back_populates="slot", cascade="all, delete-orphan")
    access_logs = relationship("ParkingAccessLog",  back_populates="slot", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ParkingSlot {self.slot_number} [{self.status}]>"


# ── ParkingAllocation (resident/tenant/staff permanent allocation) ─────────────

class ParkingAllocation(Base, TimestampMixin):
    __tablename__ = "parking_allocations"

    society_id    = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    slot_id       = Column(UUID(as_uuid=True), ForeignKey("parking_slots.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id       = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="SET NULL"), nullable=True, index=True)
    vehicle_id    = Column(UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True)
    allocated_to_user   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    allocated_by        = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    allocation_type = Column(Enum(SlotType), nullable=False, index=True)
    status          = Column(Enum(AllocationStatus), default=AllocationStatus.ACTIVE, nullable=False, index=True)
    start_date      = Column(Date, nullable=False)
    end_date        = Column(Date, nullable=True)   # null = indefinite
    monthly_charge  = Column(Integer, nullable=True)   # future finance integration
    notes           = Column(Text, nullable=True)
    released_at     = Column(DateTime, nullable=True)
    released_by     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    society      = relationship("Society")
    slot         = relationship("ParkingSlot", back_populates="allocations")
    flat         = relationship("Flat")
    vehicle      = relationship("Vehicle")
    allocated_user = relationship("User", foreign_keys=[allocated_to_user])
    allocator    = relationship("User", foreign_keys=[allocated_by])
    releaser     = relationship("User", foreign_keys=[released_by])

    def __repr__(self):
        return f"<ParkingAllocation slot={self.slot_id} [{self.status}]>"


# ── VisitorParking (temporary assignment for visitor vehicles) ─────────────────

class VisitorParking(Base, TimestampMixin):
    __tablename__ = "visitor_parking"

    society_id      = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    slot_id         = Column(UUID(as_uuid=True), ForeignKey("parking_slots.id", ondelete="SET NULL"), nullable=True, index=True)
    visitor_id      = Column(UUID(as_uuid=True), nullable=True, index=True)   # ref to visitors table
    vehicle_number  = Column(String(30), nullable=False, index=True)
    vehicle_type    = Column(String(50), nullable=True)
    assigned_by     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    check_in_time   = Column(DateTime, nullable=True)
    check_out_time  = Column(DateTime, nullable=True)
    expected_duration_hours = Column(Integer, default=4, nullable=False)
    status          = Column(Enum(VisitorParkingStatus), default=VisitorParkingStatus.ACTIVE, nullable=False, index=True)
    purpose         = Column(String(255), nullable=True)
    host_flat_id    = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="SET NULL"), nullable=True)
    notes           = Column(Text, nullable=True)

    # RFID/access readiness
    temp_access_code = Column(String(50), nullable=True)   # QR/temp code

    society  = relationship("Society")
    slot     = relationship("ParkingSlot")
    assigner = relationship("User", foreign_keys=[assigned_by])
    host_flat = relationship("Flat")

    def __repr__(self):
        return f"<VisitorParking {self.vehicle_number} [{self.status}]>"


# ── ParkingViolation ──────────────────────────────────────────────────────────

class ParkingViolation(Base, TimestampMixin):
    __tablename__ = "parking_violations"

    society_id       = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    slot_id          = Column(UUID(as_uuid=True), ForeignKey("parking_slots.id", ondelete="SET NULL"), nullable=True, index=True)
    vehicle_number   = Column(String(30), nullable=False, index=True)
    vehicle_id       = Column(UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True)
    violation_type   = Column(Enum(ViolationType), nullable=False, index=True)
    reported_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    description      = Column(Text, nullable=True)
    photo_url        = Column(String(500), nullable=True)
    is_resolved      = Column(Boolean, default=False, nullable=False, index=True)
    resolved_at      = Column(DateTime, nullable=True)
    fine_amount      = Column(Integer, nullable=True)   # future finance integration

    society   = relationship("Society")
    slot      = relationship("ParkingSlot")
    vehicle   = relationship("Vehicle", foreign_keys=[vehicle_id])
    reporter  = relationship("User", foreign_keys=[reported_by])
    resolver  = relationship("User", foreign_keys=[resolved_by])

    def __repr__(self):
        return f"<ParkingViolation {self.vehicle_number} [{self.violation_type}]>"


# ── ParkingAccessLog (RFID / manual gate entry log) ──────────────────────────

class ParkingAccessLog(Base, TimestampMixin):
    __tablename__ = "parking_access_logs"

    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    slot_id        = Column(UUID(as_uuid=True), ForeignKey("parking_slots.id", ondelete="SET NULL"), nullable=True, index=True)
    vehicle_id     = Column(UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True)
    vehicle_number = Column(String(30), nullable=False, index=True)
    user_id        = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    access_type    = Column(Enum(AccessType), nullable=False, index=True)
    access_method  = Column(Enum(AccessMethod), default=AccessMethod.MANUAL, nullable=False)
    access_time    = Column(DateTime, nullable=False, index=True)
    gate_id        = Column(UUID(as_uuid=True), nullable=True)   # Gate ref
    rfid_tag       = Column(String(100), nullable=True)          # scanned RFID
    is_authorized  = Column(Boolean, default=True, nullable=False, index=True)
    notes          = Column(Text, nullable=True)

    society = relationship("Society")
    slot    = relationship("ParkingSlot", back_populates="access_logs")
    vehicle = relationship("Vehicle", foreign_keys=[vehicle_id])
    user    = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<ParkingAccessLog {self.vehicle_number} {self.access_type} {self.access_time}>"
