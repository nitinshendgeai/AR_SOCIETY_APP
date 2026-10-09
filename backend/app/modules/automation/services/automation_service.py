"""Automatic tasks: reminders and housekeeping that used to wait for someone to press a button.

Each task is worked out per society and runs at most once per period (a day, or a
week for the digests) — the `scheduled_job_runs` unique key makes that true even with
several workers. Tasks that only inform the office are on by default; the dues reminder
that goes out to members is off until the society turns it on.
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.agreement_tracker import AgreementStatus, AgreementTracker
from app.models.notification import NotificationType
from app.models.role import Role
from app.models.society import AccountStatus, Society
from app.models.user import User, UserRole
from app.modules.automation.models.automation import SocietyAutomation, ScheduledJobRun
from app.modules.billing.models.billing import BillingCycle, MaintenanceChargeConfig
from app.modules.billing.services.defaulters import MemberDues
from app.modules.inventory.services.inventory_service import InventoryService
from app.modules.visitor.models.visitor import Visitor, VisitorStatus
from app.services.notification_service import NotificationService
from app.utils.local_time import local_today, zone

logger = logging.getLogger(__name__)

OFFICE_ROLES = ("Society Admin", "Committee Chairman", "Committee Secretary", "Committee Treasurer", "Committee Member")
RUN_FROM_HOUR = 8          # society-local hour from which the day's tasks may run
VISITOR_PENDING_HOURS = 24


@dataclass(frozen=True)
class Job:
    key: str
    title: str
    description: str
    schedule: str            # "daily" | "weekly"
    default_on: bool
    setting: str             # SocietyAutomation column that switches it


JOBS: List[Job] = [
    Job("dues_reminders", "Maintenance dues reminders",
        "Reminds members with overdue maintenance, no more often than the interval you set.",
        "daily", False, "dues_reminders"),
    Job("agreement_alerts", "Tenant agreement alerts",
        "Tells the office and the tenant 30 days and 7 days before a rental agreement ends.",
        "daily", True, "agreement_alerts"),
    Job("asset_alerts", "Asset service and warranty digest",
        "A weekly note to the office of assets due for service and warranties about to end.",
        "weekly", True, "asset_alerts"),
    Job("billing_nudge", "Billing cycle reminder",
        "A weekly note to the office when this month's maintenance bills have not been started.",
        "weekly", True, "billing_nudge"),
    Job("visitor_expiry", "Expire unanswered visitor requests",
        f"Closes visitor requests nobody answered within {VISITOR_PENDING_HOURS} hours.",
        "daily", True, "visitor_expiry"),
]
JOB_BY_KEY: Dict[str, Job] = {j.key: j for j in JOBS}
DEFAULTS = {"dues_reminders": False, "reminder_every_days": 7, "reminder_min_months": 1,
            "agreement_alerts": True, "asset_alerts": True, "billing_nudge": True, "visitor_expiry": True}
SETTING_FIELDS = tuple(DEFAULTS)


def period_key(job: Job, today: date) -> str:
    if job.schedule == "weekly":
        y, w, _ = today.isocalendar()
        return f"{y}-W{w:02d}"
    return today.isoformat()


class AutomationService:
    def __init__(self, db: Session):
        self.db = db

    # ── Settings ─────────────────────────────────────────────────────────────

    def settings(self, society_id: UUID) -> dict:
        row = self.db.query(SocietyAutomation).filter(SocietyAutomation.society_id == society_id).first()
        return {f: (getattr(row, f) if row is not None else DEFAULTS[f]) for f in SETTING_FIELDS}

    def update_settings(self, society_id: UUID, changes: dict) -> dict:
        row = self.db.query(SocietyAutomation).filter(SocietyAutomation.society_id == society_id).first()
        if row is None:
            row = SocietyAutomation(society_id=society_id, **DEFAULTS)
            self.db.add(row)
        for k, v in changes.items():
            if k in SETTING_FIELDS and v is not None:
                setattr(row, k, v)
        self.db.commit()
        return self.settings(society_id)

    def overview(self, society_id: UUID) -> dict:
        settings = self.settings(society_id)
        jobs = []
        for j in JOBS:
            last = (self.db.query(ScheduledJobRun)
                    .filter(ScheduledJobRun.society_id == society_id, ScheduledJobRun.job == j.key)
                    .order_by(ScheduledJobRun.started_at.desc()).first())
            jobs.append({
                "key": j.key, "title": j.title, "description": j.description, "schedule": j.schedule,
                "enabled": bool(settings[j.setting]),
                "last_run": None if last is None else {
                    "status": last.status, "summary": last.summary, "manual": last.manual,
                    "ran_at": last.started_at.isoformat()},
            })
        return {"settings": settings, "jobs": jobs}

    # ── Running ──────────────────────────────────────────────────────────────

    def run_job(self, society_id: UUID, key: str, *, manual: bool = False, today: Optional[date] = None,
                now: Optional[datetime] = None) -> Optional[ScheduledJobRun]:
        """Run one task for one society for the current period. Returns the run, or None
        if this period's run already exists (another worker, or already done today)."""
        job = JOB_BY_KEY[key]
        society = self.db.query(Society).filter(Society.id == society_id).first()
        if society is None:
            return None
        tz = zone(getattr(society, "timezone", None))
        today = today or local_today(tz)
        now = now or datetime.utcnow()
        pk = f"manual-{now:%Y%m%d%H%M%S%f}" if manual else period_key(job, today)
        run = ScheduledJobRun(job=key, society_id=society_id, period_key=pk, manual=manual,
                              status="running", started_at=now)
        try:
            with self.db.begin_nested():
                self.db.add(run)
                self.db.flush()
        except IntegrityError:
            self.db.expire_all()
            return None
        self.db.commit()
        try:
            summary = getattr(self, f"_job_{key}")(society_id, today, self.settings(society_id))
            run.status, run.summary = "ok", summary
        except Exception as exc:  # noqa: BLE001 - a failing task is recorded, never raised
            logger.exception("[automation] %s failed for %s", key, society_id)
            if not self.db.is_active:        # a database error leaves the transaction unusable
                self.db.rollback()
            run = self.db.query(ScheduledJobRun).filter(ScheduledJobRun.id == run.id).first()
            run.status, run.summary = "error", f"{type(exc).__name__}: {exc}"[:500]
        run.finished_at = datetime.utcnow()
        self.db.commit()
        return run

    def run_due(self, now: Optional[datetime] = None) -> int:
        """One pass over every active society: run each switched-on task whose period
        has not run yet, once the society's own clock has reached the run hour."""
        now = now or datetime.utcnow()
        ran = 0
        societies = (self.db.query(Society)
                     .filter(Society.is_active == True,
                             Society.account_status.in_((AccountStatus.TRIAL, AccountStatus.ACTIVE))).all())
        for society in societies:
            tz = zone(getattr(society, "timezone", None))
            if to_local_hour(now, tz) < RUN_FROM_HOUR:
                continue
            settings = self.settings(society.id)
            for job in JOBS:
                if not settings[job.setting]:
                    continue
                try:
                    if self.run_job(society.id, job.key, now=now) is not None:
                        ran += 1
                except Exception:  # noqa: BLE001
                    logger.exception("[automation] could not run %s for %s", job.key, society.id)
                    self.db.rollback()
        return ran

    # ── Who to tell ──────────────────────────────────────────────────────────

    def _office(self, society_id: UUID) -> List[UUID]:
        rows = (self.db.query(User.id).join(UserRole, UserRole.user_id == User.id)
                .join(Role, Role.id == UserRole.role_id)
                .filter(User.society_id == society_id, User.is_active == True, Role.name.in_(OFFICE_ROLES))
                .distinct().all())
        return [r[0] for r in rows]

    def _tell(self, users, title: str, body: str, module: str, entity_id: Optional[str] = None,
              route: Optional[str] = None, push: bool = True) -> int:
        n = 0
        for uid in users:
            if NotificationService.send(db=self.db, user_id=uid, title=title, body=body,
                                        type=NotificationType.REMINDER, module=module,
                                        entity_id=entity_id, action_url=route, push=push):
                n += 1
        return n

    # ── Tasks ────────────────────────────────────────────────────────────────

    def _job_dues_reminders(self, society_id: UUID, today: date, s: dict) -> str:
        result = MemberDues(self.db).remind(
            society_id, None, int(s["reminder_min_months"]), user=None,
            not_reminded_within_days=int(s["reminder_every_days"]))
        return (f"Reminded {result['flats_reminded']} flat(s); "
                f"{len(result['flats_without_app_login'])} had nobody with an app login")

    def _job_agreement_alerts(self, society_id: UUID, today: date, s: dict) -> str:
        office = self._office(society_id)
        rows = (self.db.query(AgreementTracker)
                .filter(AgreementTracker.society_id == society_id,
                        AgreementTracker.status == AgreementStatus.ACTIVE,
                        AgreementTracker.end_date >= today,
                        AgreementTracker.end_date <= today + timedelta(days=30)).all())
        sent = 0
        for a in rows:
            days = (a.end_date - today).days
            stage = None
            if days <= 7 and not a.alert_sent_7:
                stage = 7
            elif days > 7 and not a.alert_sent_30:
                stage = 30
            if stage is None:
                continue
            tenant = a.tenant
            flat = a.flat
            where = f"{flat.wing.name} {flat.flat_number}" if flat is not None and flat.wing is not None else "a flat"
            who = tenant.full_name if tenant is not None else "the tenant"
            title = "Rental agreement ending soon"
            body = (f"{who}'s agreement for {where} ends on {a.end_date:%d %b %Y} "
                    f"({days} day{'s' if days != 1 else ''} left).")
            users = list(office)
            if tenant is not None and tenant.user_id:
                users.append(tenant.user_id)
            self._tell(users, title, body, "agreement", str(a.id))
            if stage == 7:
                a.alert_sent_7 = True
                a.alert_sent_30 = True
            else:
                a.alert_sent_30 = True
            self.db.commit()
            sent += 1
        return f"{sent} agreement alert(s) sent"

    def _job_asset_alerts(self, society_id: UUID, today: date, s: dict) -> str:
        inv = InventoryService(self.db)
        due = inv.list_assets(society_id, limit=500, due=True)
        warranties = inv.get_expiring_warranties(society_id)
        if not due and not warranties:
            return "Nothing due"
        parts = []
        if due:
            overdue = sum(1 for a in due if a.next_service_due and a.next_service_due < today)
            parts.append(f"{len(due)} asset(s) due for service" + (f" ({overdue} overdue)" if overdue else ""))
        if warranties:
            parts.append(f"{len(warranties)} warrant{'y' if len(warranties) == 1 else 'ies'} ending soon")
        self._tell(self._office(society_id), "Assets need attention", "; ".join(parts) + ".", "assets")
        return "; ".join(parts)

    def _job_billing_nudge(self, society_id: UUID, today: date, s: dict) -> str:
        if today.day < 3:
            return "Too early in the month"
        started = (self.db.query(func.count(BillingCycle.id))
                   .filter(BillingCycle.society_id == society_id, BillingCycle.is_active == True,
                           BillingCycle.cycle_start <= today, BillingCycle.cycle_end >= today).scalar()) or 0
        if started:
            return "This month's cycle exists"
        ever = (self.db.query(func.count(BillingCycle.id)).filter(BillingCycle.society_id == society_id).scalar() or 0) \
            + (self.db.query(func.count(MaintenanceChargeConfig.id))
               .filter(MaintenanceChargeConfig.society_id == society_id).scalar() or 0)
        if not ever:
            return "Billing not set up yet"
        n = self._tell(self._office(society_id), "Maintenance bills not started",
                       f"There is no billing cycle for {today:%B %Y} yet. Create one in Maintenance Billing.",
                       "billing", route="/billing/maintenance")
        return f"Reminded {n} person(s)"

    def _job_visitor_expiry(self, society_id: UUID, today: date, s: dict) -> str:
        cutoff = datetime.utcnow() - timedelta(hours=VISITOR_PENDING_HOURS)
        rows = (self.db.query(Visitor).filter(Visitor.society_id == society_id,
                                              Visitor.status == VisitorStatus.PENDING,
                                              Visitor.created_at < cutoff).all())
        for v in rows:
            v.status = VisitorStatus.EXPIRED
        self.db.commit()
        return f"{len(rows)} request(s) expired"


def to_local_hour(now_utc: datetime, tz) -> int:
    from app.utils.local_time import to_local
    return to_local(now_utc, tz).hour
