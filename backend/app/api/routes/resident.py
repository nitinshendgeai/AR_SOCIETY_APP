from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.db.session import get_db
from app.models.resident import ResidentType
from app.schemas.resident import ResidentCreate, ResidentUpdate, ResidentOut, ResidentCreateOut
from app.schemas.resident_edit_request import (
    ResidentEditRequestCreate, ResidentEditRequestOut, ResidentEditRequestReject,
)
from app.services.resident_service import ResidentService
from app.services.resident_edit_request_service import ResidentEditRequestService
from app.core.dependencies import require_admin_committee, get_current_user
from app.models.user import User

router = APIRouter(prefix="/residents", tags=["Residents"])


@router.post("/", response_model=ResidentCreateOut, status_code=201)
def create_resident(data: ResidentCreate, db: Session = Depends(get_db),
                     current_user: User = Depends(require_admin_committee)):
    return ResidentService(db).create(data, current_user)


@router.get("/", response_model=List[ResidentOut])
def list_residents(
    flat_id: Optional[UUID] = None,
    resident_type: Optional[ResidentType] = None,
    is_active: Optional[bool] = True,
    search: Optional[str] = Query(None, description="Matches name, phone, or email"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ResidentService(db).list(
        current_user, flat_id=flat_id, resident_type=resident_type,
        is_active=is_active, search=search, skip=skip, limit=limit,
    )


@router.get("/me", response_model=ResidentOut)
def get_my_resident_profile(db: Session = Depends(get_db),
                             current_user: User = Depends(get_current_user)):
    return ResidentService(db).get_me(current_user)


@router.get("/{resident_id}", response_model=ResidentOut)
def get_resident(resident_id: UUID, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    return ResidentService(db).get_or_404(resident_id, current_user)


@router.patch("/{resident_id}", response_model=ResidentOut)
def update_resident(resident_id: UUID, data: ResidentUpdate, db: Session = Depends(get_db),
                     current_user: User = Depends(require_admin_committee)):
    return ResidentService(db).update(resident_id, data, current_user)


# ── Self-service edit requests ─────────────────────────────────────────────
# A Resident cannot PATCH /residents/{id} directly (require_admin_committee
# above) — instead they submit a request here, which only takes effect once
# an Admin or Committee member approves it below.

@router.post("/edit-requests", response_model=ResidentEditRequestOut, status_code=201)
def create_edit_request(data: ResidentEditRequestCreate, db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    return ResidentEditRequestService(db).create_request(data, current_user)


@router.get("/edit-requests/mine", response_model=List[ResidentEditRequestOut])
def list_my_edit_requests(db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    return ResidentEditRequestService(db).list_mine(current_user)


@router.get("/edit-requests/pending", response_model=List[ResidentEditRequestOut])
def list_pending_edit_requests(db: Session = Depends(get_db),
                                current_user: User = Depends(require_admin_committee)):
    return ResidentEditRequestService(db).list_pending(current_user.society_id)


@router.post("/edit-requests/{request_id}/approve", response_model=ResidentEditRequestOut)
def approve_edit_request(request_id: UUID, db: Session = Depends(get_db),
                          current_user: User = Depends(require_admin_committee)):
    return ResidentEditRequestService(db).approve(request_id, current_user)


@router.post("/edit-requests/{request_id}/reject", response_model=ResidentEditRequestOut)
def reject_edit_request(request_id: UUID, data: ResidentEditRequestReject, db: Session = Depends(get_db),
                         current_user: User = Depends(require_admin_committee)):
    return ResidentEditRequestService(db).reject(request_id, data.reason, current_user)
