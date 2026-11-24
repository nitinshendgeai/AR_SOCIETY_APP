from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.modules.accounts_agent.models.agent import SEVERITIES


class SettingsUpdate(BaseModel):
    monitoring_enabled: Optional[bool] = None
    notify_min_severity: Optional[str] = None
    z_threshold: Optional[float] = Field(None, ge=2.5, le=6.0)
    recurring_tolerance_pct: Optional[float] = Field(None, ge=1, le=100)
    duplicate_window_days: Optional[int] = Field(None, ge=1, le=60)
    # "anthropic": bye-law answers worded by Claude and free-text entry requests read by Claude. Takes effect only
    # when the deployment also sets ANTHROPIC_API_KEY. "disabled" (default): deterministic answers only.
    llm_provider: Optional[str] = None

    @field_validator("llm_provider")
    @classmethod
    def _llm(cls, v):
        if v is not None and v not in ("disabled", "anthropic"):
            raise ValueError("must be 'disabled' or 'anthropic'")
        return v

    @field_validator("notify_min_severity")
    @classmethod
    def _sev(cls, v):
        if v is not None and v not in SEVERITIES:
            raise ValueError(f"must be one of {', '.join(SEVERITIES)}")
        return v


class MonitoringToggle(BaseModel):
    enabled: bool


class FindingReview(BaseModel):
    status: str
    note: Optional[str] = Field(None, max_length=1000)


class ProposalApprove(BaseModel):
    confirm: bool = False                 # explicit confirmation is mandatory
    note: Optional[str] = Field(None, max_length=1000)


class ProposalReject(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)
