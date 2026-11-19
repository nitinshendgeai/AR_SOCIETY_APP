"""Transactional outbox for the Accounts Agent.

A SQLAlchemy `after_flush` listener turns every voucher change into a row of `accounts_agent_events`, written on the
SAME connection and transaction as the voucher itself:

  * commit   → voucher and event become durable together;
  * rollback → (incl. a rolled-back posting SAVEPOINT) both vanish, so an uncommitted transaction is never analysed.

Hooking the flush instead of individual endpoints covers every posting pathway (`AccountsService.build_voucher` is the
only place a Voucher is constructed) and any pathway added later.

The listener must never break a financial transaction: the insert runs in its own SAVEPOINT, uses ON CONFLICT DO
NOTHING (duplicate events are impossible) and every exception is logged and swallowed.
"""
import logging
from datetime import datetime
from typing import Iterable, List, Tuple

from sqlalchemy import event, inspect as sa_inspect
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
_installed = False

# Voucher columns whose change is worth re-analysing, and the event each produces.
_STATE_EVENTS = (
    ("is_cancelled", "voucher.cancelled"),
    ("approval_status", "voucher.approval_changed"),
    ("edited_at", "voucher.edited"),
    ("reversed_at", "voucher.reversed"),
)


def event_key(voucher_id, event_type: str, token: str = "") -> str:
    """Idempotency key: the same voucher change can only ever produce one event."""
    return f"{event_type}:{voucher_id}:{token}"[:160]


def _changed(obj, attr: str):
    state = sa_inspect(obj)
    hist = state.attrs[attr].history
    return hist.has_changes(), (hist.added[0] if hist.added else None)


def collect_events(session: Session) -> List[Tuple[object, str, str]]:
    """(voucher, event_type, key) for every voucher change in the flush that just happened."""
    from app.modules.accounts.models.accounts import Voucher
    out: List[Tuple[object, str, str]] = []
    for obj in session.new:
        if isinstance(obj, Voucher):
            out.append((obj, "voucher.created", event_key(obj.id, "voucher.created")))
    for obj in session.dirty:
        if not isinstance(obj, Voucher) or not session.is_modified(obj, include_collections=False):
            continue
        for attr, etype in _STATE_EVENTS:
            changed, new = _changed(obj, attr)
            if not changed:
                continue
            if attr == "is_cancelled" and not new:
                continue                                   # un-cancel never happens; ignore
            token = new.isoformat() if isinstance(new, datetime) else str(new)
            out.append((obj, etype, event_key(obj.id, etype, token)))
    return out


def _insert_ignoring_duplicates(connection, rows: Iterable[dict]) -> None:
    from app.modules.accounts_agent.models.agent import AgentEvent
    table = AgentEvent.__table__
    if connection.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    for row in rows:
        connection.execute(insert(table).values(**row).on_conflict_do_nothing(index_elements=["idempotency_key"]))


def _after_flush(session: Session, flush_context) -> None:
    try:
        found = collect_events(session)
        if not found:
            return
        now = datetime.utcnow()
        import uuid
        rows = [{
            "id": uuid.uuid4(), "society_id": v.society_id, "voucher_id": v.id, "event_type": etype,
            "idempotency_key": key, "status": "pending", "attempts": 0, "next_attempt_at": now,
            "created_at": now, "updated_at": now, "is_active": True,
        } for v, etype, key in found]
        connection = session.connection()
        with connection.begin_nested():
            _insert_ignoring_duplicates(connection, rows)
    except Exception:  # noqa: BLE001 — monitoring must never block a financial transaction
        logger.exception("[accounts-agent] could not enqueue monitoring event; the transaction continues")


def install_outbox_listener() -> None:
    global _installed
    if _installed:
        return
    event.listen(Session, "after_flush", _after_flush)
    _installed = True
