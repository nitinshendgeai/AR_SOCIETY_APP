from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.schemas.wing import WingCreate, WingUpdate, WingOut
from app.services.wing_service import WingService
from app.core.dependencies import require_admin, require_committee, get_current_user
from app.models.user import User

router = APIRouter(prefix="/wings", tags=["Wings"])


@router.post("/", response_model=WingOut, status_code=201)
def create_wing(data: WingCreate, db: Session = Depends(get_db),
                 current_user: User = Depends(require_admin)):
    return WingService(db).create(data, current_user)


@router.get("/", response_model=List[WingOut])
def list_wings(skip: int = 0, limit: int = 50, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    return WingService(db).list(current_user, skip, limit)


@router.get("/by-society/{society_id}", response_model=List[WingOut])
def wings_by_society(society_id: UUID, db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    return WingService(db).list_by_society(society_id, current_user)


@router.get("/{wing_id}", response_model=WingOut)
def get_wing(wing_id: UUID, db: Session = Depends(get_db),
              current_user: User = Depends(get_current_user)):
    return WingService(db).get_or_404(wing_id, current_user)


@router.patch("/{wing_id}", response_model=WingOut)
def update_wing(wing_id: UUID, data: WingUpdate, db: Session = Depends(get_db),
                 current_user: User = Depends(require_committee)):
    return WingService(db).update(wing_id, data, current_user)


@router.post("/{wing_id}/activate", response_model=WingOut)
def activate_wing(wing_id: UUID, db: Session = Depends(get_db),
                   current_user: User = Depends(require_admin)):
    return WingService(db).toggle_active(wing_id, activate=True, current_user=current_user)


@router.post("/{wing_id}/deactivate", response_model=WingOut)
def deactivate_wing(wing_id: UUID, db: Session = Depends(get_db),
                     current_user: User = Depends(require_admin)):
    return WingService(db).toggle_active(wing_id, activate=False, current_user=current_user)


@router.delete("/{wing_id}", status_code=204)
def delete_wing(wing_id: UUID, db: Session = Depends(get_db),
                 current_user: User = Depends(require_admin)):
    WingService(db).delete(wing_id, current_user)
