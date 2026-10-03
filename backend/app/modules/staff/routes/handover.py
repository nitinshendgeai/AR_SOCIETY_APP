from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field, field_validator, model_validator
from app.schemas import validators as val
from app.core.tenant_scope import assert_society_access
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.core.dependencies import (
    get_current_user, require_roles,
    require_admin_committee, require_supervisor_above, require_any_staff,
)
from app.models.user import User
from app.modules.staff.models.handover import HandoverItemType, HandoverStatus
from app.modules.staff.services.handover_service import HandoverService
from app.schemas.common import OrmBase, TimestampSchema

router = APIRouter(prefix="/handovers", tags=["Shift Handover / Takeover"])

admin_committee  = require_admin_committee
supervisor_above = require_supervisor_above
any_staff        = require_any_staff


# ── Inline schemas ────────────────────────────────────────────────────────────
class HandoverItemCreate(OrmBase):
    item_type:    HandoverItemType
    title:        str = Field(max_length=255)
    description:  Optional[str] = None
    is_urgent:    bool = False
    is_resolved:  bool = False
    reference_id: Optional[str] = Field(default=None, max_length=100)
    quantity:     Optional[int] = Field(default=None, ge=0, le=1_000_000)

    _title = field_validator("title", mode="before")(val.line_max(255, required=True))
    _description = field_validator("description", mode="before")(val.note_max(1000))
    _ref = field_validator("reference_id", mode="before")(val.line_max(100))

class HandoverCreate(OrmBase):
    society_id:        UUID
    outgoing_staff_id: Optional[UUID] = None
    incoming_staff_id: Optional[UUID] = None
    duty_assignment_id: Optional[UUID] = None
    area:              Optional[str] = None
    shift_start:       Optional[datetime] = None
    shift_end:         Optional[datetime] = None
    summary:           str
    items:             List[HandoverItemCreate] = Field(default=[], max_length=100)

    _area = field_validator("area", mode="before")(val.line_max(255))
    _summary = field_validator("summary", mode="before")(val.note_max(2000, required=True))

    @model_validator(mode="after")
    def _times(self):
        if self.shift_start and self.shift_end and self.shift_end <= self.shift_start:
            raise ValueError("The shift end must be after its start")
        return self

class TakeoverRequest(OrmBase):
    notes: Optional[str] = None

    _notes = field_validator("notes", mode="before")(val.note_max(1000))

class DisputeRequest(OrmBase):
    reason: str

    _reason = field_validator("reason", mode="before")(val.note_max(1000, required=True))

class VerifyRequest(OrmBase):
    notes: Optional[str] = None

    _notes = field_validator("notes", mode="before")(val.note_max(1000))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", status_code=201)
def create_handover(data: HandoverCreate, db: Session = Depends(get_db),
                    user: User = Depends(any_staff)):
    return HandoverService(db).create_handover(data.model_dump(), user)


@router.post("/{handover_id}/items", status_code=201)
def add_item(handover_id: UUID, data: HandoverItemCreate,
             db: Session = Depends(get_db),
             user: User = Depends(any_staff)):
    return HandoverService(db).add_item(handover_id, data.model_dump(), user)


@router.post("/{handover_id}/submit")
def submit_handover(handover_id: UUID, db: Session = Depends(get_db),
                    user: User = Depends(any_staff)):
    return HandoverService(db).submit_handover(handover_id, user)


@router.post("/{handover_id}/accept")
def accept_takeover(handover_id: UUID, data: TakeoverRequest,
                    db: Session = Depends(get_db),
                    user: User = Depends(any_staff)):
    return HandoverService(db).accept_takeover(handover_id, data.notes or "", user)


@router.post("/{handover_id}/dispute")
def dispute_handover(handover_id: UUID, data: DisputeRequest,
                     db: Session = Depends(get_db),
                     user: User = Depends(any_staff)):
    return HandoverService(db).dispute_handover(handover_id, data.reason, user)


@router.post("/{handover_id}/verify")
def verify_handover(handover_id: UUID, data: VerifyRequest,
                    db: Session = Depends(get_db),
                    user: User = Depends(supervisor_above)):
    return HandoverService(db).verify_handover(handover_id, data.notes or "", user)


@router.get("/{handover_id}")
def get_handover(handover_id: UUID, db: Session = Depends(get_db),
                 user: User = Depends(any_staff)):
    return HandoverService(db).get_handover(handover_id, user)


@router.get("/pending/{staff_id}")
def pending_handovers(staff_id: UUID, db: Session = Depends(get_db),
                      user: User = Depends(any_staff)):
    return HandoverService(db).get_pending_for_staff(staff_id, user)


@router.get("/society/{society_id}")
def society_handovers(society_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                      db: Session = Depends(get_db),
                      user: User = Depends(supervisor_above)):
    assert_society_access(user, society_id)
    return HandoverService(db).get_by_society(society_id, skip, limit)


@router.get("/staff/{staff_id}/history")
def staff_handover_history(staff_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=200),
                            db: Session = Depends(get_db),
                            user: User = Depends(any_staff)):
    return HandoverService(db).get_staff_history(staff_id, skip, limit, user)
