from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.schemas.society import SocietyCreate, SocietyUpdate, SocietyOut
from app.services.society_service import SocietyService
from app.core.dependencies import require_admin, require_committee, get_current_user
from app.models.user import User

router = APIRouter(prefix="/societies", tags=["Societies"])


@router.post("/", response_model=SocietyOut, status_code=201,
             dependencies=[Depends(require_admin)])
def create_society(data: SocietyCreate, db: Session = Depends(get_db)):
    return SocietyService(db).create(data)


@router.get("/", response_model=List[SocietyOut],
            dependencies=[Depends(get_current_user)])
def list_societies(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return SocietyService(db).list(skip, limit)


@router.get("/{society_id}", response_model=SocietyOut,
            dependencies=[Depends(get_current_user)])
def get_society(society_id: UUID, db: Session = Depends(get_db)):
    return SocietyService(db).get_or_404(society_id)


@router.patch("/{society_id}", response_model=SocietyOut,
              dependencies=[Depends(require_committee)])
def update_society(society_id: UUID, data: SocietyUpdate, db: Session = Depends(get_db)):
    return SocietyService(db).update(society_id, data)


@router.delete("/{society_id}", status_code=204,
               dependencies=[Depends(require_admin)])
def delete_society(society_id: UUID, db: Session = Depends(get_db)):
    SocietyService(db).delete(society_id)
