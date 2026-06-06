from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.schemas.user import UserOut, UserUpdate, AdminUserCreate, PasswordResetResponse
from app.services.user_service import UserService
from app.core.dependencies import require_admin, get_current_user
from app.models.user import User
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["Users"])


class AssignRoleRequest(BaseModel):
    role_name: str


@router.get("/", response_model=List[UserOut],
            dependencies=[Depends(require_admin)])
def list_users(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return [UserOut.from_orm_with_roles(u) for u in UserService(db).list(skip, limit)]


@router.post("/", response_model=UserOut, status_code=201,
             dependencies=[Depends(require_admin)])
def create_user(data: AdminUserCreate, db: Session = Depends(get_db)):
    user, _ = UserService(db).create(data)
    return UserOut.from_orm_with_roles(user)


@router.get("/{user_id}", response_model=UserOut,
            dependencies=[Depends(require_admin)])
def get_user(user_id: UUID, db: Session = Depends(get_db)):
    return UserOut.from_orm_with_roles(UserService(db).get_or_404(user_id))


@router.patch("/{user_id}", response_model=UserOut,
              dependencies=[Depends(require_admin)])
def update_user(user_id: UUID, data: UserUpdate, db: Session = Depends(get_db)):
    return UserOut.from_orm_with_roles(UserService(db).update(user_id, data))


@router.post("/{user_id}/roles", response_model=UserOut,
             dependencies=[Depends(require_admin)])
def assign_role(user_id: UUID, body: AssignRoleRequest, db: Session = Depends(get_db)):
    user = UserService(db).assign_role(user_id, body.role_name)
    return UserOut.from_orm_with_roles(user)


@router.delete("/{user_id}/roles/{role_name}", response_model=UserOut,
               dependencies=[Depends(require_admin)])
def remove_role(user_id: UUID, role_name: str, db: Session = Depends(get_db)):
    user = UserService(db).remove_role(user_id, role_name)
    return UserOut.from_orm_with_roles(user)


@router.post("/{user_id}/reset-password", response_model=PasswordResetResponse,
             dependencies=[Depends(require_admin)])
def reset_password(user_id: UUID, db: Session = Depends(get_db)):
    _, temp_pwd = UserService(db).reset_password(user_id)
    return PasswordResetResponse(temporary_password=temp_pwd)


@router.delete("/{user_id}", status_code=204,
               dependencies=[Depends(require_admin)])
def delete_user(user_id: UUID, db: Session = Depends(get_db)):
    UserService(db).delete(user_id)
