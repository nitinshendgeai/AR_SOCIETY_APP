from sqlalchemy import Column, String, Integer, Text, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class Wing(Base, TimestampMixin):
    __tablename__ = "wings"
    # Partial unique indexes (active rows only) rather than plain
    # UniqueConstraints — a soft-deleted wing (is_active=False) must free up
    # its name/code for reuse, since the app-level assert_unique_name/
    # assert_unique_code checks already only look at active rows, so a hard
    # constraint on the raw columns silently disagreed with them and made a
    # deleted wing's name permanently unreusable. Mirrors the pattern already
    # used for Vehicle/Resident (see alembic/versions/d5e6f7a8b9c0_*.py).
    __table_args__ = (
        Index(
            "uq_wing_society_name",
            "society_id", "name",
            unique=True,
            postgresql_where=text("is_active = true"),
            sqlite_where=text("is_active = 1"),
        ),
        Index(
            "uq_wing_society_code",
            "society_id", "code",
            unique=True,
            postgresql_where=text("is_active = true"),
            sqlite_where=text("is_active = 1"),
        ),
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
