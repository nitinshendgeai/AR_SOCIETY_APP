from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import (
    get_current_user, require_roles,
    require_admin_committee, require_supervisor_above, require_any_member,
)
from app.models.user import User
from app.modules.complaint.schemas.complaint import (
    ComplaintCreate, ComplaintOut, ComplaintListOut,
    ComplaintAssignRequest, ComplaintStatusUpdateRequest,
    ComplaintReopenRequest, CommentCreate, CommentOut,
    AttachmentCreate, AttachmentOut,
)
from app.modules.complaint.services.complaint_service import ComplaintService

router = APIRouter(prefix="/complaints", tags=["Complaint Management"])

staff_or_above     = require_supervisor_above
committee_or_admin = require_admin_committee
any_member         = require_any_member


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("/", response_model=ComplaintOut, status_code=201)
def create_complaint(
    data:    ComplaintCreate,
    request: Request,
    db:      Session = Depends(get_db),
    user:    User    = Depends(any_member),
):
    return ComplaintService(db).create_complaint(data, user, request)


@router.get("/{complaint_id}", response_model=ComplaintOut,
            dependencies=[Depends(any_member)])
def get_complaint(complaint_id: UUID, db: Session = Depends(get_db)):
    return ComplaintService(db).get_complaint(complaint_id)


# ── Workflow actions ──────────────────────────────────────────────────────────

@router.post("/{complaint_id}/assign", response_model=ComplaintOut)
def assign_complaint(
    complaint_id: UUID,
    data:    ComplaintAssignRequest,
    request: Request,
    db:      Session = Depends(get_db),
    user:    User    = Depends(committee_or_admin),
):
    return ComplaintService(db).assign_complaint(complaint_id, data, user, request)


@router.post("/{complaint_id}/status", response_model=ComplaintOut)
def update_status(
    complaint_id: UUID,
    data:    ComplaintStatusUpdateRequest,
    request: Request,
    db:      Session = Depends(get_db),
    user:    User    = Depends(staff_or_above),
):
    return ComplaintService(db).update_status(complaint_id, data, user, request)


@router.post("/{complaint_id}/reopen", response_model=ComplaintOut)
def reopen_complaint(
    complaint_id: UUID,
    data:    ComplaintReopenRequest,
    request: Request,
    db:      Session = Depends(get_db),
    user:    User    = Depends(any_member),
):
    return ComplaintService(db).reopen_complaint(complaint_id, data, user, request)


# ── Comments ──────────────────────────────────────────────────────────────────

@router.post("/{complaint_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    complaint_id: UUID,
    data:    CommentCreate,
    request: Request,
    db:      Session = Depends(get_db),
    user:    User    = Depends(any_member),
):
    return ComplaintService(db).add_comment(complaint_id, data, user, request)


# ── Attachments ───────────────────────────────────────────────────────────────

@router.post("/{complaint_id}/attachments", response_model=AttachmentOut, status_code=201)
def add_attachment(
    complaint_id: UUID,
    data: AttachmentCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(any_member),
):
    return ComplaintService(db).add_attachment(complaint_id, data, user)


# ── Query endpoints ───────────────────────────────────────────────────────────

@router.get("/society/{society_id}", response_model=List[ComplaintListOut])
def list_society_complaints(
    society_id: UUID,
    skip: int = 0, limit: int = 50,
    db:   Session = Depends(get_db),
    user: User    = Depends(committee_or_admin),
):
    return ComplaintService(db).list_by_society(society_id, skip, limit)


@router.get("/society/{society_id}/open", response_model=List[ComplaintListOut])
def list_open_complaints(
    society_id: UUID,
    db:   Session = Depends(get_db),
    user: User    = Depends(committee_or_admin),
):
    return ComplaintService(db).list_open(society_id)


@router.get("/me/complaints", response_model=List[ComplaintListOut])
def my_complaints(
    skip: int = 0, limit: int = 50,
    db:   Session = Depends(get_db),
    user: User    = Depends(any_member),
):
    return ComplaintService(db).list_my_complaints(user.id, skip, limit)


@router.get("/me/assigned", response_model=List[ComplaintListOut])
def assigned_to_me(
    skip: int = 0, limit: int = 50,
    db:   Session = Depends(get_db),
    user: User    = Depends(staff_or_above),
):
    return ComplaintService(db).list_assigned_to_me(user.id, skip, limit)
