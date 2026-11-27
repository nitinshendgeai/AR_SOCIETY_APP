"""The managing committee register: the committee's term, its office-bearers, their powers and how to reach them.

Every member of the society may see it (the committee's names and contacts are on every society's notice board);
admins and committee members keep it up to date. A member who leaves an office keeps the record with the date they left,
so the register shows who held which office when.
"""
from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.tenant_scope import assert_society_access
from app.models.flat import Flat
from app.models.resident import Resident
from app.models.user import User
from app.models.wing import Wing
from app.modules.governance.models.governance import (
    COMMITTEE_POSITIONS, SINGLE_OFFICE, CommitteeMember, ManagingCommittee,
)
from app.utils.local_time import society_today

POSITION_LABELS = {"chairman": "Chairman", "vice_chairman": "Vice-Chairman", "secretary": "Secretary",
                   "joint_secretary": "Joint Secretary", "treasurer": "Treasurer", "member": "Committee Member",
                   "co_opted": "Co-opted Member", "invitee": "Special Invitee"}
TERM_YEARS = 5          # MCS Act s.73CB(6) / model bye-law 117: the committee's term is five years
ELECTION_NOTICE_DAYS = 120


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:                       # 29 February
        return d.replace(year=d.year + years, day=28)


class CommitteeService:
    def __init__(self, db: Session):
        self.db = db

    # ── Reading ─────────────────────────────────────────────────────────────────────────────────────────────────

    def register(self, society_id: UUID, user: User) -> dict:
        """The committee in office (the latest one formed) and the earlier ones, newest first."""
        assert_society_access(user, society_id)
        today = society_today(self.db, society_id)
        rows = (self.db.query(ManagingCommittee)
                .filter(ManagingCommittee.society_id == society_id, ManagingCommittee.is_active == True)  # noqa: E712
                .order_by(ManagingCommittee.formed_on.desc()).all())
        current = rows[0] if rows else None
        return {"today": today.isoformat(), "positions": [{"key": k, "label": POSITION_LABELS[k]} for k in COMMITTEE_POSITIONS],
                "current": self.committee_out(current, today) if current else None,
                "past": [self.committee_out(c, today, brief=True) for c in rows[1:]]}

    def committee_out(self, c: ManagingCommittee, today: date, brief: bool = False) -> dict:
        members = [m for m in c.members if m.is_active]
        serving = [m for m in members if m.to_date is None or m.to_date >= today]
        former = [m for m in members if m.to_date is not None and m.to_date < today]
        order = {k: i for i, k in enumerate(COMMITTEE_POSITIONS)}
        serving.sort(key=lambda m: (order.get(m.position, 99), m.sort_order, m.full_name))
        days_left = (c.term_ends_on - today).days if c.term_ends_on else None
        out = {"id": str(c.id), "name": c.name, "formed_on": c.formed_on.isoformat(),
               "term_ends_on": c.term_ends_on.isoformat() if c.term_ends_on else None, "days_left": days_left,
               "term_over": days_left is not None and days_left < 0, "election_note": c.election_note,
               "members": [self.member_out(m) for m in serving]}
        if brief:
            return {**out, "members": [self.member_out(m) for m in sorted(members, key=lambda m: order.get(m.position, 99))]}
        out["former_members"] = [self.member_out(m) for m in sorted(former, key=lambda m: m.to_date, reverse=True)]
        out["warnings"] = self._warnings(c, serving, days_left)
        return out

    @staticmethod
    def member_out(m: CommitteeMember) -> dict:
        powers = [p for p, on in (("Cheque signatory", m.cheque_signatory), ("Approves payments", m.approves_payments),
                                  ("Signs documents", m.signs_documents)) if on]
        return {"id": str(m.id), "resident_id": str(m.resident_id) if m.resident_id else None, "full_name": m.full_name,
                "flat": m.flat_label, "position": m.position, "position_label": POSITION_LABELS.get(m.position, m.position),
                "phone": m.phone, "email": m.email, "from_date": m.from_date.isoformat(),
                "to_date": m.to_date.isoformat() if m.to_date else None,
                "cheque_signatory": m.cheque_signatory, "approves_payments": m.approves_payments,
                "signs_documents": m.signs_documents, "spending_limit": m.spending_limit, "authorities": powers,
                "responsibilities": m.responsibilities}

    @staticmethod
    def _warnings(c: ManagingCommittee, serving: List[CommitteeMember], days_left: Optional[int]) -> List[str]:
        held = {m.position for m in serving}
        out = [f"No {POSITION_LABELS[p]} in office." for p in ("chairman", "secretary", "treasurer") if p not in held]
        signatories = sum(1 for m in serving if m.cheque_signatory)
        if signatories < 2:
            out.append("Fewer than two cheque signatories: the society's bank account usually needs two of them "
                       "(Chairman / Secretary / Treasurer).")
        if days_left is not None and days_left < 0:
            out.append("The committee's term has ended: elections are overdue.")
        elif days_left is not None and days_left <= ELECTION_NOTICE_DAYS:
            out.append(f"The term ends in {days_left} days: the election process should start.")
        if c.term_ends_on and _add_years(c.formed_on, TERM_YEARS) < c.term_ends_on:
            out.append(f"The term is longer than {TERM_YEARS} years, the most the Act allows.")
        return out

    # ── Committees ──────────────────────────────────────────────────────────────────────────────────────────────

    def _committee(self, committee_id: UUID, user: User) -> ManagingCommittee:
        c = self.db.query(ManagingCommittee).filter(ManagingCommittee.id == committee_id,
                                                    ManagingCommittee.is_active == True).first()  # noqa: E712
        if c is None:
            raise HTTPException(404, "Committee not found")
        assert_society_access(user, c.society_id)
        return c

    def create_committee(self, society_id: UUID, data: dict, user: User) -> dict:
        assert_society_access(user, society_id)
        formed = data["formed_on"]
        ends = data.get("term_ends_on") or (_add_years(formed, TERM_YEARS) - timedelta(days=1))
        if ends <= formed:
            raise HTTPException(422, "The term must end after the committee was formed.")
        c = ManagingCommittee(society_id=society_id, formed_on=formed, term_ends_on=ends, created_by=user.id,
                              name=(data.get("name") or f"Managing Committee {formed.year}–{ends.year}")[:150],
                              election_note=data.get("election_note"))
        self.db.add(c)
        self.db.commit()
        return self.committee_out(c, society_today(self.db, society_id))

    def update_committee(self, committee_id: UUID, changes: dict, user: User) -> dict:
        c = self._committee(committee_id, user)
        for k in ("name", "formed_on", "term_ends_on", "election_note"):
            if k in changes and changes[k] is not None:
                setattr(c, k, changes[k])
        if c.term_ends_on and c.term_ends_on <= c.formed_on:
            raise HTTPException(422, "The term must end after the committee was formed.")
        self.db.commit()
        return self.committee_out(c, society_today(self.db, c.society_id))

    # ── Members ─────────────────────────────────────────────────────────────────────────────────────────────────

    def _resident(self, society_id: UUID, resident_id: UUID):
        row = (self.db.query(Resident, Flat, Wing).join(Flat, Flat.id == Resident.flat_id)
               .join(Wing, Wing.id == Flat.wing_id)
               .filter(Resident.id == resident_id, Wing.society_id == society_id).first())
        if row is None:
            raise HTTPException(404, "That resident is not in this society.")
        return row

    def _check_office(self, c: ManagingCommittee, position: str, from_date: date, replace: bool,
                      exclude: Optional[UUID] = None) -> None:
        if position not in COMMITTEE_POSITIONS:
            raise HTTPException(422, "Unknown position")
        if position not in SINGLE_OFFICE:
            return
        holders = [m for m in c.members if m.is_active and m.position == position and m.id != exclude
                   and (m.to_date is None or m.to_date >= from_date)]
        if holders and not replace:
            raise HTTPException(409, f"{holders[0].full_name} is already {POSITION_LABELS[position]}. Replace them "
                                     f"(they leave the office the day before) or choose another position.")
        for h in holders:                                       # the outgoing holder leaves the day before
            h.to_date = from_date - timedelta(days=1)

    def add_member(self, committee_id: UUID, data: dict, user: User) -> dict:
        c = self._committee(committee_id, user)
        today = society_today(self.db, c.society_id)
        from_date = data.get("from_date") or c.formed_on
        if from_date < c.formed_on:
            raise HTTPException(422, "A member cannot join before the committee was formed.")
        name, phone, email, flat_label = data.get("full_name"), data.get("phone"), data.get("email"), data.get("flat")
        if data.get("resident_id"):
            r, f, w = self._resident(c.society_id, data["resident_id"])
            name = name or r.full_name
            phone = phone or r.phone
            email = email or r.email
            flat_label = flat_label or f"{w.name} {f.flat_number}"
        if not (name or "").strip():
            raise HTTPException(422, "Give the member's name or choose the resident.")
        position = data.get("position") or "member"
        self._check_office(c, position, from_date, bool(data.get("replace")))
        office_powers = position in ("chairman", "secretary", "treasurer")
        m = CommitteeMember(
            committee_id=c.id, society_id=c.society_id, resident_id=data.get("resident_id"), full_name=name.strip()[:255],
            flat_label=flat_label, position=position, phone=phone, email=email, from_date=from_date,
            to_date=data.get("to_date"),
            # The bye-laws' usual signatories: the three office-bearers, unless the committee decided otherwise.
            cheque_signatory=data.get("cheque_signatory", office_powers),
            approves_payments=data.get("approves_payments", office_powers),
            signs_documents=data.get("signs_documents", position in ("chairman", "secretary")),
            spending_limit=data.get("spending_limit"), responsibilities=data.get("responsibilities"))
        self.db.add(m)
        self.db.commit()
        self.db.refresh(c)
        return self.committee_out(c, today)

    def _member(self, member_id: UUID, user: User) -> CommitteeMember:
        m = self.db.query(CommitteeMember).filter(CommitteeMember.id == member_id,
                                                  CommitteeMember.is_active == True).first()  # noqa: E712
        if m is None:
            raise HTTPException(404, "Committee member not found")
        assert_society_access(user, m.society_id)
        return m

    def update_member(self, member_id: UUID, changes: dict, user: User) -> dict:
        m = self._member(member_id, user)
        c = self._committee(m.committee_id, user)
        if changes.get("position") and changes["position"] != m.position:
            self._check_office(c, changes["position"], changes.get("from_date") or m.from_date,
                               bool(changes.get("replace")), exclude=m.id)
        for k in ("full_name", "flat", "position", "phone", "email", "from_date", "to_date", "cheque_signatory",
                  "approves_payments", "signs_documents", "spending_limit", "responsibilities"):
            if k in changes:
                setattr(m, "flat_label" if k == "flat" else k, changes[k])
        if m.to_date is not None and m.to_date < m.from_date:
            raise HTTPException(422, "The leaving date cannot be before the joining date.")
        self.db.commit()
        self.db.refresh(c)
        return self.committee_out(c, society_today(self.db, c.society_id))

    def remove_member(self, member_id: UUID, user: User) -> dict:
        """Entered by mistake: take the row off the register (someone who LEFT the office gets a leaving date)."""
        m = self._member(member_id, user)
        c = self._committee(m.committee_id, user)
        m.is_active = False
        self.db.commit()
        self.db.refresh(c)
        return self.committee_out(c, society_today(self.db, c.society_id))
