"""Accounts Agent worker — a separate, independently recoverable process.

    python -m app.modules.accounts_agent.worker            # run forever
    python -m app.modules.accounts_agent.worker --once     # drain what is due, then exit (cron / tests)

Reliability model
* The API only writes outbox rows (same transaction as the voucher). It never starts threads for the agent.
* This worker claims rows with a lease (`locked_until`); PostgreSQL uses FOR UPDATE SKIP LOCKED so several workers can
  run side by side. A worker that dies leaves a `processing` row whose lease expires; the next claim recovers it.
* Each event is processed in its own transaction; findings are idempotent (unique dedupe key), so a retry — or a
  duplicate delivery — never creates a second finding.
* Failures back off exponentially; after MAX_ATTEMPTS the event is parked as `dead` and admins are notified.
* Nothing here can block or fail a financial transaction: the accounting side never waits for this process.
"""
import argparse
import logging
import os
import signal
import socket
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.modules.accounts_agent.models.agent import AgentEvent, AgentLearningRun, AgentSettings
from app.modules.accounts_agent.services import audit, notify
from app.modules.accounts_agent.services.engine import get_settings, process_event
from app.modules.accounts_agent.services.learning import learn_society

logger = logging.getLogger("accounts_agent.worker")

BATCH_SIZE = 50
LEASE_SECONDS = 120
MAX_ATTEMPTS = 6
POLL_SECONDS = 5
RELEARN_AFTER = timedelta(hours=24)
RETENTION = timedelta(days=30)
BACKOFF_BASE_SECONDS = 30
BACKOFF_CAP_SECONDS = 3600


def backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2 ** max(0, attempts - 1))))


def claim_batch(db: Session, worker_id: str, limit: int = BATCH_SIZE, now: Optional[datetime] = None) -> List[UUID]:
    """Lease up to `limit` due events: new ones, ones whose retry time has come, and ones a dead worker left behind."""
    now = now or datetime.utcnow()
    q = db.query(AgentEvent).filter(_due_filter(now)).order_by(AgentEvent.created_at).limit(limit)
    if db.get_bind().dialect.name == "postgresql":
        q = q.with_for_update(skip_locked=True)
    ids = []
    for e in q.all():
        e.attempts += 1
        if e.attempts > MAX_ATTEMPTS:
            e.status, e.last_error, e.locked_until = "dead", (e.last_error or "gave up after repeated crashes"), None
            e.dead_at = now
            notify.notify_job_failure(db, e.society_id, e.id, e.attempts - 1)
            continue
        e.status, e.locked_by, e.locked_until = "processing", worker_id, now + timedelta(seconds=LEASE_SECONDS)
        ids.append(e.id)
    db.commit()
    return ids


def _due_filter(now: datetime):
    return or_(and_(AgentEvent.status.in_(("pending", "failed")), AgentEvent.next_attempt_at <= now),
               and_(AgentEvent.status == "processing", AgentEvent.locked_until < now))


def due_societies(db: Session, limit: int = BATCH_SIZE, now: Optional[datetime] = None) -> List[UUID]:
    """Societies that have events due in the next batch (read only, no lease)."""
    now = now or datetime.utcnow()
    rows = db.query(AgentEvent.society_id, AgentEvent.created_at).filter(_due_filter(now)) \
        .order_by(AgentEvent.created_at).limit(limit).all()
    db.commit()                               # end the read transaction before learning starts its own work
    return list(dict.fromkeys(r[0] for r in rows))


def _ensure_profile(db: Session, society_id: UUID, done: set) -> None:
    """A society's first event bootstraps its learning profile; later runs refresh it daily."""
    if society_id in done:
        return
    done.add(society_id)
    last = (db.query(AgentLearningRun.started_at).filter(AgentLearningRun.society_id == society_id,
                                                         AgentLearningRun.status == "completed")
            .order_by(AgentLearningRun.started_at.desc()).first())
    if last is None or datetime.utcnow() - last[0] > RELEARN_AFTER:
        try:
            run = learn_society(db, society_id)
            audit.record(db, society_id, "learning_completed", "learning_run", run.id,
                         details={"vouchers": run.voucher_count, "confidence": run.confidence_label})
            db.commit()
            if last is None:
                notify.notify_learning_complete(db, society_id, run)
        except Exception:  # noqa: BLE001 — a failed learning run must not stop monitoring
            try:
                db.commit()                   # keep the run's "failed" record in the learning history
            except Exception:  # noqa: BLE001
                db.rollback()
            logger.exception("[accounts-agent] learning failed society=%s", society_id)
            try:
                s = get_settings(db, society_id)
                s.last_error = "learning failed; see worker log"
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()


def _fail(db: Session, event_id: UUID, exc: Exception) -> None:
    db.rollback()
    e = db.get(AgentEvent, event_id)
    if e is None:
        return
    e.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"          # no financial data in the error text
    e.locked_until = None
    if e.attempts >= MAX_ATTEMPTS:
        e.status, e.dead_at = "dead", datetime.utcnow()
        notify.notify_job_failure(db, e.society_id, e.id, e.attempts)
    else:
        e.status, e.next_attempt_at = "failed", datetime.utcnow() + backoff(e.attempts)
    try:
        s = get_settings(db, e.society_id)
        s.last_error = "monitoring job failed; will retry" if e.status == "failed" else "monitoring job parked after repeated failures"
    except Exception:  # noqa: BLE001
        pass
    db.commit()


def run_once(db: Session, worker_id: Optional[str] = None, limit: int = BATCH_SIZE) -> Dict[str, int]:
    """Claim and process one batch. Returns counts. Safe to call from tests or cron."""
    worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
    learned: set = set()
    # Refresh learning profiles BEFORE leasing anything: a long learning run must not outlast the leases of the batch
    # (another worker would then re-claim and re-process those events).
    for sid in due_societies(db, limit):
        _ensure_profile(db, sid, learned)
    ids = claim_batch(db, worker_id, limit)
    out = {"claimed": len(ids), "done": 0, "failed": 0, "findings": 0}
    by_society: Dict[UUID, list] = {}
    for eid in ids:
        e = db.get(AgentEvent, eid)
        if e is None or e.status != "processing" or e.locked_by != worker_id:
            continue
        try:
            _ensure_profile(db, e.society_id, learned)        # no-op unless the society was not due before the claim
            new = process_event(db, e)
            db.commit()
            out["done"] += 1
            out["findings"] += len(new)
            by_society.setdefault(e.society_id, []).extend(new)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[accounts-agent] event %s failed: %s", eid, type(exc).__name__)
            _fail(db, eid, exc)
            out["failed"] += 1
    for sid, findings in by_society.items():          # notifications after the findings are safely committed
        try:
            notify.notify_findings(db, sid, findings)
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("[accounts-agent] notification failed society=%s", sid)
    return out


MAX_DRAIN_PASSES = 1000          # a hard stop for --once: 1,000 batches of BATCH_SIZE events


def drain(db: Session, worker_id: Optional[str] = None, limit: int = BATCH_SIZE,
          max_passes: int = MAX_DRAIN_PASSES) -> Dict[str, int]:
    """Process every event that is due NOW, batch by batch, until a claim comes back empty (D-08 of the functional
    audit: `--once` used to stop after one batch). It cannot loop forever on a failing event: a failure sets the event's
    next attempt in the future (backoff), so it is not due again during this drain, and the number of passes is capped."""
    total = {"claimed": 0, "done": 0, "failed": 0, "findings": 0, "passes": 0}
    for _ in range(max_passes):
        counts = run_once(db, worker_id, limit)
        total["passes"] += 1
        for k in ("claimed", "done", "failed", "findings"):
            total[k] += counts.get(k, 0)
        if not counts.get("claimed"):
            break
    return total


SCAN_EVERY = timedelta(hours=24)


def scan_due(db: Session, limit: int = 20) -> int:
    """The daily society-wide compliance scan (Engine B). One society at a time, each in its own transaction, so a
    failure in one society never affects another and no society's data is read for another."""
    from app.modules.accounts_agent.legal import compliance
    from app.modules.accounts_agent.models.agent import AgentAuditLog, AgentSettings
    cutoff = datetime.utcnow() - SCAN_EVERY
    done = 0
    for (sid,) in db.query(AgentSettings.society_id).filter(AgentSettings.monitoring_enabled == True).all():  # noqa: E712
        if done >= limit:
            break
        last = (db.query(AgentAuditLog.created_at).filter(AgentAuditLog.society_id == sid, AgentAuditLog.action == "compliance_scan")
                .order_by(AgentAuditLog.created_at.desc()).first())
        if last and last[0] > cutoff:
            continue
        try:
            out = compliance.run_scan(db, sid)
            created = out.pop("_created")
            db.commit()
            done += 1
            notify.notify_findings(db, sid, created)
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("[accounts-agent] compliance scan failed society=%s", sid)
    return done


def maintenance(db: Session) -> int:
    """Drop old finished outbox rows (findings keep the record)."""
    cutoff = datetime.utcnow() - RETENTION
    n = (db.query(AgentEvent).filter(AgentEvent.status.in_(("done", "skipped")), AgentEvent.processed_at < cutoff)
         .delete(synchronize_session=False))
    db.commit()
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Accounts Agent monitoring worker")
    ap.add_argument("--once", action="store_true",
                    help="process every event that is due now, batch by batch, then exit")
    ap.add_argument("--scan", action="store_true", help="run the due daily compliance scans, then exit")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    import app.models  # noqa: F401 — register every model
    from app.db.session import get_session_factory
    stop = {"flag": False}
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.update(flag=True))
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    if args.scan:
        db = get_session_factory()()
        try:
            logger.info("[accounts-agent] compliance scans run: %d", scan_due(db, limit=10_000))
        finally:
            db.close()
        return 0
    logger.info("[accounts-agent] worker %s started", worker_id)
    last_maint = 0.0
    while not stop["flag"]:
        db = get_session_factory()()
        try:
            if args.once:
                counts = drain(db, worker_id)
                logger.info("[accounts-agent] drained: %s", counts)
                break
            counts = run_once(db, worker_id)
            if time.time() - last_maint > 3600:
                maintenance(db)
                scan_due(db)
                last_maint = time.time()
        except Exception:  # noqa: BLE001 — the loop itself must survive a database blip
            logger.exception("[accounts-agent] worker pass failed")
            counts = {"claimed": 0}
        finally:
            db.close()
        if args.once:
            break
        if not counts.get("claimed"):
            time.sleep(POLL_SECONDS)
    logger.info("[accounts-agent] worker stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
