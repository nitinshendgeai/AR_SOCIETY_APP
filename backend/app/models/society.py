from sqlalchemy import Column, String, Text, Boolean, Integer
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class Society(Base, TimestampMixin):
    __tablename__ = "societies"

    # Identity
    society_code  = Column(String(20), nullable=True, unique=True, index=True)
    name          = Column(String(255), nullable=False, unique=True, index=True)
    address       = Column(Text, nullable=True)
    city          = Column(String(100), nullable=True)
    state         = Column(String(100), nullable=True)
    pincode       = Column(String(20), nullable=True)
    country       = Column(String(50), default="India", nullable=True)

    # Operational
    timezone      = Column(String(50), default="Asia/Kolkata", nullable=False)
    total_wings   = Column(Integer, nullable=True)
    total_flats   = Column(Integer, nullable=True)

    # Contact
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    emergency_contact_name  = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)
    logo_url      = Column(String(500), nullable=True)
    website       = Column(String(255), nullable=True)

    # Settings (future: store as JSON config)
    maintenance_day  = Column(Integer, nullable=True)  # day of month for dues
    late_fee_percent = Column(Integer, nullable=True)  # % late fee
    allow_tenant_portal = Column(Boolean, default=True, nullable=False)
    require_visitor_approval = Column(Boolean, default=True, nullable=False)

    # Relationships
    wings = relationship("Wing", back_populates="society", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Society {self.society_code or self.name}>"
