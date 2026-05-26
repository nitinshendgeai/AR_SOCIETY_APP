from sqlalchemy import Column, String, Boolean, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base, TimestampMixin


class VehicleType(str, enum.Enum):
    CAR        = "car"
    MOTORCYCLE = "motorcycle"
    SCOOTER    = "scooter"
    AUTO       = "auto"
    TRUCK      = "truck"
    VAN        = "van"
    BICYCLE    = "bicycle"
    OTHER      = "other"


class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicles"

    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id        = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=True, index=True)
    resident_id    = Column(UUID(as_uuid=True), ForeignKey("residents.id", ondelete="SET NULL"), nullable=True, index=True)
    tenant_id      = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)
    registered_by  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Identity
    vehicle_number = Column(String(30), nullable=False, index=True)
    vehicle_type   = Column(Enum(VehicleType), default=VehicleType.CAR, nullable=False, index=True)
    make           = Column(String(100), nullable=True)   # Honda, Maruti
    model          = Column(String(100), nullable=True)   # City, Swift
    color          = Column(String(50), nullable=True)
    year           = Column(String(4), nullable=True)

    # Parking
    parking_slot   = Column(String(20), nullable=True, index=True)

    # Future integrations
    rfid_tag       = Column(String(100), nullable=True, unique=True, index=True)   # RFID gate integration
    fasttag_number = Column(String(50), nullable=True)   # FASTag for toll/barrier
    insurance_expiry = Column(String(10), nullable=True)  # YYYY-MM-DD
    rc_number      = Column(String(50), nullable=True)    # Registration Certificate

    remarks        = Column(Text, nullable=True)

    # Relationships
    society      = relationship("Society")
    flat         = relationship("Flat", back_populates="vehicles")
    resident     = relationship("Resident", back_populates="vehicles")
    tenant       = relationship("Tenant", back_populates="vehicles")
    registrar    = relationship("User", foreign_keys=[registered_by])

    def __repr__(self):
        return f"<Vehicle {self.vehicle_number} [{self.vehicle_type}]>"
