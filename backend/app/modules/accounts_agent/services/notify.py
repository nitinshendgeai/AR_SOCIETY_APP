"""Notifications through the app's existing NotificationService. Recipients are the society's own admin/committee
members. Grouped (one notification per batch per society) and de-duplicated (no second unread one for the same key)."""
import logging
from typing import Iterable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationType
from app.models.permission import Permission, RolePermission
from app.models.user import User, UserRole
from app.modules.accounts_agent.models.agent import AgentFinding, SEVERITY_RANK
from app.modules.accounts_agent.services.engine import get_settings, severity_at_least
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)
MODULE = "accounts_agent"


def recipients(db: Session, society_id: UUID) -> List[UUID]:
    """Active admin/committee users of THIS society."""
    rows = (db.query(User.id).join(UserRole, UserRole.user_id == User.id)
            .join(RolePermission, RolePermission.role_id == UserRole.role_id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .filter(User.society_id == society_id, User.is_active == True, Permission.code == "admin_committee")  # noqa: E712
            .distinct().all())
    return [r[0] for r in rows]


def _send(db: Session, society_id: UUID, title: str, body: str, dedupe: str, *, ntype=NotificationType.ALERT,
          action_url: str = "/accounts-agent", push: bool = False, only: Optional[Iterable[UUID]] = None) -> int:
    sent = 0
    for uid in (list(only) if only is not None else recipients(db, society_id)):
        already = (db.query(Notification.id).filter(Notification.user_id == uid, Notification.module == MODULE,
                                                    Notification.entity_id == dedupe, Notification.is_read == False).first())  # noqa: E712
        if already:
            continue
        if NotificationService.send(db, uid, title, body, type=ntype, module=MODULE, entity_id=dedupe,
                                    action_url=action_url, push=push, urgent=push):
            sent += 1
    return sent


def notify_findings(db: Session, society_id: UUID, findings: List[AgentFinding]) -> int:
    """One grouped notification for the findings at or above the society's notification threshold."""
    minimum = get_settings(db, society_id).notify_min_severity
    worth = [f for f in findings if severity_at_least(f.severity, minimum)]
    if not worth:
        return 0
    worth.sort(key=lambda f: SEVERITY_RANK[f.severity])
    crit = sum(1 for f in worth if f.severity == "CRITICAL")
    high = sum(1 for f in worth if f.severity == "HIGH")
    if len(worth) == 1:
        f = worth[0]
        title, dedupe = f"Accounts Agent: {f.severity.title()} — {f.title}"[:200], f"finding:{f.id}"
        body = f"{f.transaction_ref or 'A transaction'}: {f.title}. Open the Accounts Agent to review."
    else:
        title = f"Accounts Agent: {len(worth)} findings need review"
        body = f"{crit} critical, {high} high-severity and {len(worth) - crit - high} other finding(s) were detected."
        dedupe = f"batch:{worth[0].id}"
    return _send(db, society_id, title, body, dedupe, push=bool(crit))


def notify_proposal_needs_approval(db: Session, society_id: UUID, proposal) -> int:
    return _send(db, society_id, "Accounts Agent: correction awaiting approval",
                 f"A correction proposal for {proposal.title} needs your approval.", f"proposal:{proposal.id}",
                 ntype=NotificationType.APPROVAL, action_url=f"/accounts-agent/proposals/{proposal.id}")


def notify_proposal_decided(db: Session, society_id: UUID, proposal, outcome: str, actor_id: UUID) -> int:
    return _send(db, society_id, f"Accounts Agent: proposal {outcome}", f"The proposal '{proposal.title}' was {outcome}.",
                 f"proposal-{outcome}:{proposal.id}", ntype=NotificationType.INFO,
                 action_url=f"/accounts-agent/proposals/{proposal.id}", only=[u for u in recipients(db, society_id)])


def notify_job_failure(db: Session, society_id: UUID, event_id, attempts: int) -> int:
    return _send(db, society_id, "Accounts Agent: monitoring job is failing",
                 f"A monitoring job failed {attempts} times and has been parked. Findings may be delayed; an administrator should check the worker.",
                 f"job-failed:{event_id}")


def notify_learning_complete(db: Session, society_id: UUID, run) -> int:
    return _send(db, society_id, "Accounts Agent: learning completed",
                 f"Learned from {run.voucher_count} vouchers ({run.window_start:%d %b %Y} – {run.window_end:%d %b %Y}); "
                 f"confidence: {run.confidence_label}.", f"learning:{run.id}", ntype=NotificationType.INFO)
