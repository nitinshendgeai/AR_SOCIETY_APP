"""Outbox + worker reliability."""
from datetime import datetime, timedelta

import pytest

from app.modules.accounts.models.accounts import Voucher
from app.modules.accounts.services.accounts_service import Line
from app.modules.accounts_agent import worker
from app.modules.accounts_agent.models.agent import AgentEvent, AgentFinding
from app.modules.accounts_agent.services import outbox
from tests.accounts_agent.helpers import D, Rig


@pytest.fixture
def rig(db):
    return Rig(db, "mon")


def events(db, rig, **kw):
    return db.query(AgentEvent).filter(AgentEvent.society_id == rig.sid, *[getattr(AgentEvent, k) == v for k, v in kw.items()]).all()


def test_event_is_created_with_the_voucher_in_the_same_transaction(rig, db):
    v = rig.payment(1, "office_expenses", 500)
    ev = events(db, rig, voucher_id=v.id)
    assert [e.event_type for e in ev] == ["voucher.created"] and ev[0].status == "pending"
    assert ev[0].society_id == v.society_id


def test_rolled_back_transaction_creates_no_event(rig, db):
    before = db.query(AgentEvent).count()
    sp = db.begin_nested()
    rig.svc.build_voucher(rig.sid, "payment", rig.today, [Line(rig.chart["office_expenses"], debit=D("5")),
                                                          Line(rig.chart["bank"], credit=D("5"))])
    assert db.query(AgentEvent).count() == before + 1          # visible inside the transaction …
    sp.rollback()
    assert db.query(AgentEvent).count() == before              # … gone with it: nothing uncommitted is analysed


def test_duplicate_event_is_not_stored_twice(rig, db):
    v = rig.payment(1, "office_expenses", 500)
    outbox._insert_ignoring_duplicates(db.connection(), [{
        "id": __import__("uuid").uuid4(), "society_id": v.society_id, "voucher_id": v.id, "event_type": "voucher.created",
        "idempotency_key": outbox.event_key(v.id, "voucher.created"), "status": "pending", "attempts": 0,
        "next_attempt_at": datetime.utcnow(), "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(), "is_active": True}])
    assert len(events(db, rig, voucher_id=v.id)) == 1


def test_cancel_and_approval_changes_emit_events(rig, db):
    v = rig.payment(1, "office_expenses", 500, approved=False)
    rig.svc.cancel(v, "oops", rig.admin["user"])
    db.commit()
    types = {e.event_type for e in events(db, rig, voucher_id=v.id)}
    assert {"voucher.created", "voucher.cancelled"} <= types


def test_worker_processes_events_and_records_findings(rig, db):
    rig.seed_history()
    bad = rig.payment(0, "office_expenses", 25000)
    out = worker.run_once(db, "t1", limit=500)
    assert out["failed"] == 0 and out["claimed"] > 0
    f = db.query(AgentFinding).filter(AgentFinding.society_id == rig.sid, AgentFinding.voucher_id == bad.id).all()
    assert any(x.rule_code == "S-AMT-01" for x in f)
    assert all(e.status == "done" for e in events(db, rig, voucher_id=bad.id))
    n = db.query(AgentFinding).count()
    assert worker.run_once(db, "t1")["claimed"] == 0                 # nothing left; no second pass
    assert db.query(AgentFinding).count() == n


def test_reprocessing_an_event_never_duplicates_findings(rig, db):
    rig.seed_history()
    bad = rig.payment(0, "office_expenses", 25000)
    worker.run_once(db, "t1", limit=500)
    n = db.query(AgentFinding).filter(AgentFinding.voucher_id == bad.id).count()
    for e in events(db, rig, voucher_id=bad.id):
        e.status, e.next_attempt_at = "pending", datetime.utcnow()
    db.commit()
    worker.run_once(db, "t2", limit=500)
    assert db.query(AgentFinding).filter(AgentFinding.voucher_id == bad.id).count() == n


def test_failed_job_is_retried_with_backoff_then_succeeds(rig, db, monkeypatch):
    v = rig.payment(1, "office_expenses", 500)
    real = worker.process_event
    calls = {"n": 0}

    def flaky(d, e):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real(d, e)
    monkeypatch.setattr(worker, "process_event", flaky)
    out = worker.run_once(db, "t1", limit=500)
    ev = events(db, rig, voucher_id=v.id)[0]
    assert out["failed"] == 1 and ev.status == "failed" and ev.next_attempt_at > datetime.utcnow()
    assert "boom" in ev.last_error
    assert worker.run_once(db, "t1")["claimed"] == 0                 # backing off: not due yet
    ev.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    worker.run_once(db, "t1")
    db.refresh(ev)
    assert ev.status == "done" and ev.attempts == 2


def test_event_is_parked_after_max_attempts_and_admins_notified(rig, db, monkeypatch):
    from app.models.notification import Notification
    v = rig.payment(1, "office_expenses", 500)
    monkeypatch.setattr(worker, "process_event", lambda d, e: (_ for _ in ()).throw(RuntimeError("down")))
    ev = events(db, rig, voucher_id=v.id)[0]
    for _ in range(worker.MAX_ATTEMPTS):
        ev.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
        worker.run_once(db, "t1")
        db.refresh(ev)
    assert ev.status == "dead"
    assert db.query(Notification).filter(Notification.user_id == rig.admin["user"].id, Notification.module == "accounts_agent",
                                         Notification.title.like("%failing%")).count() == 1


def test_worker_restart_recovers_a_claimed_but_unfinished_event(rig, db):
    v = rig.payment(1, "office_expenses", 500)
    ev = events(db, rig, voucher_id=v.id)[0]
    ev.status, ev.locked_by, ev.locked_until, ev.attempts = "processing", "crashed-worker", datetime.utcnow() - timedelta(minutes=5), 1
    db.commit()
    worker.run_once(db, "new-worker")
    db.refresh(ev)
    assert ev.status == "done" and ev.locked_by == "new-worker"


def test_live_lease_is_respected(rig, db):
    v = rig.payment(1, "office_expenses", 500)
    ev = events(db, rig, voucher_id=v.id)[0]
    ev.status, ev.locked_by, ev.locked_until = "processing", "other", datetime.utcnow() + timedelta(minutes=5)
    db.commit()
    assert worker.claim_batch(db, "me") == []


def test_agent_failure_never_interrupts_accounting(rig, db, monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("agent table unavailable")
    monkeypatch.setattr(outbox, "_insert_ignoring_duplicates", broken)
    v = rig.payment(1, "office_expenses", 500)                      # the posting and commit still succeed
    assert db.query(Voucher).filter(Voucher.id == v.id).count() == 1
    assert events(db, rig, voucher_id=v.id) == []


def test_disabled_monitoring_skips_events_and_creates_no_findings(rig, db):
    from app.modules.accounts_agent.services.engine import get_settings
    get_settings(db, rig.sid).monitoring_enabled = False
    v = rig.payment(1, "office_expenses", 0.5 and 500)
    worker.run_once(db, "t1")
    assert events(db, rig, voucher_id=v.id)[0].status == "skipped"


def test_notifications_are_grouped_and_only_to_this_societys_admins(rig, db):
    from app.models.notification import Notification
    other = Rig(db, "mon-other")
    rig.seed_history()
    rig.payment(0, "office_expenses", 25000)
    rig.payment(0, "office_expenses", 26000)
    worker.run_once(db, "t1", limit=500)
    mine = db.query(Notification).filter(Notification.module == "accounts_agent", Notification.user_id == rig.admin["user"].id).all()
    assert 1 <= len(mine) <= 2
    assert db.query(Notification).filter(Notification.user_id.in_([other.admin["user"].id, rig.manager["user"].id]),
                                         Notification.module == "accounts_agent").count() == 0
    worker.run_once(db, "t1")
    again = db.query(Notification).filter(Notification.module == "accounts_agent", Notification.user_id == rig.admin["user"].id).count()
    assert again == len(mine)                                        # no spam on later passes
