"""Shops: the commercial units of a society, kept apart from the flats — their own owners, possession dates and
electricity connections."""
from sqlalchemy import Column, Date, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin

OCCUPANCY = ("owner_run", "rented", "vacant")
OCCUPANCY_LABELS = {"owner_run": "Run by the owner", "rented": "Rented out", "vacant": "Vacant"}


class Shop(Base, TimestampMixin):
    __tablename__ = "shops"
    # A deleted shop (is_active false) frees its number for reuse.
    __table_args__ = (
        Index("uq_shop_society_number", "society_id", "shop_number", unique=True,
              postgresql_where=text("is_active = true"), sqlite_where=text("is_active = 1")),
    )

    society_id  = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    shop_number = Column(String(30), nullable=False)
    floor       = Column(Integer, nullable=True)
    location    = Column(String(120), nullable=True)            # "Ground floor, Block C"
    area_sqft   = Column(Float, nullable=True)
    business_name = Column(String(150), nullable=True)          # what the shop trades as

    owner_name  = Column(String(255), nullable=False)
    owner_phone = Column(String(20), nullable=True)
    owner_email = Column(String(255), nullable=True)

    occupancy    = Column(String(20), default="vacant", nullable=False)   # owner_run | rented | vacant
    tenant_name  = Column(String(255), nullable=True)                     # who runs it when rented
    tenant_phone = Column(String(20), nullable=True)

    possession_date      = Column(Date, nullable=True)
    electric_meter_no    = Column(String(40), nullable=True)
    electric_consumer_no = Column(String(40), nullable=True)

    remarks    = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    society = relationship("Society")

    def __repr__(self):
        return f"<Shop {self.shop_number}>"
