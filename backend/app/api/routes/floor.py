from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.schemas.floor import FloorCreate, FloorUpdate, FloorOut
from app.services.floor_service import FloorService
from app.core.dependencies import require_admin, require_committee, get_current_user

router = APIRouter(prefix="/floors", tags=["Floors"])


@router.post("/", response_model=FloorOut, status_code=201,
             dependencies=[Depends(require_admin)])
def create_floor(data: FloorCreate, db: Session = Depends(get_db)):
    return FloorService(db).create(data)


@router.get("/by-wing/{wing_id}", response_model=List[FloorOut],
            dependencies=[Depends(get_current_user)])
def floors_by_wing(wing_id: UUID, db: Session = Depends(get_db)):
    return FloorService(db).list_by_wing(wing_id)


@router.get("/by-society/{society_id}", response_model=List[FloorOut],
            dependencies=[Depends(get_current_user)])
def floors_by_society(society_id: UUID, db: Session = Depends(get_db)):
    return FloorService(db).list_by_society(society_id)


@router.get("/{floor_id}", response_model=FloorOut,
            dependencies=[Depends(get_current_user)])
def get_floor(floor_id: UUID, db: Session = Depends(get_db)):
    return FloorService(db).get_or_404(floor_id)


@router.patch("/{floor_id}", response_model=FloorOut,
              dependencies=[Depends(require_committee)])
def update_floor(floor_id: UUID, data: FloorUpdate, db: Session = Depends(get_db)):
    return FloorService(db).update(floor_id, data)


@router.delete("/{floor_id}", status_code=204,
               dependencies=[Depends(require_admin)])
def delete_floor(floor_id: UUID, db: Session = Depends(get_db)):
    FloorService(db).delete(floor_id)
