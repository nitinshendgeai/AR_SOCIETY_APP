"""Request / response contract of the help assistant. See docs/HELP_ASSISTANT.md."""
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HistoryTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)       # the service trims it further to the configured limit


class AskRequest(BaseModel):
    # extra="forbid": a client that sends user_id / role / permissions gets a 422, never a silent ignore.
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=4000)
    history: List[HistoryTurn] = Field(default_factory=list, max_length=50)
    include_diagnostics: bool = False
    # Platform admins only: the society to look at. Everyone else must leave it out (or name their own society).
    target_society_id: Optional[UUID] = None


class DiagnosticsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topics: List[str] = Field(default_factory=list, max_length=10)     # empty = every supported topic
    target_society_id: Optional[UUID] = None


class Source(BaseModel):
    title: str
    section: str
    document: str
    chunk_id: str


class Finding(BaseModel):
    topic: str
    status: Literal["ok", "gap", "not_initialised", "unavailable"]
    message: str
    count: Optional[int] = None


class ProviderInfo(BaseModel):
    mode: str                  # disabled | mock | misconfigured
    status: str                # not_used | ok | timeout | error | malformed | disabled


class AskResponse(BaseModel):
    request_id: str
    status: Literal["answered", "insufficient_evidence", "restricted"]
    answer: str
    steps: List[str]
    sources: List[Source]
    config_gaps: List[Finding]
    uncertainty: Optional[str] = None
    escalation: Optional[str] = None
    provider: ProviderInfo
    audience: str
    index_version: str


class DiagnosticsResponse(BaseModel):
    request_id: str
    findings: List[Finding]
    read_only: bool = True


class StatusResponse(BaseModel):
    request_id: str
    enabled: bool
    provider: ProviderInfo
    audience: str
    diagnostics_available: bool
    diagnostic_topics: List[str]
    needs_target_society: bool
    index_version: str
    document_count: int
    limits: dict
    suggested_questions: List[str]
