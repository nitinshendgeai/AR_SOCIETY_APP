from sqlalchemy import Column, String, Date, Boolean, Enum, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base, TimestampMixin


class ResidentType(str, enum.Enum):
    OWNER      = "owner"
    CO_OWNER   = "co_owner"
    FAMILY     = "family"
    DEPENDENT  = "dependent"


class CommunicationPreference(str, enum.Enum):
    APP_ONLY  = "app_only"
    SMS       = "sms"
    EMAIL     = "email"
    WHATSAPP  = "whatsapp"
    ALL       = "all"


class Resident(Base, TimestampMixin):
    __tablename__ = "residents"

    full_name       = Column(String(255), nullable=False)
    phone           = Column(String(20), nullable=True)
    email           = Column(String(255), nullable=True)
    date_of_birth   = Column(Date, nullable=True)
    resident_type   = Column(Enum(ResidentType, values_callable=lambda e: [x.value for x in e]), default=ResidentType.OWNER, nullable=False)
    is_primary      = Column(Boolean, default=False)

    # Move in/out
    move_in_date    = Column(Date, nullable=True)
    move_out_date   = Column(Date, nullable=True)

    # KYC
    id_proof_type   = Column(String(50), nullable=True)
    id_proof_number = Column(String(100), nullable=True)
    kyc_verified    = Column(Boolean, default=False, nullable=False)
    kyc_doc_url     = Column(String(500), nullable=True)

    # Family / emergency
    family_member_count     = Column(Integer, default=0, nullable=False)
    emergency_contact_name  = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)

    # Communication preference
    comm_preference = Column(Enum(CommunicationPreference, values_callable=lambda e: [x.value for x in e]),
                             default=CommunicationPreference.APP_ONLY, nullable=True)

    # Photo
    photo_url = Column(String(500), nullable=True)

    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    flat     = relationship("Flat", back_populates="residents")
    user     = relationship("User", back_populates="residents")
    vehicles = relationship("Vehicle", back_populates="resident", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Resident {self.full_name} [{self.resident_type}]>"
