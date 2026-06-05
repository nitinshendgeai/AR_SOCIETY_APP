from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import require_platform_admin
from app.models.user import User
from app.modules.platform_admin.schemas.platform_admin import (
    ExtendTrialRequest,
    SuspendSocietyRequest,
    ActivateSocietyRequest,
)
from app.modules.platform_admin.services.platform_admin_service import PlatformAdminService

router = APIRouter(prefix="/platform-admin", tags=["Platform Admin"])


@router.get("/societies")
def list_societies(
    skip:  int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db:    Session = Depends(get_db),
    admin: User    = Depends(require_platform_admin),
):
    """List all societies with trial/subscription summary."""
    return PlatformAdminService(db).list_societies(skip=skip, limit=limit)


@router.get("/stats")
def get_platform_stats(
    db:    Session = Depends(get_db),
    admin: User    = Depends(require_platform_admin),
):
    """Platform-wide stats: counts by account status."""
    return PlatformAdminService(db).get_stats()


@router.post("/societies/{society_id}/extend-trial")
def extend_trial(
    society_id: UUID,
    data:       ExtendTrialRequest,
    db:         Session = Depends(get_db),
    admin:      User    = Depends(require_platform_admin),
):
    """Extend trial period for a society (TRIAL or EXPIRED only)."""
    return PlatformAdminService(db).extend_trial(str(society_id), data.extend_days, admin)


@router.post("/societies/{society_id}/suspend")
def suspend_society(
    society_id: UUID,
    data:       SuspendSocietyRequest,
    db:         Session = Depends(get_db),
    admin:      User    = Depends(require_platform_admin),
):
    """Suspend a society account."""
    return PlatformAdminService(db).suspend_society(str(society_id), data.reason, admin)


@router.post("/societies/{society_id}/activate")
def activate_society(
    society_id: UUID,
    data:       ActivateSocietyRequest,
    db:         Session = Depends(get_db),
    admin:      User    = Depends(require_platform_admin),
):
    """Activate a society on a paid subscription plan."""
    return PlatformAdminService(db).activate_society(str(society_id), data.plan, admin)
