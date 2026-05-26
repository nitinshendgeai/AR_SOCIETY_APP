from sqlalchemy import Column, String, Integer, Float, Enum, ForeignKey, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base, TimestampMixin


class FlatType(str, enum.Enum):
    ONE_BHK   = "1BHK"
    TWO_BHK   = "2BHK"
    THREE_BHK = "3BHK"
    FOUR_BHK  = "4BHK"
    PENTHOUSE = "Penthouse"
    STUDIO    = "Studio"
    OTHER     = "Other"


class OccupancyStatus(str, enum.Enum):
    OWNER_OCCUPIED  = "owner_occupied"
    TENANT_OCCUPIED = "tenant_occupied"
    VACANT          = "vacant"


class MaintenanceStatus(str, enum.Enum):
    CLEAR       = "clear"
    DUE         = "due"
    OVERDUE     = "overdue"
    DISPUTED    = "disputed"


class Flat(Base, TimestampMixin):
    __tablename__ = "flats"

    flat_number        = Column(String(20), nullable=False)
    floor              = Column(Integer, nullable=True)
    flat_type          = Column(Enum(FlatType), default=FlatType.TWO_BHK, nullable=True)
    area_sqft          = Column(Float, nullable=True)
    occupancy_status   = Column(Enum(OccupancyStatus), default=OccupancyStatus.VACANT, nullable=True)
    maintenance_status = Column(Enum(MaintenanceStatus), default=MaintenanceStatus.CLEAR, nullable=True)

    # Parking
    parking_slot       = Column(String(20), nullable=True)
    parking_slot_2     = Column(String(20), nullable=True)  # second slot

    # KYC / docs readiness
    kyc_verified       = Column(Boolean, default=False, nullable=False)
    remarks            = Column(Text, nullable=True)

    wing_id = Column(UUID(as_uuid=True), ForeignKey("wings.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    wing      = relationship("Wing", back_populates="flats")
    residents = relationship("Resident", back_populates="flat", cascade="all, delete-orphan")
    tenants   = relationship("Tenant",   back_populates="flat", cascade="all, delete-orphan")
    vehicles  = relationship("Vehicle",  back_populates="flat", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Flat {self.flat_number}>"
