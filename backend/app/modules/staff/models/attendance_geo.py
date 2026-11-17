"""Location check for staff attendance.

- AttendanceGeoSpot: a place staff may check in or out from (the gate, the office...): a point and a radius in metres.
- AttendanceGeoSettings: how the society applies it: `off`, `flag` (every check-in is accepted, those outside the spots or
  without a usable location are marked for the manager) or `block` (a check-in outside is refused).
- AttendanceGeoEvent: what the phone reported at one check-in or check-out, and the verdict.

Locations are recorded only at the moment of a check-in or check-out, never tracked in between.
"""
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin

MODES = ("off", "flag", "block")
# inside: within a spot's radius. outside: farther. no_location / low_accuracy / mocked: the phone gave nothing usable.
STATUSES = ("inside", "outside", "no_location", "low_accuracy", "mocked")


class AttendanceGeoSpot(Base, TimestampMixin):
    __tablename__ = "attendance_geo_spots"

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_m = Column(Integer, nullable=False, default=10, server_default="10")


class AttendanceGeoSettings(Base, TimestampMixin):
    __tablename__ = "attendance_geo_settings"
    __table_args__ = (UniqueConstraint("society_id", name="uq_attendance_geo_settings_society"),)

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    mode = Column(String(10), nullable=False, default="flag", server_default="flag")
    max_accuracy_m = Column(Integer, nullable=False, default=20, server_default="20")


class AttendanceGeoEvent(Base, TimestampMixin):
    __tablename__ = "attendance_geo_events"

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    attendance_id = Column(UUID(as_uuid=True), ForeignKey("staff_attendance.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(3), nullable=False)                        # in | out
    status = Column(String(20), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    accuracy_m = Column(Float, nullable=True)
    distance_m = Column(Float, nullable=True)                       # to the nearest spot
    spot_name = Column(String(100), nullable=True)
    mocked = Column(Boolean, nullable=False, default=False, server_default="false")

    attendance = relationship("StaffAttendance", back_populates="geo_events")
