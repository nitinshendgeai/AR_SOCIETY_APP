from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.schemas.user import UserOut, UserUpdate, AdminUserCreate, PasswordResetResponse
from app.services.user_service import UserService
from app.core.dependencies import require_admin
from app.models.user import User
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["Users"])


class AssignRoleRequest(BaseModel):
    role_name: str


def _society_id(current_user: User):
    """Return the caller's society scope when present; allow global admin users to operate without one."""
    return current_user.society_id


@router.get("/admin/dashboard")
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Simple admin dashboard payload used by the RBAC tests."""
    return {
        "user_id": str(current_user.id),
        "email": current_user.email,
        "role_count": len(current_user.user_roles),
    }


@router.get("/", response_model=List[UserOut])
def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    sid = _society_id(current_user)
    return [UserOut.from_orm_with_roles(u) for u in UserService(db).list(sid, skip, limit)]


@router.post("/", response_model=UserOut, status_code=201)
def create_user(
    data: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    sid = _society_id(current_user)
    user, _ = UserService(db).create(data, sid)
    return UserOut.from_orm_with_roles(user)


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    sid = _society_id(current_user)
    return UserOut.from_orm_with_roles(UserService(db).get_or_404(user_id, sid))


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: UUID,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    sid = _society_id(current_user)
    return UserOut.from_orm_with_roles(UserService(db).update(user_id, data, sid))


@router.post("/{user_id}/roles", response_model=UserOut)
def assign_role(
    user_id: UUID,
    body: AssignRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    sid = _society_id(current_user)
    user = UserService(db).assign_role(user_id, body.role_name, sid)
    return UserOut.from_orm_with_roles(user)


@router.delete("/{user_id}/roles/{role_name}", response_model=UserOut)
def remove_role(
    user_id: UUID,
    role_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    sid = _society_id(current_user)
    user = UserService(db).remove_role(user_id, role_name, sid)
    return UserOut.from_orm_with_roles(user)


@router.post("/{user_id}/reset-password", response_model=PasswordResetResponse)
def reset_password(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    sid = _society_id(current_user)
    _, temp_pwd = UserService(db).reset_password(user_id, sid)
    return PasswordResetResponse(temporary_password=temp_pwd)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    sid = _society_id(current_user)
    UserService(db).delete(user_id, sid)
