import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.schemas.society import SocietyCreate, SocietyUpdate, SocietyOut
from app.services.society_service import SocietyService
from app.services.society_setup_service import SocietySetupService
from app.core.dependencies import require_admin, require_committee, get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/societies", tags=["Societies"])


@router.post("/", response_model=SocietyOut, status_code=201)
def create_society(data: SocietyCreate, request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(require_admin)):
    society = SocietyService(db).create(data)
    return society


@router.post("/{society_id}/initialize")
def initialize_society(society_id: UUID,
                        db: Session = Depends(get_db),
                        user: User = Depends(require_admin)):
    """Initialize a society — creates default roles and operational users."""
    society = SocietyService(db).get_or_404(society_id)
    return SocietySetupService(db).initialize_society(society, user)


@router.post("/register-and-initialize", status_code=201)
def register_and_initialize(data: SocietyCreate, request: Request,
                              db: Session = Depends(get_db),
                              user: User = Depends(require_admin)):
    """One-shot: register society + auto-initialize roles and default users."""
    society = SocietyService(db).create(data)
    result  = SocietySetupService(db).initialize_society(society, user)
    result["society"] = {
        "id":           str(society.id),
        "name":         society.name,
        "society_code": society.society_code,
    }
    return result


@router.get("/", response_model=List[SocietyOut])
def list_societies(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return societies visible to the caller.
    - Platform admins (no society_id): all societies.
    - Everyone else: only their own society.
    """
    logger.info(
        "[GET /societies/] user=%s society_id=%s",
        current_user.id, current_user.society_id,
    )
    try:
        if current_user.society_id:
            society = SocietyService(db).get_or_404(current_user.society_id)
            logger.info(
                "[GET /societies/] returning society=%s trial_start=%s trial_end=%s",
                society.id, society.trial_start_date, society.trial_end_date,
            )
            return [society]
        else:
            societies = SocietyService(db).list(skip, limit)
            logger.info("[GET /societies/] platform admin — returning %d societies", len(societies))
            return societies
    except Exception as exc:
        logger.exception("[GET /societies/] UNEXPECTED ERROR: %s", exc)
        raise


@router.get("/{society_id}", response_model=SocietyOut)
def get_society(
    society_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch a single society. Non-platform users may only fetch their own."""
    logger.info("[GET /societies/%s] user=%s", society_id, current_user.id)
    if current_user.society_id and current_user.society_id != society_id:
        raise HTTPException(status_code=403, detail="Access denied to this society")
    return SocietyService(db).get_or_404(society_id)


@router.patch("/{society_id}", response_model=SocietyOut,
              dependencies=[Depends(require_committee)])
def update_society(society_id: UUID, data: SocietyUpdate, db: Session = Depends(get_db)):
    return SocietyService(db).update(society_id, data)


@router.delete("/{society_id}", status_code=204,
               dependencies=[Depends(require_admin)])
def delete_society(society_id: UUID, db: Session = Depends(get_db)):
    SocietyService(db).delete(society_id)
