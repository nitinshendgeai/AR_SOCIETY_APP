"""Keeps a suspended society out.

A platform admin can suspend a society (non-payment, misuse, a request to pause). From then on nobody who belongs to it
can sign in, refresh a session, or use the API, apart from the calls that let the app learn why and sign out. Platform
admins (who belong to no society) are never blocked. Trials that have run out are *not* blocked here: they stay
usable and are only flagged, until it is decided how a lapsed trial should behave.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.society import AccountStatus, Society

SUSPENDED_MESSAGE = "Your society's account is suspended. Please contact support."
CANCELLED_MESSAGE = "Your society's account has been closed. Please contact support."

# Calls a blocked user may still make, so the app can show who they are and sign out.
ALLOWED_SUFFIXES = ("/auth/me", "/auth/logout")


def society_block_reason(db: Session, user) -> Optional[str]:
    """Why this user's society is shut, or None if they may carry on."""
    society_id = getattr(user, "society_id", None)
    if society_id is None or getattr(user, "is_superadmin", False):
        return None
    status = db.query(Society.account_status).filter(Society.id == society_id).scalar()
    if status == AccountStatus.SUSPENDED:
        return SUSPENDED_MESSAGE
    if status == AccountStatus.CANCELLED:
        return CANCELLED_MESSAGE
    return None


def service_block_reason(db: Session, user, path: str) -> Optional[str]:
    """Why this call is refused because the platform owner has switched the service off for the user's society, or
    None. Core calls, platform admins and users who belong to no society are never refused."""
    from app.core.services_catalog import effective_services, service_for_path
    society_id = getattr(user, "society_id", None)
    if society_id is None or getattr(user, "is_superadmin", False):
        return None
    service = service_for_path(path)
    if service is None:
        return None
    if service.key in effective_services(db, society_id):
        return None
    return f"{service.label} is not enabled for your society. Please contact support."


def path_is_allowed(path: str) -> bool:
    return path.rstrip("/").endswith(ALLOWED_SUFFIXES)


# A login that belongs to no society and is not a platform admin (for example one made through the public
# POST /auth/register) has no society's data to see. The code treats "no society" as "platform admin, no tenant
# filter", so such a login must never reach it: it may only manage its own sign-in.
NO_SOCIETY_MESSAGE = "Your account is not linked to a society yet. Please contact your society office."
_OWN_ACCOUNT_PREFIXES = ("/auth/me", "/auth/logout", "/auth/change-password", "/auth/accept-terms",
                         "/auth/sessions")


RESIDENT_LEVEL_ROLES = frozenset({"Resident", "Tenant"})


def no_society_block_reason(user, path: str) -> Optional[str]:
    """Why this call is refused because the login belongs to no society, or None. Platform admins (is_superadmin),
    logins of a society and logins that hold any role above resident level are never refused here: a resident or
    tenant must belong to a society, so one that doesn't (the public registration's result) has no business with
    society data."""
    if getattr(user, "society_id", None) is not None or getattr(user, "is_superadmin", False):
        return None
    role_names = {ur.role.name for ur in (getattr(user, "user_roles", None) or []) if ur.role}
    if role_names - RESIDENT_LEVEL_ROLES:
        return None
    tail = path.split("/api/v1", 1)[-1].rstrip("/")
    if tail.startswith(_OWN_ACCOUNT_PREFIXES):
        return None
    return NO_SOCIETY_MESSAGE
