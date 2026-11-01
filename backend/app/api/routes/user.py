from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.db.session import get_db
from app.schemas.user import UserOut, UserCreatedOut, UserUpdate, AdminUserCreate, PasswordResetResponse
from app.services.user_service import UserService
from app.services.password_reset_service import PasswordResetService
from app.models.password_reset_request import PasswordResetStatus
from app.core.dependencies import require_admin
from app.models.user import User
from pydantic import BaseModel, Field
from app.services.starting_password import set_starting_password

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


@router.post("/", response_model=UserCreatedOut, status_code=201)
def create_user(
    data: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a user in the admin's society. The response carries the
    temporary password, once, for the admin to hand over."""
    sid = _society_id(current_user)
    user, temp_password = UserService(db).create(data, sid)
    return UserCreatedOut(**UserOut.from_orm_with_roles(user).model_dump(), temporary_password=temp_password)


class StartingPasswordIn(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    dry_run: bool = False


@router.post("/starting-password", response_model=dict)
def set_starting_password_for_residents(
    data: StartingPasswordIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Give residents who have never signed in the same starting password, forced to change at first sign-in. Only
    resident logins linked to an active resident, never used; admins, committee, staff and anyone who has signed in
    are not touched. `dry_run` says who would be set and changes nothing. The password is never returned."""
    if current_user.society_id is None:
        raise HTTPException(status_code=400, detail="Choose a society first")
    return set_starting_password(db, current_user.society_id, data.password, data.dry_run, current_user, request)


# ── "Forgot password?" requests (declared before /{user_id}) ──────────────────

@router.get("/password-reset-requests")
def list_password_reset_requests(
    status: str = "pending",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Members who asked for a new password from the login screen.
    `status`: pending (default), completed, dismissed, or all."""
    if status != "all" and status not in {s.value for s in PasswordResetStatus}:
        raise HTTPException(422, "status must be pending, completed, dismissed or all")
    return PasswordResetService(db).list_requests(
        _society_id(current_user), None if status == "all" else PasswordResetStatus(status))


@router.post("/password-reset-requests/{request_id}/reset", response_model=PasswordResetResponse)
def resolve_password_reset_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Reset the member's password; the temporary one is returned to give them."""
    temp_pwd = PasswordResetService(db).resolve(request_id, current_user)
    return PasswordResetResponse(temporary_password=temp_pwd)


@router.post("/password-reset-requests/{request_id}/dismiss")
def dismiss_password_reset_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return PasswordResetService(db).dismiss(request_id, current_user)


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
    PasswordResetService(db).close_pending_for_user(user_id, current_user)
    return PasswordResetResponse(temporary_password=temp_pwd)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    sid = _society_id(current_user)
    UserService(db).delete(user_id, sid)
