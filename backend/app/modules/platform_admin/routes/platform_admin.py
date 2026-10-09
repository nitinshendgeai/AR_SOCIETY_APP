from typing import Optional
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
    LimitsRequest,
)
from app.modules.platform_admin.services.platform_admin_service import PlatformAdminService

router = APIRouter(prefix="/platform-admin", tags=["Platform Admin"])


@router.get("/societies")
def list_societies(
    skip:  int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q:     Optional[str] = Query(None, description="Name, code, city or contact email"),
    status: Optional[str] = Query(None, description="TRIAL, ACTIVE, EXPIRED, SUSPENDED or CANCELLED"),
    db:    Session = Depends(get_db),
    admin: User    = Depends(require_platform_admin),
):
    """List societies with their trial/subscription state, usage and contact."""
    return PlatformAdminService(db).list_societies(skip=skip, limit=limit, q=q, status=status)


@router.get("/societies/{society_id}")
def society_detail(
    society_id: UUID,
    db:    Session = Depends(get_db),
    admin: User    = Depends(require_platform_admin),
):
    """One society: profile, subscription, usage against limits, its admins and what the platform has done to it."""
    return PlatformAdminService(db).society_detail(str(society_id))


@router.get("/activity")
def activity(
    limit: int = Query(50, ge=1, le=200),
    db:    Session = Depends(get_db),
    admin: User    = Depends(require_platform_admin),
):
    """Recent actions by platform admins across all societies."""
    return PlatformAdminService(db).activity(limit=limit)


@router.put("/societies/{society_id}/limits")
def set_limits(
    society_id: UUID,
    data:       LimitsRequest,
    db:         Session = Depends(get_db),
    admin:      User    = Depends(require_platform_admin),
):
    """Set how many users, flats and MB of storage the society may use. Not below what it already has."""
    return PlatformAdminService(db).set_limits(str(society_id), data.allowed_users, data.allowed_flats,
                                               data.allowed_storage_mb, admin)


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
    return PlatformAdminService(db).activate_society(str(society_id), data.plan, admin, data.expires_on)
