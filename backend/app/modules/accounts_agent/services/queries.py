"""Read models for the API. Every query filters by society_id."""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.modules.accounts_agent.models.agent import (
    OPEN_FINDING_STATUSES, SEVERITIES, AgentEvent, AgentFinding, AgentLearningRun, AgentProposal, AgentSettings,
)
from app.modules.accounts_agent.models.agent import UNIFIED_CLASS
from app.modules.accounts_agent.services.engine import get_settings

HUMAN_REVIEW = {"NEW": "PENDING_REVIEW", "UNDER_REVIEW": "IN_REVIEW", "APPROVED": "REVIEWED_CONFIRMED",
                "REJECTED": "REVIEWED_NOT_AN_ISSUE", "RESOLVED": "REVIEWED_RESOLVED", "IGNORED": "REVIEWED_IGNORED"}
from app.modules.accounts_agent.services.learning import WINDOW_MONTHS

DELAY_AFTER = timedelta(minutes=5)


def settings_dict(s: AgentSettings) -> dict:
    return {"monitoring_enabled": s.monitoring_enabled, "notify_min_severity": s.notify_min_severity,
            "z_threshold": s.z_threshold, "recurring_tolerance_pct": s.recurring_tolerance_pct,
            "duplicate_window_days": s.duplicate_window_days, "llm_provider": s.llm_provider,
            "learning_window_months": WINDOW_MONTHS}


def run_dict(r: Optional[AgentLearningRun]) -> Optional[dict]:
    if r is None:
        return None
    return {"id": str(r.id), "status": r.status, "window_start": r.window_start.isoformat(), "window_end": r.window_end.isoformat(),
            "started_at": r.started_at.isoformat(), "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "voucher_count": r.voucher_count, "line_count": r.line_count, "months_covered": r.months_covered,
            "days_covered": r.days_covered, "pattern_count": r.pattern_count, "confidence_score": r.confidence_score,
            "confidence_label": r.confidence_label, "summary": r.summary, "error": r.error}


def last_completed_run(db: Session, society_id: UUID) -> Optional[AgentLearningRun]:
    return (db.query(AgentLearningRun).filter(AgentLearningRun.society_id == society_id, AgentLearningRun.status == "completed")
            .order_by(AgentLearningRun.started_at.desc()).first())


def status(db: Session, society_id: UUID) -> dict:
    s = get_settings(db, society_id)
    now = datetime.utcnow()
    backlog = db.query(func.count(AgentEvent.id)).filter(
        AgentEvent.society_id == society_id, AgentEvent.status.in_(("pending", "failed", "processing"))).scalar() or 0
    oldest = db.query(func.min(AgentEvent.created_at)).filter(
        AgentEvent.society_id == society_id, AgentEvent.status.in_(("pending", "failed", "processing"))).scalar()
    dead = db.query(func.count(AgentEvent.id)).filter(AgentEvent.society_id == society_id, AgentEvent.status == "dead").scalar() or 0
    if not s.monitoring_enabled:
        state = "disabled"
    elif dead:
        state = "degraded"
    elif oldest and now - oldest > DELAY_AFTER:
        state = "delayed"
    else:
        state = "operational"
    run = last_completed_run(db, society_id)
    return {"state": state, "monitoring_enabled": s.monitoring_enabled, "last_monitored_at": s.last_monitored_at.isoformat() if s.last_monitored_at else None,
            "pending_events": backlog, "failed_events": dead, "last_error": s.last_error,
            "last_learning_at": run.finished_at.isoformat() if run and run.finished_at else None,
            "learning_confidence": run.confidence_label if run else "none"}


def dashboard(db: Session, society_id: UUID) -> dict:
    sev = dict(db.query(AgentFinding.severity, func.count(AgentFinding.id)).filter(
        AgentFinding.society_id == society_id, AgentFinding.status.in_(OPEN_FINDING_STATUSES)).group_by(AgentFinding.severity).all())
    resolved = db.query(func.count(AgentFinding.id)).filter(AgentFinding.society_id == society_id, AgentFinding.status == "RESOLVED").scalar() or 0
    pending = db.query(func.count(AgentProposal.id)).filter(AgentProposal.society_id == society_id, AgentProposal.status == "PENDING").scalar() or 0
    analysed = db.query(func.count(func.distinct(AgentEvent.voucher_id))).filter(
        AgentEvent.society_id == society_id, AgentEvent.status == "done").scalar() or 0
    run = last_completed_run(db, society_id)
    return {"status": status(db, society_id), "transactions_analysed": analysed,
            "findings_open": {s: int(sev.get(s, 0)) for s in SEVERITIES}, "resolved_findings": resolved, "pending_approvals": pending,
            "learning": {"window_months": WINDOW_MONTHS, "last_run": run_dict(run)}}


def finding_dict(f: AgentFinding, detail: bool = False) -> dict:
    d = {"id": str(f.id), "voucher_id": str(f.voucher_id) if f.voucher_id else None, "transaction_ref": f.transaction_ref,
         "voucher_date": f.voucher_date.isoformat() if f.voucher_date else None, "category": f.category,
         "finding_class": f.finding_class, "severity": f.severity, "confidence": f.confidence, "rule_code": f.rule_code,
         "title": f.title, "status": f.status, "created_at": f.created_at.isoformat(), "learning_confidence": f.learning_confidence,
         "explanation": f.explanation, "recommended_action": f.recommended_action,
         "classification": UNIFIED_CLASS.get(f.finding_class, "ADVISORY_OBSERVATION"),
         "engine": f.engine or "accounting", "compliance_category": f.compliance_category,
         "legal_rule_code": f.legal_rule_code, "flat_id": str(f.flat_id) if f.flat_id else None,
         "vendor_id": str(f.vendor_id) if f.vendor_id else None,
         "human_review_status": HUMAN_REVIEW.get(f.status, "PENDING_REVIEW"), "resolution_status": f.status}
    if detail:
        d["legal_source"] = f.legal_source
        d.update({"expected_behaviour": f.expected_behaviour, "actual_behaviour": f.actual_behaviour, "evidence": f.evidence,
                  "reviewed_by": str(f.reviewed_by) if f.reviewed_by else None,
                  "reviewed_at": f.reviewed_at.isoformat() if f.reviewed_at else None, "resolution_note": f.resolution_note,
                  "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None})
    return d


def proposal_dict(p: AgentProposal) -> dict:
    return {"id": str(p.id), "society_id": str(p.society_id), "finding_id": str(p.finding_id), "voucher_id": str(p.voucher_id) if p.voucher_id else None,
            "action_type": p.action_type, "status": p.status, "title": p.title, "explanation": p.explanation,
            "before": p.before_values, "after": p.after_values, "impact": p.impact, "executable": p.executable,
            "created_at": p.created_at.isoformat(), "decided_at": p.decided_at.isoformat() if p.decided_at else None,
            "decision_note": p.decision_note, "result": p.result,
            "created_by": str(p.created_by) if p.created_by else None, "decided_by": str(p.decided_by) if p.decided_by else None,
            "requires_other_approver": p.action_type in ("cancel_voucher", "edit_voucher")}


def list_findings(db: Session, society_id: UUID, *, severity=None, category=None, status=None, finding_class=None,
                  date_from=None, date_to=None, q=None, page=1, page_size=25, engine=None, compliance_category=None,
                  classification=None, flat_id=None, vendor_id=None, section=None) -> dict:
    from app.modules.accounts_agent.legal.sections import CLAIMED, SECTIONS
    qry = db.query(AgentFinding).filter(AgentFinding.society_id == society_id)
    if section in SECTIONS:
        cats = SECTIONS[section][1]
        qry = qry.filter(AgentFinding.category.in_(cats) if cats else AgentFinding.category.notin_(CLAIMED))
    if engine:
        qry = qry.filter(AgentFinding.engine == engine)
    if compliance_category:
        qry = qry.filter(AgentFinding.compliance_category == compliance_category)
    if classification:
        qry = qry.filter(AgentFinding.finding_class.in_([k for k, v in UNIFIED_CLASS.items() if v == classification]))
    if flat_id:
        qry = qry.filter(AgentFinding.flat_id == flat_id)
    if vendor_id:
        qry = qry.filter(AgentFinding.vendor_id == vendor_id)
    if severity:
        qry = qry.filter(AgentFinding.severity == severity)
    if category:
        qry = qry.filter(AgentFinding.category == category)
    if status:
        qry = qry.filter(AgentFinding.status == status)
    if finding_class:
        qry = qry.filter(AgentFinding.finding_class == finding_class)
    if date_from:
        qry = qry.filter(AgentFinding.voucher_date >= date_from)
    if date_to:
        qry = qry.filter(AgentFinding.voucher_date <= date_to)
    if q:
        like = f"%{q.strip().replace('%', '').replace('_', '')}%"
        qry = qry.filter(or_(AgentFinding.title.ilike(like), AgentFinding.transaction_ref.ilike(like),
                             AgentFinding.explanation.ilike(like)))
    total = qry.count()
    rank = {s: i for i, s in enumerate(SEVERITIES)}
    from sqlalchemy import case
    order = case(*[(AgentFinding.severity == s, i) for s, i in rank.items()], else_=9)
    rows = qry.order_by(order, AgentFinding.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [finding_dict(f) for f in rows], "total": total, "page": page, "page_size": page_size}
