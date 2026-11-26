"""Accounts Agent tables. Every row belongs to a society (`society_id`, indexed); nothing here duplicates an accounting
or notification table — findings and proposals only *point at* vouchers.

- AgentSettings        one row per society (created lazily).
- AgentLearningRun     one row per learning run over the rolling three-month window.
- AgentPattern         the society's current learning profile (replaced by each run).
- AgentEvent           transactional outbox: written in the same transaction as the voucher change.
- AgentFinding         one structured finding (a validation failure, an anomaly or an observation).
- AgentProposal        a correction proposal; executed only after an authorised person approves it.
- AgentAuditLog        append-only trail of agent and reviewer actions.
- AgentAiUsage         AI tokens spent (and saved) per society, month and feature.
- AgentAiAnswer        an AI-worded answer kept for reuse: the same question on the same clauses costs no tokens.
"""
from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL")
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}            # 0 = most severe
FINDING_STATUSES = ("NEW", "UNDER_REVIEW", "APPROVED", "REJECTED", "RESOLVED", "IGNORED")
OPEN_FINDING_STATUSES = ("NEW", "UNDER_REVIEW", "APPROVED")
# What the agent is actually claiming (never present a statistic as a confirmed error).
FINDING_CLASSES = ("confirmed_validation_failure", "strongly_suspected_anomaly", "statistical_deviation", "informational")
# The unified classification (Part 14). Engine A's original classes map onto it (see UNIFIED_CLASS); Engine B stores
# these values directly in `finding_class`. A potential issue is never presented as a confirmed violation.
UNIFIED_CLASSES = ("CONFIRMED_ACCOUNTING_ERROR", "CONFIRMED_STATUTORY_VALIDATION_FAILURE", "POTENTIAL_NON_COMPLIANCE",
                   "SUSPECTED_ACCOUNTING_ANOMALY", "MISSING_DOCUMENTATION", "INTERNAL_POLICY_DEVIATION",
                   "LEGAL_SOURCE_CONFLICT", "ADVISORY_OBSERVATION")
UNIFIED_CLASS = {"confirmed_validation_failure": "CONFIRMED_ACCOUNTING_ERROR",
                 "strongly_suspected_anomaly": "SUSPECTED_ACCOUNTING_ANOMALY",
                 "statistical_deviation": "SUSPECTED_ACCOUNTING_ANOMALY",
                 "informational": "ADVISORY_OBSERVATION", **{c: c for c in UNIFIED_CLASSES}}
EVENT_STATUSES = ("pending", "processing", "done", "failed", "dead", "skipped")
PROPOSAL_STATUSES = ("PENDING", "EXECUTED", "ACKNOWLEDGED", "REJECTED", "STALE", "FAILED")
PROPOSAL_ACTIONS = ("edit_voucher", "cancel_voucher", "source_review", "remediation")


class AgentSettings(Base, TimestampMixin):
    __tablename__ = "accounts_agent_settings"
    __table_args__ = (UniqueConstraint("society_id", name="uq_agent_settings_society"),)

    society_id              = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    monitoring_enabled      = Column(Boolean, default=True, nullable=False)
    notify_min_severity     = Column(String(16), default="HIGH", nullable=False)
    z_threshold             = Column(Float, default=3.5, nullable=False)
    recurring_tolerance_pct = Column(Float, default=10.0, nullable=False)
    duplicate_window_days   = Column(Integer, default=7, nullable=False)
    llm_provider            = Column(String(30), default="disabled", nullable=False)
    # Most AI tokens this society may spend in a calendar month; past it the agent answers from the app's own data.
    ai_monthly_token_budget = Column(Integer, default=300000, nullable=False)
    # Set by the PLATFORM administrator only (never by the society): "on" / "off" overrides what the society's plan
    # includes; NULL follows the plan. ai_override_tokens replaces the plan's allowance when set.
    ai_plan_override        = Column(String(8), nullable=True)
    ai_override_tokens      = Column(Integer, nullable=True)
    last_monitored_at       = Column(DateTime, nullable=True)
    last_error              = Column(Text, nullable=True)
    updated_by              = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class AgentLearningRun(Base, TimestampMixin):
    __tablename__ = "accounts_agent_learning_runs"

    society_id       = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    window_start     = Column(Date, nullable=False)
    window_end       = Column(Date, nullable=False)
    status           = Column(String(16), default="running", nullable=False)       # running | completed | failed
    started_at       = Column(DateTime, nullable=False)
    finished_at      = Column(DateTime, nullable=True)
    voucher_count    = Column(Integer, default=0, nullable=False)
    line_count       = Column(Integer, default=0, nullable=False)
    months_covered   = Column(Integer, default=0, nullable=False)
    days_covered     = Column(Integer, default=0, nullable=False)
    pattern_count    = Column(Integer, default=0, nullable=False)
    confidence_score = Column(Float, default=0.0, nullable=False)
    confidence_label = Column(String(16), default="none", nullable=False)           # none | limited | moderate | good
    summary          = Column(JSON, nullable=True)
    error            = Column(Text, nullable=True)
    triggered_by     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (Index("ix_agent_runs_society_started", "society_id", "started_at"),)


class AgentPattern(Base, TimestampMixin):
    __tablename__ = "accounts_agent_patterns"
    __table_args__ = (
        UniqueConstraint("society_id", "pattern_type", "pattern_key", name="uq_agent_pattern_key"),
    )

    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id       = Column(UUID(as_uuid=True), ForeignKey("accounts_agent_learning_runs.id", ondelete="SET NULL"), nullable=True)
    pattern_type = Column(String(30), nullable=False)      # account_amount | vendor | ledger_pair | voucher_type | recurring
    pattern_key  = Column(String(200), nullable=False)
    sample_count = Column(Integer, default=0, nullable=False)
    stats        = Column(JSON, nullable=False)


class AgentEvent(Base, TimestampMixin):
    __tablename__ = "accounts_agent_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_agent_event_idem"),
        Index("ix_agent_events_claim", "status", "next_attempt_at"),
    )

    society_id      = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    # Not a foreign key on purpose: an event must be insertable in the same flush as the voucher it names.
    voucher_id      = Column(UUID(as_uuid=True), nullable=False, index=True)
    event_type      = Column(String(30), nullable=False)    # voucher.created | .edited | .cancelled | .approval_changed
    idempotency_key = Column(String(160), nullable=False)
    status          = Column(String(12), default="pending", nullable=False)
    attempts        = Column(Integer, default=0, nullable=False)
    next_attempt_at = Column(DateTime, nullable=False)
    locked_until    = Column(DateTime, nullable=True)
    locked_by       = Column(String(60), nullable=True)
    last_error      = Column(Text, nullable=True)
    processed_at    = Column(DateTime, nullable=True)
    # Administrative recovery of a dead event (functional audit D-10)
    dead_at         = Column(DateTime, nullable=True)
    requeue_count   = Column(Integer, default=0, nullable=False, server_default="0")
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    acknowledge_note = Column(Text, nullable=True)


class AgentFinding(Base, TimestampMixin):
    __tablename__ = "accounts_agent_findings"
    __table_args__ = (
        UniqueConstraint("society_id", "dedupe_key", name="uq_agent_finding_dedupe"),
        Index("ix_agent_findings_list", "society_id", "status", "severity", "created_at"),
    )

    society_id         = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    voucher_id         = Column(UUID(as_uuid=True), ForeignKey("vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    transaction_ref    = Column(String(60), nullable=True)                      # voucher number, kept readable if the voucher is gone
    category           = Column(String(40), nullable=False, index=True)
    finding_class      = Column(String(40), nullable=False)
    severity           = Column(String(16), nullable=False, index=True)
    confidence         = Column(Float, nullable=False)
    rule_code          = Column(String(40), nullable=False, index=True)
    dedupe_key         = Column(String(200), nullable=False)
    title              = Column(String(200), nullable=False)
    explanation        = Column(Text, nullable=False)
    expected_behaviour = Column(Text, nullable=True)
    actual_behaviour   = Column(Text, nullable=True)
    evidence           = Column(JSON, nullable=True)
    recommended_action = Column(Text, nullable=True)
    status             = Column(String(16), default="NEW", nullable=False)
    reviewed_by        = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at        = Column(DateTime, nullable=True)
    resolution_note    = Column(Text, nullable=True)
    resolved_at        = Column(DateTime, nullable=True)
    learning_confidence = Column(String(16), nullable=True)                      # the profile's label when this was raised
    source_event_id    = Column(UUID(as_uuid=True), nullable=True)
    voucher_date       = Column(Date, nullable=True, index=True)
    # Engine B (legal & bye-law compliance) and the residential-accounting checks use the same table.
    engine             = Column(String(12), nullable=False, default="accounting", server_default="accounting")
    compliance_category = Column(String(40), nullable=True)
    legal_rule_code    = Column(String(60), nullable=True, index=True)
    legal_source       = Column(JSON, nullable=True)       # the rule version, its source, clause, status and verification
    flat_id            = Column(UUID(as_uuid=True), ForeignKey("flats.id", ondelete="SET NULL"), nullable=True)
    vendor_id          = Column(UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)

    proposals = relationship("AgentProposal", back_populates="finding", order_by="AgentProposal.created_at")


class AgentProposal(Base, TimestampMixin):
    __tablename__ = "accounts_agent_proposals"
    __table_args__ = (Index("ix_agent_proposals_list", "society_id", "status", "created_at"),)

    society_id          = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id          = Column(UUID(as_uuid=True), ForeignKey("accounts_agent_findings.id", ondelete="CASCADE"), nullable=False, index=True)
    voucher_id          = Column(UUID(as_uuid=True), ForeignKey("vouchers.id", ondelete="SET NULL"), nullable=True, index=True)
    action_type         = Column(String(20), nullable=False)
    status              = Column(String(12), default="PENDING", nullable=False)
    voucher_fingerprint = Column(String(64), nullable=False)
    title               = Column(String(200), nullable=False)
    explanation         = Column(Text, nullable=False)
    before_values       = Column(JSON, nullable=False)
    after_values        = Column(JSON, nullable=True)
    impact              = Column(JSON, nullable=True)           # per-ledger debit/credit effect of the correction
    executable          = Column(Boolean, default=True, nullable=False)
    created_by          = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_by          = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at          = Column(DateTime, nullable=True)
    decision_note       = Column(Text, nullable=True)
    result              = Column(JSON, nullable=True)           # what executing it did, and the agent's verification

    finding = relationship("AgentFinding", back_populates="proposals")


class AgentAuditLog(Base, TimestampMixin):
    __tablename__ = "accounts_agent_audit_logs"
    __table_args__ = (Index("ix_agent_audit_society_created", "society_id", "created_at"),)

    society_id  = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)   # None: the agent itself
    action      = Column(String(40), nullable=False, index=True)
    entity_type = Column(String(30), nullable=False)
    entity_id   = Column(String(64), nullable=True)
    details     = Column(JSON, nullable=True)


class AgentAiUsage(Base, TimestampMixin):
    """One row per society, month ('2026-11') and feature ('bylaw_answer', 'entry_reading')."""
    __tablename__ = "accounts_agent_ai_usage"
    __table_args__ = (UniqueConstraint("society_id", "month", "feature", name="uq_agent_ai_usage"),)

    society_id        = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    month             = Column(String(7), nullable=False)
    feature           = Column(String(30), nullable=False)
    ai_calls          = Column(Integer, default=0, nullable=False)       # requests actually sent
    input_tokens      = Column(Integer, default=0, nullable=False)
    output_tokens     = Column(Integer, default=0, nullable=False)
    reused_answers    = Column(Integer, default=0, nullable=False)       # served from a kept answer: no tokens
    answered_locally  = Column(Integer, default=0, nullable=False)       # the app's own data was enough: no tokens
    over_budget       = Column(Integer, default=0, nullable=False)       # AI wanted but the month's budget was used up
    not_included      = Column(Integer, default=0, nullable=False)       # AI wanted but the subscription has no AI
    failed_calls      = Column(Integer, default=0, nullable=False)


class AgentAiAnswer(Base, TimestampMixin):
    """An AI answer kept for reuse. [key] covers the question's words and the exact clauses it was given, so a change
    to the library (another clause matching) asks afresh."""
    __tablename__ = "accounts_agent_ai_answers"
    __table_args__ = (UniqueConstraint("society_id", "feature", "key", name="uq_agent_ai_answer"),)

    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    feature      = Column(String(30), nullable=False)
    key          = Column(String(64), nullable=False)
    payload      = Column(JSON, nullable=False)
    hits         = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime, nullable=True)


class PlatformAiPlan(Base, TimestampMixin):
    """What each subscription plan includes in AI, set by the platform administrator. plan_key is a plan
    ('starter', 'growth', 'enterprise') or 'trial'; for 'trial' the tokens cover the whole trial, not a month."""
    __tablename__ = "platform_ai_plans"

    plan_key       = Column(String(30), nullable=False, unique=True)
    ai_included    = Column(Boolean, default=False, nullable=False)
    monthly_tokens = Column(Integer, default=0, nullable=False)
    updated_by     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
