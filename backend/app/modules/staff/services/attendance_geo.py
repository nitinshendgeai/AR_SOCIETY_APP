"""
Is the phone where staff are meant to check in from?

The check runs on the server, on what the phone reports (latitude, longitude, how accurate the reading is, and whether
Android says it is a mocked location), so a changed app cannot simply say "inside".

Verdicts, in this order:
- `mocked`: the phone says the location is faked.
- `no_location`: nothing usable was sent.
- `low_accuracy`: the reading is less accurate than the society's limit (indoors, under a roof): the person should wait for
  a better one rather than be judged on a guess.
- `inside` / `outside`: the distance to the nearest spot against that spot's radius.

With the society's mode `off`, or no spot set up, nothing is checked and nothing is recorded: attendance works as before.
`flag` accepts every check-in and records the verdict for the manager; `block` refuses anything but `inside`.
"""
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.staff.models.attendance_geo import (
    MODES, AttendanceGeoEvent, AttendanceGeoSettings, AttendanceGeoSpot,
)

EARTH_RADIUS_M = 6371008.8
DEFAULT_MODE = "flag"
DEFAULT_MAX_ACCURACY_M = 20


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres (haversine)."""
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


@dataclass
class GeoVerdict:
    status: str
    mode: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy_m: Optional[float] = None
    distance_m: Optional[float] = None
    spot_name: Optional[str] = None
    radius_m: Optional[int] = None
    mocked: bool = False

    @property
    def refused(self) -> bool:
        return self.mode == "block" and self.status != "inside"

    def message(self, max_accuracy_m: int) -> str:
        if self.status == "mocked":
            return "A fake or mocked location was detected. Turn it off to continue."
        if self.status == "no_location":
            return "Turn on your phone's location and allow it for this app, then try again."
        if self.status == "low_accuracy":
            return (f"Your phone's location is only accurate to {round(self.accuracy_m or 0)} m (the limit is {max_accuracy_m} m). "
                    "Go to open sky, wait a moment and try again.")
        return f"You are {round(self.distance_m or 0)} m from {self.spot_name} (allowed {self.radius_m} m)."


class AttendanceGeoService:
    def __init__(self, db: Session):
        self.db = db

    # ── Setup ────────────────────────────────────────────────────────────────────────────────────────────────────────
    def settings(self, society_id: UUID) -> dict:
        row = self.db.query(AttendanceGeoSettings).filter(AttendanceGeoSettings.society_id == society_id).first()
        return {"mode": row.mode if row else DEFAULT_MODE,
                "max_accuracy_m": row.max_accuracy_m if row else DEFAULT_MAX_ACCURACY_M}

    def save_settings(self, society_id: UUID, mode: str, max_accuracy_m: int) -> dict:
        if mode not in MODES:
            raise HTTPException(422, "Mode must be off, flag or block")
        if not (5 <= max_accuracy_m <= 100):
            raise HTTPException(422, "The accuracy limit is 5 to 100 metres")
        row = self.db.query(AttendanceGeoSettings).filter(AttendanceGeoSettings.society_id == society_id).first()
        if not row:
            row = AttendanceGeoSettings(society_id=society_id)
            self.db.add(row)
        row.mode, row.max_accuracy_m = mode, max_accuracy_m
        self.db.flush()
        return self.settings(society_id)

    def spots(self, society_id: UUID) -> List[AttendanceGeoSpot]:
        return (self.db.query(AttendanceGeoSpot).filter(AttendanceGeoSpot.society_id == society_id,
                                                        AttendanceGeoSpot.is_active == True)  # noqa: E712
                .order_by(AttendanceGeoSpot.name).all())

    def status_for_staff(self, society_id: UUID) -> dict:
        """What the staff app needs to know before it asks for the phone's location."""
        s = self.settings(society_id)
        return {"enabled": s["mode"] != "off" and bool(self.spots(society_id)), **s}

    # ── The check ────────────────────────────────────────────────────────────────────────────────────────────────────
    def assess(self, society_id: UUID, reading: Optional[dict]) -> Optional[GeoVerdict]:
        """The verdict for a reading, or None when no check applies. `reading`: latitude, longitude, accuracy_m, mocked."""
        s = self.settings(society_id)
        spots = self.spots(society_id)
        if s["mode"] == "off" or not spots:
            return None
        v = GeoVerdict(status="no_location", mode=s["mode"])
        if not reading or reading.get("latitude") is None or reading.get("longitude") is None:
            return v
        v.latitude, v.longitude = reading["latitude"], reading["longitude"]
        v.accuracy_m, v.mocked = reading.get("accuracy_m"), bool(reading.get("mocked"))
        nearest = min(spots, key=lambda sp: distance_m(v.latitude, v.longitude, sp.latitude, sp.longitude))
        v.distance_m = distance_m(v.latitude, v.longitude, nearest.latitude, nearest.longitude)
        v.spot_name, v.radius_m = nearest.name, nearest.radius_m
        if v.mocked:
            v.status = "mocked"
        elif v.accuracy_m is None or v.accuracy_m > s["max_accuracy_m"]:
            v.status = "low_accuracy"
        else:
            v.status = "inside" if v.distance_m <= nearest.radius_m else "outside"
        return v

    def enforce(self, society_id: UUID, reading: Optional[dict]) -> Optional[GeoVerdict]:
        """`assess`, refusing (422) when the society blocks and the phone is not inside a spot."""
        v = self.assess(society_id, reading)
        if v and v.refused:
            raise HTTPException(422, v.message(self.settings(society_id)["max_accuracy_m"]))
        return v

    def record(self, society_id: UUID, attendance_id: UUID, kind: str, v: Optional[GeoVerdict]) -> None:
        if v is None:
            return
        self.db.add(AttendanceGeoEvent(
            society_id=society_id, attendance_id=attendance_id, kind=kind, status=v.status, latitude=v.latitude,
            longitude=v.longitude, accuracy_m=v.accuracy_m,
            distance_m=round(v.distance_m, 1) if v.distance_m is not None else None, spot_name=v.spot_name, mocked=v.mocked))
