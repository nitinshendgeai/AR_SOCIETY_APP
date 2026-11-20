"""Administrative recovery of dead monitoring events (functional audit D-10).

An event is parked as `dead` after MAX_ATTEMPTS failed analyses. An administrator / committee member of the SAME
society can then either
* requeue it — it gets one fresh round of attempts, at most MAX_REQUEUES times per event, so a permanently broken
  event cannot be retried forever; or
* acknowledge it with a note — it stays dead (nothing is analysed) but no longer marks monitoring as degraded.
Both are audited. Requeueing is idempotent: only a dead event can be requeued, and findings are de-duplicated by their
unique key, so re-analysing a voucher never creates a second finding. No financial record is touched.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.accounts_agent.models.agent import AgentEvent
from app.modules.accounts_agent.services import audit

MAX_REQUEUES = 3
RECENT = timedelta(days=7)


def _get(db: Session, society_id: UUID, event_id: UUID, lock: bool = False) -> AgentEvent:
    q = db.query(AgentEvent).filter(AgentEvent.id == event_id, AgentEvent.society_id == society_id)
    if lock and db.get_bind().dialect.name == "postgresql":
        q = q.with_for_update()
    e = q.first()
    if e is None:
        raise HTTPException(404, "Monitoring event not found")
    return e


def event_dict(e: AgentEvent) -> dict:
    return {"id": str(e.id), "voucher_id": str(e.voucher_id), "event_type": e.event_type, "status": e.status,
            "attempts": e.attempts, "last_error": e.last_error, "created_at": e.created_at.isoformat() if e.created_at else None,
            "dead_at": e.dead_at.isoformat() if e.dead_at else None, "requeue_count": e.requeue_count or 0,
            "requeues_left": max(MAX_REQUEUES - (e.requeue_count or 0), 0),
            "acknowledged": e.acknowledged_at is not None,
            "acknowledged_at": e.acknowledged_at.isoformat() if e.acknowledged_at else None,
            "acknowledged_by": str(e.acknowledged_by) if e.acknowledged_by else None,
            "acknowledge_note": e.acknowledge_note}


def list_dead(db: Session, society_id: UUID, include_acknowledged: bool = True) -> List[dict]:
    q = db.query(AgentEvent).filter(AgentEvent.society_id == society_id, AgentEvent.status == "dead")
    if not include_acknowledged:
        q = q.filter(AgentEvent.acknowledged_at.is_(None))
    return [event_dict(e) for e in q.order_by(AgentEvent.created_at.desc()).limit(200)]


def requeue(db: Session, society_id: UUID, event_id: UUID, user) -> AgentEvent:
    e = _get(db, society_id, event_id, lock=True)
    if e.status != "dead":
        raise HTTPException(409, f"Only a failed (dead) event can be requeued; this one is {e.status}.")
    if (e.requeue_count or 0) >= MAX_REQUEUES:
        raise HTTPException(409, f"This event has already been requeued {MAX_REQUEUES} times and keeps failing. "
                                 "Acknowledge it with a note and report the error to support.")
    e.status, e.attempts, e.next_attempt_at = "pending", 0, datetime.utcnow()
    e.locked_until = e.locked_by = None
    e.requeue_count = (e.requeue_count or 0) + 1
    e.acknowledged_at = e.acknowledged_by = e.acknowledge_note = None
    audit.record(db, society_id, "event_requeued", "event", e.id, user.id,
                 {"voucher_id": str(e.voucher_id), "event_type": e.event_type, "requeue_count": e.requeue_count,
                  "last_error": (e.last_error or "")[:200]})
    db.commit()
    return e


def acknowledge(db: Session, society_id: UUID, event_id: UUID, user, note: str) -> AgentEvent:
    note = (note or "").strip()
    if len(note) < 5:
        raise HTTPException(422, "Say why the failure is being acknowledged (at least a few words).")
    e = _get(db, society_id, event_id, lock=True)
    if e.status != "dead":
        raise HTTPException(409, f"Only a failed (dead) event can be acknowledged; this one is {e.status}.")
    if e.acknowledged_at is not None:
        return e                                            # idempotent
    e.acknowledged_at, e.acknowledged_by, e.acknowledge_note = datetime.utcnow(), user.id, note[:500]
    audit.record(db, society_id, "event_acknowledged", "event", e.id, user.id,
                 {"voucher_id": str(e.voucher_id), "event_type": e.event_type, "note": note[:200]})
    db.commit()
    return e


def counts(db: Session, society_id: UUID, now: Optional[datetime] = None) -> dict:
    """Unacknowledged dead events (degrade monitoring), of which recent; and acknowledged historical ones (do not)."""
    now = now or datetime.utcnow()
    rows = db.query(AgentEvent.acknowledged_at, AgentEvent.dead_at, AgentEvent.created_at).filter(
        AgentEvent.society_id == society_id, AgentEvent.status == "dead").all()
    open_ = [r for r in rows if r[0] is None]
    recent = [r for r in open_ if (r[1] or r[2]) and now - (r[1] or r[2]) <= RECENT]
    return {"unacknowledged": len(open_), "recent": len(recent), "acknowledged": len(rows) - len(open_)}
