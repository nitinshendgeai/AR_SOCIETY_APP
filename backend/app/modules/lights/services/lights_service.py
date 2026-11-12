import re
from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_
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
    AREA_KINDS, CAMERA, LOCATIONS, MAX_PER_KIND, NOT_WORKING, SPOT, TUBE, WORKING, CommonArea, CommonAreaItem,
    LightCheckEntry, LightPoint,
)


def point_key(wing_id, floor_number: int, kind: str, location: str, flat_id) -> str:
    return f"{wing_id}:{floor_number}:{kind}:{location}:{flat_id or '-'}"


def area_location(kind: str, n: int) -> str:
    return f"{kind}_{n}"


def area_point_key(area_id, kind: str, n: int) -> str:
    return f"area:{area_id}:{kind}:{n}"


def parse_area_location(location: str):
    """("tube", 3) for "tube_3"; None when it is not of that shape."""
    m = re.fullmatch(r"([a-z]+)_(\d+)", location or "")
    return (m.group(1), int(m.group(2))) if m else None


def area_light_label(kind: str, n: int, count: int) -> str:
    """"Tube light 3" - or just "Camera" when the area has only one of that kind."""
    one = AREA_KINDS[kind][0]
    return one if count <= 1 else f"{one} {n}"


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
            self._apply_check(point, status, now, user, r.get("note"))
            counts[status] += 1
        self.db.commit()
        return {"checked": len(seen), "working": counts[WORKING], "not_working": counts[NOT_WORKING],
                "checked_at": iso_utc(now)}

    def _apply_check(self, point: LightPoint, status: str, now: datetime, user: User, note: Optional[str]) -> None:
        """Set how a light was found, keep when it was first found not working, and log the check."""
        was_not_working = point.status == NOT_WORKING and point.is_active
        point.is_active = True
        point.status = status
        point.last_checked_at = now
        point.last_checked_by = user.id
        if status == NOT_WORKING:
            if not was_not_working or point.not_working_since is None:
                point.not_working_since = now
        else:
            point.not_working_since = None
        self.db.add(LightCheckEntry(society_id=point.society_id, point_id=point.id, event="checked", status=status,
                                    at=now, by_user=user.id, note=(note or None)))

    # ── Replacing ────────────────────────────────────────────────────────────

    def _labels(self, points: List[LightPoint]) -> List[dict]:
        area_ids = {p.area_id for p in points if p.area_id}
        areas = {a.id: a for a in self.db.query(CommonArea).filter(CommonArea.id.in_(area_ids)).all()} if area_ids else {}
        counts = ({(i.area_id, i.kind): i.count for i in self.db.query(CommonAreaItem)
                   .filter(CommonAreaItem.area_id.in_(area_ids), CommonAreaItem.is_active == True).all()}  # noqa: E712
                  if area_ids else {})
        wing_ids = {p.wing_id for p in points if p.wing_id} | {a.wing_id for a in areas.values() if a.wing_id}
        wings = {w.id: w for w in self.db.query(Wing).filter(Wing.id.in_(wing_ids)).all()} if wing_ids else {}
        flat_ids = {p.flat_id for p in points if p.flat_id}
        flats = {f.id: f for f in self.db.query(Flat).filter(Flat.id.in_(flat_ids)).all()} if flat_ids else {}
        names = self._names(p.last_checked_by for p in points)
        out = []
        for p in points:
            area = areas.get(p.area_id)
            wing = wings.get(area.wing_id if area else p.wing_id)
            flat = flats.get(p.flat_id)
            if area is not None:
                parsed = parse_area_location(p.location)
                label = (area_light_label(p.kind, parsed[1], counts.get((p.area_id, p.kind), 1))
                         if parsed and p.kind in AREA_KINDS else p.location)
            else:
                label = LOCATIONS[p.kind].get(p.location, p.location)
            out.append({
                "id": str(p.id), "kind": p.kind, "location": p.location, "label": label,
                "area_id": str(p.area_id) if p.area_id else None, "area_name": area.name if area else None,
                "wing_id": str(wing.id) if wing else None, "wing_name": wing.name if wing else None,
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
        q = self.db.query(LightPoint).filter(LightPoint.society_id == society_id, LightPoint.status == NOT_WORKING,
                                             LightPoint.is_active == True)  # noqa: E712
        if wing_id is not None:
            wing_areas = [a.id for a in self.db.query(CommonArea).filter(CommonArea.wing_id == wing_id).all()]
            q = q.filter(or_(LightPoint.wing_id == wing_id, LightPoint.area_id.in_(wing_areas)))
        points = q.order_by(LightPoint.not_working_since).all()
        rows = self._labels(points)
        return {"count": len(rows), "tube": sum(1 for r in rows if r["kind"] == TUBE),
                "spot": sum(1 for r in rows if r["kind"] == SPOT),
                "camera": sum(1 for r in rows if r["kind"] == CAMERA),
                "other": sum(1 for r in rows if r["kind"] not in (TUBE, SPOT, CAMERA)), "rows": rows}

    def replace(self, point_id: UUID, item_id: Optional[UUID], quantity: float, note: Optional[str], user: User) -> dict:
        """The light was replaced: take the new tube or bulb out of the store and mark the light working again.
        A camera that was put right (not swapped for a spare from the store) needs no store item."""
        point = self.db.query(LightPoint).filter(LightPoint.id == point_id).first()
        if point is None:
            raise HTTPException(status_code=404, detail="Light not found")
        assert_society_access(user, point.society_id)
        if point.status != NOT_WORKING:
            raise HTTPException(status_code=409, detail="This light is not marked as not working")
        label = self._labels([point])[0]["label"]
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
        points = (self.db.query(LightPoint).filter(LightPoint.society_id == society_id, LightPoint.is_active == True)  # noqa: E712
                  .all())
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
            """The same wing / floor / flat narrowing for the lights of floors and flats, wherever they are queried.
            A common area's lights are reported separately, below."""
            q = q.filter(LightPoint.area_id.is_(None), LightPoint.is_active == True)  # noqa: E712
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
            for flats_wing, floor_no, n in (self.db.query(Flat.wing_id, Flat.floor, func.count(Flat.id))
                                         .filter(Flat.wing_id.in_(wing_ids), Flat.is_active == True)  # noqa: E712
                                         .group_by(Flat.wing_id, Flat.floor).all()):
                flat_counts[(flats_wing, floor_no)] = n

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
        # Common areas: all of them, or a wing's own; a floor or a flat narrows the report to floors, so no areas then.
        area_rows, area_sum = [], {"checked": 0, WORKING: 0, NOT_WORKING: 0, "replaced": 0, "still": 0}
        if floor_number is None and flat is None:
            area_rows, area_sum = self._area_report(society_id, wing_id, start, end)

        flat_lights = None
        if flat is not None:
            by_location = {p.location: (st, at) for p, st, at in final.values()}
            flat_lights = [{"location": loc, "label": name,
                            "status": by_location[loc][0] if loc in by_location else None,
                            "checked_at": iso_utc(by_location[loc][1]) if loc in by_location else None}
                           for loc, name in LOCATIONS[SPOT].items()]
        return {
            "month": label,
            "totals": {"checked": len(final) + area_sum["checked"], "working": totals[WORKING] + area_sum[WORKING],
                       "not_working": totals[NOT_WORKING] + area_sum[NOT_WORKING],
                       "replaced": replaced + area_sum["replaced"], "still_not_working": still + area_sum["still"]},
            "floors": out,
            "areas": area_rows,
            "areas_not_checked": sum(1 for r in area_rows if r["status"] == "not_checked"),
            "areas_partly_checked": sum(1 for r in area_rows if r["status"] == "partial"),
            "floors_not_checked": sum(1 for r in out if r["status"] == "not_checked"),
            "floors_partly_checked": sum(1 for r in out if r["status"] == "partial"),
            "flat": {"id": str(flat.id), "label": flat.flat_number, "lights": flat_lights} if flat is not None else None,
        }

    def _area_report(self, society_id: UUID, wing_id: Optional[UUID], start: datetime, end: datetime):
        """The common areas' part of a month's report: per area, per kind, how many were checked and found how."""
        q = self.db.query(CommonArea).filter(CommonArea.society_id == society_id, CommonArea.is_active == True)  # noqa: E712
        if wing_id is not None:
            q = q.filter(CommonArea.wing_id == wing_id)
        areas = q.order_by(CommonArea.name).all()
        summary = {"checked": 0, WORKING: 0, NOT_WORKING: 0, "replaced": 0, "still": 0}
        if not areas:
            return [], summary
        ids = [a.id for a in areas]
        items = self._items_by_area(ids)
        wings = {w.id: w.name for w in self.db.query(Wing).filter(Wing.id.in_({a.wing_id for a in areas if a.wing_id})).all()}
        rows = (self.db.query(LightCheckEntry, LightPoint)
                .join(LightPoint, LightCheckEntry.point_id == LightPoint.id)
                .filter(LightCheckEntry.society_id == society_id, LightCheckEntry.at >= start, LightCheckEntry.at < end,
                        LightPoint.area_id.in_(ids), LightPoint.is_active == True)  # noqa: E712
                .order_by(LightCheckEntry.at, LightCheckEntry.created_at).all())
        final: Dict[UUID, tuple] = {}
        for entry, point in rows:
            final[point.id] = (point, entry.status)
            if entry.event == "replaced":
                summary["replaced"] += 1
        per_area = {a.id: {"id": str(a.id), "name": a.name, "wing_name": wings.get(a.wing_id),
                           "items": [{"kind": it.kind, "label": AREA_KINDS[it.kind][1], "expected": it.count,
                                      "checked": 0, "working": 0, "not_working": 0} for it in items.get(a.id, [])]}
                    for a in areas}
        for point, status in final.values():
            summary["checked"] += 1
            summary[status] += 1
            for it in per_area[point.area_id]["items"]:
                if it["kind"] == point.kind:
                    it["checked"] += 1
                    it[status] += 1
        out = []
        for a in areas:
            row = per_area[a.id]
            expected = sum(i["expected"] for i in row["items"])
            checked = sum(i["checked"] for i in row["items"])
            row["status"] = "not_checked" if checked == 0 else ("done" if checked >= expected else "partial")
            out.append(row)
        summary["still"] = (self.db.query(func.count(LightPoint.id))
                            .filter(LightPoint.area_id.in_(ids), LightPoint.status == NOT_WORKING,
                                    LightPoint.is_active == True).scalar() or 0)  # noqa: E712
        return out, summary

    # ── Common areas: set up by the Manager or Admin, checked by the staff ───

    def _items_by_area(self, area_ids) -> Dict[UUID, List[CommonAreaItem]]:
        order = list(AREA_KINDS)
        rows = (self.db.query(CommonAreaItem).filter(CommonAreaItem.area_id.in_(area_ids),
                                                     CommonAreaItem.is_active == True).all())  # noqa: E712
        out: Dict[UUID, List[CommonAreaItem]] = {}
        for it in sorted(rows, key=lambda i: order.index(i.kind) if i.kind in order else 99):
            out.setdefault(it.area_id, []).append(it)
        return out

    def _area_out(self, area: CommonArea, items: List[CommonAreaItem], wing_name: Optional[str]) -> dict:
        return {"id": str(area.id), "name": area.name,
                "wing_id": str(area.wing_id) if area.wing_id else None, "wing_name": wing_name,
                "items": [{"kind": i.kind, "label": AREA_KINDS[i.kind][1], "count": i.count} for i in items]}

    def _area(self, area_id: UUID, user: User) -> CommonArea:
        area = self.db.query(CommonArea).filter(CommonArea.id == area_id, CommonArea.is_active == True).first()  # noqa: E712
        if area is None:
            raise HTTPException(status_code=404, detail="Area not found")
        assert_society_access(user, area.society_id)
        return area

    @staticmethod
    def _clean_items(items: List[dict]) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for it in items:
            kind, count = it.get("kind"), it.get("count")
            if kind not in AREA_KINDS:
                raise HTTPException(status_code=422, detail=f"'{kind}' is not something an area can hold")
            if kind in out:
                raise HTTPException(status_code=422, detail=f"{AREA_KINDS[kind][1]} is listed twice")
            if not isinstance(count, int) or not 1 <= count <= MAX_PER_KIND:
                raise HTTPException(status_code=422, detail=f"How many {AREA_KINDS[kind][1].lower()}? Between 1 and {MAX_PER_KIND}")
            out[kind] = count
        if not out:
            raise HTTPException(status_code=422, detail="Add at least one thing to check in this area")
        return out

    def _name_free(self, society_id: UUID, name: str, exclude: Optional[UUID] = None) -> None:
        q = self.db.query(CommonArea).filter(CommonArea.society_id == society_id, CommonArea.is_active == True,  # noqa: E712
                                             func.lower(CommonArea.name) == name.lower())
        if exclude is not None:
            q = q.filter(CommonArea.id != exclude)
        if q.first() is not None:
            raise HTTPException(status_code=409, detail=f"There is already an area called {name}")

    def _area_input(self, society_id: UUID, name: str, wing_id: Optional[UUID], items: List[dict], user: User):
        name = (name or "").strip()
        if not 2 <= len(name) <= 80:
            raise HTTPException(status_code=422, detail="Give the area a name (2 to 80 letters)")
        counts = self._clean_items(items)
        wing_name = None
        if wing_id is not None:
            wing_name = self._wing(society_id, wing_id, user).name
        return name, counts, wing_name

    def list_areas(self, society_id: UUID, user: User) -> List[dict]:
        assert_society_access(user, society_id)
        areas = (self.db.query(CommonArea).filter(CommonArea.society_id == society_id, CommonArea.is_active == True)  # noqa: E712
                 .order_by(CommonArea.name).all())
        if not areas:
            return []
        items = self._items_by_area([a.id for a in areas])
        wings = {w.id: w.name for w in self.db.query(Wing).filter(Wing.id.in_({a.wing_id for a in areas if a.wing_id})).all()}
        return [self._area_out(a, items.get(a.id, []), wings.get(a.wing_id)) for a in areas]

    def create_area(self, society_id: UUID, name: str, wing_id: Optional[UUID], items: List[dict], user: User) -> dict:
        assert_society_access(user, society_id)
        name, counts, wing_name = self._area_input(society_id, name, wing_id, items, user)
        self._name_free(society_id, name)
        area = CommonArea(society_id=society_id, wing_id=wing_id, name=name)
        self.db.add(area)
        self.db.flush()
        for kind, count in counts.items():
            self.db.add(CommonAreaItem(society_id=society_id, area_id=area.id, kind=kind, count=count))
        self.db.commit()
        return self._area_out(area, self._items_by_area([area.id]).get(area.id, []), wing_name)

    def update_area(self, area_id: UUID, name: str, wing_id: Optional[UUID], items: List[dict], user: User) -> dict:
        area = self._area(area_id, user)
        name, counts, wing_name = self._area_input(area.society_id, name, wing_id, items, user)
        self._name_free(area.society_id, name, exclude=area.id)
        area.name, area.wing_id = name, wing_id
        existing = {i.kind: i for i in self.db.query(CommonAreaItem).filter(CommonAreaItem.area_id == area.id).all()}
        for kind, count in counts.items():
            row = existing.get(kind)
            if row is None:
                self.db.add(CommonAreaItem(society_id=area.society_id, area_id=area.id, kind=kind, count=count))
            else:
                row.count, row.is_active = count, True
        for kind, row in existing.items():
            if kind not in counts:
                row.is_active = False
        # Lights beyond the new count (or of a kind taken away) drop out of the lists; they come back if the count does.
        for point in self.db.query(LightPoint).filter(LightPoint.area_id == area.id).all():
            parsed = parse_area_location(point.location)
            if parsed and parsed[0] in counts and parsed[1] > counts[parsed[0]]:
                point.is_active = False
            elif parsed and parsed[0] not in counts:
                point.is_active = False
        self.db.commit()
        return self._area_out(area, self._items_by_area([area.id]).get(area.id, []), wing_name)

    def delete_area(self, area_id: UUID, user: User) -> None:
        """Take an area off the lists. Its history is kept."""
        area = self._area(area_id, user)
        area.is_active = False
        for point in self.db.query(LightPoint).filter(LightPoint.area_id == area.id).all():
            point.is_active = False
        self.db.commit()

    def area_sheet(self, area_id: UUID, user: User) -> dict:
        """What to check in one area: each kind it holds, numbered, with how each light was last found."""
        area = self._area(area_id, user)
        items = self._items_by_area([area.id]).get(area.id, [])
        points = {p.point_key: p for p in self.db.query(LightPoint).filter(LightPoint.area_id == area.id,
                                                                         LightPoint.is_active == True).all()}  # noqa: E712
        names = self._names(p.last_checked_by for p in points.values())
        groups = []
        for it in items:
            cells = []
            for n in range(1, it.count + 1):
                p = points.get(area_point_key(area.id, it.kind, n))
                cells.append({
                    "location": area_location(it.kind, n), "label": area_light_label(it.kind, n, it.count),
                    "status": p.status if p else None,
                    "last_checked_at": iso_utc(p.last_checked_at) if p else None,
                    "last_checked_by": names.get(p.last_checked_by) if p else None,
                    "not_working_since": iso_utc(p.not_working_since) if p and p.not_working_since else None,
                })
            groups.append({"flat_id": None, "label": AREA_KINDS[it.kind][1], "points": cells})
        return {"area_id": str(area.id), "name": area.name, "groups": groups}

    def record_area(self, area_id: UUID, results: List[dict], user: User) -> dict:
        """Save what was found in an area, every line stamped with the same date and time."""
        area = self._area(area_id, user)
        if not results:
            raise HTTPException(status_code=422, detail="Mark at least one light")
        counts = {i.kind: i.count for i in self._items_by_area([area.id]).get(area.id, [])}
        points = {p.point_key: p for p in self.db.query(LightPoint).filter(LightPoint.area_id == area.id).all()}
        now = datetime.utcnow()
        seen = set()
        tally = {WORKING: 0, NOT_WORKING: 0}
        for r in results:
            location, status = r["location"], r["status"]
            parsed = parse_area_location(location)
            if parsed is None or parsed[0] not in counts or not 1 <= parsed[1] <= counts[parsed[0]]:
                raise HTTPException(status_code=422, detail=f"'{location}' is not in this area")
            if status not in tally:
                raise HTTPException(status_code=422, detail="Mark each light Working or Not working")
            kind, n = parsed
            key = area_point_key(area.id, kind, n)
            if key in seen:
                raise HTTPException(status_code=422, detail="A light is marked twice")
            seen.add(key)
            point = points.get(key)
            if point is None:
                point = LightPoint(society_id=area.society_id, area_id=area.id, kind=kind, location=location,
                                   point_key=key, status=status, last_checked_at=now, last_checked_by=user.id)
                self.db.add(point)
                self.db.flush()
            self._apply_check(point, status, now, user, r.get("note"))
            tally[status] += 1
        self.db.commit()
        return {"checked": len(seen), "working": tally[WORKING], "not_working": tally[NOT_WORKING],
                "checked_at": iso_utc(now)}
