"""Accounts Agent API. The society is always taken from the authenticated user (platform admins must name one); a
`society_id` query value is never trusted on its own. Read: manager and above. Review, propose, approve/reject,
settings and learning: admin / committee."""
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.core.dependencies import require_admin_committee, require_manager_above
from app.core.tenant_scope import resolve_create_society_id
from app.db.session import get_db
from app.models.user import User
from app.modules.accounts.models.accounts import Voucher, VoucherEntry
from app.modules.accounts_agent.models.agent import (
    FINDING_STATUSES, SEVERITIES, AgentAuditLog, AgentFinding, AgentLearningRun, AgentProposal,
)
from app.modules.accounts_agent.schemas.agent import (
    FindingReview, MonitoringToggle, ProposalApprove, ProposalReject, SettingsUpdate,
)
from app.modules.accounts_agent.services import audit, learning, llm, notify, proposals, queries
from app.modules.accounts_agent.services.engine import get_settings
from app.utils.local_time import society_today

router = APIRouter(prefix="/accounts-agent", tags=["Accounts Agent"])


def _sid(user: User, society_id: Optional[UUID]) -> UUID:
    return resolve_create_society_id(user, society_id)


@router.get("/status")
def agent_status(society_id: Optional[UUID] = None, db: Session = Depends(get_db), user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    out = queries.status(db, sid)
    db.commit()
    return out


@router.get("/dashboard")
def agent_dashboard(society_id: Optional[UUID] = None, db: Session = Depends(get_db), user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    out = queries.dashboard(db, sid)
    db.commit()
    return out


@router.get("/settings")
def get_agent_settings(society_id: Optional[UUID] = None, db: Session = Depends(get_db), user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    s = get_settings(db, sid)
    db.commit()
    return {**queries.settings_dict(s), "llm_status": llm.provider_status(s.llm_provider)}


@router.put("/settings")
def update_agent_settings(data: SettingsUpdate, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                          user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    s = get_settings(db, sid)
    changes = data.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(s, k, v)
    s.updated_by = user.id
    audit.record(db, sid, "settings_updated", "settings", s.id, user.id, changes)
    db.commit()
    return queries.settings_dict(s)


@router.post("/monitoring")
def set_monitoring(data: MonitoringToggle, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                   user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    s = get_settings(db, sid)
    s.monitoring_enabled, s.updated_by = data.enabled, user.id
    audit.record(db, sid, "monitoring_enabled" if data.enabled else "monitoring_disabled", "settings", s.id, user.id)
    db.commit()
    return queries.status(db, sid)


@router.get("/learning/status")
def learning_status(society_id: Optional[UUID] = None, db: Session = Depends(get_db), user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    run = queries.last_completed_run(db, sid)
    today = society_today(db, sid)
    start, end = learning.window_bounds(today)
    return {"window_months": learning.WINDOW_MONTHS, "window_start": start.isoformat(), "window_end": end.isoformat(),
            "last_run": queries.run_dict(run),
            "limited": bool(run is None or run.confidence_label in ("none", "limited")),
            "message": ("The agent has not learned from this society's books yet." if run is None else
                        "Limited learning confidence: there is little history in the last three months, so statistical checks are conservative."
                        if run.confidence_label in ("none", "limited") else "Learned from the last three months of this society's books.")}


@router.post("/learning/run")
def run_learning(society_id: Optional[UUID] = None, db: Session = Depends(get_db), user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    try:
        run = learning.learn_society(db, sid, triggered_by=user.id)
        audit.record(db, sid, "learning_completed", "learning_run", run.id, user.id,
                     {"vouchers": run.voucher_count, "confidence": run.confidence_label})
        db.commit()
    except Exception:
        try:
            db.commit()                       # keep the run's "failed" record so the learning history shows it
        except Exception:  # noqa: BLE001
            db.rollback()
        raise HTTPException(500, "Learning could not be completed; see the learning history.")
    try:
        notify.notify_learning_complete(db, sid, run)
    except Exception:  # noqa: BLE001
        db.rollback()
    return queries.run_dict(run)


@router.get("/learning/history")
def learning_history(society_id: Optional[UUID] = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                     db: Session = Depends(get_db), user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    q = db.query(AgentLearningRun).filter(AgentLearningRun.society_id == sid)
    total = q.count()
    rows = q.order_by(AgentLearningRun.started_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [queries.run_dict(r) for r in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/findings")
def list_findings(society_id: Optional[UUID] = None, severity: Optional[str] = None, category: Optional[str] = None,
                  status: Optional[str] = None, finding_class: Optional[str] = None, date_from: Optional[date] = None,
                  date_to: Optional[date] = None, q: Optional[str] = Query(None, max_length=100),
                  page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                  db: Session = Depends(get_db), user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    if severity and severity not in SEVERITIES:
        raise HTTPException(422, "Unknown severity")
    if status and status not in FINDING_STATUSES:
        raise HTTPException(422, "Unknown status")
    return queries.list_findings(db, sid, severity=severity, category=category, status=status, finding_class=finding_class,
                                 date_from=date_from, date_to=date_to, q=q, page=page, page_size=page_size)


def _finding(db: Session, sid: UUID, finding_id: UUID) -> AgentFinding:
    f = db.query(AgentFinding).filter(AgentFinding.id == finding_id, AgentFinding.society_id == sid).first()
    if not f:
        raise HTTPException(404, "Finding not found")
    return f


def _voucher_detail(db: Session, sid: UUID, voucher_id) -> Optional[dict]:
    if not voucher_id:
        return None
    v = (db.query(Voucher).options(selectinload(Voucher.entries).joinedload(VoucherEntry.account), selectinload(Voucher.entries).joinedload(VoucherEntry.vendor))
         .filter(Voucher.id == voucher_id, Voucher.society_id == sid).first())
    if not v:
        return None
    return {"id": str(v.id), "voucher_number": v.voucher_number, "voucher_type": v.voucher_type, "voucher_date": v.voucher_date.isoformat(),
            "amount": str(v.amount), "narration": v.narration, "reference": v.reference, "approval_status": v.approval_status,
            "is_cancelled": v.is_cancelled, "source_type": v.source_type,
            "entries": [{"line_no": e.line_no, "account": e.account.name if e.account else None, "debit": str(e.debit), "credit": str(e.credit),
                         "vendor": e.vendor.company_name if e.vendor else None, "narration": e.narration} for e in v.entries]}


@router.get("/findings/{finding_id}")
def finding_detail(finding_id: UUID, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                   user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    f = _finding(db, sid, finding_id)
    d = queries.finding_dict(f, detail=True)
    d["voucher"] = _voucher_detail(db, sid, f.voucher_id)
    d["proposals"] = [queries.proposal_dict(p) for p in f.proposals]
    s = get_settings(db, sid)
    d["ai_explanation"] = llm.explain_finding(s.llm_provider, d)
    return d


@router.post("/findings/{finding_id}/review")
def review_finding(finding_id: UUID, data: FindingReview, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                   user: User = Depends(require_admin_committee)):
    return queries.finding_dict(proposals.review_finding(db, _sid(user, society_id), finding_id, user, data.status, data.note), detail=True)


@router.get("/findings/{finding_id}/history")
def finding_history(finding_id: UUID, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                    user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    f = _finding(db, sid, finding_id)
    pids = [str(p.id) for p in f.proposals]
    ids = [str(f.id)] + pids
    rows = (db.query(AgentAuditLog).filter(AgentAuditLog.society_id == sid, AgentAuditLog.entity_id.in_(ids))
            .order_by(AgentAuditLog.created_at).all())
    return [_audit_dict(r) for r in rows]


@router.post("/findings/{finding_id}/proposals", status_code=201)
def create_proposal(finding_id: UUID, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                    user: User = Depends(require_admin_committee)):
    return queries.proposal_dict(proposals.create_proposal(db, _sid(user, society_id), finding_id, user))


@router.get("/proposals")
def list_proposals(society_id: Optional[UUID] = None, status: Optional[str] = None, page: int = Query(1, ge=1),
                   page_size: int = Query(25, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    q = db.query(AgentProposal).filter(AgentProposal.society_id == sid)
    if status:
        q = q.filter(AgentProposal.status == status)
    total = q.count()
    rows = q.order_by(AgentProposal.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [queries.proposal_dict(p) for p in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/proposals/{proposal_id}")
def proposal_detail(proposal_id: UUID, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                    user: User = Depends(require_manager_above)):
    sid = _sid(user, society_id)
    p = db.query(AgentProposal).filter(AgentProposal.id == proposal_id, AgentProposal.society_id == sid).first()
    if not p:
        raise HTTPException(404, "Proposal not found")
    return queries.proposal_dict(p)


@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: UUID, data: ProposalApprove, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                     user: User = Depends(require_admin_committee)):
    if not data.confirm:
        raise HTTPException(422, "Approval must be explicitly confirmed (confirm: true)")
    return queries.proposal_dict(proposals.approve_proposal(db, _sid(user, society_id), proposal_id, user, data.note))


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: UUID, data: ProposalReject, society_id: Optional[UUID] = None, db: Session = Depends(get_db),
                    user: User = Depends(require_admin_committee)):
    return queries.proposal_dict(proposals.reject_proposal(db, _sid(user, society_id), proposal_id, user, data.reason))


def _audit_dict(r: AgentAuditLog) -> dict:
    return {"id": str(r.id), "created_at": r.created_at.isoformat(), "actor_id": str(r.actor_id) if r.actor_id else None,
            "actor": "Accounts Agent" if r.actor_id is None else "User", "action": r.action, "entity_type": r.entity_type,
            "entity_id": r.entity_id, "details": r.details}


@router.get("/audit-logs")
def audit_logs(society_id: Optional[UUID] = None, action: Optional[str] = None, page: int = Query(1, ge=1),
               page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(require_admin_committee)):
    sid = _sid(user, society_id)
    q = db.query(AgentAuditLog).filter(AgentAuditLog.society_id == sid)
    if action:
        q = q.filter(AgentAuditLog.action == action)
    total = q.count()
    rows = q.order_by(AgentAuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_audit_dict(r) for r in rows], "total": total, "page": page, "page_size": page_size}
