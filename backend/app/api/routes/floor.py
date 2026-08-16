from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.schemas.floor import FloorCreate, FloorUpdate, FloorOut
from app.services.floor_service import FloorService
from app.core.dependencies import require_admin, require_committee, get_current_user
from app.models.user import User

router = APIRouter(prefix="/floors", tags=["Floors"])


@router.post("/", response_model=FloorOut, status_code=201)
def create_floor(data: FloorCreate, db: Session = Depends(get_db),
                  current_user: User = Depends(require_admin)):
    return FloorService(db).create(data, current_user)


@router.get("/by-wing/{wing_id}", response_model=List[FloorOut])
def floors_by_wing(wing_id: UUID, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    return FloorService(db).list_by_wing(wing_id, current_user)


@router.get("/by-society/{society_id}", response_model=List[FloorOut])
def floors_by_society(society_id: UUID, db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    return FloorService(db).list_by_society(society_id, current_user)


@router.get("/{floor_id}", response_model=FloorOut)
def get_floor(floor_id: UUID, db: Session = Depends(get_db),
              current_user: User = Depends(get_current_user)):
    return FloorService(db).get_or_404(floor_id, current_user)


@router.patch("/{floor_id}", response_model=FloorOut)
def update_floor(floor_id: UUID, data: FloorUpdate, db: Session = Depends(get_db),
                  current_user: User = Depends(require_committee)):
    return FloorService(db).update(floor_id, data, current_user)


@router.delete("/{floor_id}", status_code=204)
def delete_floor(floor_id: UUID, db: Session = Depends(get_db),
                  current_user: User = Depends(require_admin)):
    FloorService(db).delete(floor_id, current_user)
