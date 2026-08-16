from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.db.session import get_db
from app.models.resident import ResidentType
from app.schemas.resident import ResidentCreate, ResidentUpdate, ResidentOut, ResidentCreateOut
from app.services.resident_service import ResidentService
from app.core.dependencies import require_admin_committee, get_current_user
from app.models.user import User

router = APIRouter(prefix="/residents", tags=["Residents"])


@router.post("/", response_model=ResidentCreateOut, status_code=201)
def create_resident(data: ResidentCreate, db: Session = Depends(get_db),
                     current_user: User = Depends(require_admin_committee)):
    return ResidentService(db).create(data, current_user)


@router.get("/", response_model=List[ResidentOut])
def list_residents(
    flat_id: Optional[UUID] = None,
    resident_type: Optional[ResidentType] = None,
    is_active: Optional[bool] = True,
    search: Optional[str] = Query(None, description="Matches name, phone, or email"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ResidentService(db).list(
        current_user, flat_id=flat_id, resident_type=resident_type,
        is_active=is_active, search=search, skip=skip, limit=limit,
    )


@router.get("/{resident_id}", response_model=ResidentOut)
def get_resident(resident_id: UUID, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    return ResidentService(db).get_or_404(resident_id, current_user)


@router.patch("/{resident_id}", response_model=ResidentOut)
def update_resident(resident_id: UUID, data: ResidentUpdate, db: Session = Depends(get_db),
                     current_user: User = Depends(require_admin_committee)):
    return ResidentService(db).update(resident_id, data, current_user)
