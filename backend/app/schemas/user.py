from pydantic import EmailStr, Field, field_validator
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from app.schemas.common import OrmBase, TimestampSchema
from app.schemas.validators import name as _clean_name, phone as _clean_phone, text as _clean_text
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
    full_name:            str = Field(max_length=255)
    phone:                Optional[str] = None
    role_name:            Optional[str] = Field(default=None, max_length=50)
    must_change_password: bool = True

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower().strip()

    _name = field_validator("full_name", mode="before")(_clean_name)
    _phone = field_validator("phone", mode="before")(_clean_phone)
    _role = field_validator("role_name", mode="before")(_clean_text)


class UserUpdate(OrmBase):
    full_name:     Optional[str] = Field(default=None, max_length=255)
    phone:         Optional[str] = None
    profile_image: Optional[str] = None
    status:        Optional[UserStatus] = None

    _name = field_validator("full_name", mode="before")(_clean_name)
    _phone = field_validator("phone", mode="before")(_clean_phone)


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
    society_id:           Optional[UUID] = None
    last_login:           Optional[datetime] = None
    roles:                List[str] = []

    @classmethod
    def from_orm_with_roles(cls, user) -> "UserOut":
        roles = [ur.role.name for ur in user.user_roles if ur.role]
        data  = cls.model_validate(user)
        data.roles = roles
        data.society_id = user.society_id
        return data


class UserCreatedOut(UserOut):
    """A new user, with the temporary password the admin hands over — shown
    this once; it can only be replaced by resetting the password."""
    temporary_password: str

