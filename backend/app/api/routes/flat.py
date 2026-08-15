from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.schemas.flat import FlatCreate, FlatUpdate, FlatOut
from app.services.flat_service import FlatService
from app.core.dependencies import require_admin, require_committee, get_current_user
from app.models.user import User

router = APIRouter(prefix="/flats", tags=["Flats"])


@router.post("/", response_model=FlatOut, status_code=201)
def create_flat(data: FlatCreate, db: Session = Depends(get_db),
                 current_user: User = Depends(require_admin)):
    return FlatService(db).create(data, current_user)


@router.get("/", response_model=List[FlatOut])
def list_flats(skip: int = 0, limit: int = 50, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    return FlatService(db).list(current_user, skip, limit)


@router.get("/by-wing/{wing_id}", response_model=List[FlatOut])
def flats_by_wing(wing_id: UUID, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    return FlatService(db).list_by_wing(wing_id, current_user)


@router.get("/by-society/{society_id}", response_model=List[FlatOut])
def flats_by_society(society_id: UUID, db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    return FlatService(db).list_by_society(society_id, current_user)


@router.get("/{flat_id}", response_model=FlatOut)
def get_flat(flat_id: UUID, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    return FlatService(db).get_or_404(flat_id, current_user)


@router.patch("/{flat_id}", response_model=FlatOut)
def update_flat(flat_id: UUID, data: FlatUpdate, db: Session = Depends(get_db),
                 current_user: User = Depends(require_committee)):
    return FlatService(db).update(flat_id, data, current_user)


@router.delete("/{flat_id}", status_code=204)
def delete_flat(flat_id: UUID, db: Session = Depends(get_db),
                 current_user: User = Depends(require_admin)):
    FlatService(db).delete(flat_id, current_user)
