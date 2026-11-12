import re
from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.tenant_scope import assert_society_access
from app.models.flat import Flat
from app.models.floor import Floor
from app.models.society import Society
from app.models.user import User
from app.models.wing import Wing
from app.modules.inventory.schemas.inventory import IssueCreate
from app.modules.inventory.services.inventory_service import InventoryService
from app.utils.local_time import iso_utc, local_to_utc_naive, local_today, zone
from app.modules.lights.models.lights import (
    CAMERA, LOCATIONS, NOT_WORKING, SPOT, TUBE, WORKING, LightCheckEntry, LightPoint,
)


def point_key(wing_id, floor_number: int, kind: str, location: str, flat_id) -> str:
    return f"{wing_id}:{floor_number}:{kind}:{location}:{flat_id or '-'}"


class LightService:
    def __init__(self, db: Session):
        self.db = db

    # ── Lookups ──────────────────────────────────────────────────────────────

    def _wing(self, society_id: UUID, wing_id: UUID, user: User) -> Wing:
        assert_society_access(user, society_id)
        wing = self.db.query(Wing).filter(Wing.id == wing_id, Wing.society_id == society_id,
                                          Wing.is_active == True).first()  # noqa: E712
        if wing is None:
            raise HTTPException(status_code=404, detail="Wing not found")
        return wing

    def _flats(self, wing_id: UUID, floor_number: int) -> List[Flat]:
        flats = (self.db.query(Flat).filter(Flat.wing_id == wing_id, Flat.floor == floor_number,
                                            Flat.is_active == True).all())  # noqa: E712
        return sorted(flats, key=lambda f: (len(f.flat_number), f.flat_number))

    @staticmethod
    def _kind(kind: str) -> str:
        if kind not in LOCATIONS:
            raise HTTPException(status_code=422, detail="Choose tube lights or spot lights")
        return kind

    def floors(self, society_id: UUID, wing_id: UUID, user: User) -> List[dict]:
        """The floors of a wing, for the picker."""
        self._wing(society_id, wing_id, user)
        rows = (self.db.query(Floor).filter(Floor.wing_id == wing_id, Floor.is_active == True)  # noqa: E712
                .order_by(Floor.floor_number).all())
        return [{"floor_number": f.floor_number, "name": f.floor_name or f"Floor {f.floor_number}"} for f in rows]

    def _points_of(self, wing_id: UUID, floor_number: int, kind: str) -> Dict[str, LightPoint]:
        rows = (self.db.query(LightPoint).filter(LightPoint.wing_id == wing_id, LightPoint.floor_number == floor_number,
                                                 LightPoint.kind == kind).all())
        return {p.point_key: p for p in rows}

    def _names(self, user_ids) -> Dict[UUID, str]:
        ids = {i for i in user_ids if i}
        if not ids:
            return {}
        return {u.id: u.full_name for u in self.db.query(User).filter(User.id.in_(ids)).all()}

    # ── The form ─────────────────────────────────────────────────────────────

    def sheet(self, society_id: UUID, wing_id: UUID, floor_number: int, kind: str, user: User) -> dict:
        """What to check on one floor: its 4 tube lights, or the 3 spot lights of each flat, each with how it was last
        found and when."""
        self._wing(society_id, wing_id, user)
        kind = self._kind(kind)
        points = self._points_of(wing_id, floor_number, kind)
        names = self._names(p.last_checked_by for p in points.values())

        def cell(location: str, label: str, flat_id) -> dict:
            p = points.get(point_key(wing_id, floor_number, kind, location, flat_id))
            return {
                "location": location, "label": label,
                "status": p.status if p else None,                      # None: not checked yet
                "last_checked_at": iso_utc(p.last_checked_at) if p else None,
                "last_checked_by": names.get(p.last_checked_by) if p else None,
                "not_working_since": iso_utc(p.not_working_since) if p and p.not_working_since else None,
            }

        if kind in (TUBE, CAMERA):                       # the floor's own: its tube lights, or its camera
            groups = [{"flat_id": None, "label": "This floor",
                       "points": [cell(loc, label, None) for loc, label in LOCATIONS[kind].items()]}]
        else:
            groups = [{"flat_id": str(f.id), "label": f"Flat {f.flat_number}",
                       "points": [cell(loc, label, f.id) for loc, label in LOCATIONS[SPOT].items()]}
                      for f in self._flats(wing_id, floor_number)]
        return {"wing_id": str(wing_id), "floor_number": floor_number, "kind": kind, "groups": groups}

    def record(self, society_id: UUID, wing_id: UUID, floor_number: int, kind: str, results: List[dict],
               user: User) -> dict:
        """Save what the electrician or plumber found. Every line is stamped with the same date and time."""
        self._wing(society_id, wing_id, user)
        kind = self._kind(kind)
        if not results:
            raise HTTPException(status_code=422, detail="Mark at least one light")
        flats = {str(f.id): f for f in self._flats(wing_id, floor_number)} if kind == SPOT else {}
        points = self._points_of(wing_id, floor_number, kind)
        now = datetime.utcnow()
        seen = set()
        counts = {WORKING: 0, NOT_WORKING: 0}
        for r in results:
            location, status = r["location"], r["status"]
            if location not in LOCATIONS[kind]:
                raise HTTPException(status_code=422, detail=f"'{location}' is not a {kind} light")
            if status not in counts:
                raise HTTPException(status_code=422, detail="Mark each light Working or Not working")
            flat_id = r.get("flat_id")
            if kind == SPOT:
                if flat_id is None or str(flat_id) not in flats:
                    raise HTTPException(status_code=422, detail="That flat is not on this floor")
                flat_id = flats[str(flat_id)].id
            else:
                flat_id = None
            key = point_key(wing_id, floor_number, kind, location, flat_id)
            if key in seen:
                raise HTTPException(status_code=422, detail="A light is marked twice")
            seen.add(key)
            point = points.get(key)
            if point is None:
                point = LightPoint(society_id=society_id, wing_id=wing_id, floor_number=floor_number, kind=kind,
                                   location=location, flat_id=flat_id, point_key=key, status=status,
                                   last_checked_at=now, last_checked_by=user.id)
                self.db.add(point)
                self.db.flush()
            was_not_working = point.status == NOT_WORKING
            point.status = status
            point.last_checked_at = now
            point.last_checked_by = user.id
            if status == NOT_WORKING:
                if not was_not_working or point.not_working_since is None:
                    point.not_working_since = now
            else:
                point.not_working_since = None
            self.db.add(LightCheckEntry(society_id=society_id, point_id=point.id, event="checked", status=status,
                                        at=now, by_user=user.id, note=(r.get("note") or None)))
            counts[status] += 1
        self.db.commit()
        return {"checked": len(seen), "working": counts[WORKING], "not_working": counts[NOT_WORKING],
                "checked_at": iso_utc(now)}

    # ── Replacing ────────────────────────────────────────────────────────────

    def _labels(self, points: List[LightPoint]) -> List[dict]:
        wings = {w.id: w for w in self.db.query(Wing).filter(Wing.id.in_({p.wing_id for p in points})).all()} if points else {}
        flat_ids = {p.flat_id for p in points if p.flat_id}
        flats = {f.id: f for f in self.db.query(Flat).filter(Flat.id.in_(flat_ids)).all()} if flat_ids else {}
        names = self._names(p.last_checked_by for p in points)
        out = []
        for p in points:
            wing = wings.get(p.wing_id)
            flat = flats.get(p.flat_id)
            out.append({
                "id": str(p.id), "kind": p.kind, "location": p.location,
                "label": LOCATIONS[p.kind].get(p.location, p.location),
                "wing_id": str(p.wing_id), "wing_name": wing.name if wing else None,
                "floor_number": p.floor_number,
                "flat_id": str(p.flat_id) if p.flat_id else None, "flat_label": flat.flat_number if flat else None,
                "status": p.status,
                "not_working_since": iso_utc(p.not_working_since),
                "last_checked_at": iso_utc(p.last_checked_at),
                "last_checked_by": names.get(p.last_checked_by),
            })
        return out

    def not_working(self, society_id: UUID, wing_id: Optional[UUID], user: User) -> dict:
        """Every light found not working and not replaced yet, oldest first."""
        assert_society_access(user, society_id)
        q = self.db.query(LightPoint).filter(LightPoint.society_id == society_id, LightPoint.status == NOT_WORKING)
        if wing_id is not None:
            q = q.filter(LightPoint.wing_id == wing_id)
        points = q.order_by(LightPoint.not_working_since, LightPoint.floor_number).all()
        rows = self._labels(points)
        return {"count": len(rows), "tube": sum(1 for r in rows if r["kind"] == TUBE),
                "spot": sum(1 for r in rows if r["kind"] == SPOT),
                "camera": sum(1 for r in rows if r["kind"] == CAMERA), "rows": rows}

    def replace(self, point_id: UUID, item_id: Optional[UUID], quantity: float, note: Optional[str], user: User) -> dict:
        """The light was replaced: take the new tube or bulb out of the store and mark the light working again.
        A camera that was put right (not swapped for a spare from the store) needs no store item."""
        point = self.db.query(LightPoint).filter(LightPoint.id == point_id).first()
        if point is None:
            raise HTTPException(status_code=404, detail="Light not found")
        assert_society_access(user, point.society_id)
        if point.status != NOT_WORKING:
            raise HTTPException(status_code=409, detail="This light is not marked as not working")
        label = LOCATIONS[point.kind].get(point.location, point.location)
        if item_id is None and point.kind != CAMERA:
            raise HTTPException(status_code=422, detail="Choose the tube or bulb that was used")
        if item_id is not None:
            # The store first: it refuses when there is not enough stock, and then nothing here changes.
            InventoryService(self.db).issue_item(
                IssueCreate(item_id=item_id, issued_to_user=user.id, quantity_issued=quantity, consumed=True,
                            purpose=f"Replaced {label.lower()}" + (f" - {note}" if note else "")), user)
        now = datetime.utcnow()
        point.status = WORKING
        point.not_working_since = None
        point.last_checked_at = now
        point.last_checked_by = user.id
        self.db.add(LightCheckEntry(society_id=point.society_id, point_id=point.id, event="replaced", status=WORKING,
                                    at=now, by_user=user.id, note=note or None, item_id=item_id,
                                    quantity=quantity if item_id is not None else None))
        self.db.commit()
        return {"replaced_at": iso_utc(now)}

    # ── Summary ──────────────────────────────────────────────────────────────

    def summary(self, society_id: UUID, user: User) -> dict:
        """How many lights are known, working and not working, for a dashboard or the top of the screen."""
        assert_society_access(user, society_id)
        points = self.db.query(LightPoint).filter(LightPoint.society_id == society_id).all()
        last = max((p.last_checked_at for p in points), default=None)
        return {"total": len(points), "working": sum(1 for p in points if p.status == WORKING),
                "not_working": sum(1 for p in points if p.status == NOT_WORKING),
                "last_checked_at": iso_utc(last)}

    # ── The monthly report ───────────────────────────────────────────────────

    @staticmethod
    def _month_window(month: Optional[str], tz) -> tuple:
        """(label, first instant, first instant of the next month) of a "YYYY-MM" month on the society's clock, as
        naive UTC. No month means the current one."""
        if month is None:
            today = local_today(tz)
            year, mon = today.year, today.month
        else:
            m = re.fullmatch(r"(\d{4})-(\d{2})", month)
            if not m or not 1 <= int(m.group(2)) <= 12:
                raise HTTPException(status_code=422, detail="Month must look like 2026-11")
            year, mon = int(m.group(1)), int(m.group(2))
        nxt = date(year + (mon == 12), mon % 12 + 1, 1)
        from datetime import time as _time
        start = local_to_utc_naive(date(year, mon, 1), _time(0, 0), tz)
        end = local_to_utc_naive(nxt, _time(0, 0), tz)
        return f"{year:04d}-{mon:02d}", start, end

    def report(self, society_id: UUID, month: Optional[str], user: User, wing_id: Optional[UUID] = None,
               floor_number: Optional[int] = None, flat_id: Optional[UUID] = None) -> dict:
        """What was checked in a month: the lights found working and not working, how many were replaced, and for
        every floor whether it was checked at all (4 tube lights and the camera, plus 3 spot lights for each flat).

        Narrowed by a wing, a floor, or one flat. A flat is only its 3 spot lights: the tube lights belong to the floor."""
        assert_society_access(user, society_id)
        society = self.db.query(Society).filter(Society.id == society_id).first()
        tz = zone(getattr(society, "timezone", None))
        label, start, end = self._month_window(month, tz)

        flat = None
        if flat_id is not None:
            flat = (self.db.query(Flat).join(Wing, Flat.wing_id == Wing.id)
                    .filter(Flat.id == flat_id, Wing.society_id == society_id, Flat.is_active == True).first())  # noqa: E712
            if flat is None:
                raise HTTPException(status_code=404, detail="Flat not found")
            wing_id, floor_number = flat.wing_id, flat.floor
        elif wing_id is not None:
            self._wing(society_id, wing_id, user)

        def narrowed(q):
            """The same wing / floor / flat narrowing for light points, wherever they are queried."""
            if wing_id is not None:
                q = q.filter(LightPoint.wing_id == wing_id)
            if floor_number is not None:
                q = q.filter(LightPoint.floor_number == floor_number)
            if flat is not None:
                q = q.filter(LightPoint.flat_id == flat.id)
            return q

        # Each light counts once, as it stood at the end of the month; a replacement after a check makes it working.
        rows = narrowed(self.db.query(LightCheckEntry, LightPoint)
                        .join(LightPoint, LightCheckEntry.point_id == LightPoint.id)
                        .filter(LightCheckEntry.society_id == society_id, LightCheckEntry.at >= start,
                                LightCheckEntry.at < end)
                        ).order_by(LightCheckEntry.at, LightCheckEntry.created_at).all()
        final: Dict[UUID, tuple] = {}              # point id -> (point, status at month end, when)
        replaced = 0
        for entry, point in rows:
            final[point.id] = (point, entry.status, entry.at)
            if entry.event == "replaced":
                replaced += 1

        floor_q = (self.db.query(Floor, Wing).join(Wing, Floor.wing_id == Wing.id)
                   .filter(Floor.society_id == society_id, Floor.is_active == True,  # noqa: E712
                           Wing.is_active == True))  # noqa: E712
        if wing_id is not None:
            floor_q = floor_q.filter(Floor.wing_id == wing_id)
        if floor_number is not None:
            floor_q = floor_q.filter(Floor.floor_number == floor_number)
        floors = floor_q.all()
        wing_ids = {w.id for _f, w in floors}
        flat_counts: Dict[tuple, int] = {}
        if wing_ids:
            for wing_id, floor_no, n in (self.db.query(Flat.wing_id, Flat.floor, func.count(Flat.id))
                                         .filter(Flat.wing_id.in_(wing_ids), Flat.is_active == True)  # noqa: E712
                                         .group_by(Flat.wing_id, Flat.floor).all()):
                flat_counts[(wing_id, floor_no)] = n

        per_floor: Dict[tuple, dict] = {}
        for floor, wing in floors:
            flats = 1 if flat is not None else flat_counts.get((wing.id, floor.floor_number), 0)
            per_floor[(wing.id, floor.floor_number)] = {
                "wing_id": str(wing.id), "wing_name": wing.name, "floor_number": floor.floor_number,
                "floor_name": floor.floor_name or f"Floor {floor.floor_number}", "flats": flats,
                "tube": {"expected": 0 if flat is not None else len(LOCATIONS[TUBE]),
                         "checked": 0, "working": 0, "not_working": 0},
                "spot": {"expected": flats * len(LOCATIONS[SPOT]), "checked": 0, "working": 0, "not_working": 0},
                "camera": {"expected": 0 if flat is not None else len(LOCATIONS[CAMERA]),
                           "checked": 0, "working": 0, "not_working": 0},
            }
        totals = {WORKING: 0, NOT_WORKING: 0}
        for point, status, _at in final.values():
            totals[status] = totals.get(status, 0) + 1
            row = per_floor.get((point.wing_id, point.floor_number))
            if row is not None:
                part = row[point.kind]
                part["checked"] += 1
                part[status] += 1

        out = []
        for row in sorted(per_floor.values(), key=lambda r: (r["wing_name"], r["floor_number"])):
            expected = sum(row[k]["expected"] for k in (TUBE, SPOT, CAMERA))
            checked = sum(row[k]["checked"] for k in (TUBE, SPOT, CAMERA))
            row["status"] = "not_checked" if checked == 0 else ("done" if checked >= expected else "partial")
            out.append(row)

        still = narrowed(self.db.query(func.count(LightPoint.id))
                         .filter(LightPoint.society_id == society_id, LightPoint.status == NOT_WORKING)).scalar() or 0
        flat_lights = None
        if flat is not None:
            by_location = {p.location: (st, at) for p, st, at in final.values()}
            flat_lights = [{"location": loc, "label": name,
                            "status": by_location[loc][0] if loc in by_location else None,
                            "checked_at": iso_utc(by_location[loc][1]) if loc in by_location else None}
                           for loc, name in LOCATIONS[SPOT].items()]
        return {
            "month": label,
            "totals": {"checked": len(final), "working": totals[WORKING], "not_working": totals[NOT_WORKING],
                       "replaced": replaced, "still_not_working": still},
            "floors": out,
            "floors_not_checked": sum(1 for r in out if r["status"] == "not_checked"),
            "floors_partly_checked": sum(1 for r in out if r["status"] == "partial"),
            "flat": {"id": str(flat.id), "label": flat.flat_number, "lights": flat_lights} if flat is not None else None,
        }
