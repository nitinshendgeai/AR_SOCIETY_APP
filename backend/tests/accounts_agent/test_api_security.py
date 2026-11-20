"""Approval security, society isolation and API behaviour."""
import pytest

from app.modules.accounts.models.accounts import Voucher, VoucherRevision
from app.modules.accounts_agent import worker
from app.modules.accounts_agent.models.agent import AgentAuditLog, AgentFinding, AgentPattern, AgentProposal
from app.modules.accounts_agent.services.learning import Profile
from tests.accounts_agent.helpers import Rig
from tests.conftest import make_user

API = "/api/v1/accounts-agent"


@pytest.fixture
def rig(db):
    return Rig(db, "api")


@pytest.fixture
def dup(rig, db):
    """Two payments with the same reference → a confirmed duplicate finding on the second."""
    ven = rig.vendor()
    rig.payment(2, "security_charges", 25000, vendor=ven, reference="INV-1")
    second = rig.payment(2, "security_charges", 25000, vendor=ven, reference="INV-1")
    worker.run_once(db, "w", limit=500)
    f = db.query(AgentFinding).filter(AgentFinding.voucher_id == second.id, AgentFinding.rule_code == "R-DUP-02").one()
    return second, f


def make_proposal(client, rig, f):
    r = client.post(f"{API}/findings/{f.id}/proposals", headers=rig.admin["headers"])
    assert r.status_code == 201, r.text
    return r.json()


# ── Permissions ───────────────────────────────────────────────────────────────

def test_endpoints_require_authentication_and_role(client, rig):
    assert client.get(f"{API}/dashboard").status_code in (401, 403)
    res = make_user(rig.db, "res@agentapi.com", role="Resident")
    res["user"].society_id = rig.sid
    rig.db.commit()
    assert client.get(f"{API}/dashboard", headers=res["headers"]).status_code == 403
    assert client.get(f"{API}/dashboard", headers=rig.manager["headers"]).status_code == 200


def test_manager_can_read_but_not_decide(client, rig, dup):
    _, f = dup
    mgr = rig.manager["headers"]
    assert client.get(f"{API}/findings", headers=mgr).json()["total"] >= 1
    assert client.post(f"{API}/findings/{f.id}/proposals", headers=mgr).status_code == 403
    p = make_proposal(client, rig, f)
    assert client.post(f"{API}/proposals/{p['id']}/approve", json={"confirm": True}, headers=mgr).status_code == 403
    assert client.post(f"{API}/proposals/{p['id']}/reject", json={"reason": "no"}, headers=mgr).status_code == 403
    assert client.put(f"{API}/settings", json={"monitoring_enabled": False}, headers=mgr).status_code == 403


# ── Approval workflow ─────────────────────────────────────────────────────────

def test_approval_requires_explicit_confirmation(client, rig, dup):
    _, f = dup
    p = make_proposal(client, rig, f)
    r = client.post(f"{API}/proposals/{p['id']}/approve", json={}, headers=rig.admin["headers"])
    assert r.status_code == 422
    assert not rig.db.get(Voucher, f.voucher_id).is_cancelled


def test_agent_proposes_but_changes_nothing_until_approved(client, rig, db, dup):
    v, f = dup
    p = make_proposal(client, rig, f)
    assert p["status"] == "PENDING" and p["action_type"] == "cancel_voucher" and p["executable"]
    assert p["impact"] and p["before"]["lines"]
    db.refresh(v)
    assert v.is_cancelled is False


def test_approved_correction_runs_through_the_accounting_service_with_audit_trail(client, rig, db, dup):
    v, f = dup
    p = make_proposal(client, rig, f)
    r = client.post(f"{API}/proposals/{p['id']}/approve", json={"confirm": True, "note": "yes dup"}, headers=rig.chair["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "EXECUTED" and body["result"]["verification"]["finding_cleared"] is True
    db.refresh(v)
    assert v.is_cancelled and v.cancelled_by == rig.chair["user"].id and "Accounts Agent correction" in v.cancel_reason
    assert db.query(Voucher).filter(Voucher.id == v.id).count() == 1                   # never deleted
    db.refresh(f)
    assert f.status == "RESOLVED"
    actions = {a.action for a in db.query(AgentAuditLog).filter(AgentAuditLog.society_id == rig.sid)}
    assert {"finding_created", "proposal_created", "proposal_approved", "proposal_verified"} <= actions
    from app.models.audit_log import AuditLog
    assert db.query(AuditLog).filter(AuditLog.entity_id == str(v.id), AuditLog.module == "accounts").count() >= 1


def test_double_approval_executes_once(client, rig, db, dup):
    v, f = dup
    p = make_proposal(client, rig, f)
    ok = client.post(f"{API}/proposals/{p['id']}/approve", json={"confirm": True}, headers=rig.chair["headers"])
    again = client.post(f"{API}/proposals/{p['id']}/approve", json={"confirm": True}, headers=rig.chair["headers"])
    assert ok.status_code == 200 and again.status_code == 409
    db.refresh(v)
    first_cancel = v.cancelled_at
    assert db.query(AgentAuditLog).filter(AgentAuditLog.action == "proposal_approved").count() == 1
    assert v.cancelled_at == first_cancel


def test_rejected_proposal_cannot_execute(client, rig, db, dup):
    v, f = dup
    p = make_proposal(client, rig, f)
    assert client.post(f"{API}/proposals/{p['id']}/reject", json={"reason": "it is genuine"}, headers=rig.admin["headers"]).status_code == 200
    r = client.post(f"{API}/proposals/{p['id']}/approve", json={"confirm": True}, headers=rig.chair["headers"])
    assert r.status_code == 409
    db.refresh(v)
    assert not v.is_cancelled


def test_stale_proposal_cannot_execute(client, rig, db, dup):
    v, f = dup
    p = make_proposal(client, rig, f)
    v.narration = "edited after the proposal"                 # the voucher changed behind the proposal's back
    db.commit()
    r = client.post(f"{API}/proposals/{p['id']}/approve", json={"confirm": True}, headers=rig.chair["headers"])
    assert r.status_code == 409 and "changed" in r.json()["detail"].lower() if "detail" in r.json() else r.status_code == 409
    db.refresh(v)
    assert not v.is_cancelled
    assert db.get(AgentProposal, __import__("uuid").UUID(p["id"])).status == "STALE"


def test_ledger_mapping_correction_edits_via_voucher_service_keeping_revision(client, rig, db):
    rig.seed_history()
    bad = rig.payment(0, "security_charges", 6050, vendor=rig.clean, reference="CLN-X")
    worker.run_once(db, "w", limit=500)
    f = db.query(AgentFinding).filter(AgentFinding.voucher_id == bad.id, AgentFinding.rule_code == "S-MAP-01").one()
    p = make_proposal(client, rig, f)
    assert p["action_type"] == "edit_voucher"
    assert any(i["account"] == "Housekeeping & Cleaning" for i in p["impact"])
    r = client.post(f"{API}/proposals/{p['id']}/approve", json={"confirm": True}, headers=rig.chair["headers"])
    assert r.status_code == 200, r.text
    db.expire_all()
    names = {e.account.name for e in db.get(Voucher, bad.id).entries}
    assert "Housekeeping & Cleaning" in names and "Security Charges" not in names
    assert db.query(VoucherRevision).filter(VoucherRevision.voucher_id == bad.id).count() == 1     # earlier version kept


def test_auto_posted_voucher_gets_a_source_review_not_an_edit(client, rig, db):
    import uuid
    from app.modules.accounts.services.accounts_service import Line
    from tests.accounts_agent.helpers import D
    src = uuid.uuid4()
    mk = lambda: rig.svc.build_voucher(rig.sid, "payment", rig.today, [Line(rig.chart["office_expenses"], debit=D("100")),  # noqa: E731
                                                                       Line(rig.chart["bank"], credit=D("100"))],
                                       source_type="vendor_payment", source_id=src)
    mk(); b = mk(); db.commit()
    worker.run_once(db, "w", limit=500)
    f = db.query(AgentFinding).filter(AgentFinding.voucher_id == b.id, AgentFinding.rule_code == "R-DUP-01").one()
    p = make_proposal(client, rig, f)
    assert p["action_type"] == "source_review" and p["executable"] is False and p["after"] is None
    r = client.post(f"{API}/proposals/{p['id']}/approve", json={"confirm": True}, headers=rig.chair["headers"])
    assert r.json()["status"] == "ACKNOWLEDGED"
    db.refresh(b)
    assert not b.is_cancelled                                 # books untouched


def test_finding_without_a_derivable_correction_is_refused_honestly(client, rig, db):
    rig.seed_history()
    v = rig.payment(0, "office_expenses", 25000)
    worker.run_once(db, "w", limit=500)
    f = db.query(AgentFinding).filter(AgentFinding.voucher_id == v.id, AgentFinding.rule_code == "S-AMT-01").one()
    r = client.post(f"{API}/findings/{f.id}/proposals", headers=rig.admin["headers"])
    assert r.status_code == 422


def test_review_requires_a_reason_for_dismissals(client, rig, dup):
    _, f = dup
    h = rig.admin["headers"]
    assert client.post(f"{API}/findings/{f.id}/review", json={"status": "IGNORED"}, headers=h).status_code == 422
    r = client.post(f"{API}/findings/{f.id}/review", json={"status": "IGNORED", "note": "known"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "IGNORED"
    hist = client.get(f"{API}/findings/{f.id}/history", headers=h).json()
    assert [x["action"] for x in hist][-1] == "finding_reviewed"


# ── Society isolation ─────────────────────────────────────────────────────────

@pytest.fixture
def two(db):
    a, b = Rig(db, "isoA"), Rig(db, "isoB")
    for r in (a, b):
        ven = r.vendor()
        r.payment(2, "security_charges", 25000, vendor=ven, reference="INV-1")
        r.payment(2, "security_charges", 25000, vendor=ven, reference="INV-1")
    worker.run_once(db, "w", limit=500)
    return a, b


def test_society_a_cannot_see_society_b_findings(client, two, db):
    a, b = two
    mine = client.get(f"{API}/findings", headers=a.admin["headers"]).json()
    assert mine["total"] >= 1
    ids_b = {str(f.id) for f in db.query(AgentFinding).filter(AgentFinding.society_id == b.sid)}
    assert ids_b and not ids_b & {x["id"] for x in mine["items"]}
    fid_b = next(iter(ids_b))
    assert client.get(f"{API}/findings/{fid_b}", headers=a.admin["headers"]).status_code == 404
    assert client.get(f"{API}/findings/{fid_b}/history", headers=a.admin["headers"]).status_code == 404
    assert client.post(f"{API}/findings/{fid_b}/review", json={"status": "UNDER_REVIEW"}, headers=a.admin["headers"]).status_code == 404


def test_frontend_supplied_society_id_is_not_trusted(client, two):
    a, b = two
    for path in ("/dashboard", "/findings", "/learning/status", "/audit-logs", "/proposals", "/settings"):
        r = client.get(f"{API}{path}", params={"society_id": str(b.sid)}, headers=a.admin["headers"])
        assert r.status_code == 403, path
    assert client.put(f"{API}/settings", params={"society_id": str(b.sid)}, json={"monitoring_enabled": False},
                      headers=a.admin["headers"]).status_code == 403
    assert client.post(f"{API}/learning/run", params={"society_id": str(b.sid)}, headers=a.admin["headers"]).status_code == 403


def test_society_a_cannot_approve_or_reject_society_b_proposals(client, two, db):
    a, b = two
    fb = db.query(AgentFinding).filter(AgentFinding.society_id == b.sid, AgentFinding.rule_code == "R-DUP-02").first()
    p = client.post(f"{API}/findings/{fb.id}/proposals", headers=b.admin["headers"]).json()
    assert client.post(f"{API}/proposals/{p['id']}/approve", json={"confirm": True}, headers=a.admin["headers"]).status_code == 404
    assert client.post(f"{API}/proposals/{p['id']}/reject", json={"reason": "nope"}, headers=a.admin["headers"]).status_code == 404
    assert client.get(f"{API}/proposals/{p['id']}", headers=a.admin["headers"]).status_code == 404
    assert client.post(f"{API}/findings/{fb.id}/proposals", headers=a.admin["headers"]).status_code == 404
    assert db.get(AgentProposal, __import__("uuid").UUID(p["id"])).status == "PENDING"


def test_learning_profiles_are_per_society(client, two, db):
    a, b = two
    client.post(f"{API}/learning/run", headers=a.admin["headers"])
    client.post(f"{API}/learning/run", headers=b.admin["headers"])
    pa = db.query(AgentPattern).filter(AgentPattern.society_id == a.sid).all()
    assert pa and not any(str(b.chart["security_charges"].id) in p.pattern_key or str(b.chart["security_charges"].id) in str(p.stats) for p in pa)
    assert Profile(db, a.sid).get("account_amount", f"{b.chart['security_charges'].id}:dr") is None
    assert client.get(f"{API}/learning/history", headers=a.admin["headers"]).json()["total"] >= 1


def test_background_jobs_stay_society_scoped(two, db):
    """An event is analysed against its own society's data: a voucher id from society B named in an event of society A
    is skipped, never analysed."""
    a, b = two
    from datetime import datetime
    from app.modules.accounts_agent.models.agent import AgentEvent
    vb = db.query(Voucher).filter(Voucher.society_id == b.sid).first()
    ev = AgentEvent(society_id=a.sid, voucher_id=vb.id, event_type="voucher.created", idempotency_key="forged-1",
                    status="pending", next_attempt_at=datetime.utcnow())
    db.add(ev)
    db.commit()
    before = db.query(AgentFinding).filter(AgentFinding.society_id == a.sid).count()
    worker.run_once(db, "w", limit=500)
    db.refresh(ev)
    assert ev.status == "skipped" and "not found" in ev.last_error
    assert db.query(AgentFinding).filter(AgentFinding.society_id == a.sid).count() == before


# ── Settings / learning ───────────────────────────────────────────────────────

def test_settings_validation_and_monitoring_toggle(client, rig):
    h = rig.admin["headers"]
    assert client.put(f"{API}/settings", json={"z_threshold": 1.0}, headers=h).status_code == 422
    assert client.put(f"{API}/settings", json={"notify_min_severity": "BOGUS"}, headers=h).status_code == 422
    assert client.put(f"{API}/settings", json={"z_threshold": 4.0}, headers=h).json()["z_threshold"] == 4.0
    assert client.post(f"{API}/monitoring", json={"enabled": False}, headers=h).json()["state"] == "disabled"
    assert client.post(f"{API}/monitoring", json={"enabled": True}, headers=h).json()["monitoring_enabled"] is True


def test_dashboard_and_learning_report_real_numbers(client, rig, db):
    rig.seed_history()
    rig.payment(0, "office_expenses", 25000)
    worker.run_once(db, "w", limit=500)
    d = client.get(f"{API}/dashboard", headers=rig.manager["headers"]).json()
    assert d["transactions_analysed"] >= 16 and d["findings_open"]["HIGH"] >= 1 and d["status"]["state"] == "operational"
    assert d["learning"]["window_months"] == 3 and d["learning"]["last_run"]["voucher_count"] >= 15
    ls = client.get(f"{API}/learning/status", headers=rig.manager["headers"]).json()
    assert ls["limited"] is True and ls["last_run"]["confidence_label"] == "limited"      # 15 vouchers: honestly "limited"
    assert "Limited learning confidence" in ls["message"]
    r = client.get(f"{API}/findings", params={"severity": "HIGH", "q": "unusually", "page_size": 5}, headers=rig.manager["headers"]).json()
    assert r["total"] >= 1 and r["items"][0]["severity"] == "HIGH"
    assert client.get(f"{API}/findings", params={"severity": "NOPE"}, headers=rig.manager["headers"]).status_code == 422


# ── Duplicate pairs: never cancel both copies ─────────────────────────────────

def _pair(rig, db):
    ven = rig.vendor()
    first = rig.payment(2, "security_charges", 25000, vendor=ven, reference="INV-DUP")
    second = rig.payment(2, "security_charges", 25000, vendor=ven, reference="INV-DUP")
    worker.run_once(db, "w", limit=500)
    return first, second


def _legacy_finding_on_first(rig, db, first, second):
    """A duplicate finding on the EARLIER copy, as the agent used to create before only the later copy was flagged."""
    from app.modules.accounts_agent.services import engine
    from app.modules.accounts_agent.services.context import Draft
    pair = ":".join(sorted([str(first.id), str(second.id)]))
    d = Draft("R-DUP-02", "duplicate", "confirmed_validation_failure", "HIGH", 0.97, "Confirmed duplicate voucher",
              "legacy", evidence={"other_voucher_id": str(second.id)}, subject=pair)
    (f,) = engine.store_findings(db, first, [d], "limited")
    db.commit()
    return f


def test_duplicate_pair_gets_one_finding_and_approval_keeps_the_original(client, rig, db):
    first, second = _pair(rig, db)
    dups = db.query(AgentFinding).filter(AgentFinding.society_id == rig.sid, AgentFinding.rule_code.like("R-DUP%")).all()
    assert [f.voucher_id for f in dups] == [second.id]
    p = make_proposal(client, rig, dups[0])
    assert client.post(f"{API}/proposals/{p['id']}/approve", json={"confirm": True}, headers=rig.chair["headers"]).status_code == 200
    db.refresh(first), db.refresh(second)
    assert second.is_cancelled and not first.is_cancelled


def test_twin_cancellation_makes_the_other_copys_proposal_stale(client, rig, db):
    first, second = _pair(rig, db)
    f_second = db.query(AgentFinding).filter(AgentFinding.voucher_id == second.id, AgentFinding.rule_code == "R-DUP-02").one()
    f_first = _legacy_finding_on_first(rig, db, first, second)
    p_second, p_first = make_proposal(client, rig, f_second), make_proposal(client, rig, f_first)
    assert client.post(f"{API}/proposals/{p_second['id']}/approve", json={"confirm": True}, headers=rig.chair["headers"]).status_code == 200
    worker.run_once(db, "w", limit=500)                    # the cancellation event closes the twin's finding
    db.refresh(f_first)
    assert f_first.status == "RESOLVED"
    stale = db.query(AgentProposal).filter(AgentProposal.finding_id == f_first.id).one()
    assert stale.status == "STALE"
    r = client.post(f"{API}/proposals/{p_first['id']}/approve", json={"confirm": True}, headers=rig.chair["headers"])
    assert r.status_code == 409
    db.refresh(first)
    assert not first.is_cancelled                          # the genuine voucher stays in the books


def test_second_duplicate_approval_is_refused_even_before_the_worker_runs(client, rig, db):
    """The approval itself re-checks the duplicate, so a lagging (or stopped) worker cannot lead to both copies being cancelled."""
    first, second = _pair(rig, db)
    f_second = db.query(AgentFinding).filter(AgentFinding.voucher_id == second.id, AgentFinding.rule_code == "R-DUP-02").one()
    f_first = _legacy_finding_on_first(rig, db, first, second)
    p_second, p_first = make_proposal(client, rig, f_second), make_proposal(client, rig, f_first)
    assert client.post(f"{API}/proposals/{p_second['id']}/approve", json={"confirm": True}, headers=rig.chair["headers"]).status_code == 200
    r = client.post(f"{API}/proposals/{p_first['id']}/approve", json={"confirm": True}, headers=rig.chair["headers"])
    assert r.status_code == 409 and "no longer a duplicate" in r.json().get("detail", r.text)
    db.refresh(first), db.refresh(f_first)
    assert not first.is_cancelled and f_first.status == "RESOLVED"
    import uuid
    assert db.get(AgentProposal, uuid.UUID(p_first["id"])).status == "STALE"


def test_failed_learning_run_from_the_api_stays_in_the_history(client, rig, db, monkeypatch):
    from app.modules.accounts_agent.services import learning

    def broken(*a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(learning, "account_meta", broken)
    r = client.post(f"{API}/learning/run", headers=rig.admin["headers"])
    assert r.status_code == 500 and "learning history" in r.text
    hist = client.get(f"{API}/learning/history", headers=rig.admin["headers"])
    assert hist.status_code == 200, hist.text
    assert "failed" in hist.text
