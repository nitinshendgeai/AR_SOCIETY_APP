from sqlalchemy import Column, String, Integer, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class Floor(Base, TimestampMixin):
    __tablename__ = "floors"
    # Partial unique index (active rows only) — see Wing's __table_args__
    # for why a plain UniqueConstraint here would make a deleted floor's
    # number permanently unreusable.
    __table_args__ = (
        Index(
            "uq_floor_wing_number",
            "wing_id", "floor_number",
            unique=True,
            postgresql_where=text("is_active = true"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    floor_number = Column(Integer, nullable=False)        # 0 = Ground, 1, 2, …
    floor_name   = Column(String(50), nullable=True)      # "Ground Floor", "1st Floor"

    wing_id    = Column(UUID(as_uuid=True), ForeignKey("wings.id", ondelete="CASCADE"), nullable=False, index=True)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    wing = relationship("Wing", back_populates="floors")

    def __repr__(self):
        return f"<Floor wing={self.wing_id} number={self.floor_number}>"
