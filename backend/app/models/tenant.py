from sqlalchemy import Column, String, Date, Numeric, ForeignKey, Boolean, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base, TimestampMixin


class PoliceVerificationStatus(str, enum.Enum):
    PENDING    = "pending"
    SUBMITTED  = "submitted"
    VERIFIED   = "verified"
    REJECTED   = "rejected"


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    full_name        = Column(String(255), nullable=False)
    phone            = Column(String(20), nullable=True)
    email            = Column(String(255), nullable=True)

    # Agreement
    agreement_start_date = Column(Date, nullable=True)
    agreement_end_date   = Column(Date, nullable=True)
    lease_start_date     = Column(Date, nullable=True)   # kept for BC
    lease_end_date       = Column(Date, nullable=True)
    monthly_rent         = Column(Numeric(12, 2), nullable=True)
    security_deposit     = Column(Numeric(12, 2), nullable=True)
    agreement_doc_url    = Column(String(500), nullable=True)

    # KYC
    id_proof_type    = Column(String(50), nullable=True)
    id_proof_number  = Column(String(100), nullable=True)
    kyc_verified     = Column(Boolean, default=False, nullable=False)
    kyc_doc_url      = Column(String(500), nullable=True)

    # Police verification
    police_verification_status = Column(
        Enum(PoliceVerificationStatus),
        default=PoliceVerificationStatus.PENDING, nullable=True
    )
    police_verification_date = Column(Date, nullable=True)

    # Emergency contact
    emergency_contact_name  = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)

    # Move-in/out
    move_in_date  = Column(Date, nullable=True)
    move_out_date = Column(Date, nullable=True)
    remarks       = Column(Text, nullable=True)

    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    flat     = relationship("Flat", back_populates="tenants")
    user     = relationship("User", back_populates="tenants")
    vehicles = relationship("Vehicle", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant {self.full_name}>"
