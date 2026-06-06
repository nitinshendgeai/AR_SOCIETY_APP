from sqlalchemy import Column, String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class Floor(Base, TimestampMixin):
    __tablename__ = "floors"
    __table_args__ = (
        UniqueConstraint("wing_id", "floor_number", name="uq_floor_wing_number"),
    )

    floor_number = Column(Integer, nullable=False)        # 0 = Ground, 1, 2, …
    floor_name   = Column(String(50), nullable=True)      # "Ground Floor", "1st Floor"

    wing_id    = Column(UUID(as_uuid=True), ForeignKey("wings.id", ondelete="CASCADE"), nullable=False, index=True)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    wing = relationship("Wing", back_populates="floors")

    def __repr__(self):
        return f"<Floor wing={self.wing_id} number={self.floor_number}>"
