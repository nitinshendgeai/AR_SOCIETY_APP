from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
from typing import List, Optional, Union
from uuid import UUID


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
    # When one login belongs to several societies the first call answers with the list to choose from; the
    # app then sends the same credentials again with the chosen society.
    society_id: Optional[UUID] = None


class SocietyChoice(BaseModel):
    """One society a person can sign in to."""
    society_id:   Optional[str] = None            # None: the platform console
    society_name: str
    roles:        List[str] = []
    current:      bool = False


class LoginChoiceResponse(BaseModel):
    requires_society_choice: bool = True
    choices: List[SocietyChoice]


class SwitchSocietyRequest(BaseModel):
    society_id: UUID


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


class SessionOut(BaseModel):
    """A device signed in to this account."""
    id:           str
    device:       Optional[str] = None
    ip_address:   Optional[str] = None
    signed_in_at: datetime
    last_seen_at: Optional[datetime] = None
    current:      bool = False
