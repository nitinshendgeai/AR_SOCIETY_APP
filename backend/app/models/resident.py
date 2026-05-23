from sqlalchemy import Column, String, Date, Boolean, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base, TimestampMixin


class ResidentType(str, enum.Enum):
    OWNER      = "owner"
    CO_OWNER   = "co_owner"
    FAMILY     = "family"
    DEPENDENT  = "dependent"


class Resident(Base, TimestampMixin):
    __tablename__ = "residents"

    full_name      = Column(String(255), nullable=False)
    phone          = Column(String(20), nullable=True)
    email          = Column(String(255), nullable=True)
    date_of_birth  = Column(Date, nullable=True)
    resident_type  = Column(Enum(ResidentType), default=ResidentType.OWNER, nullable=False)
    is_primary     = Column(Boolean, default=False)     # primary contact for the flat
    move_in_date   = Column(Date, nullable=True)
    move_out_date  = Column(Date, nullable=True)
    id_proof_type  = Column(String(50), nullable=True)
    id_proof_number = Column(String(100), nullable=True)

    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    flat = relationship("Flat", back_populates="residents")
    user = relationship("User", back_populates="residents")

    def __repr__(self):
        return f"<Resident id={self.id} name={self.full_name!r}>"
