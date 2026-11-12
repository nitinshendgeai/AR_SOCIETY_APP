from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_any_staff
from app.db.session import get_db
from app.models.user import User
from app.modules.lights.services.lights_service import LightService

# Electricians and plumbers (technical staff), supervisors, the manager and the committee.
router = APIRouter(prefix="/light-checks", tags=["Light checks"], dependencies=[Depends(require_any_staff)])


class ResultIn(BaseModel):
    location: str
    flat_id: Optional[UUID] = None
    status: str = Field(pattern="^(working|not_working)$")
    note: Optional[str] = Field(default=None, max_length=500)


class CheckIn(BaseModel):
    wing_id: UUID
    floor_number: int = Field(ge=-5, le=200)
    kind: str = Field(pattern="^(tube|spot|camera)$")
    results: List[ResultIn]


class ReplaceIn(BaseModel):
    item_id: Optional[UUID] = None             # the tube or bulb taken from the store; a camera put right needs none
    quantity: float = Field(default=1, gt=0, le=100)
    note: Optional[str] = Field(default=None, max_length=500)


@router.get("/{society_id}/floors")
def floors(society_id: UUID, wing_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LightService(db).floors(society_id, wing_id, user)


@router.get("/{society_id}/sheet")
def sheet(society_id: UUID, wing_id: UUID, floor_number: int, kind: str = Query(..., pattern="^(tube|spot|camera)$"),
          db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LightService(db).sheet(society_id, wing_id, floor_number, kind, user)


@router.post("/{society_id}/check", status_code=201)
def check(society_id: UUID, data: CheckIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LightService(db).record(society_id, data.wing_id, data.floor_number, data.kind,
                                   [r.model_dump() for r in data.results], user)


@router.get("/{society_id}/not-working")
def not_working(society_id: UUID, wing_id: Optional[UUID] = None, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    return LightService(db).not_working(society_id, wing_id, user)


@router.get("/{society_id}/summary")
def summary(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LightService(db).summary(society_id, user)


@router.get("/{society_id}/report")
def report(society_id: UUID, month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
           wing_id: Optional[UUID] = None, floor_number: Optional[int] = Query(None, ge=-5, le=200),
           flat_id: Optional[UUID] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LightService(db).report(society_id, month, user, wing_id, floor_number, flat_id)


@router.post("/point/{point_id}/replace")
def replace(point_id: UUID, data: ReplaceIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LightService(db).replace(point_id, data.item_id, data.quantity, data.note, user)
