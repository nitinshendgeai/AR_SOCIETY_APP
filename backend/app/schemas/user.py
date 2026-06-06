from pydantic import EmailStr, field_validator
from typing import List, Optional
from app.schemas.common import OrmBase, TimestampSchema
from app.models.user import UserStatus


class RoleOut(OrmBase):
    id:   object
    name: str


class UserCreate(OrmBase):
    email:     EmailStr
    phone:     Optional[str] = None
    full_name: str
    password:  str


class AdminUserCreate(OrmBase):
    """Used by admin to create a user and optionally assign a role immediately."""
    email:                EmailStr
    full_name:            str
    phone:                Optional[str] = None
    role_name:            Optional[str] = None
    must_change_password: bool = True

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower().strip()


class UserUpdate(OrmBase):
    full_name:     Optional[str] = None
    phone:         Optional[str] = None
    profile_image: Optional[str] = None
    status:        Optional[UserStatus] = None


class PasswordResetResponse(OrmBase):
    temporary_password: str
    message:            str = "Password has been reset. User must change it on next login."


class UserOut(TimestampSchema):
    email:                str
    phone:                Optional[str]
    full_name:            str
    status:               UserStatus
    is_superadmin:        bool
    must_change_password: bool = False
    terms_accepted:       bool = False
    setup_completed:      bool = False
    roles:                List[str] = []

    @classmethod
    def from_orm_with_roles(cls, user) -> "UserOut":
        roles = [ur.role.name for ur in user.user_roles if ur.role]
        data  = cls.model_validate(user)
        data.roles = roles
        return data
