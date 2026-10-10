from datetime import date, datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import _user_has_permission
from app.core.tenant_scope import assert_society_access
from app.models.flat import Flat
from app.models.notification import NotificationType
from app.models.resident import Resident
from app.models.tenant import Tenant
from app.models.user import User
from app.models.wing import Wing
from app.modules.gate.models.gate import (
    HELP_KINDS, HELP_STATUSES, PARCEL_STATUSES, DomesticHelp, DomesticHelpEntry, DomesticHelpFlat, Parcel,
)
from app.services.notification_service import NotificationService

PASS_VALID_DAYS = 365


def _label(flat: Optional[Flat]) -> str:
    if flat is None:
        return "-"
    return f"{flat.wing.name} {flat.flat_number}" if flat.wing else flat.flat_number


class GateService:
    def __init__(self, db: Session):
        self.db = db

    # ── Who is who ───────────────────────────────────────────────────────────

    def is_gate(self, user: User) -> bool:
        return _user_has_permission(user, "security")

    def is_office(self, user: User) -> bool:
        return _user_has_permission(user, "admin_committee")

    def own_flat_ids(self, user: User) -> set:
        ids = {r.flat_id for r in self.db.query(Resident).filter(Resident.user_id == user.id,
                                                                Resident.is_active == True)}  # noqa: E712
        ids |= {t.flat_id for t in self.db.query(Tenant).filter(Tenant.user_id == user.id,
                                                               Tenant.is_active == True)}  # noqa: E712
        return ids

    def flat_user_ids(self, flat_id: UUID) -> List[UUID]:
        res = self.db.query(Resident.user_id).filter(Resident.flat_id == flat_id, Resident.is_active == True,  # noqa: E712
                                                     Resident.user_id != None)  # noqa: E711
        ten = self.db.query(Tenant.user_id).filter(Tenant.flat_id == flat_id, Tenant.is_active == True,  # noqa: E712
                                                   Tenant.user_id != None)  # noqa: E711
        return list({r[0] for r in (*res, *ten)})

    def _flat_in_society(self, flat_id: UUID, society_id: UUID) -> Flat:
        flat = (self.db.query(Flat).join(Wing, Flat.wing_id == Wing.id)
                .filter(Flat.id == flat_id, Wing.society_id == society_id).first())
        if flat is None:
            raise HTTPException(404, "Flat not found in this society")
        return flat

    def _tell_flat(self, flat_id: UUID, title: str, body: str, module: str, entity_id: str, route: str,
                   push: bool) -> None:
        for uid in self.flat_user_ids(flat_id):
            NotificationService.send(db=self.db, user_id=uid, title=title, body=body, type=NotificationType.INFO,
                                     module=module, entity_id=entity_id, action_url=route, push=push)

    # ══ Parcels ══════════════════════════════════════════════════════════════

    def log_parcel(self, society_id: UUID, data: dict, user: User) -> Parcel:
        assert_society_access(user, society_id)
        flat = self._flat_in_society(data["flat_id"], society_id)
        p = Parcel(society_id=society_id, flat_id=flat.id, courier=data.get("courier"),
                   description=data.get("description"), recipient_name=data.get("recipient_name"),
                   status="at_gate", received_at=datetime.utcnow(), logged_by=user.id)
        self.db.add(p)
        self.db.commit()
        what = (p.courier or "A parcel").strip()
        self._tell_flat(flat.id, "Parcel at the gate",
                        f"{what} left a parcel for {p.recipient_name or 'your flat'} at the gate. "
                        f"Please collect it from security.", "parcel", str(p.id), "/parcels", push=True)
        return p

    def list_parcels(self, society_id: UUID, user: User, status: Optional[str] = None) -> List[Parcel]:
        assert_society_access(user, society_id)
        q = self.db.query(Parcel).filter(Parcel.society_id == society_id)
        if status:
            if status not in PARCEL_STATUSES:
                raise HTTPException(422, "Unknown status")
            q = q.filter(Parcel.status == status)
        if not (self.is_gate(user) or self.is_office(user)):
            q = q.filter(Parcel.flat_id.in_(list(self.own_flat_ids(user)) or [None]))
        return q.order_by(Parcel.received_at.desc()).limit(300).all()

    def _parcel(self, parcel_id: UUID, user: User) -> Parcel:
        p = self.db.query(Parcel).filter(Parcel.id == parcel_id).first()
        if p is None:
            raise HTTPException(404, "Parcel not found")
        assert_society_access(user, p.society_id)
        if not (self.is_gate(user) or self.is_office(user)) and p.flat_id not in self.own_flat_ids(user):
            raise HTTPException(404, "Parcel not found")
        return p

    def hand_over(self, parcel_id: UUID, user: User, collected_by: Optional[str]) -> Parcel:
        p = self._parcel(parcel_id, user)
        if p.status != "at_gate":
            raise HTTPException(409, f"This parcel is already {p.status.replace('_', ' ')}")
        p.status, p.collected_at, p.closed_by = "collected", datetime.utcnow(), user.id
        p.collected_by_name = (collected_by or "").strip() or None
        self.db.commit()
        return p

    def return_parcel(self, parcel_id: UUID, user: User, note: Optional[str]) -> Parcel:
        p = self._parcel(parcel_id, user)
        if not (self.is_gate(user) or self.is_office(user)):
            raise HTTPException(403, "Only security or the office can return a parcel")
        if p.status != "at_gate":
            raise HTTPException(409, f"This parcel is already {p.status.replace('_', ' ')}")
        p.status, p.closed_by, p.note = "returned", user.id, (note or "").strip() or None
        self.db.commit()
        return p

    def parcel_out(self, p: Parcel) -> dict:
        return {
            "id": str(p.id), "flat_id": str(p.flat_id), "flat": _label(p.flat), "courier": p.courier,
            "description": p.description, "recipient_name": p.recipient_name, "status": p.status,
            "received_at": p.received_at, "collected_at": p.collected_at,
            "collected_by_name": p.collected_by_name, "note": p.note,
        }

    # ══ Domestic help ════════════════════════════════════════════════════════

    @staticmethod
    def _next_pass(db: Session, society_id: UUID) -> str:
        taken = db.query(DomesticHelp.pass_no).filter(DomesticHelp.society_id == society_id,
                                                      DomesticHelp.pass_no != None).all()  # noqa: E711
        top = max((int(n[0].split("-")[1]) for n in taken), default=0)
        return f"DH-{top + 1:04d}"

    def register_help(self, society_id: UUID, data: dict, user: User) -> DomesticHelp:
        assert_society_access(user, society_id)
        if data["kind"] not in HELP_KINDS:
            raise HTTPException(422, "Unknown kind of help")
        office = self.is_office(user)
        flat_ids = list(dict.fromkeys(data.get("flat_ids") or []))
        if not office:
            own = self.own_flat_ids(user)
            if not flat_ids:
                if len(own) != 1:
                    raise HTTPException(422, "Choose the flat the person will work in")
                flat_ids = list(own)
            if any(f not in own for f in flat_ids):
                raise HTTPException(403, "You can add help only to your own flat")
        if not flat_ids:
            raise HTTPException(422, "Choose at least one flat")
        for fid in flat_ids:
            self._flat_in_society(fid, society_id)

        mobile = data["mobile"].strip()
        existing = (self.db.query(DomesticHelp).filter(DomesticHelp.society_id == society_id,
                                                       DomesticHelp.mobile == mobile,
                                                       DomesticHelp.status != "ended").first())
        if existing is not None:
            for fid in flat_ids:
                if not any(l.flat_id == fid for l in existing.flats):
                    self.db.add(DomesticHelpFlat(help_id=existing.id, flat_id=fid))
            self.db.commit()
            self.db.refresh(existing)
            return existing

        h = DomesticHelp(society_id=society_id, name=data["name"].strip(), mobile=mobile, kind=data["kind"],
                         id_proof=data.get("id_proof"), registered_by=user.id, status="pending",
                         police_verified=bool(data.get("police_verified")) and office)
        self.db.add(h)
        self.db.flush()
        for fid in flat_ids:
            self.db.add(DomesticHelpFlat(help_id=h.id, flat_id=fid))
        self.db.commit()
        if office:
            return self.approve_help(h.id, user, data.get("valid_until"), h.police_verified)
        self._tell_office(h)
        return h

    def _tell_office(self, h: DomesticHelp) -> None:
        for u in self.db.query(User).filter(User.society_id == h.society_id, User.is_active == True).all():  # noqa: E712
            if self.is_office(u):
                NotificationService.send(db=self.db, user_id=u.id, title="Domestic help to verify",
                                         body=f"{h.name} ({h.kind}) has been registered and needs a pass.",
                                         type=NotificationType.APPROVAL, module="domestic_help",
                                         entity_id=str(h.id), action_url="/domestic-help", push=False)

    def _help(self, help_id: UUID, user: User) -> DomesticHelp:
        h = self.db.query(DomesticHelp).filter(DomesticHelp.id == help_id).first()
        if h is None:
            raise HTTPException(404, "Not found")
        assert_society_access(user, h.society_id)
        if not (self.is_gate(user) or self.is_office(user)):
            if not {l.flat_id for l in h.flats} & self.own_flat_ids(user):
                raise HTTPException(404, "Not found")
        return h

    def list_help(self, society_id: UUID, user: User, status: Optional[str] = None,
                  q: Optional[str] = None) -> List[DomesticHelp]:
        assert_society_access(user, society_id)
        query = self.db.query(DomesticHelp).filter(DomesticHelp.society_id == society_id)
        if status:
            if status not in HELP_STATUSES:
                raise HTTPException(422, "Unknown status")
            query = query.filter(DomesticHelp.status == status)
        if q:
            like = f"%{q.strip().lower()}%"
            query = query.filter(or_(func.lower(DomesticHelp.name).like(like), DomesticHelp.mobile.like(like),
                                     func.lower(func.coalesce(DomesticHelp.pass_no, "")).like(like)))
        if not (self.is_gate(user) or self.is_office(user)):
            query = (query.join(DomesticHelpFlat, DomesticHelpFlat.help_id == DomesticHelp.id)
                     .filter(DomesticHelpFlat.flat_id.in_(list(self.own_flat_ids(user)) or [None])).distinct())
        return query.order_by(DomesticHelp.name).all()

    def approve_help(self, help_id: UUID, user: User, valid_until: Optional[date] = None,
                     police_verified: Optional[bool] = None) -> DomesticHelp:
        h = self._help(help_id, user)
        if h.status not in ("pending", "suspended", "ended"):
            raise HTTPException(409, "This person already has a pass")
        if h.pass_no is None:
            h.pass_no = self._next_pass(self.db, h.society_id)
        h.status, h.approved_by = "active", user.id
        h.valid_until = valid_until or (date.today() + timedelta(days=PASS_VALID_DAYS))
        if police_verified is not None:
            h.police_verified = police_verified
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(409, "Another pass was issued at the same moment; please try again")
        for l in h.flats:
            self._tell_flat(l.flat_id, "Domestic help pass issued",
                            f"{h.name} ({h.kind}) now has pass {h.pass_no}, valid till {h.valid_until:%d %b %Y}.",
                            "domestic_help", str(h.id), "/domestic-help", push=False)
        return h

    def set_help_status(self, help_id: UUID, user: User, status: str, note: Optional[str]) -> DomesticHelp:
        h = self._help(help_id, user)
        if status not in ("suspended", "ended"):
            raise HTTPException(422, "Use approve to activate a pass")
        if h.status == status:
            return h
        h.status, h.note = status, (note or "").strip() or None
        self.db.commit()
        return h

    def renew_help(self, help_id: UUID, user: User, valid_until: Optional[date]) -> DomesticHelp:
        h = self._help(help_id, user)
        if h.status != "active":
            raise HTTPException(409, "Only an active pass can be renewed")
        h.valid_until = valid_until or (max(h.valid_until or date.today(), date.today())
                                        + timedelta(days=PASS_VALID_DAYS))
        self.db.commit()
        return h

    def remove_flat(self, help_id: UUID, flat_id: UUID, user: User) -> DomesticHelp:
        h = self._help(help_id, user)
        link = next((l for l in h.flats if l.flat_id == flat_id), None)
        if link is None:
            raise HTTPException(404, "That flat is not on this person's list")
        if not self.is_office(user) and flat_id not in self.own_flat_ids(user):
            raise HTTPException(403, "You can change only your own flat")
        self.db.delete(link)
        self.db.commit()
        self.db.refresh(h)
        return h

    # ── Gate entries ─────────────────────────────────────────────────────────

    def effective_status(self, h: DomesticHelp) -> str:
        if h.status == "active" and h.valid_until is not None and h.valid_until < date.today():
            return "expired"
        return h.status

    def _open_entry(self, help_id: UUID) -> Optional[DomesticHelpEntry]:
        return (self.db.query(DomesticHelpEntry).filter(DomesticHelpEntry.help_id == help_id,
                                                        DomesticHelpEntry.out_at == None)  # noqa: E711
                .order_by(DomesticHelpEntry.in_at.desc()).first())

    def gate_scan(self, help_id: UUID, user: User) -> dict:
        """Check the person in, or out if they are inside. Pass must be active, in date and for at least one flat."""
        h = self._help(help_id, user)
        if not (self.is_gate(user) or self.is_office(user)):
            raise HTTPException(403, "Only security can record entries")
        open_entry = self._open_entry(h.id)
        now = datetime.utcnow()
        if open_entry is not None:                 # leaving is always allowed, whatever the pass says
            open_entry.out_at = now
            direction = "out"
        else:
            state = self.effective_status(h)
            if state != "active":
                why = {"pending": "has no pass yet", "suspended": "pass is suspended", "ended": "pass has ended",
                       "expired": "pass has expired"}[state]
                raise HTTPException(409, f"{h.name}'s {why}" if state != "pending" else f"{h.name} {why}")
            if not h.flats:
                raise HTTPException(409, f"{h.name} is not linked to any flat")
            self.db.add(DomesticHelpEntry(help_id=h.id, society_id=h.society_id, in_at=now, logged_by=user.id))
            direction = "in"
        self.db.commit()
        verb = "has come in" if direction == "in" else "has left"
        for l in h.flats:
            self._tell_flat(l.flat_id, "Domestic help at the gate", f"{h.name} ({h.kind}) {verb}.",
                            "domestic_help", str(h.id), "/domestic-help", push=False)
        return {"direction": direction, "name": h.name, "kind": h.kind, "scanned_at": now,
                "flats": [_label(l.flat) for l in h.flats]}

    def inside(self, society_id: UUID, user: User) -> List[DomesticHelp]:
        assert_society_access(user, society_id)
        if not (self.is_gate(user) or self.is_office(user)):
            raise HTTPException(403, "Not allowed")
        ids = [e[0] for e in self.db.query(DomesticHelpEntry.help_id).filter(
            DomesticHelpEntry.society_id == society_id, DomesticHelpEntry.out_at == None).distinct()]  # noqa: E711
        return self.db.query(DomesticHelp).filter(DomesticHelp.id.in_(ids)).order_by(DomesticHelp.name).all() if ids else []

    def entries(self, help_id: UUID, user: User, days: int = 30) -> List[DomesticHelpEntry]:
        h = self._help(help_id, user)
        since = datetime.utcnow() - timedelta(days=days)
        return [e for e in h.entries if e.in_at >= since]

    def help_out(self, h: DomesticHelp) -> dict:
        open_entry = self._open_entry(h.id)
        return {
            "id": str(h.id), "name": h.name, "mobile": h.mobile, "kind": h.kind, "id_proof": h.id_proof,
            "police_verified": h.police_verified, "pass_no": h.pass_no, "status": h.status,
            "effective_status": self.effective_status(h),
            "valid_until": h.valid_until.isoformat() if h.valid_until else None,
            "flats": [{"flat_id": str(l.flat_id), "label": _label(l.flat)} for l in h.flats],
            "inside": open_entry is not None, "in_at": open_entry.in_at if open_entry else None, "note": h.note,
        }
