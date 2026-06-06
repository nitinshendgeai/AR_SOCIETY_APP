from sqlalchemy import Column, String, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class Wing(Base, TimestampMixin):
    __tablename__ = "wings"
    __table_args__ = (
        UniqueConstraint("society_id", "name", name="uq_wing_society_name"),
        UniqueConstraint("society_id", "code", name="uq_wing_society_code"),
    )

    name         = Column(String(100), nullable=False)
    code         = Column(String(20), nullable=True)       # e.g. "A", "B", "North"
    description  = Column(Text, nullable=True)
    total_floors = Column(Integer, nullable=True)

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    society = relationship("Society", back_populates="wings")
    flats   = relationship("Flat", back_populates="wing", cascade="all, delete-orphan")
    floors  = relationship("Floor", back_populates="wing", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Wing id={self.id} name={self.name!r}>"
