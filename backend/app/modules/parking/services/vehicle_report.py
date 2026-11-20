"""The vehicle report: what the society knows about vehicles, in four parts.

  * Vehicles   - every resident and tenant vehicle on record: type, flat, parking, and whether its insurance has run out.
  * Parking    - slots by zone (free, taken, blocked), flats with more vehicles than parking, parking that ends soon.
  * Violations - the month's parking violations, the fines charged, taken off or on a bill, and vehicles that keep offending.
  * Gate       - the month's entries and exits (residents, visitors, vehicles nobody knows) and visitor vehicles inside now.

Read-only. It narrows to a wing, a flat, or (for violations and the gate) a month on the society's own calendar."""
import re
from collections import Counter
from datetime import date, datetime, time as dtime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.tenant_scope import assert_society_access
from app.models.flat import Flat, OccupancyStatus
from app.models.society import Society
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.wing import Wing
from app.modules.billing.services.bill_pdf import flat_label
from app.modules.parking.models.parking import (
    AccessType, AllocationStatus, ParkingAccessLog, ParkingAllocation, ParkingSlot, ParkingViolation, ParkingZone,
    SlotStatus, VisitorParking, VisitorParkingStatus,
)
from app.modules.parking.services.parking_service import ParkingService
from app.utils.local_time import iso_utc, local_to_utc_naive, local_today, to_local, zone

INSURANCE_SOON_DAYS = 30
ENDING_SOON_DAYS = 30
VIOLATION_WORDS = {
    "unauthorized": "Unauthorised vehicle", "expired_permit": "Expired permit", "wrong_slot": "Wrong slot",
    "double_parking": "Double parking", "blocked_access": "Blocking access", "restricted_zone": "Restricted zone",
    "no_parking": "No-parking area",
}
FINE_WORDS = {"active": "On the next bill", "billed": "On a bill", "cancelled": "Taken off"}
VEHICLE_WORDS = {"car": "Car", "motorcycle": "Motorcycle", "scooter": "Scooter", "auto": "Auto", "truck": "Truck",
                 "van": "Van", "bicycle": "Bicycle", "other": "Other"}
METHOD_WORDS = {"manual": "Guard", "rfid": "RFID", "anpr": "Camera", "app": "App", "biometric": "Biometric"}


def month_window(month: Optional[str], tz) -> tuple:
    """("2026-11", first instant, first instant of the next month) on the society's clock, as naive UTC."""
    if month is None:
        today = local_today(tz)
        year, mon = today.year, today.month
    else:
        m = re.fullmatch(r"(\d{4})-(\d{2})", month)
        if not m or not 1 <= int(m.group(2)) <= 12:
            raise HTTPException(status_code=422, detail="Month must look like 2026-11")
        year, mon = int(m.group(1)), int(m.group(2))
    nxt = date(year + (mon == 12), mon % 12 + 1, 1)
    return (f"{year:04d}-{mon:02d}", local_to_utc_naive(date(year, mon, 1), dtime(0, 0), tz),
            local_to_utc_naive(nxt, dtime(0, 0), tz))


def _insurance(expiry: Optional[str], today: date) -> str:
    """none | expired | soon | ok, for an expiry written YYYY-MM-DD."""
    try:
        d = date.fromisoformat((expiry or "").strip())
    except ValueError:
        return "none"
    if d < today:
        return "expired"
    return "soon" if d <= today + timedelta(days=INSURANCE_SOON_DAYS) else "ok"


def _cap(rows: List[dict], limit: Optional[int]) -> List[dict]:
    return rows if limit is None else rows[:limit]


class VehicleReportService:
    def __init__(self, db: Session):
        self.db = db
        self.parking = ParkingService(db)

    # ── What the report is narrowed to ────────────────────────────────────────

    def _scope(self, society_id: UUID, wing_id: Optional[UUID], flat_id: Optional[UUID]) -> dict:
        """The flats the report covers: None means every flat; otherwise the set of flat ids, with names for the heading."""
        if flat_id is not None:
            flat = (self.db.query(Flat).join(Wing, Flat.wing_id == Wing.id)
                    .filter(Flat.id == flat_id, Wing.society_id == society_id, Flat.is_active == True).first())  # noqa: E712
            if flat is None:
                raise HTTPException(status_code=404, detail="Flat not found")
            return {"flat_ids": {flat.id}, "wing": flat.wing.name if flat.wing else None, "flat": flat_label(flat)}
        if wing_id is not None:
            wing = self.db.query(Wing).filter(Wing.id == wing_id, Wing.society_id == society_id,
                                              Wing.is_active == True).first()  # noqa: E712
            if wing is None:
                raise HTTPException(status_code=404, detail="Wing not found")
            ids = {f.id for f in self.db.query(Flat.id).filter(Flat.wing_id == wing_id, Flat.is_active == True)}  # noqa: E712
            return {"flat_ids": ids, "wing": wing.name, "flat": None}
        return {"flat_ids": None, "wing": None, "flat": None}

    @staticmethod
    def _in(scope: dict, flat_id) -> bool:
        return scope["flat_ids"] is None or (flat_id is not None and flat_id in scope["flat_ids"])

    # ── The report ────────────────────────────────────────────────────────────

    def build(self, society_id: UUID, user: User, month: Optional[str] = None, wing_id: Optional[UUID] = None,
              flat_id: Optional[UUID] = None, limit: Optional[int] = None) -> dict:
        """[limit]: rows to return in each list (the screen shows a few; the printout and the file take them all)."""
        assert_society_access(user, society_id)
        society = self.db.query(Society).filter(Society.id == society_id).first()
        tz = zone(getattr(society, "timezone", None))
        label, start, end = month_window(month, tz)
        today = local_today(tz)
        scope = self._scope(society_id, wing_id, flat_id)
        flats: Dict[UUID, Flat] = {}

        def flat_text(fid) -> str:
            if fid is None:
                return ""
            if fid not in flats:
                flats[fid] = self.db.query(Flat).filter(Flat.id == fid).first()
            return flat_label(flats[fid]) if flats[fid] else ""

        vehicles = self._vehicles(society_id, user, scope, today, flat_text, limit)
        every_vehicle = vehicles.pop("_rows")                 # the parking part needs all of them, not the screen's few
        return {
            "month": label, "month_label": datetime(int(label[:4]), int(label[5:]), 1).strftime("%B %Y"),
            "as_on": today.isoformat(), "timezone": tz.key, "wing": scope["wing"], "flat": scope["flat"],
            "vehicles": vehicles,
            "parking": self._parking(society_id, scope, today, flat_text, every_vehicle, limit),
            "violations": self._violations(society_id, scope, start, end, tz, flat_text, limit),
            "gate": self._gate(society_id, scope, start, end, tz, flat_text, limit),
        }

    # ── Vehicles ──────────────────────────────────────────────────────────────

    def _vehicles(self, society_id, user, scope, today, flat_text, limit) -> dict:
        rows = []
        for r in self.parking.vehicles_overview(society_id, user):
            if not self._in(scope, r["flat_id"]):
                continue
            rows.append({
                "vehicle_number": r["vehicle_number"], "type": VEHICLE_WORDS.get(r["vehicle_type"], r["vehicle_type"]),
                "make_model": " ".join(p for p in (r["make"], r["model"]) if p), "color": r["color"] or "",
                "flat": flat_text(r["flat_id"]), "flat_id": str(r["flat_id"]) if r["flat_id"] else None,
                "wing": r["wing_name"] or "", "owner": r["owner_name"] or "",
                "category": "Tenant" if r["category"] == "tenant" else "Owner / resident",
                "has_parking": r["has_parking"], "parking_slot": r["parking_slot"] or "",
                "insurance_expiry": r.get("insurance_expiry") or "", "insurance": _insurance(r.get("insurance_expiry"), today),
            })
        by_flat = Counter(r["flat_id"] for r in rows if r["flat_id"])
        # Occupied flats in scope with no vehicle on record
        q = (self.db.query(Flat).join(Wing, Flat.wing_id == Wing.id)
             .filter(Wing.society_id == society_id, Flat.is_active == True,  # noqa: E712
                     Flat.occupancy_status != OccupancyStatus.VACANT))
        if scope["flat_ids"] is not None:
            q = q.filter(Flat.id.in_(scope["flat_ids"]))
        without = sorted(flat_label(f) for f in q.all() if str(f.id) not in by_flat)
        insurance = Counter(r["insurance"] for r in rows)
        summary = {
            "total": len(rows), "with_parking": sum(1 for r in rows if r["has_parking"]),
            "without_parking": sum(1 for r in rows if not r["has_parking"]),
            "by_type": dict(Counter(r["type"] for r in rows).most_common()),
            "by_wing": dict(sorted(Counter(r["wing"] or "-" for r in rows).items())),
            "insurance_expired": insurance["expired"], "insurance_soon": insurance["soon"],
            "insurance_missing": insurance["none"], "flats_without_vehicle": len(without),
        }
        rows.sort(key=lambda r: (r["insurance"] not in ("expired", "soon"), r["flat"], r["vehicle_number"]))
        return {"summary": summary, "rows": _cap(rows, limit), "row_count": len(rows),
                "flats_without_vehicle": without if limit is None else without[:limit], "_rows": rows}

    # ── Parking ───────────────────────────────────────────────────────────────

    def _parking(self, society_id, scope, today, flat_text, vehicle_rows, limit) -> dict:
        zones = self.db.query(ParkingZone).filter(ParkingZone.society_id == society_id,
                                                  ParkingZone.is_active == True).order_by(ParkingZone.name).all()  # noqa: E712
        slots = self.db.query(ParkingSlot).filter(ParkingSlot.society_id == society_id,
                                                  ParkingSlot.is_active == True).all()  # noqa: E712
        allocations = (self.db.query(ParkingAllocation)
                       .filter(ParkingAllocation.society_id == society_id, ParkingAllocation.is_active == True,  # noqa: E712
                               ParkingAllocation.status == AllocationStatus.ACTIVE).all())
        allotted_slots = {a.slot_id for a in allocations}
        zone_rows = []
        for z in zones:
            mine = [s for s in slots if s.zone_id == z.id]
            zone_rows.append({
                "zone": z.name, "code": z.code or "", "total": len(mine),
                "allotted": sum(1 for s in mine if s.id in allotted_slots),
                "free": sum(1 for s in mine if s.status == SlotStatus.AVAILABLE and s.id not in allotted_slots),
                "reserved": sum(1 for s in mine if s.status == SlotStatus.RESERVED),
                "blocked": sum(1 for s in mine if s.status in (SlotStatus.BLOCKED, SlotStatus.UNDER_MAINTENANCE)),
            })
        # Flats with more vehicles than parking
        per_flat: Dict[str, dict] = {}
        for r in vehicle_rows:
            if not r["flat_id"]:
                continue
            f = per_flat.setdefault(r["flat_id"], {"flat": r["flat"], "vehicles": 0, "with_parking": 0})
            f["vehicles"] += 1
            f["with_parking"] += 1 if r["has_parking"] else 0
        short = sorted(({**f, "without_parking": f["vehicles"] - f["with_parking"]}
                        for f in per_flat.values() if f["with_parking"] < f["vehicles"]), key=lambda f: f["flat"])
        # Parking that ends soon
        soon = []
        for a in allocations:
            if a.end_date and today <= a.end_date <= today + timedelta(days=ENDING_SOON_DAYS) and self._in(scope, a.flat_id):
                soon.append({"slot": a.slot_number or "", "flat": flat_text(a.flat_id), "vehicle": a.vehicle_number or "",
                             "ends": a.end_date.isoformat()})
        soon.sort(key=lambda s: s["ends"])
        summary = {
            "slots": sum(z["total"] for z in zone_rows), "allotted": sum(z["allotted"] for z in zone_rows),
            "free": sum(z["free"] for z in zone_rows), "blocked": sum(z["blocked"] for z in zone_rows),
            "flats_short": len(short), "ending_soon": len(soon),
        }
        return {"summary": summary, "zones": zone_rows, "flats_short": _cap(short, limit), "flats_short_count": len(short),
                "ending_soon": _cap(soon, limit), "ending_soon_count": len(soon)}

    # ── Violations ────────────────────────────────────────────────────────────

    def _violations(self, society_id, scope, start, end, tz, flat_text, limit) -> dict:
        found = (self.db.query(ParkingViolation)
                 .filter(ParkingViolation.society_id == society_id, ParkingViolation.is_active == True,  # noqa: E712
                         ParkingViolation.created_at >= start, ParkingViolation.created_at < end)
                 .order_by(ParkingViolation.created_at.desc()).all())
        rows = []
        for v in found:
            fid = self.parking._flat_for_violation(v)
            if not self._in(scope, fid):
                continue
            self.parking._with_fine_status(v)
            status = getattr(v, "fine_status", None)
            rows.append({
                "date": to_local(v.created_at, tz).date().isoformat(), "vehicle_number": v.vehicle_number,
                "type": VIOLATION_WORDS.get(v.violation_type.value, v.violation_type.value),
                "flat": flat_text(fid), "slot": v.slot.slot_number if v.slot else "", "description": v.description or "",
                "fine": v.fine_amount or 0, "fine_status": FINE_WORDS.get(status, "") if v.fine_amount else "",
                "fine_status_key": status if v.fine_amount else None, "resolved": bool(v.is_resolved),
            })
        repeat = Counter(r["vehicle_number"] for r in rows)
        charged = sum(r["fine"] for r in rows if r["fine_status_key"] in ("active", "billed"))
        summary = {
            "total": len(rows), "open": sum(1 for r in rows if not r["resolved"]),
            "resolved": sum(1 for r in rows if r["resolved"]),
            "by_type": dict(Counter(r["type"] for r in rows).most_common()),
            "fines_charged": charged,
            "fines_on_bills": sum(r["fine"] for r in rows if r["fine_status_key"] == "billed"),
            "fines_taken_off": sum(r["fine"] for r in rows if r["fine_status_key"] == "cancelled"),
            "fines_not_charged": sum(r["fine"] for r in rows if r["fine"] and r["fine_status_key"] is None),
        }
        offenders = [{"vehicle_number": n, "count": c, "flat": next((r["flat"] for r in rows if r["vehicle_number"] == n), "")}
                     for n, c in repeat.most_common() if c >= 2]
        return {"summary": summary, "rows": _cap(rows, limit), "row_count": len(rows), "repeat_offenders": offenders}

    # ── Gate ──────────────────────────────────────────────────────────────────

    def _gate(self, society_id, scope, start, end, tz, flat_text, limit) -> dict:
        logs = (self.db.query(ParkingAccessLog)
                .filter(ParkingAccessLog.society_id == society_id, ParkingAccessLog.is_active == True,  # noqa: E712
                        ParkingAccessLog.access_time >= start, ParkingAccessLog.access_time < end)
                .order_by(ParkingAccessLog.access_time.desc()).all())
        rows = []
        for g in logs:
            who = "resident" if g.vehicle_id else ("visitor" if g.is_authorized else "unknown")
            fid = g.vehicle.flat_id if g.vehicle else None
            # A flat or wing narrows to its residents' vehicles: a visitor's or stranger's plate belongs to no flat.
            if scope["flat_ids"] is not None and not (who == "resident" and self._in(scope, fid)):
                continue
            rows.append({
                "time": iso_utc(g.access_time), "vehicle_number": g.vehicle_number,
                "direction": "Entry" if g.access_type == AccessType.ENTRY else "Exit", "who": who,
                "flat": flat_text(fid) if who == "resident" else "", "method": METHOD_WORDS.get(g.access_method.value, g.access_method.value),
                "allowed": bool(g.is_authorized), "notes": g.notes or "",
            })
        inside, month_visits = self._visitor_parking(society_id, scope, start, end, tz, flat_text)
        stays = [m["minutes"] for m in month_visits if m["minutes"] is not None]
        summary = {
            "total": len(rows), "entries": sum(1 for r in rows if r["direction"] == "Entry"),
            "exits": sum(1 for r in rows if r["direction"] == "Exit"),
            "residents": sum(1 for r in rows if r["who"] == "resident"), "visitors": sum(1 for r in rows if r["who"] == "visitor"),
            "unknown": sum(1 for r in rows if r["who"] == "unknown"), "not_allowed": sum(1 for r in rows if not r["allowed"]),
            "visitor_inside": len(inside), "visitor_visits": len(month_visits),
            "visitor_overstayed": sum(1 for m in month_visits if m["overstayed"]),
            "visitor_avg_stay_minutes": round(sum(stays) / len(stays)) if stays else None,
        }
        return {"summary": summary, "rows": _cap(rows, limit), "row_count": len(rows),
                "visitors_inside": _cap(inside, limit)}

    def _visitor_parking(self, society_id, scope, start, end, tz, flat_text):
        now = datetime.utcnow()
        q = self.db.query(VisitorParking).filter(VisitorParking.society_id == society_id, VisitorParking.is_active == True)  # noqa: E712
        inside, visits = [], []
        for vp in q.all():
            if not self._in(scope, vp.host_flat_id):
                continue
            expected = timedelta(hours=vp.expected_duration_hours or 0)
            if vp.status == VisitorParkingStatus.ACTIVE and vp.check_in_time:
                since = now - vp.check_in_time
                inside.append({
                    "vehicle_number": vp.vehicle_number, "host_flat": flat_text(vp.host_flat_id),
                    "since": iso_utc(vp.check_in_time), "expected_hours": vp.expected_duration_hours,
                    "overstayed": since > expected, "minutes": round(since.total_seconds() / 60),
                    "slot": vp.slot.slot_number if vp.slot else "",
                })
            if vp.check_in_time and start <= vp.check_in_time < end:
                stay = ((vp.check_out_time or now) - vp.check_in_time)
                visits.append({"minutes": round(stay.total_seconds() / 60) if vp.check_out_time else None,
                               "overstayed": stay > expected})
        inside.sort(key=lambda r: -r["minutes"])
        return inside, visits
