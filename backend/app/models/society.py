from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class Society(Base, TimestampMixin):
    __tablename__ = "societies"

    name         = Column(String(255), nullable=False, unique=True, index=True)
    address      = Column(Text, nullable=True)
    city         = Column(String(100), nullable=True)
    state        = Column(String(100), nullable=True)
    pincode      = Column(String(20), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    logo_url     = Column(String(500), nullable=True)

    # Relationships
    wings = relationship("Wing", back_populates="society", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Society id={self.id} name={self.name!r}>"
