import re
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


class SelfRegistrationRequest(BaseModel):
    society_name:        str
    society_code:        str
    contact_person_name: str
    contact_email:       EmailStr
    contact_mobile:      str
    city:                str
    state:               str
    country:             str = "India"
    total_wings:         int = 1
    total_flats:         int = 1
    terms_accepted:      bool

    @field_validator("society_code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        code = v.strip().upper()
        if not re.match(r'^[A-Z0-9]{3,10}$', code):
            raise ValueError("society_code must be 3-10 uppercase alphanumeric characters")
        return code

    @field_validator("contact_mobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        digits = re.sub(r'\D', '', v)
        if len(digits) != 10:
            raise ValueError("contact_mobile must be a 10-digit mobile number")
        return digits

    @field_validator("terms_accepted")
    @classmethod
    def must_accept_terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must accept the Terms & Conditions to register")
        return v

    @field_validator("total_wings")
    @classmethod
    def validate_wings(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("total_wings must be between 1 and 100")
        return v

    @field_validator("total_flats")
    @classmethod
    def validate_flats(cls, v: int) -> int:
        if v < 1 or v > 10000:
            raise ValueError("total_flats must be between 1 and 10000")
        return v


class CredentialOut(BaseModel):
    role:     str
    email:    str
    password: str


class SelfRegistrationOut(BaseModel):
    society_id:     str
    society_name:   str
    society_code:   str
    trial_end_date: str
    trial_days:     int
    credentials:    list[CredentialOut]
    message:        str


class TrialStatusOut(BaseModel):
    account_status:        str
    is_trial:              bool
    trial_start_date:      Optional[str]
    trial_end_date:        Optional[str]
    trial_days_remaining:  int
    trial_expired:         bool
    expiry_warning:        bool   # ≤ 7 days
    expiry_critical:       bool   # ≤ 3 days
    subscription_plan:     Optional[str]
    subscription_status:   Optional[str]
    setup_completed:       bool
    setup_completion_percentage: int


class SetupProgressUpdate(BaseModel):
    setup_completion_percentage: int
    setup_completed: bool = False

    @field_validator("setup_completion_percentage")
    @classmethod
    def valid_pct(cls, v: int) -> int:
        if v < 0 or v > 100:
            raise ValueError("setup_completion_percentage must be 0-100")
        return v


class AcceptTermsRequest(BaseModel):
    terms_accepted: bool

    @field_validator("terms_accepted")
    @classmethod
    def must_be_true(cls, v: bool) -> bool:
        if not v:
            raise ValueError("terms_accepted must be true")
        return v
