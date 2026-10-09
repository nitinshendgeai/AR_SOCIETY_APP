from datetime import date
from typing import Optional
from pydantic import BaseModel, field_validator


class ExtendTrialRequest(BaseModel):
    extend_days: int

    @field_validator("extend_days")
    @classmethod
    def valid_days(cls, v: int) -> int:
        if v < 1 or v > 365:
            raise ValueError("extend_days must be between 1 and 365")
        return v


class SuspendSocietyRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_required(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("Say why the society is being suspended")
        return v.strip()


class LimitsRequest(BaseModel):
    allowed_users: int
    allowed_flats: int
    allowed_storage_mb: int

    @field_validator("allowed_users", "allowed_flats", "allowed_storage_mb")
    @classmethod
    def positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Must be at least 1")
        return v


class ActivateSocietyRequest(BaseModel):
    plan: str = "starter"
    expires_on: Optional[date] = None      # when the paid period ends, if known

    @field_validator("plan")
    @classmethod
    def valid_plan(cls, v: str) -> str:
        if v not in ("starter", "growth", "enterprise"):
            raise ValueError("plan must be starter, growth, or enterprise")
        return v


class SocietyAdminSummary(BaseModel):
    id:              str
    name:            str
    society_code:    Optional[str]
    city:            Optional[str]
    account_status:  str
    is_trial:        bool
    trial_end_date:  Optional[str]
    trial_days_remaining: int
    setup_completed: bool
    setup_completion_percentage: int
    total_flats:     Optional[int]
    created_at:      str

    class Config:
        from_attributes = True


class PlatformStatsOut(BaseModel):
    total_societies:   int
    trial_societies:   int
    active_societies:  int
    expired_societies: int
    suspended_societies: int
    expiring_soon:     int   # trial ends in ≤ 7 days
