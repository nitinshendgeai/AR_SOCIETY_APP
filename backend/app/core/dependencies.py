from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.models.role import Role

bearer_scheme = HTTPBearer()


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
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()

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
    """Factory that returns a dependency requiring at least one of the given roles."""
    def _checker(current_user: User = Depends(get_current_user)) -> User:
        user_roles = {ur.role.name for ur in current_user.user_roles if ur.role}
        if not user_roles.intersection(set(role_names)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access requires one of roles: {', '.join(role_names)}",
            )
        return current_user
    return _checker


# Convenience role guards
require_admin      = require_roles("Admin")
require_committee  = require_roles("Admin", "Committee")
require_resident   = require_roles("Admin", "Committee", "Resident")
require_security   = require_roles("Admin", "Security")
require_staff      = require_roles("Admin", "Staff")
