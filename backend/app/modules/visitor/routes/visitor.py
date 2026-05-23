from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User
from app.modules.visitor.schemas.visitor import (
    VisitorCreate, VisitorOut, VisitorApproveRequest,
    VisitorRejectRequest, VisitorCheckInRequest, VisitorCheckOutRequest,
    GateCreate, GateOut,
)
from app.modules.visitor.services.visitor_service import VisitorService

router = APIRouter(prefix="/visitors", tags=["Visitor & Gate Management"])

# Role guards
security_or_admin = require_roles("Admin", "Security")
resident_or_above = require_roles("Admin", "Committee", "Resident")


# ── Gates ─────────────────────────────────────────────────────────────────────

@router.post("/gates", response_model=GateOut, status_code=201,
             dependencies=[Depends(require_roles("Admin"))])
def create_gate(data: GateCreate, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    return VisitorService(db).create_gate(data, current_user)


@router.get("/gates/{society_id}", response_model=List[GateOut],
            dependencies=[Depends(get_current_user)])
def list_gates(society_id: UUID, db: Session = Depends(get_db)):
    return VisitorService(db).list_gates(society_id)


# ── Visitor workflow ──────────────────────────────────────────────────────────

@router.post("/", response_model=VisitorOut, status_code=201)
def create_visitor(
    data:    VisitorCreate,
    request: Request,
    db:      Session = Depends(get_db),
    current_user: User = Depends(security_or_admin),
):
    """Security guard logs a new visitor at the gate."""
    return VisitorService(db).create_visitor(data, current_user, request)


@router.post("/{visitor_id}/approve", response_model=VisitorOut)
def approve_visitor(
    visitor_id: UUID,
    data:       VisitorApproveRequest,
    request:    Request,
    db:         Session = Depends(get_db),
    current_user: User = Depends(resident_or_above),
):
    """Resident approves a visitor."""
    return VisitorService(db).approve_visitor(visitor_id, data, current_user, request)


@router.post("/{visitor_id}/reject", response_model=VisitorOut)
def reject_visitor(
    visitor_id: UUID,
    data:       VisitorRejectRequest,
    request:    Request,
    db:         Session = Depends(get_db),
    current_user: User = Depends(resident_or_above),
):
    """Resident rejects a visitor."""
    return VisitorService(db).reject_visitor(visitor_id, data, current_user, request)


@router.post("/{visitor_id}/checkin", response_model=VisitorOut)
def check_in(
    visitor_id: UUID,
    data:       VisitorCheckInRequest,
    request:    Request,
    db:         Session = Depends(get_db),
    current_user: User = Depends(security_or_admin),
):
    """Guard checks visitor in."""
    return VisitorService(db).check_in(
        visitor_id, data.gate_id, current_user, data.notes, request
    )


@router.post("/{visitor_id}/checkout", response_model=VisitorOut)
def check_out(
    visitor_id: UUID,
    data:       VisitorCheckOutRequest,
    request:    Request,
    db:         Session = Depends(get_db),
    current_user: User = Depends(security_or_admin),
):
    """Guard checks visitor out."""
    return VisitorService(db).check_out(
        visitor_id, data.gate_id, current_user, data.notes, request
    )


# ── Query endpoints ───────────────────────────────────────────────────────────

@router.get("/{visitor_id}", response_model=VisitorOut,
            dependencies=[Depends(get_current_user)])
def get_visitor(visitor_id: UUID, db: Session = Depends(get_db)):
    return VisitorService(db).get_visitor(visitor_id)


@router.get("/society/{society_id}", response_model=List[VisitorOut],
            dependencies=[Depends(require_roles("Admin", "Committee", "Security"))])
def list_society_visitors(
    society_id: UUID,
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
):
    """Admin/Security: all visitors for a society."""
    return VisitorService(db).list_by_society(society_id, skip, limit)


@router.get("/society/{society_id}/inside", response_model=List[VisitorOut],
            dependencies=[Depends(require_roles("Admin", "Committee", "Security"))])
def currently_inside(society_id: UUID, db: Session = Depends(get_db)):
    """Who is currently inside the society."""
    return VisitorService(db).get_currently_inside(society_id)


@router.get("/me/pending-approvals", response_model=List[VisitorOut])
def pending_approvals(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(resident_or_above),
):
    """Resident: visitors waiting for my approval."""
    return VisitorService(db).get_pending_approvals(current_user.id)


@router.get("/me/visitors", response_model=List[VisitorOut])
def my_visitors(
    skip: int = 0, limit: int = 50,
    db:   Session = Depends(get_db),
    current_user: User = Depends(resident_or_above),
):
    """Resident: all my visitors."""
    return VisitorService(db).get_my_visitors(current_user.id, skip, limit)
