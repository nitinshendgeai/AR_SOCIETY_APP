from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.schemas.flat import FlatCreate, FlatUpdate, FlatOut
from app.services.flat_service import FlatService
from app.core.dependencies import require_admin, require_committee, get_current_user

router = APIRouter(prefix="/flats", tags=["Flats"])


@router.post("/", response_model=FlatOut, status_code=201,
             dependencies=[Depends(require_admin)])
def create_flat(data: FlatCreate, db: Session = Depends(get_db)):
    return FlatService(db).create(data)


@router.get("/", response_model=List[FlatOut],
            dependencies=[Depends(get_current_user)])
def list_flats(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return FlatService(db).list(skip, limit)


@router.get("/by-wing/{wing_id}", response_model=List[FlatOut],
            dependencies=[Depends(get_current_user)])
def flats_by_wing(wing_id: UUID, db: Session = Depends(get_db)):
    return FlatService(db).list_by_wing(wing_id)


@router.get("/by-society/{society_id}", response_model=List[FlatOut],
            dependencies=[Depends(get_current_user)])
def flats_by_society(society_id: UUID, db: Session = Depends(get_db)):
    return FlatService(db).list_by_society(society_id)


@router.get("/{flat_id}", response_model=FlatOut,
            dependencies=[Depends(get_current_user)])
def get_flat(flat_id: UUID, db: Session = Depends(get_db)):
    return FlatService(db).get_or_404(flat_id)


@router.patch("/{flat_id}", response_model=FlatOut,
              dependencies=[Depends(require_committee)])
def update_flat(flat_id: UUID, data: FlatUpdate, db: Session = Depends(get_db)):
    return FlatService(db).update(flat_id, data)


@router.delete("/{flat_id}", status_code=204,
               dependencies=[Depends(require_admin)])
def delete_flat(flat_id: UUID, db: Session = Depends(get_db)):
    FlatService(db).delete(flat_id)
