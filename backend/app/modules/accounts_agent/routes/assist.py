"""Accounts Agent assistant: bye-law questions with clause references, entries drafted for approval, and notice /
agenda drafts. Every call is scoped to the caller's own society."""
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import _user_has_permission, get_current_user, require_admin_committee, require_manager_above
from app.core.tenant_scope import resolve_create_society_id
from app.db.session import get_db
from app.models.user import User
from app.modules.accounts_agent.assist import bylaws, entries, notices
from app.modules.accounts_agent.services.engine import get_settings

router = APIRouter(prefix="/accounts-agent", tags=["Accounts Agent — Assistant"])


def _sid(user: User, society_id: Optional[UUID]) -> UUID:
    try:
        return resolve_create_society_id(user, society_id)
    except HTTPException as exc:
        if exc.status_code == 403:
            raise HTTPException(403, "You can only view or act on your own society's Accounts Agent data.") from exc
        raise


class BylawQuestion(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)


@router.post("/bylaws/ask")
def ask_bylaws(data: BylawQuestion, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """Any member of the society may ask. The society's own figures (dues, funds, approvals) are added to the answer
    only for managers, admins and committee members."""
    sid = _sid(user, society_id)
    out = bylaws.ask(db, sid, data.question, user, get_settings(db, sid))
    if not _user_has_permission(user, "manager_above"):
        out["society_facts"] = None
    return out


class EntryDraft(BaseModel):
    text: Optional[str] = Field(None, max_length=1000, description="The entry in your own words")
    voucher_type: Optional[str] = Field(None, pattern="^(payment|receipt)$")
    amount: Optional[str] = Field(None, max_length=20)
    voucher_date: Optional[date] = None
    vendor_id: Optional[UUID] = None
    ledger_id: Optional[UUID] = None
    money_account: Optional[str] = Field(None, pattern="^(bank|cash)$")
    reference: Optional[str] = Field(None, max_length=100)
    narration: Optional[str] = Field(None, max_length=250)
    # The person confirms this vendor payment is not for the vendor's booked, unpaid bills (an advance, a cash purchase).
    not_against_bill: bool = False
    save: bool = False


@router.post("/entries/draft")
def draft_entry(data: EntryDraft, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                user: User = Depends(require_manager_above)):
    """With save=false: the proposed voucher (nothing stored). With save=true: the voucher is created as PENDING
    through the accounts service; it counts only after approval by another admin or committee member."""
    sid = _sid(user, society_id)
    if not data.text and not data.amount:
        raise HTTPException(422, "Describe the entry or give at least the amount.")
    body = data.model_dump(exclude={"save"})
    return entries.draft(db, sid, user, body, get_settings(db, sid), save=data.save)


class EntryRecord(BaseModel):
    """A hand-off the person confirmed: the agent records it through Billing / Vendor Bills."""
    kind: str = Field(..., pattern="^(member_receipt|vendor_bill_payment)$")
    amount: str = Field(..., max_length=20)
    flat_id: Optional[UUID] = None
    vendor_id: Optional[UUID] = None
    paid_on: Optional[date] = None
    money_account: Optional[str] = Field(None, pattern="^(bank|cash)$")
    payment_mode: Optional[str] = Field(None, pattern="^(cash|upi|bank_transfer|cheque|neft|rtgs)$")
    reference: Optional[str] = Field(None, max_length=100)
    text: Optional[str] = Field(None, max_length=1000)
    confirm: bool = False


@router.post("/entries/record")
def record_entry(data: EntryRecord, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                 user: User = Depends(require_manager_above)):
    """Record a member's payment or a vendor-bill payment for the person (who must confirm it): a receipt / payment
    through the same service and controls as the office screens, posted to the books."""
    sid = _sid(user, society_id)
    return entries.record(db, sid, user, data.model_dump())


class NoticeDraft(BaseModel):
    kind: str = Field(..., pattern="^(AGM|SGM|COMMITTEE|DUES)$")
    meeting_date: Optional[date] = None
    time: Optional[str] = Field(None, max_length=40)
    venue: Optional[str] = Field(None, max_length=200)
    financial_year: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}$")
    subject: Optional[str] = Field(None, max_length=300)
    resolutions: Optional[List[str]] = Field(None, max_length=20)
    extra_items: Optional[List[str]] = Field(None, max_length=20)
    only_defaulters: bool = True
    pay_within_days: int = Field(15, ge=1, le=90)
    save: bool = False


@router.post("/notices/draft")
def draft_notice(data: NoticeDraft, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                 user: User = Depends(require_admin_committee)):
    """The draft text. With save=true it is stored as DRAFT notice(s) to edit and publish from Notices."""
    sid = _sid(user, society_id)
    return notices.draft(db, sid, user, data.kind, data.model_dump(exclude={"kind", "save"}), save=data.save)
