"""The gym's attendance book: who came in, and when they left.

The Gym Trainer keeps it at the gym door. He picks the flat, ticks the members who arrive, and ticks them out when they
leave. Only the owners' side of the society uses the gym (owners, co-owners, their family and dependents, the people
on the Residents list); tenants are never listed. The member's name and flat are written on each visit as they were that
day, so the weekly and monthly reports stay right if someone later moves out or is renamed."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin


class GymVisit(Base, TimestampMixin):
    __tablename__ = "gym_visits"
    __table_args__ = (
        Index("ix_gym_visits_society_in", "society_id", "checked_in_at"),
    )

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="SET NULL"), nullable=True, index=True)
    resident_id = Column(UUID(as_uuid=True), ForeignKey("residents.id", ondelete="SET NULL"), nullable=True, index=True)

    # As they were on the day.
    member_name = Column(String(255), nullable=False)
    flat_label = Column(String(60), nullable=False)
    member_type = Column(String(20), nullable=True)            # owner, co_owner, family, dependent

    # Stored as naive UTC, like every other timestamp here.
    checked_in_at = Column(DateTime, nullable=False)
    checked_out_at = Column(DateTime, nullable=True)
    checked_in_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    checked_out_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Closed on a later day than the visit (nobody ticked them out): the time is when it was closed, not when they left,
    # so the report counts the visit but not its length.
    closed_late = Column(Boolean, nullable=False, default=False)
