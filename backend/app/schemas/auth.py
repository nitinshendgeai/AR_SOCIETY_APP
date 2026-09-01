from pydantic import BaseModel, EmailStr, field_validator
from typing import List, Optional


class RegisterRequest(BaseModel):
    email:     EmailStr
    phone:     Optional[str] = None
    full_name: str
    password:  str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    # Accepts either an email (admin/committee/staff accounts) or a mobile
    # number (resident/tenant accounts auto-provisioned by phone — see
    # app/services/user_provisioning.py) — kept as a plain str rather than
    # EmailStr since a phone number is not a valid email format.
    email:    str
    password: str


class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class TokenPayload(BaseModel):
    sub:   str
    type:  str
    roles: List[str] = []
