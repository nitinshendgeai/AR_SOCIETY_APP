from sqlalchemy import Column, String, Date, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    full_name        = Column(String(255), nullable=False)
    phone            = Column(String(20), nullable=True)
    email            = Column(String(255), nullable=True)
    lease_start_date = Column(Date, nullable=True)
    lease_end_date   = Column(Date, nullable=True)
    monthly_rent     = Column(Numeric(12, 2), nullable=True)
    security_deposit = Column(Numeric(12, 2), nullable=True)
    id_proof_type    = Column(String(50), nullable=True)
    id_proof_number  = Column(String(100), nullable=True)
    emergency_contact_name  = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)

    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    flat = relationship("Flat", back_populates="tenants")
    user = relationship("User", back_populates="tenants")

    def __repr__(self):
        return f"<Tenant id={self.id} name={self.full_name!r}>"
