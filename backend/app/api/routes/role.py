from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.models.role import Role
from app.models.user import User, UserRole
from app.core.dependencies import get_current_user
from pydantic import BaseModel


class RoleListItem(BaseModel):
    id:          str
    name:        str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get("/", response_model=List[RoleListItem])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return roles that are in use within the caller's society.
    Superadmins / users without a society get all platform roles.
    """
    if not current_user.society_id:
        # Platform admin — show all
        roles = db.query(Role).order_by(Role.name).all()
    else:
        # Return distinct roles assigned to users in this society
        roles = (
            db.query(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .join(User, User.id == UserRole.user_id)
            .filter(User.society_id == current_user.society_id, User.is_active == True)
            .distinct()
            .order_by(Role.name)
            .all()
        )
        # If the society has no users yet, fall back to all platform roles
        if not roles:
            roles = db.query(Role).order_by(Role.name).all()

    return [RoleListItem(id=str(r.id), name=r.name, description=r.description)
            for r in roles]
