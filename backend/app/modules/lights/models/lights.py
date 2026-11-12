"""Common lights the society keeps working: the tube lights on each floor and its staircase, the spot lights in the
hall, bedroom and kitchen of each flat, and the camera on each floor.

A light point is created the first time it is checked, so nothing has to be set up in advance. Every check and every
replacement is kept as an entry with the date, the time and the person, so the months can be compared."""
from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin

TUBE, SPOT, CAMERA = "tube", "spot", "camera"
WORKING, NOT_WORKING = "working", "not_working"

# location code -> the words the screen shows
TUBE_LOCATIONS = {
    "floor_1": "Floor tube light 1",
    "floor_2": "Floor tube light 2",
    "stair_1": "Staircase tube light 1",
    "stair_2": "Staircase tube light 2",
}
SPOT_LOCATIONS = {"hall": "Hall", "bedroom": "Bedroom", "kitchen": "Kitchen"}
CAMERA_LOCATIONS = {"camera": "Floor camera"}                  # one camera on each floor
LOCATIONS = {TUBE: TUBE_LOCATIONS, SPOT: SPOT_LOCATIONS, CAMERA: CAMERA_LOCATIONS}


class LightPoint(Base, TimestampMixin):
    __tablename__ = "light_points"
    __table_args__ = (Index("ix_light_points_floor", "wing_id", "floor_number", "kind"),)

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    wing_id = Column(UUID(as_uuid=True), ForeignKey("wings.id", ondelete="CASCADE"), nullable=False)
    floor_number = Column(Integer, nullable=False)                     # 0 = ground, as on the floor and flat records
    kind = Column(String(10), nullable=False)                          # tube | spot | camera
    location = Column(String(20), nullable=False)                      # floor_1 ... stair_2 | hall | bedroom | kitchen
    flat_id = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="CASCADE"), nullable=True)   # spot lights only
    # wing:floor:kind:location:flat - one point once, though a NULL flat would not stop a duplicate in a unique index
    point_key = Column(String(160), nullable=False, unique=True)

    status = Column(String(12), nullable=False)                        # working | not_working, as last checked
    last_checked_at = Column(DateTime, nullable=False)
    last_checked_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    not_working_since = Column(DateTime, nullable=True)                # when it was first found out, until replaced


class LightCheckEntry(Base, TimestampMixin):
    __tablename__ = "light_check_entries"

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    point_id = Column(UUID(as_uuid=True), ForeignKey("light_points.id", ondelete="CASCADE"), nullable=False, index=True)
    event = Column(String(10), nullable=False)                         # checked | replaced
    status = Column(String(12), nullable=False)                        # the state after this event
    at = Column(DateTime, nullable=False, index=True)
    by_user = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, nullable=True)
    # a replacement: what was taken from the store
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True)
    quantity = Column(Float, nullable=True)
