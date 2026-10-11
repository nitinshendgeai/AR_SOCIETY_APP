"""The manager's daily checklist.

What shows today is worked out from three things: the standing items (daily rounds, weekly and monthly tasks,
statutory dates) filtered to what the society actually has — its assets and its staff — what has already been ticked,
and live counts from the society's records (see live_items). Only ticks and the end-of-day sign-off are stored.
"""
import calendar
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.tenant_scope import assert_society_access
from app.models.society import Society
from app.models.user import User
from app.modules.checklist.models.checklist import (CATEGORIES, CATEGORY_LABELS, FREQUENCIES, ChecklistItem,
                                                    ChecklistLog, ChecklistSignoff)
from app.modules.checklist.services.live_items import ACTIVE_STAFF, LIVE_ASSET_STATUSES, LiveItems
from app.modules.checklist.services.standard_items import items_for, packs_for_state
from app.modules.governance.services.governance_service import is_office
from app.modules.inventory.models.inventory import Asset, AssetCategory
from app.modules.staff.models.staff import Staff, StaffDepartment
from app.utils.local_time import iso_utc, local_today, zone

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
PACK_LABELS = {"central": "All-India (central) rules", "maharashtra": "Maharashtra"}
ASSET_WORDS = {"lift": "lift", "cctv": "CCTV system", "pump": "pump", "generator": "generator",
               "biometric": "biometric device", "fire_safety": "fire-safety asset", "electrical": "electrical asset",
               "hvac": "HVAC unit", "vehicle": "vehicle", "air_conditioner": "air conditioner",
               "water_tank": "water tank", "water_treatment": "STP / water-treatment plant", "solar": "solar system",
               "gym_equipment": "gym equipment item", "intercom": "intercom", "garden_equipment": "garden equipment",
               "it_equipment": "IT equipment item", "furniture": "furniture item", "other": "other asset"}
OPEN_STATES = ("overdue", "due")


def _on(y: int, m: int, d: int) -> date:
    return date(y, m, min(d, calendar.monthrange(y, m)[1]))


def months_of(item: ChecklistItem) -> List[int]:
    return sorted({int(x) for x in (item.due_months or "").split(",") if x.strip().isdigit() and 1 <= int(x) <= 12})


def schedule_text(item: ChecklistItem) -> str:
    f = item.frequency
    ordinal = lambda n: "last day" if n >= 31 else f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"  # noqa: E731
    if f == "daily":
        return "Every day"
    if f == "weekly":
        return f"Every {WEEKDAYS[item.due_weekday or 0]}"
    if f == "monthly":
        return f"Every month, by the {ordinal(item.due_day or 1)}"
    if f == "on_dates":
        ms = ", ".join(MONTHS[m - 1] for m in months_of(item))
        return f"{ms}, by the {ordinal(item.due_day or 1)}"
    return "When the licence or certificate runs out"


def occurrences(item: ChecklistItem, today: date) -> List[date]:
    """The dates a monthly / on-dates item falls due, a year either side of today."""
    ms = months_of(item) if item.frequency == "on_dates" else list(range(1, 13))
    out = [_on(y, m, item.due_day or 1) for y in (today.year - 1, today.year, today.year + 1) for m in ms]
    return sorted(out)


class Occurrence:
    """Where one item stands: the date it falls due, what was logged for it, and its state."""
    __slots__ = ("due_on", "log", "state", "days")

    def __init__(self, due_on: Optional[date], log: Optional[ChecklistLog], state: str, days: Optional[int]):
        self.due_on, self.log, self.state, self.days = due_on, log, state, days


def locate(item: ChecklistItem, today: date, logs: List[ChecklistLog]) -> Occurrence:
    """The occurrence that matters now. `logs` are this item's logs, newest `for_date` first."""
    by_date = {l.for_date: l for l in logs}
    f = item.frequency

    def state_for(due: date) -> str:
        if due < today:
            return "overdue"
        if due == today:
            return "due"
        return "soon" if (due - today).days <= item.lead_days else "ok"

    def wrap(due: date, log: Optional[ChecklistLog]) -> Occurrence:
        if log is not None:
            return Occurrence(due, log, log.status, (due - today).days)
        return Occurrence(due, None, state_for(due), (due - today).days)

    if f == "daily":
        return wrap(today, by_date.get(today))
    if f == "weekly":
        due = today - timedelta(days=(today.weekday() - (item.due_weekday or 0)) % 7)
        created = item.created_at.date() if item.created_at else today
        if not logs and created > due:               # this week's day passed before the item was on the list
            due += timedelta(days=7)
        return wrap(due, by_date.get(due))
    if f == "licence":
        done = next((l for l in logs if l.status == "done" and l.valid_until), None)
        if not done:
            return Occurrence(None, None, "unrecorded", None)
        return Occurrence(done.valid_until, done, state_for(done.valid_until), (done.valid_until - today).days)
    occs = occurrences(item, today)
    prev = [o for o in occs if o <= today]
    nxt = [o for o in occs if o > today]
    gaps = [(b - a).days for a, b in zip(occs, occs[1:])]
    horizon = (min(gaps) if gaps else 365) + 10
    never = not logs
    created = item.created_at.date() if item.created_at else today
    for o in reversed(prev):                         # the latest occurrence not yet logged, within reach
        if (today - o).days > horizon:
            break
        if o in by_date:
            continue
        if never and created > o:                    # the date passed before this item was on the list
            if item.statutory and horizon >= 80:     # a yearly or quarterly date: ask once if it was met
                return Occurrence(o, None, "unconfirmed", (o - today).days)
            continue
        return wrap(o, None)
    if nxt:
        return wrap(nxt[0], by_date.get(nxt[0]))
    return Occurrence(None, None, "ok", None)


def _group(item: ChecklistItem) -> str:
    if item.statutory or item.category == "compliance" or item.frequency == "licence":
        return "compliance"
    return "daily" if item.frequency == "daily" else "periodic"


class ChecklistService:
    def __init__(self, db: Session):
        self.db = db

    # ── Setup ───────────────────────────────────────────────────────────────────────────────────────────────────
    def _society(self, society_id: UUID, user: User) -> Society:
        assert_society_access(user, society_id)
        society = self.db.query(Society).filter(Society.id == society_id).first()
        if not society:
            raise HTTPException(404, "Society not found")
        return society

    def ensure_standard(self, society: Society) -> None:
        """Add the built-in items this society does not have yet (its state decides which packs). Items the society
        deleted or switched off keep their row, so they are never added back."""
        have = {c for (c,) in self.db.query(ChecklistItem.code).filter(
            ChecklistItem.society_id == society.id, ChecklistItem.code != None)}  # noqa: E711
        added = False
        for spec in items_for(packs_for_state(society.state)):
            if spec["code"] in have:
                continue
            self.db.add(ChecklistItem(society_id=society.id, is_enabled=True, **spec))
            added = True
        if added:
            try:
                self.db.commit()
            except IntegrityError:           # another request opened the checklist first and added them
                self.db.rollback()

    def _counts(self, society_id: UUID) -> Tuple[Dict[str, int], Dict[str, int]]:
        assets = {}
        for cat, n in (self.db.query(Asset.asset_category, func.count(Asset.id))
                       .filter(Asset.society_id == society_id, Asset.is_active == True,  # noqa: E712
                               Asset.status.in_(LIVE_ASSET_STATUSES)).group_by(Asset.asset_category)):
            assets[cat.value if hasattr(cat, "value") else str(cat)] = int(n)
        staff = {}
        for dept, n in (self.db.query(Staff.department, func.count(Staff.id))
                        .filter(Staff.society_id == society_id, Staff.is_active == True,  # noqa: E712
                                Staff.status.in_(ACTIVE_STAFF)).group_by(Staff.department)):
            staff[dept.value if hasattr(dept, "value") else str(dept)] = int(n)
        return assets, staff

    @staticmethod
    def applies(item: ChecklistItem, assets: Dict[str, int], staff: Dict[str, int]) -> Tuple[bool, Optional[str]]:
        """Does this society have what the item is about? And, if so, the reason to show beside it."""
        reasons = []
        if item.asset_category:
            n = assets.get(item.asset_category, 0)
            if not n:
                return False, f"No {ASSET_WORDS.get(item.asset_category, item.asset_category)} in your assets"
            word = ASSET_WORDS.get(item.asset_category, item.asset_category)
            reasons.append(f"{n} {word}{'s' if n != 1 else ''} in your assets")
        if item.staff_department:
            if item.staff_department == "any":
                n = sum(staff.values())
                if not n:
                    return False, "No staff on record"
                reasons.append(f"{n} staff member{'s' if n != 1 else ''}")
            else:
                n = staff.get(item.staff_department, 0)
                if not n:
                    return False, f"No {item.staff_department} staff on record"
                reasons.append(f"{n} {item.staff_department} staff")
        return True, " · ".join(reasons) or None

    def _logs(self, society_id: UUID) -> Dict[UUID, List[ChecklistLog]]:
        rows = (self.db.query(ChecklistLog).filter(ChecklistLog.society_id == society_id,
                                                   ChecklistLog.is_active == True)  # noqa: E712
                .order_by(ChecklistLog.for_date.desc()).all())
        out: Dict[UUID, List[ChecklistLog]] = {}
        for l in rows:
            out.setdefault(l.item_id, []).append(l)
        return out

    def _names(self, ids) -> Dict[UUID, str]:
        ids = {i for i in ids if i}
        if not ids:
            return {}
        return {u.id: u.full_name for u in self.db.query(User).filter(User.id.in_(ids)).all()}

    # ── Output ──────────────────────────────────────────────────────────────────────────────────────────────────
    def _log_out(self, log: Optional[ChecklistLog], names: Dict[UUID, str]) -> Optional[dict]:
        if log is None:
            return None
        return {"id": str(log.id), "for_date": log.for_date.isoformat(), "status": log.status,
                "done_on": log.done_on.isoformat(), "note": log.note, "reference": log.reference,
                "valid_until": log.valid_until.isoformat() if log.valid_until else None,
                "done_by": names.get(log.done_by), "recorded_at": iso_utc(log.updated_at)}

    def _item_out(self, item: ChecklistItem, occ: Optional[Occurrence], reason: Optional[str], names, logs) -> dict:
        last_done = next((l for l in logs if l.status == "done"), None)
        return {
            "id": str(item.id), "code": item.code, "title": item.title, "detail": item.detail,
            "category": item.category, "category_label": CATEGORY_LABELS.get(item.category, item.category),
            "frequency": item.frequency, "schedule": schedule_text(item), "group": _group(item),
            "due_weekday": item.due_weekday, "due_day": item.due_day, "due_months": months_of(item),
            "lead_days": item.lead_days, "asset_category": item.asset_category,
            "staff_department": item.staff_department, "statutory": item.statutory,
            "legal_basis": item.legal_basis, "jurisdiction": item.jurisdiction,
            "jurisdiction_label": PACK_LABELS.get(item.jurisdiction or ""), "link_key": item.link_key,
            "is_enabled": item.is_enabled, "is_standard": item.code is not None, "applies_because": reason,
            "due_on": occ.due_on.isoformat() if occ and occ.due_on else None,
            "days_left": occ.days if occ else None, "state": occ.state if occ else None,
            "log": self._log_out(occ.log if occ else None, names),
            "last_done_on": last_done.done_on.isoformat() if last_done else None,
            "last_reference": last_done.reference if last_done else None,
            "valid_until": last_done.valid_until.isoformat() if last_done and last_done.valid_until else None,
        }

    # ── Today ───────────────────────────────────────────────────────────────────────────────────────────────────
    def today(self, society_id: UUID, user: User) -> dict:
        society = self._society(society_id, user)
        self.ensure_standard(society)
        tz = zone(society.timezone)
        today = local_today(tz)
        assets, staff = self._counts(society_id)
        logs = self._logs(society_id)
        items = (self.db.query(ChecklistItem).filter(ChecklistItem.society_id == society_id,
                                                     ChecklistItem.is_active == True,  # noqa: E712
                                                     ChecklistItem.is_enabled == True)  # noqa: E712
                 .order_by(ChecklistItem.sort_order, ChecklistItem.title).all())
        names = self._names({l.done_by for ls in logs.values() for l in ls})
        out, hidden_unrecorded, to_confirm = [], 0, 0
        for it in items:
            ok, reason = self.applies(it, assets, staff)
            if not ok:
                continue
            ls = logs.get(it.id, [])
            done_today = next((l for l in ls if l.done_on == today), None)
            occ = Occurrence(done_today.for_date, done_today, done_today.status, 0) if done_today \
                else locate(it, today, ls)
            if occ.state == "unrecorded":
                hidden_unrecorded += 1
                continue
            if occ.state == "unconfirmed":      # asked once, in the Compliance tab — not part of the day's work
                to_confirm += 1
                continue
            if occ.state in ("ok", "done", "skipped") and not done_today:
                continue                      # nothing to do with it today
            if occ.state == "soon" and it.frequency in ("daily", "weekly"):
                continue
            out.append(self._item_out(it, occ, reason, names, ls))
        counted = [i for i in out if i["state"] in OPEN_STATES + ("done", "skipped")]
        done = [i for i in counted if i["state"] in ("done", "skipped")]
        live = LiveItems(self.db).all(society_id, today, tz)
        signoff = (self.db.query(ChecklistSignoff).filter(ChecklistSignoff.society_id == society_id,
                                                          ChecklistSignoff.for_date == today).first())
        sn_names = self._names({signoff.signed_by}) if signoff else {}
        return {
            "as_of": today.isoformat(), "society": society.name, "state": society.state,
            "items": out, "live": live,
            "summary": {"total": len(counted), "done": len(done),
                        "overdue": sum(1 for i in counted if i["state"] == "overdue"),
                        "live_open": len(live), "live_high": sum(1 for l in live if l["severity"] == "high"),
                        "compliance_unrecorded": hidden_unrecorded, "compliance_unconfirmed": to_confirm},
            "signoff": self._signoff_out(signoff, sn_names) if signoff else None,
            "jurisdiction": self.jurisdiction(society),
            "categories": [{"key": c, "label": CATEGORY_LABELS[c]} for c in CATEGORIES],
        }

    def jurisdiction(self, society: Society) -> dict:
        packs = packs_for_state(society.state)
        state = (society.state or "").strip()
        return {"state": state or None, "packs": [{"key": p, "label": PACK_LABELS[p]} for p in packs],
                "state_pack_loaded": len(packs) > 1,
                "note": ("Built-in legal items are a starting list, not legal advice: check each against your "
                         "bye-laws and the current rules with your auditor or legal advisor, and switch off or "
                         "reword what does not apply."
                         + ("" if len(packs) > 1 else
                            (f" Rules specific to {state} are not built in — add them as your own items."
                             if state else " Set the society's state in Society Settings to load its rules.")))}

    # ── Ticking ─────────────────────────────────────────────────────────────────────────────────────────────────
    def _item(self, item_id: UUID, user: User) -> ChecklistItem:
        item = self.db.query(ChecklistItem).filter(ChecklistItem.id == item_id,
                                                   ChecklistItem.is_active == True).first()  # noqa: E712
        if not item:
            raise HTTPException(404, "Item not found")
        assert_society_access(user, item.society_id)
        return item

    def complete(self, item_id: UUID, user: User, status: str = "done", done_on: Optional[date] = None,
                 note: Optional[str] = None, reference: Optional[str] = None,
                 valid_until: Optional[date] = None) -> dict:
        item = self._item(item_id, user)
        society = self.db.query(Society).filter(Society.id == item.society_id).first()
        today = local_today(zone(society.timezone if society else None))
        if status not in ("done", "skipped"):
            raise HTTPException(400, "Status must be done or skipped")
        if done_on and done_on > today:
            raise HTTPException(400, "The date done cannot be in the future")
        if valid_until and valid_until < (done_on or today) and item.frequency == "licence" and status == "done":
            raise HTTPException(400, "The licence cannot run out before the day it was renewed")
        if status == "skipped" and not (note or "").strip():
            raise HTTPException(400, "Say why this is skipped")
        logs = self._logs(item.society_id).get(item.id, [])
        if item.frequency == "licence":
            for_date = today
            if status == "done" and not valid_until:
                raise HTTPException(400, "Enter the date the licence or certificate runs to")
        else:
            occ = locate(item, today, logs)
            for_date = occ.due_on or today
        log = next((l for l in logs if l.for_date == for_date), None)
        if log is None:
            log = ChecklistLog(society_id=item.society_id, item_id=item.id, for_date=for_date)
            self.db.add(log)
        log.status, log.done_on = status, done_on or today
        log.note = (note or "").strip() or None
        log.reference = (reference or "").strip() or None
        log.valid_until = valid_until
        log.done_by = user.id
        log.is_active = True
        self.db.commit()
        return {"ok": True, "for_date": for_date.isoformat()}

    def undo(self, item_id: UUID, user: User, for_date: date) -> None:
        item = self._item(item_id, user)
        log = (self.db.query(ChecklistLog).filter(ChecklistLog.item_id == item.id, ChecklistLog.for_date == for_date,
                                                  ChecklistLog.is_active == True).first())  # noqa: E712
        if not log:
            raise HTTPException(404, "Nothing recorded for that date")
        self.db.delete(log)
        self.db.commit()

    # ── Compliance calendar ─────────────────────────────────────────────────────────────────────────────────────
    def compliance(self, society_id: UUID, user: User) -> dict:
        society = self._society(society_id, user)
        self.ensure_standard(society)
        today = local_today(zone(society.timezone))
        assets, staff = self._counts(society_id)
        logs = self._logs(society_id)
        names = self._names({l.done_by for ls in logs.values() for l in ls})
        items = (self.db.query(ChecklistItem).filter(ChecklistItem.society_id == society_id,
                                                     ChecklistItem.is_active == True,  # noqa: E712
                                                     ChecklistItem.is_enabled == True)  # noqa: E712
                 .order_by(ChecklistItem.sort_order).all())
        rows = []
        for it in items:
            if _group(it) != "compliance":
                continue
            ok, reason = self.applies(it, assets, staff)
            if not ok:
                continue
            ls = logs.get(it.id, [])
            rows.append(self._item_out(it, locate(it, today, ls), reason, names, ls))
        rank = {"overdue": 0, "unconfirmed": 1, "due": 2, "soon": 3, "unrecorded": 4, "ok": 5, "done": 6, "skipped": 7}
        rows.sort(key=lambda r: (rank.get(r["state"], 9), r["due_on"] or "9999", r["title"]))
        return {"as_of": today.isoformat(), "items": rows, "jurisdiction": self.jurisdiction(society),
                "summary": {"overdue": sum(1 for r in rows if r["state"] == "overdue"),
                            "unconfirmed": sum(1 for r in rows if r["state"] == "unconfirmed"),
                            "soon": sum(1 for r in rows if r["state"] in ("due", "soon")),
                            "unrecorded": sum(1 for r in rows if r["state"] == "unrecorded"),
                            "total": len(rows)}}

    # ── Managing the list ───────────────────────────────────────────────────────────────────────────────────────
    def list_items(self, society_id: UUID, user: User) -> dict:
        society = self._society(society_id, user)
        self.ensure_standard(society)
        today = local_today(zone(society.timezone))
        assets, staff = self._counts(society_id)
        logs = self._logs(society_id)
        items = (self.db.query(ChecklistItem).filter(ChecklistItem.society_id == society_id,
                                                     ChecklistItem.is_active == True)  # noqa: E712
                 .order_by(ChecklistItem.sort_order, ChecklistItem.title).all())
        names = self._names({l.done_by for ls in logs.values() for l in ls})
        rows = []
        for it in items:
            ok, reason = self.applies(it, assets, staff)
            ls = logs.get(it.id, [])
            row = self._item_out(it, locate(it, today, ls) if ok else None, reason, names, ls)
            row["applicable"] = ok
            rows.append(row)
        return {"items": rows, "jurisdiction": self.jurisdiction(society),
                "categories": [{"key": c, "label": CATEGORY_LABELS[c]} for c in CATEGORIES],
                "asset_categories": [{"key": c.value, "label": ASSET_WORDS.get(c.value, c.value).capitalize()}
                                     for c in AssetCategory],
                "departments": [{"key": "any", "label": "Any staff"}]
                + [{"key": d.value, "label": d.value.capitalize()} for d in StaffDepartment]}

    def _check(self, data: dict) -> dict:
        """Validate the fields an item is made or changed with; return the cleaned ones."""
        out = dict(data)
        if "title" in out:
            out["title"] = " ".join((out["title"] or "").split())
            if len(out["title"]) < 3:
                raise HTTPException(400, "Give the item a title")
        if out.get("category") is not None and out["category"] not in CATEGORIES:
            raise HTTPException(400, "Unknown category")
        if out.get("frequency") is not None and out["frequency"] not in FREQUENCIES:
            raise HTTPException(400, "Unknown frequency")
        if out.get("asset_category") and out["asset_category"] not in {c.value for c in AssetCategory}:
            raise HTTPException(400, "Unknown asset kind")
        if out.get("staff_department") and out["staff_department"] != "any" \
                and out["staff_department"] not in {d.value for d in StaffDepartment}:
            raise HTTPException(400, "Unknown staff department")
        if out.get("due_months") is not None:
            if isinstance(out["due_months"], (list, tuple)):
                out["due_months"] = ",".join(str(int(m)) for m in sorted(set(out["due_months"])))
            out["due_months"] = out["due_months"] or None
        return out

    def _check_schedule(self, item: ChecklistItem) -> None:
        f = item.frequency
        if f == "weekly" and (item.due_weekday is None or not 0 <= item.due_weekday <= 6):
            raise HTTPException(400, "Choose the day of the week")
        if f in ("monthly", "on_dates") and (item.due_day is None or not 1 <= item.due_day <= 31):
            raise HTTPException(400, "Choose the day of the month (1–31)")
        if f == "on_dates" and not months_of(item):
            raise HTTPException(400, "Choose the months")
        if f in ("daily", "licence"):
            item.due_weekday = item.due_day = None
        if f != "on_dates":
            item.due_months = None
        if f != "weekly":
            item.due_weekday = None
        if f in ("daily", "weekly"):
            item.lead_days = 0

    def create_item(self, society_id: UUID, user: User, data: dict) -> dict:
        society = self._society(society_id, user)
        clean = self._check(data)
        for key in ("title", "frequency"):
            if not clean.get(key):
                raise HTTPException(400, f"{key.capitalize()} is required")
        item = ChecklistItem(society_id=society.id, created_by=user.id, sort_order=900, is_enabled=True,
                             category=clean.get("category") or "housekeeping", code=None, jurisdiction=None,
                             **{k: v for k, v in clean.items() if k in (
                                 "title", "detail", "frequency", "due_weekday", "due_day", "due_months", "lead_days",
                                 "asset_category", "staff_department", "statutory", "legal_basis", "link_key")})
        item.lead_days = item.lead_days or 0
        self._check_schedule(item)
        self.db.add(item)
        self.db.commit()
        return {"id": str(item.id)}

    def update_item(self, item_id: UUID, user: User, data: dict) -> dict:
        item = self._item(item_id, user)
        clean = self._check(data)
        if item.code and item.statutory and not is_office(user):
            raise HTTPException(403, "Only the admin or a committee member can change a statutory item")
        for k in ("title", "detail", "category", "frequency", "due_weekday", "due_day", "due_months", "lead_days",
                  "asset_category", "staff_department", "legal_basis", "link_key", "is_enabled", "statutory"):
            if k in clean:
                setattr(item, k, clean[k])
        self._check_schedule(item)
        self.db.commit()
        return {"id": str(item.id)}

    def delete_item(self, item_id: UUID, user: User) -> None:
        item = self._item(item_id, user)
        if item.code:
            raise HTTPException(400, "A built-in item cannot be deleted — switch it off instead")
        item.is_active = False
        self.db.commit()

    # ── End of day ──────────────────────────────────────────────────────────────────────────────────────────────
    def _signoff_out(self, s: ChecklistSignoff, names: Dict[UUID, str]) -> dict:
        return {"for_date": s.for_date.isoformat(), "signed_by": names.get(s.signed_by), "remarks": s.remarks,
                "routine_total": s.routine_total, "routine_done": s.routine_done, "live_open": s.live_open,
                "signed_at": iso_utc(s.updated_at)}

    def sign_off(self, society_id: UUID, user: User, remarks: Optional[str]) -> dict:
        data = self.today(society_id, user)
        today = date.fromisoformat(data["as_of"])
        s = (self.db.query(ChecklistSignoff).filter(ChecklistSignoff.society_id == society_id,
                                                    ChecklistSignoff.for_date == today).first())
        if not s:
            s = ChecklistSignoff(society_id=society_id, for_date=today)
            self.db.add(s)
        s.signed_by = user.id
        s.remarks = (remarks or "").strip() or None
        s.routine_total, s.routine_done = data["summary"]["total"], data["summary"]["done"]
        s.live_open = data["summary"]["live_open"]
        s.is_active = True
        self.db.commit()
        return self._signoff_out(s, {user.id: user.full_name})

    def history(self, society_id: UUID, user: User, days: int = 30) -> List[dict]:
        society = self._society(society_id, user)
        today = local_today(zone(society.timezone))
        since = today - timedelta(days=max(1, min(days, 366)))
        signs = {s.for_date: s for s in self.db.query(ChecklistSignoff).filter(
            ChecklistSignoff.society_id == society_id, ChecklistSignoff.for_date >= since)}
        counts = {d: int(n) for d, n in self.db.query(ChecklistLog.done_on, func.count(ChecklistLog.id)).filter(
            ChecklistLog.society_id == society_id, ChecklistLog.done_on >= since, ChecklistLog.status == "done",
            ChecklistLog.is_active == True).group_by(ChecklistLog.done_on)}  # noqa: E712
        names = self._names({s.signed_by for s in signs.values()})
        out = []
        for d in sorted(set(signs) | set(counts), reverse=True):
            s = signs.get(d)
            out.append({"date": d.isoformat(), "ticked": counts.get(d, 0),
                        "signoff": self._signoff_out(s, names) if s else None})
        return out
