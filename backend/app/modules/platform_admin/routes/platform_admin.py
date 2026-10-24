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
    ServiceSwitchRequest,
    CleanDataRequest,
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


# ── Services ──────────────────────────────────────────────────────────────────

@router.get("/societies/{society_id}/services")
def society_services(society_id: UUID, db: Session = Depends(get_db), admin: User = Depends(require_platform_admin)):
    """Every optional service and whether it is on for this society."""
    return PlatformAdminService(db).society_services(str(society_id))


@router.put("/societies/{society_id}/services/{service_key}")
def switch_service(society_id: UUID, service_key: str, data: ServiceSwitchRequest, db: Session = Depends(get_db),
                   admin: User = Depends(require_platform_admin)):
    """Switch one service on or off for this society. Off closes its API calls and hides its menu items."""
    return PlatformAdminService(db).set_service(str(society_id), service_key, data.enabled, admin)


# ── Clean data ────────────────────────────────────────────────────────────────

@router.get("/societies/{society_id}/clean-data")
def clean_data_preview(society_id: UUID, db: Session = Depends(get_db), admin: User = Depends(require_platform_admin)):
    """What "Clean data" would delete for this society: rows per table. Deletes nothing."""
    return PlatformAdminService(db).clean_data_preview(str(society_id))


@router.post("/societies/{society_id}/clean-data")
def clean_data(society_id: UUID, data: CleanDataRequest, db: Session = Depends(get_db),
               admin: User = Depends(require_platform_admin)):
    """Permanently delete all of the society's data (rows only; the society itself, other societies and platform
    admins are kept). `confirm` must be the society's code, typed in full."""
    return PlatformAdminService(db).clean_data(str(society_id), data.confirm, admin)


@router.post("/societies/{society_id}/restore-logins")
def restore_default_logins(society_id: UUID, db: Session = Depends(get_db), admin: User = Depends(require_platform_admin)):
    """Recreate the society's missing default logins (admin, chairman, secretary, treasurer) with the standard
    first-login password, which must be changed at first sign-in. Existing logins are not touched."""
    return PlatformAdminService(db).restore_default_logins(str(society_id), admin)
