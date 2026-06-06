from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.schemas.wing import WingCreate, WingUpdate, WingOut
from app.services.wing_service import WingService
from app.core.dependencies import require_admin, require_committee, get_current_user

router = APIRouter(prefix="/wings", tags=["Wings"])


@router.post("/", response_model=WingOut, status_code=201,
             dependencies=[Depends(require_admin)])
def create_wing(data: WingCreate, db: Session = Depends(get_db)):
    return WingService(db).create(data)


@router.get("/", response_model=List[WingOut],
            dependencies=[Depends(get_current_user)])
def list_wings(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return WingService(db).list(skip, limit)


@router.get("/by-society/{society_id}", response_model=List[WingOut],
            dependencies=[Depends(get_current_user)])
def wings_by_society(society_id: UUID, db: Session = Depends(get_db)):
    return WingService(db).list_by_society(society_id)


@router.get("/{wing_id}", response_model=WingOut,
            dependencies=[Depends(get_current_user)])
def get_wing(wing_id: UUID, db: Session = Depends(get_db)):
    return WingService(db).get_or_404(wing_id)


@router.patch("/{wing_id}", response_model=WingOut,
              dependencies=[Depends(require_committee)])
def update_wing(wing_id: UUID, data: WingUpdate, db: Session = Depends(get_db)):
    return WingService(db).update(wing_id, data)


@router.post("/{wing_id}/activate", response_model=WingOut,
             dependencies=[Depends(require_admin)])
def activate_wing(wing_id: UUID, db: Session = Depends(get_db)):
    return WingService(db).toggle_active(wing_id, activate=True)


@router.post("/{wing_id}/deactivate", response_model=WingOut,
             dependencies=[Depends(require_admin)])
def deactivate_wing(wing_id: UUID, db: Session = Depends(get_db)):
    return WingService(db).toggle_active(wing_id, activate=False)


@router.delete("/{wing_id}", status_code=204,
               dependencies=[Depends(require_admin)])
def delete_wing(wing_id: UUID, db: Session = Depends(get_db)):
    WingService(db).delete(wing_id)
