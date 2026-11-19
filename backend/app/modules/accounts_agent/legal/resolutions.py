"""Structured General Body and Managing Committee resolutions, and matching a payment or fund movement to the
resolution that authorised it.

The app's existing governance module records meetings and the free text of their resolutions. This register adds what
an accounts audit needs (authority, purpose, amount, vendor, ledger, period, quorum) and can import carried resolutions
from governance meetings — imported rows stay RECORDED until a person checks the extracted amount and verifies them.
"""
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.accounts_agent.legal.models import (
    APPROVAL_AUTHORITIES, MEETING_TYPES, RESOLUTION_CATEGORIES, SocietyResolution,
)
from app.modules.accounts_agent.services import audit

AUTHORITY_FOR_MEETING = {"AGM": "GENERAL_BODY", "SGM": "GENERAL_BODY", "COMMITTEE": "MANAGING_COMMITTEE"}
GOV_MEETING = {"agm": "AGM", "sgm": "SGM", "committee": "COMMITTEE"}
AMOUNT = re.compile(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)", re.I)
LIVE = ("RECORDED", "VERIFIED")
EDITABLE = ("resolution_number", "meeting_type", "meeting_date", "notice_date", "agenda", "attendance",
            "quorum_required", "votes_for", "votes_against", "votes_abstain", "approval_authority", "category",
            "purpose", "approved_amount", "vendor_id", "account_id", "work_order_id", "contract_id", "conditions",
            "period_from", "period_to", "supporting_document_id", "supersedes_id")


def _check_refs(db: Session, society_id: UUID, data: dict) -> None:
    from app.modules.accounts.models.accounts import Account
    from app.modules.vendor.models.vendor import AMCContract, Vendor, WorkOrder
    from app.modules.accounts_agent.legal.models import LegalDocument
    for key, model in (("vendor_id", Vendor), ("account_id", Account), ("work_order_id", WorkOrder),
                       ("contract_id", AMCContract), ("supporting_document_id", LegalDocument),
                       ("supersedes_id", SocietyResolution)):
        if data.get(key):
            row = db.get(model, data[key])
            if row is None or getattr(row, "society_id", None) != society_id:
                raise HTTPException(422, f"{key.replace('_id', '').replace('_', ' ')} not found in this society")


def _validate(data: dict) -> None:
    if data.get("meeting_type") and data["meeting_type"] not in MEETING_TYPES:
        raise HTTPException(422, "Meeting type must be AGM, SGM or COMMITTEE")
    if data.get("approval_authority") and data["approval_authority"] not in APPROVAL_AUTHORITIES:
        raise HTTPException(422, "Approval authority must be GENERAL_BODY or MANAGING_COMMITTEE")
    if data.get("category") and data["category"] not in RESOLUTION_CATEGORIES:
        raise HTTPException(422, "Unknown resolution category")
    if data.get("approved_amount") is not None and Decimal(str(data["approved_amount"])) < 0:
        raise HTTPException(422, "The approved amount cannot be negative")
    if data.get("period_from") and data.get("period_to") and data["period_to"] < data["period_from"]:
        raise HTTPException(422, "The period ends before it starts")


def create(db: Session, society_id: UUID, user, data: dict) -> SocietyResolution:
    data = {k: v for k, v in data.items() if k in EDITABLE}
    data.setdefault("approval_authority", AUTHORITY_FOR_MEETING.get(data.get("meeting_type")))
    _validate(data)
    _check_refs(db, society_id, data)
    r = SocietyResolution(society_id=society_id, status="RECORDED", created_by=user.id, **data)
    db.add(r)
    db.flush()
    if r.supersedes_id:
        old = db.get(SocietyResolution, r.supersedes_id)
        old.status = "SUPERSEDED"
    audit.record(db, society_id, "resolution_recorded", "resolution", r.id, user.id, {"number": r.resolution_number})
    return r


def update(db: Session, r: SocietyResolution, user, data: dict) -> SocietyResolution:
    if r.status in ("SUPERSEDED", "REJECTED"):
        raise HTTPException(409, f"A {r.status.lower()} resolution cannot be edited")
    data = {k: v for k, v in data.items() if k in EDITABLE and v is not None}
    _validate(data)
    _check_refs(db, r.society_id, data)
    for k, v in data.items():
        setattr(r, k, v)
    if r.status == "VERIFIED":                 # an edited resolution must be checked again
        r.status, r.verified_by, r.verified_at = "RECORDED", None, None
    audit.record(db, r.society_id, "resolution_updated", "resolution", r.id, user.id, {"fields": sorted(data)})
    return r


def problems(r: SocietyResolution) -> List[str]:
    """What stops this resolution being treated as a valid authority."""
    out = []
    expected = AUTHORITY_FOR_MEETING.get(r.meeting_type)
    if expected and r.approval_authority != expected:
        out.append(f"A {r.meeting_type} resolution is an act of the {expected.replace('_', ' ').lower()}, not the "
                   f"{r.approval_authority.replace('_', ' ').lower()}")
    if r.quorum_required is not None and r.attendance is not None and r.attendance < r.quorum_required:
        out.append(f"Attendance {r.attendance} is below the quorum of {r.quorum_required}")
    if r.votes_for is not None and r.votes_against is not None and r.votes_for <= r.votes_against:
        out.append("The recorded votes do not show the resolution as carried")
    if r.meeting_type in ("AGM", "SGM") and r.notice_date and r.notice_date > r.meeting_date:
        out.append("The notice is dated after the meeting")
    return out


def verify(db: Session, r: SocietyResolution, user, note: Optional[str]) -> SocietyResolution:
    if r.status != "RECORDED":
        raise HTTPException(409, f"Only a recorded resolution can be verified (this one is {r.status.lower()})")
    p = problems(r)
    if p:
        raise HTTPException(422, "Cannot verify: " + "; ".join(p))
    r.status, r.verified_by, r.verified_at = "VERIFIED", user.id, datetime.utcnow()
    audit.record(db, r.society_id, "resolution_verified", "resolution", r.id, user.id, {"note": (note or "")[:200]})
    return r


def import_governance(db: Session, society_id: UUID, user) -> int:
    """Carried resolutions of held meetings that are not yet in the register. Amounts found in the text are extracted
    for a person to check; nothing imported is verified automatically."""
    from app.modules.governance.models.governance import Meeting, MeetingResolution
    have = {g for (g,) in db.query(SocietyResolution.governance_resolution_id)
            .filter(SocietyResolution.society_id == society_id, SocietyResolution.governance_resolution_id.isnot(None))}
    n = 0
    rows = (db.query(MeetingResolution, Meeting).join(Meeting, Meeting.id == MeetingResolution.meeting_id)
            .filter(Meeting.society_id == society_id, Meeting.status == "held", MeetingResolution.outcome == "carried").all())
    for res, m in rows:
        if res.id in have:
            continue
        mt = GOV_MEETING.get(m.meeting_type)
        if not mt:
            continue
        amt = AMOUNT.search(res.text or "")
        db.add(SocietyResolution(
            society_id=society_id, resolution_number=f"{m.meeting_date:%Y%m%d}/{res.number}", meeting_type=mt,
            meeting_date=m.meeting_date, agenda=m.agenda, attendance=sum(1 for a in m.attendees if a.present) or None,
            approval_authority=AUTHORITY_FOR_MEETING[mt], category="other", purpose=res.text,
            approved_amount=Decimal(amt.group(1).replace(",", "")) if amt else None,
            conditions="Imported from the meeting minutes; check the amount, vendor and period before verifying.",
            governance_resolution_id=res.id, status="RECORDED", created_by=user.id))
        n += 1
    if n:
        audit.record(db, society_id, "resolutions_imported", "resolution", None, user.id, {"count": n})
    db.flush()
    return n


@dataclass
class Match:
    resolutions: List[SocietyResolution]
    approved_total: Decimal
    verified: bool


def authorising(db: Session, society_id: UUID, *, on: date, vendor_id=None, account_id=None, work_order_id=None,
                contract_id=None, categories=None, authority: Optional[str] = None) -> Match:
    """Live resolutions that could authorise a payment/movement on `on` for this vendor / ledger / work."""
    q = db.query(SocietyResolution).filter(SocietyResolution.society_id == society_id,
                                           SocietyResolution.status.in_(LIVE), SocietyResolution.meeting_date <= on)
    rows = []
    for r in q.all():
        if r.period_to and r.period_to < on:
            continue
        if categories and r.category not in categories:
            continue
        if authority == "GENERAL_BODY" and r.approval_authority != "GENERAL_BODY":
            continue
        if problems(r):
            continue
        hit = ((vendor_id and r.vendor_id == vendor_id) or (account_id and r.account_id == account_id)
               or (work_order_id and r.work_order_id == work_order_id) or (contract_id and r.contract_id == contract_id))
        if hit:
            rows.append(r)
    total = sum((Decimal(str(r.approved_amount)) for r in rows if r.approved_amount is not None), Decimal("0"))
    return Match(rows, total, bool(rows) and all(r.status == "VERIFIED" for r in rows))


def resolution_dict(r: SocietyResolution) -> dict:
    return {"id": str(r.id), "resolution_number": r.resolution_number, "meeting_type": r.meeting_type,
            "meeting_date": r.meeting_date.isoformat(), "notice_date": r.notice_date.isoformat() if r.notice_date else None,
            "agenda": r.agenda, "attendance": r.attendance, "quorum_required": r.quorum_required,
            "votes_for": r.votes_for, "votes_against": r.votes_against, "votes_abstain": r.votes_abstain,
            "approval_authority": r.approval_authority, "category": r.category, "purpose": r.purpose,
            "approved_amount": str(r.approved_amount) if r.approved_amount is not None else None,
            "vendor_id": str(r.vendor_id) if r.vendor_id else None, "account_id": str(r.account_id) if r.account_id else None,
            "work_order_id": str(r.work_order_id) if r.work_order_id else None,
            "contract_id": str(r.contract_id) if r.contract_id else None, "conditions": r.conditions,
            "period_from": r.period_from.isoformat() if r.period_from else None,
            "period_to": r.period_to.isoformat() if r.period_to else None,
            "supporting_document_id": str(r.supporting_document_id) if r.supporting_document_id else None,
            "governance_resolution_id": str(r.governance_resolution_id) if r.governance_resolution_id else None,
            "status": r.status, "problems": problems(r),
            "verified_at": r.verified_at.isoformat() if r.verified_at else None}
