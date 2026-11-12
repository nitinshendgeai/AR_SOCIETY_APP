from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_any_staff, require_manager_above
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


class AreaItemIn(BaseModel):
    kind: str = Field(pattern="^(tube|spot|drum|halogen|camera)$")
    count: int = Field(ge=1, le=100)


class AreaIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    wing_id: Optional[UUID] = None             # a Lobby in every wing is one area per wing
    items: List[AreaItemIn]


class AreaCheckIn(BaseModel):
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


# ── Common areas: the Manager or Admin sets them up, the staff check them ────

@router.get("/{society_id}/areas")
def areas(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LightService(db).list_areas(society_id, user)


@router.post("/{society_id}/areas", status_code=201, dependencies=[Depends(require_manager_above)])
def create_area(society_id: UUID, data: AreaIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LightService(db).create_area(society_id, data.name, data.wing_id, [i.model_dump() for i in data.items], user)


@router.put("/area/{area_id}", dependencies=[Depends(require_manager_above)])
def update_area(area_id: UUID, data: AreaIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LightService(db).update_area(area_id, data.name, data.wing_id, [i.model_dump() for i in data.items], user)


@router.delete("/area/{area_id}", status_code=204, dependencies=[Depends(require_manager_above)])
def delete_area(area_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    LightService(db).delete_area(area_id, user)


@router.get("/area/{area_id}/sheet")
def area_sheet(area_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LightService(db).area_sheet(area_id, user)


@router.post("/area/{area_id}/check", status_code=201)
def check_area(area_id: UUID, data: AreaCheckIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LightService(db).record_area(area_id, [r.model_dump() for r in data.results], user)


@router.post("/point/{point_id}/replace")
def replace(point_id: UUID, data: ReplaceIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LightService(db).replace(point_id, data.item_id, data.quantity, data.note, user)
