"""Regression tests for the functional-audit defects D-05 … D-10 (monitoring and intelligence)."""
import json
from datetime import date, datetime, timedelta

import pytest

from app.modules.accounts_agent import worker
from app.modules.accounts_agent.legal import calendar as cal
from app.modules.accounts_agent.legal.models import ComplianceItem
from app.modules.accounts_agent.models.agent import AgentAuditLog, AgentEvent, AgentFinding
from app.modules.accounts_agent.services import queries
from app.modules.billing.models.billing import ChargeType
from app.modules.accounts.services.accounts_service import fiscal_year
from tests.accounts_agent.helpers import Rig, codes
from tests.accounts_agent.legal_helpers import LRig

API = "/api/v1/accounts-agent"


@pytest.fixture
def lrig(db):
    return LRig(db, "p3")


def _last_fy(today):
    return fiscal_year(date(today.year - (0 if today.month >= 4 else 1) - 1, 4, 1))


# ── D-05: statutory calendar before registration / onboarding ──────────────────────────────────────────────────

def test_d05_new_society_without_registration_date_is_asked_to_confirm_not_told_overdue(lrig, db):
    lrig.scan()                                            # the society was created (onboarded) today
    agm = db.query(ComplianceItem).filter(ComplianceItem.society_id == lrig.sid, ComplianceItem.code == "AGM",
                                          ComplianceItem.financial_period == _last_fy(lrig.today)).one()
    assert agm.applicability == cal.PV and "started using the app" in agm.applicability_reason
    for f in lrig.findings("L-CAL-01"):
        assert f.finding_class == "ADVISORY_OBSERVATION" and "confirm whether it applies" in f.title
    for f in lrig.findings("L-AUD-01"):
        assert f.finding_class == "ADVISORY_OBSERVATION" and f.severity == "LOW"


def test_d05_years_before_registration_are_not_applicable(lrig, db):
    lrig.registered(lrig.today - timedelta(days=10))       # registered after last year ended
    lrig.scan()
    agm = db.query(ComplianceItem).filter(ComplianceItem.society_id == lrig.sid, ComplianceItem.code == "AGM",
                                          ComplianceItem.financial_period == _last_fy(lrig.today)).one()
    assert agm.applicability == "NOT_APPLICABLE" and "registered on" in agm.applicability_reason
    assert [f for f in lrig.findings("L-CAL-01") if f.evidence["period"] == _last_fy(lrig.today)] == []
    assert lrig.findings("L-AUD-01") == []


def test_d05_established_society_overdue_is_still_reported(lrig, db):
    lrig.registered(date(2005, 6, 1))
    lrig.scan()
    agm = db.query(ComplianceItem).filter(ComplianceItem.society_id == lrig.sid, ComplianceItem.code == "AGM",
                                          ComplianceItem.financial_period == _last_fy(lrig.today)).one()
    assert agm.applicability == "APPLICABLE"
    if agm.due_date < lrig.today:
        f = [x for x in lrig.findings("L-CAL-01") if x.evidence["item"] == "AGM"]
        assert f and f[0].finding_class == "POTENTIAL_NON_COMPLIANCE" and "overdue" in f[0].title


def test_d05_a_persons_own_choice_is_never_overwritten(lrig, db):
    lrig.registered(date(2005, 6, 1))
    lrig.scan()
    agm = db.query(ComplianceItem).filter(ComplianceItem.society_id == lrig.sid, ComplianceItem.code == "AGM",
                                          ComplianceItem.financial_period == _last_fy(lrig.today)).one()
    cal.update_item(db, agm, lrig.admin["user"], {"applicability": "APPLICABLE", "applicability_reason": "AGM held late"})
    db.commit()
    lrig.registered(lrig.today - timedelta(days=10))
    lrig.scan()
    db.refresh(agm)
    assert agm.applicability == "APPLICABLE"


# ── D-06: interest — rate versus accrual period ─────────────────────────────────────────────────────────────────

def _interest_bill(r, rate, to_days_after_bill):
    fl = r.flat_rows[0]
    old = r.cycle(r.today - timedelta(days=100), r.today - timedelta(days=70), name="Old")
    r.bill(fl, old, [(ChargeType.MAINTENANCE, "Service Charges", 10000, 10000)])
    cy = r.cycle(r.today - timedelta(days=40), r.today - timedelta(days=10), name="New")
    b = r.bill(fl, cy, [(ChargeType.MAINTENANCE, "Service Charges", 2000, 2000),
                        (ChargeType.PENALTY, "Interest on arrears", 500, 500)], previous_dues=10000)
    start = old.due_date
    end = b.bill_date + timedelta(days=to_days_after_bill)
    b.interest_working = json.dumps([{"bill": "INV-OLD", "principal": "10000.00", "from": start.isoformat(),
                                      "to": end.isoformat(), "days": (end - start).days, "rate": str(rate),
                                      "interest": "500.00"}])
    r.db.commit()
    return b


def test_d06_period_past_the_bill_date_is_named_as_the_cause(lrig):
    _interest_bill(lrig, 12, 66)
    lrig.scan()
    (f,) = lrig.findings("L-CHG-INT-02")
    assert f.evidence["cause"] == "PERIOD" and "runs past the bill date" in f.title
    assert "66 day(s) after the bill date" in f.explanation and "not only the rate" in f.explanation


def test_d06_rate_above_the_ceiling_is_named_as_the_cause(lrig):
    _interest_bill(lrig, 21, 0)
    lrig.scan()
    (f,) = lrig.findings("L-CHG-INT-02")
    assert f.evidence["cause"] == "RATE" and "21% p.a., above the 12" in f.explanation


def test_d06_without_a_working_the_cause_is_not_guessed(lrig):
    b = _interest_bill(lrig, 12, 0)
    b.interest_working = None
    lrig.db.commit()
    lrig.scan()
    (f,) = lrig.findings("L-CHG-INT-02")
    assert f.evidence["cause"] == "UNKNOWN" and "cannot be shown" in f.explanation


# ── D-07: large expense while history is limited ────────────────────────────────────────────────────────────────

@pytest.fixture
def rig(db):
    return Rig(db, "p3b")


def test_d07_large_expense_is_flagged_without_statistics(rig):
    for d in (20, 12, 5):
        rig.payment(d, "office_expenses", 1000)
    run = rig.learn()
    assert run.confidence_label in ("none", "limited")
    d = next(x for x in rig.analyse(rig.payment(0, "office_expenses", 45000)) if x.rule_code == "R-AMT-LIM-01")
    assert d.finding_class == "informational" and d.evidence["method"] == "deterministic comparison"
    assert d.evidence["largest_prior_posting"] == "1000.00" and "not a statistical judgement" in d.explanation


def test_d07_ordinary_and_small_expenses_are_left_alone(rig):
    for dd in (20, 12, 5):
        rig.payment(dd, "office_expenses", 1000)
    rig.learn()
    assert "R-AMT-LIM-01" not in codes(rig.analyse(rig.payment(0, "office_expenses", 1500)))
    assert "R-AMT-LIM-01" not in codes(rig.analyse(rig.payment(0, "office_expenses", 9000)))   # under the floor


def test_d07_does_not_run_once_history_is_adequate(rig):
    rig.seed_history()
    run = rig.learn()
    run.confidence_label = "moderate"                     # as a society with adequate history would be
    rig.db.commit()
    assert "R-AMT-LIM-01" not in codes(rig.analyse(rig.payment(0, "office_expenses", 45000)))


# ── D-08: --once drains the whole queue ─────────────────────────────────────────────────────────────────────────

def test_d08_drain_processes_more_than_one_batch(rig, db):
    for i in range(7):
        rig.payment(1, "office_expenses", 100 + i)
    pending = db.query(AgentEvent).filter(AgentEvent.society_id == rig.sid, AgentEvent.status == "pending").count()
    assert pending >= 7
    out = worker.drain(db, "w", limit=3)
    assert out["passes"] >= 3 and out["claimed"] == pending
    assert db.query(AgentEvent).filter(AgentEvent.society_id == rig.sid, AgentEvent.status == "pending").count() == 0


def test_d08_a_failing_event_does_not_loop(rig, db, monkeypatch):
    rig.payment(1, "office_expenses", 100)
    monkeypatch.setattr(worker, "process_event", lambda d, e: (_ for _ in ()).throw(RuntimeError("down")))
    out = worker.drain(db, "w", limit=10)
    assert out["failed"] >= 1 and out["passes"] == 2           # failed once, backed off, then nothing was due


def test_d08_cli_once_drains(rig, db, monkeypatch):
    calls = []
    monkeypatch.setattr(worker, "drain", lambda d, w: calls.append(w) or {"claimed": 0})
    import app.db.session as sess
    monkeypatch.setattr(sess, "get_session_factory", lambda: (lambda: db))
    monkeypatch.setattr(db, "close", lambda: None)
    assert worker.main(["--once"]) == 0 and len(calls) == 1


# ── D-10: dead events — requeue / acknowledge ───────────────────────────────────────────────────────────────────

def _dead(rig, db, monkeypatch):
    v = rig.payment(1, "office_expenses", 500)
    ev = db.query(AgentEvent).filter(AgentEvent.voucher_id == v.id).first()
    with monkeypatch.context() as m:
        m.setattr(worker, "process_event", lambda d, e: (_ for _ in ()).throw(RuntimeError("down")))
        for _ in range(worker.MAX_ATTEMPTS):
            ev.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
            db.commit()
            worker.run_once(db, "t1")
            db.refresh(ev)
    assert ev.status == "dead" and ev.dead_at is not None
    return v, ev


def test_d10_requeue_reprocesses_without_duplicate_findings(client, rig, db, monkeypatch):
    v, ev = _dead(rig, db, monkeypatch)
    assert queries.status(db, rig.sid)["state"] == "degraded"
    r = client.post(f"{API}/events/{ev.id}/requeue", headers=rig.admin["headers"])
    assert r.status_code == 200 and r.json()["status"] == "pending" and r.json()["requeue_count"] == 1
    worker.drain(db, "w")
    db.refresh(ev)
    assert ev.status == "done"
    assert queries.status(db, rig.sid)["state"] != "degraded"
    before = db.query(AgentFinding).filter(AgentFinding.voucher_id == v.id).count()
    worker.drain(db, "w")
    assert db.query(AgentFinding).filter(AgentFinding.voucher_id == v.id).count() == before
    assert client.post(f"{API}/events/{ev.id}/requeue", headers=rig.admin["headers"]).status_code == 409   # not dead
    assert db.query(AgentAuditLog).filter(AgentAuditLog.action == "event_requeued").count() == 1


def test_d10_requeue_limit(client, rig, db, monkeypatch):
    from app.modules.accounts_agent.services import event_recovery
    _, ev = _dead(rig, db, monkeypatch)
    ev.requeue_count = event_recovery.MAX_REQUEUES
    db.commit()
    r = client.post(f"{API}/events/{ev.id}/requeue", headers=rig.admin["headers"])
    assert r.status_code == 409 and "Acknowledge" in r.json()["detail"]


def test_d10_acknowledged_failure_no_longer_degrades_but_stays_visible(client, rig, db, monkeypatch):
    _, ev = _dead(rig, db, monkeypatch)
    assert client.post(f"{API}/events/{ev.id}/acknowledge", json={"note": ""}, headers=rig.admin["headers"]).status_code == 422
    r = client.post(f"{API}/events/{ev.id}/acknowledge", json={"note": "voucher deleted by migration"},
                    headers=rig.admin["headers"])
    assert r.status_code == 200 and r.json()["acknowledged"] is True
    st = queries.status(db, rig.sid)
    assert st["state"] != "degraded" and st["failed_events"] == 0 and st["acknowledged_failed_events"] == 1
    listed = client.get(f"{API}/events/dead", headers=rig.admin["headers"]).json()
    assert listed["acknowledged"] == 1 and listed["items"][0]["acknowledge_note"] == "voucher deleted by migration"
    log = db.query(AgentAuditLog).filter(AgentAuditLog.action == "event_acknowledged").one()
    assert log.actor_id == rig.admin["user"].id


def test_d10_permissions_and_tenant_isolation(client, rig, db, monkeypatch):
    _, ev = _dead(rig, db, monkeypatch)
    assert client.post(f"{API}/events/{ev.id}/requeue", headers=rig.manager["headers"]).status_code == 403
    other = Rig(db, "p3other")
    assert client.post(f"{API}/events/{ev.id}/requeue", headers=other.admin["headers"]).status_code == 404
    assert client.post(f"{API}/events/{ev.id}/acknowledge", json={"note": "not mine at all"},
                       headers=other.admin["headers"]).status_code == 404
    assert client.get(f"{API}/events/dead", headers=other.admin["headers"]).json()["items"] == []
    db.refresh(ev)
    assert ev.status == "dead" and ev.acknowledged_at is None
