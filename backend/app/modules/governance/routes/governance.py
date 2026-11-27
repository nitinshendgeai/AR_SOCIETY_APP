import datetime as dt
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin_committee, require_any_member
from app.db.session import get_db
from app.models.user import User
from app.modules.governance.services.governance_service import GovernanceService, MAX_DOCUMENT_BYTES

router = APIRouter(prefix="/governance", tags=["Governance"])

member = Depends(require_any_member)
office = Depends(require_admin_committee)


# ── Meetings ──────────────────────────────────────────────────────────────────

class MeetingIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    meeting_type: str = "committee"
    meeting_date: dt.date
    start_time: Optional[dt.time] = None
    venue: Optional[str] = Field(default=None, max_length=200)
    agenda: Optional[str] = None


class MeetingCreate(MeetingIn):
    announce: bool = True


class MeetingUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    meeting_type: Optional[str] = None
    meeting_date: Optional[dt.date] = None
    start_time: Optional[dt.time] = None
    venue: Optional[str] = Field(default=None, max_length=200)
    agenda: Optional[str] = None
    status: Optional[str] = None


class AttendeeIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    flat_label: Optional[str] = Field(default=None, max_length=60)
    designation: Optional[str] = Field(default=None, max_length=60)
    present: bool = True


class ResolutionIn(BaseModel):
    text: str = Field(min_length=1)
    proposed_by: Optional[str] = Field(default=None, max_length=120)
    seconded_by: Optional[str] = Field(default=None, max_length=120)
    outcome: str = "carried"


class MinutesIn(BaseModel):
    minutes: Optional[str] = None
    attendees: List[AttendeeIn] = []
    resolutions: List[ResolutionIn] = []
    publish: bool = False


@router.post("/meetings/society/{society_id}", status_code=201, dependencies=[office])
def create_meeting(society_id: UUID, data: MeetingCreate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    svc = GovernanceService(db)
    body = data.model_dump()
    announce = body.pop("announce")
    return svc.meeting_out(svc.create_meeting(society_id, body, user, announce), user)


@router.get("/meetings/society/{society_id}", dependencies=[member])
def list_meetings(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = GovernanceService(db)
    return [svc.meeting_out(m, user) for m in svc.list_meetings(society_id, user)]


@router.get("/meetings/{meeting_id}", dependencies=[member])
def get_meeting(meeting_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = GovernanceService(db)
    return svc.meeting_out(svc.get_meeting(meeting_id, user), user)


@router.patch("/meetings/{meeting_id}", dependencies=[office])
def update_meeting(meeting_id: UUID, data: MeetingUpdate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    svc = GovernanceService(db)
    return svc.meeting_out(svc.update_meeting(meeting_id, data.model_dump(exclude_unset=True), user), user)


@router.put("/meetings/{meeting_id}/minutes", dependencies=[office])
def record_minutes(meeting_id: UUID, data: MinutesIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    svc = GovernanceService(db)
    return svc.meeting_out(svc.record_minutes(meeting_id, data.model_dump(), user), user)


# ── Polls ─────────────────────────────────────────────────────────────────────

class PollIn(BaseModel):
    question: str = Field(min_length=3, max_length=300)
    description: Optional[str] = None
    options: List[str] = Field(min_length=2, max_length=10)
    closes_on: dt.date
    results_after: str = Field(default="vote", pattern="^(vote|close)$")


class VoteIn(BaseModel):
    option_id: UUID


@router.post("/polls/society/{society_id}", status_code=201, dependencies=[office])
def create_poll(society_id: UUID, data: PollIn, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    svc = GovernanceService(db)
    return svc.poll_out(svc.create_poll(society_id, data.model_dump(), user), user)


@router.get("/polls/society/{society_id}", dependencies=[member])
def list_polls(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return GovernanceService(db).list_polls(society_id, user)


@router.post("/polls/{poll_id}/vote", dependencies=[member])
def vote(poll_id: UUID, data: VoteIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return GovernanceService(db).vote(poll_id, data.option_id, user)


@router.post("/polls/{poll_id}/close", dependencies=[office])
def close_poll(poll_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return GovernanceService(db).close_poll(poll_id, user)


# ── Documents ─────────────────────────────────────────────────────────────────

@router.post("/documents/society/{society_id}", status_code=201, dependencies=[office])
async def add_document(society_id: UUID, title: str = Form(...), category: str = Form("other"),
                       description: Optional[str] = Form(None), visibility: str = Form("everyone"),
                       file: UploadFile = File(...), db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    data = await file.read(MAX_DOCUMENT_BYTES + 1)
    svc = GovernanceService(db)
    d = svc.add_document(society_id, title=title, category=category, description=description,
                         visibility=visibility, file_name=file.filename or "document",
                         mime_type=file.content_type or "application/octet-stream", data=data, user=user)
    return svc.document_out(d)


@router.get("/documents/society/{society_id}", dependencies=[member])
def list_documents(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = GovernanceService(db)
    return [svc.document_out(d) for d in svc.list_documents(society_id, user)]


@router.get("/documents/{doc_id}/download", dependencies=[member])
def download_document(doc_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = GovernanceService(db).get_document(doc_id, user)
    return Response(content=d.data, media_type=d.mime_type,
                    headers={"Content-Disposition": f'attachment; filename="{d.file_name}"'})


@router.delete("/documents/{doc_id}", status_code=204, dependencies=[office])
def delete_document(doc_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    GovernanceService(db).delete_document(doc_id, user)


# ── Managing committee register ─────────────────────────────────────────────────────────────────────────────────

from app.modules.governance.services.committee_service import CommitteeService  # noqa: E402

_POSITION = "^(chairman|vice_chairman|secretary|joint_secretary|treasurer|member|co_opted|invitee)$"


class CommitteeIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=150)
    formed_on: dt.date
    term_ends_on: Optional[dt.date] = None          # default: five years
    election_note: Optional[str] = Field(default=None, max_length=2000)


class CommitteeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=150)
    formed_on: Optional[dt.date] = None
    term_ends_on: Optional[dt.date] = None
    election_note: Optional[str] = Field(default=None, max_length=2000)


class CommitteeMemberIn(BaseModel):
    resident_id: Optional[UUID] = None              # name, flat and contacts are taken from the resident
    full_name: Optional[str] = Field(default=None, max_length=255)
    flat: Optional[str] = Field(default=None, max_length=60)
    position: str = Field(default="member", pattern=_POSITION)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    from_date: Optional[dt.date] = None
    to_date: Optional[dt.date] = None
    cheque_signatory: Optional[bool] = None
    approves_payments: Optional[bool] = None
    signs_documents: Optional[bool] = None
    spending_limit: Optional[int] = Field(default=None, ge=0)
    responsibilities: Optional[str] = Field(default=None, max_length=500)
    replace: bool = False                           # the outgoing holder of this office leaves the day before


class CommitteeMemberUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=255)
    flat: Optional[str] = Field(default=None, max_length=60)
    position: Optional[str] = Field(default=None, pattern=_POSITION)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    from_date: Optional[dt.date] = None
    to_date: Optional[dt.date] = None
    cheque_signatory: Optional[bool] = None
    approves_payments: Optional[bool] = None
    signs_documents: Optional[bool] = None
    spending_limit: Optional[int] = Field(default=None, ge=0)
    responsibilities: Optional[str] = Field(default=None, max_length=500)
    replace: bool = False


@router.get("/committee/society/{society_id}", dependencies=[member])
def committee_register(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The committee in office (term, office-bearers, their powers and contacts, what is missing) and earlier ones."""
    return CommitteeService(db).register(society_id, user)


@router.post("/committee/society/{society_id}", status_code=201, dependencies=[office])
def create_committee(society_id: UUID, data: CommitteeIn, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    return CommitteeService(db).create_committee(society_id, data.model_dump(), user)


@router.put("/committee/{committee_id}", dependencies=[office])
def update_committee(committee_id: UUID, data: CommitteeUpdate, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    return CommitteeService(db).update_committee(committee_id, data.model_dump(exclude_unset=True), user)


@router.post("/committee/{committee_id}/members", status_code=201, dependencies=[office])
def add_committee_member(committee_id: UUID, data: CommitteeMemberIn, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    return CommitteeService(db).add_member(committee_id, data.model_dump(exclude_none=True), user)


@router.put("/committee/members/{member_id}", dependencies=[office])
def update_committee_member(member_id: UUID, data: CommitteeMemberUpdate, db: Session = Depends(get_db),
                            user: User = Depends(get_current_user)):
    return CommitteeService(db).update_member(member_id, data.model_dump(exclude_unset=True), user)


@router.delete("/committee/members/{member_id}", dependencies=[office])
def remove_committee_member(member_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Remove a row entered by mistake. Someone who left the office gets a leaving date instead (PUT to_date)."""
    return CommitteeService(db).remove_member(member_id, user)
