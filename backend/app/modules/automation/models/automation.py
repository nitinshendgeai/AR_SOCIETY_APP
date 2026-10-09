from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin


class SocietyAutomation(Base, TimestampMixin):
    """Which automatic tasks a society has switched on, and how they behave.

    A society with no row uses the defaults below: everything that only tells the
    office something is on; the reminder that goes out to members is off until the
    society turns it on.
    """
    __tablename__ = "society_automation"
    __table_args__ = (UniqueConstraint("society_id", name="uq_society_automation_society"),)

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    dues_reminders = Column(Boolean, nullable=False, default=False)
    reminder_every_days = Column(Integer, nullable=False, default=7)
    reminder_min_months = Column(Integer, nullable=False, default=1)
    agreement_alerts = Column(Boolean, nullable=False, default=True)
    asset_alerts = Column(Boolean, nullable=False, default=True)
    billing_nudge = Column(Boolean, nullable=False, default=True)
    visitor_expiry = Column(Boolean, nullable=False, default=True)


class ScheduledJobRun(Base, TimestampMixin):
    """One run of one automatic task for one society for one period (a day or a
    week). The unique key is what makes a task run once per period however many
    workers are running."""
    __tablename__ = "scheduled_job_runs"
    __table_args__ = (UniqueConstraint("job", "society_id", "period_key", name="uq_scheduled_job_run"),)

    job = Column(String(50), nullable=False, index=True)
    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    period_key = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False, default="running")   # running | ok | error
    manual = Column(Boolean, nullable=False, default=False)
    summary = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
