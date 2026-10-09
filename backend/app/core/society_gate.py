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


def path_is_allowed(path: str) -> bool:
    return path.rstrip("/").endswith(ALLOWED_SUFFIXES)
