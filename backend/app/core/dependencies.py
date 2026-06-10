from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User

bearer_scheme = HTTPBearer()


def _find_user_by_id(db: Session, user_id: str) -> "User | None":
    """Robust user lookup that handles both UUID objects and strings (SQLite compat)."""
    import uuid as _uuid
    # Try as proper UUID first
    try:
        uid = _uuid.UUID(str(user_id))
        try:
            user = db.query(User).filter(User.id == uid, User.is_active == True).first()
            if user:
                return user
        except Exception:
            pass
    except ValueError:
        pass

    # Fallback: string comparison
    try:
        return db.query(User).filter(
            User.id == str(user_id), User.is_active == True
        ).first()
    except Exception:
        return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    user    = _find_user_by_id(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def require_roles(*role_names: str):
    def _checker(current_user: User = Depends(get_current_user)) -> User:
        user_roles = {ur.role.name for ur in current_user.user_roles if ur.role}
        if not user_roles.intersection(set(role_names)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access requires one of roles: {', '.join(role_names)}",
            )
        return current_user
    return _checker


# ── Canonical role sets (match EXTENDED_DEFAULT_ROLES in onboarding_service.py) ──
_ROLES_PLATFORM  = ("Platform Admin",)
_ROLES_SOCIETY   = ("Society Admin",)
_ROLES_COMMITTEE = (
    "Committee Chairman", "Committee Secretary",
    "Committee Treasurer", "Committee Member",
)
_ROLES_MANAGER     = ("Manager",)
_ROLES_SUPERVISORS = (
    "Security Supervisor", "Housekeeping Supervisor", "Technical Supervisor",
)
_ROLES_STAFF = (
    "Security Staff", "Housekeeping Staff", "Technical Staff", "Gym Trainer",
)
_ROLES_RESIDENTS = ("Resident", "Tenant")

# ── Hierarchy guards (use these in all route files instead of local aliases) ──

# Full society-level admin or platform admin
require_admin = require_roles(*_ROLES_PLATFORM, *_ROLES_SOCIETY)

# Admin + all committee roles (for management actions)
require_admin_committee = require_roles(
    *_ROLES_PLATFORM, *_ROLES_SOCIETY, *_ROLES_COMMITTEE,
)

# Manager and above (admin, committee, manager)
require_manager_above = require_roles(
    *_ROLES_PLATFORM, *_ROLES_SOCIETY, *_ROLES_COMMITTEE, *_ROLES_MANAGER,
)

# Supervisor and above
require_supervisor_above = require_roles(
    *_ROLES_PLATFORM, *_ROLES_SOCIETY, *_ROLES_COMMITTEE,
    *_ROLES_MANAGER, *_ROLES_SUPERVISORS,
)

# Any staff member or above (supervisor+, manager+, admin+)
require_any_staff = require_roles(
    *_ROLES_PLATFORM, *_ROLES_SOCIETY, *_ROLES_COMMITTEE,
    *_ROLES_MANAGER, *_ROLES_SUPERVISORS, *_ROLES_STAFF,
)

# Security-related roles and above
require_security = require_roles(
    *_ROLES_PLATFORM, *_ROLES_SOCIETY, *_ROLES_COMMITTEE,
    *_ROLES_MANAGER, "Security Supervisor", "Security Staff",
)

# Any authenticated member (everyone)
require_any_member = require_roles(
    *_ROLES_PLATFORM, *_ROLES_SOCIETY, *_ROLES_COMMITTEE,
    *_ROLES_MANAGER, *_ROLES_SUPERVISORS, *_ROLES_STAFF, *_ROLES_RESIDENTS,
)

# Backwards-compatible aliases (used by existing route imports)
require_committee = require_admin_committee
require_resident  = require_any_member
require_staff     = require_any_staff


def require_platform_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform Admin access required",
        )
    return current_user
