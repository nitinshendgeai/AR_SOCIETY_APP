"""The gym attendance book: members arriving and leaving, who is inside now, and the weekly and monthly reports.

Read this before changing it: the gym is for the owners' side of the society only. A flat's members are the active
people on the Residents list (owner, co-owner, family, dependent); tenants are a separate list and are never offered."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.flat import Flat
from app.models.resident import Resident
from app.models.society import Society
from app.models.tenant import Tenant
from app.models.user import User
from app.models.wing import Wing
from app.services.resident_family_request_service import FamilyRequestService
from app.modules.gym.models.gym import GymVisit
from app.utils.local_time import iso_utc, local_to_utc_naive, local_today, to_local, zone

MEMBER_TYPE_WORDS = {"owner": "Owner", "co_owner": "Co-owner", "family": "Family", "dependent": "Dependent"}


def flat_label(flat: Flat) -> str:
    wing = flat.wing.name if flat.wing else None
    return f"{wing}-{flat.flat_number}" if wing else str(flat.flat_number)


class GymService:
    def __init__(self, db: Session, user: User):
        if user.society_id is None:
            raise HTTPException(400, "Choose a society first")
        self.db = db
        self.user = user
        self.society_id = user.society_id
        society = db.query(Society).filter(Society.id == self.society_id).first()
        self.tz = zone(getattr(society, "timezone", None))

    # ── the society's clock ────────────────────────────────────────────────────────────────────────────────────────

    def today(self) -> date:
        return local_today(self.tz)

    def _bounds(self, first: date, last: date):
        """[start, end) in naive UTC for the society's days first..last inclusive."""
        return (local_to_utc_naive(first, time(0, 0), self.tz),
                local_to_utc_naive(last + timedelta(days=1), time(0, 0), self.tz))

    def _local_day(self, dt: datetime) -> date:
        return to_local(dt, self.tz).date()

    # ── a flat's members ───────────────────────────────────────────────────────────────────────────────────────────

    def _flat(self, flat_id: UUID) -> Flat:
        flat = (self.db.query(Flat).join(Wing, Wing.id == Flat.wing_id)
                .filter(Flat.id == flat_id, Wing.society_id == self.society_id).first())
        if flat is None:
            raise HTTPException(404, "Flat not found")
        return flat

    def _eligible(self, flat_id: UUID) -> List[Resident]:
        today = self.today()
        rows = self.db.query(Resident).filter(
            Resident.flat_id == flat_id, Resident.is_active == True,                      # noqa: E712
            or_(Resident.move_out_date.is_(None), Resident.move_out_date > today),
        ).all()
        rows.sort(key=lambda r: (not r.is_primary, (r.full_name or "").lower()))
        return rows

    def _open_today(self) -> List[GymVisit]:
        start, _ = self._bounds(self.today(), self.today())
        return (self.db.query(GymVisit).filter(
            GymVisit.society_id == self.society_id, GymVisit.checked_out_at.is_(None), GymVisit.checked_in_at >= start)
            .order_by(GymVisit.checked_in_at).all())

    def members(self, flat_id: UUID) -> dict:
        flat = self._flat(flat_id)
        inside = {v.resident_id: v for v in self._open_today() if v.resident_id}
        people = self._eligible(flat.id)
        let_to_tenants = bool(self.db.query(Tenant.id).filter(Tenant.flat_id == flat.id, Tenant.is_active == True).first())  # noqa: E712
        return {
            "flat_id": str(flat.id), "flat_label": flat_label(flat), "let_to_tenants": let_to_tenants,
            # Family asked for by the resident and not yet approved by the office: not on the list, so not offered.
            "waiting_for_approval": FamilyRequestService.waiting_names(self.db, self.society_id, flat.id),
            "members": [{
                "resident_id": str(r.id), "name": r.full_name,
                "member_type": r.resident_type.value if hasattr(r.resident_type, "value") else str(r.resident_type),
                "inside": r.id in inside,
                "visit_id": str(inside[r.id].id) if r.id in inside else None,
            } for r in people],
        }

    # ── arriving and leaving ───────────────────────────────────────────────────────────────────────────────────────

    def check_in(self, flat_id: UUID, resident_ids: List[UUID]) -> dict:
        flat = self._flat(flat_id)
        wanted = list(dict.fromkeys(resident_ids))
        if not wanted:
            raise HTTPException(422, "Tick at least one member")
        eligible = {r.id: r for r in self._eligible(flat.id)}
        outsiders = [rid for rid in wanted if rid not in eligible]
        if outsiders:
            raise HTTPException(422, "Only the owners' side of a flat can use the gym: that person is not a member of this flat")
        inside = {v.resident_id for v in self._open_today() if v.resident_id}
        now, label = datetime.utcnow(), flat_label(flat)
        made, already = [], []
        for rid in wanted:
            r = eligible[rid]
            if rid in inside:
                already.append(r.full_name)
                continue
            visit = GymVisit(
                society_id=self.society_id, flat_id=flat.id, resident_id=rid, member_name=r.full_name, flat_label=label,
                member_type=r.resident_type.value if hasattr(r.resident_type, "value") else str(r.resident_type),
                checked_in_at=now, checked_in_by=self.user.id)
            self.db.add(visit)
            made.append(visit)
        self.db.commit()
        for v in made:
            self.db.refresh(v)
        return {"checked_in": [self._row(v) for v in made], "already_inside": already}

    def _close(self, visits: List[GymVisit]) -> List[GymVisit]:
        now = datetime.utcnow()
        start, _ = self._bounds(self.today(), self.today())
        closed = []
        for v in visits:
            if v.checked_out_at is not None:
                continue
            v.checked_out_at, v.checked_out_by = now, self.user.id
            v.closed_late = v.checked_in_at < start           # from an earlier day: the time is when it was closed
            closed.append(v)
        self.db.commit()
        return closed

    def check_out(self, visit_ids: List[UUID]) -> dict:
        ids = list(dict.fromkeys(visit_ids))
        if not ids:
            raise HTTPException(422, "Choose who is leaving")
        rows = self.db.query(GymVisit).filter(GymVisit.society_id == self.society_id, GymVisit.id.in_(ids)).all()
        if len(rows) != len(ids):
            raise HTTPException(404, "Visit not found")
        closed = self._close(rows)
        return {"checked_out": len(closed)}

    def check_out_all(self) -> dict:
        rows = self.db.query(GymVisit).filter(
            GymVisit.society_id == self.society_id, GymVisit.checked_out_at.is_(None)).all()
        return {"checked_out": len(self._close(rows))}

    # ── now ────────────────────────────────────────────────────────────────────────────────────────────────────────

    def _row(self, v: GymVisit, now: Optional[datetime] = None) -> dict:
        out = {
            "visit_id": str(v.id), "name": v.member_name, "flat_label": v.flat_label, "member_type": v.member_type,
            "checked_in_at": iso_utc(v.checked_in_at), "checked_out_at": iso_utc(v.checked_out_at),
        }
        if now is not None and v.checked_out_at is None:
            out["minutes_inside"] = max(0, int((now - v.checked_in_at).total_seconds() // 60))
        return out

    def live(self) -> dict:
        now, today = datetime.utcnow(), self.today()
        start, end = self._bounds(today, today)
        inside = self._open_today()
        earlier = (self.db.query(GymVisit).filter(
            GymVisit.society_id == self.society_id, GymVisit.checked_out_at.is_(None), GymVisit.checked_in_at < start)
            .order_by(GymVisit.checked_in_at).all())
        came = self.db.query(GymVisit.id).filter(
            GymVisit.society_id == self.society_id, GymVisit.checked_in_at >= start, GymVisit.checked_in_at < end).count()
        left = self.db.query(GymVisit.id).filter(
            GymVisit.society_id == self.society_id, GymVisit.checked_out_at >= start, GymVisit.checked_out_at < end).count()
        return {
            "as_of": iso_utc(now), "date": today.isoformat(),
            "inside_now": len(inside), "checked_in_today": came, "checked_out_today": left,
            "inside": [self._row(v, now) for v in inside],
            "earlier_open": [self._row(v, now) for v in earlier],
        }

    # ── reports ────────────────────────────────────────────────────────────────────────────────────────────────────

    def period(self, kind: str, on: Optional[date]) -> tuple:
        on = on or self.today()
        if kind == "week":                                         # Monday to Sunday
            first = on - timedelta(days=on.weekday())
            last = first + timedelta(days=6)
            label = f"Week of {first:%d %b %Y} to {last:%d %b %Y}"
        else:
            first = on.replace(day=1)
            nxt = (first + timedelta(days=32)).replace(day=1)
            last = nxt - timedelta(days=1)
            label = f"{first:%B %Y}"
        return first, last, label

    def report(self, kind: str, on: Optional[date] = None) -> dict:
        first, last, label = self.period(kind, on)
        start, end = self._bounds(first, last)
        visits = (self.db.query(GymVisit).filter(
            GymVisit.society_id == self.society_id, GymVisit.checked_in_at >= start, GymVisit.checked_in_at < end)
            .order_by(GymVisit.checked_in_at).all())

        per_day: Dict[date, list] = defaultdict(list)
        per_member: Dict[tuple, dict] = {}
        minutes, measured = 0, 0
        for v in visits:
            day = self._local_day(v.checked_in_at)
            per_day[day].append(v)
            key = (v.resident_id or v.member_name.lower(), v.flat_label)
            m = per_member.setdefault(key, {"name": v.member_name, "flat_label": v.flat_label, "visits": 0, "minutes": 0})
            m["visits"] += 1
            if v.checked_out_at is not None and not v.closed_late:
                length = max(0, int((v.checked_out_at - v.checked_in_at).total_seconds() // 60))
                m["minutes"] += length
                minutes += length
                measured += 1
        days, d = [], first
        while d <= last:
            rows = per_day.get(d, [])
            days.append({"date": d.isoformat(), "visits": len(rows),
                         "unique_members": len({(v.resident_id or v.member_name.lower()) for v in rows})})
            d += timedelta(days=1)
        members = sorted(per_member.values(), key=lambda m: (-m["visits"], m["name"].lower()))
        return {
            "period": kind, "from": first.isoformat(), "to": last.isoformat(), "label": label,
            "totals": {
                "visits": len(visits), "unique_members": len(per_member),
                "unique_flats": len({v.flat_label for v in visits}),
                "average_minutes": round(minutes / measured) if measured else None,
                "busiest_day": max(days, key=lambda x: x["visits"])["date"] if visits else None,
                "not_checked_out": sum(1 for v in visits if v.checked_out_at is None or v.closed_late),
            },
            "days": days,
            "members": [{"name": m["name"], "flat_label": m["flat_label"], "visits": m["visits"],
                         "total_minutes": m["minutes"]} for m in members],
        }
