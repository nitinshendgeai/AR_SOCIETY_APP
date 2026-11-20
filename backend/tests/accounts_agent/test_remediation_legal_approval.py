"""Regression tests for the functional-audit defects D-03 (legal thresholds) and D-09 (maker–checker on proposals)."""
import uuid
from datetime import date, timedelta

import pytest

from app.modules.accounts.models.accounts import Voucher
from app.modules.accounts_agent import worker
from app.modules.accounts_agent.legal import compliance, documents, registry
from app.modules.accounts_agent.legal.models import LegalRule
from app.modules.accounts_agent.models.agent import AgentAuditLog, AgentFinding, AgentProposal
from app.modules.vendor.models.vendor import ProcurementSettings
from tests.accounts_agent.legal_helpers import D, LRig

API = "/api/v1/accounts-agent"


@pytest.fixture
def rig(db):
    return LRig(db, "d03")


def _repair(rig, amount=150000):
    return rig.payment(10, "repairs_building", amount, reference="TERRACE-1", narration="Terrace waterproofing")


# ── D-03: every threshold comes from the registry and is labelled by its source ─────────────────────────────────

def test_d03_model_figure_is_labelled_and_never_more_than_advisory(rig):
    _repair(rig)
    rig.scan()
    (f,) = rig.findings("L-EXP-REP-01")
    assert f.finding_class == "ADVISORY_OBSERVATION"
    assert f.evidence["threshold_basis"] == "MODEL_REFERENCE" and f.evidence["governing_rule"] == "MH-EXP-106C13-LIMIT"
    assert "binding only if your registered bye-laws adopted it" in f.explanation
    assert "statutory limit (MH-EXP-106C13-LIMIT) is not loaded and is under legal review" in f.explanation
    assert f.legal_source["legal_status"] == "MODEL_REFERENCE" and f.legal_source["verified"] is False


def test_d03_registered_bye_law_figure_governs_and_is_named(rig, db):
    doc = rig.upload("Bye-law 157: the committee may spend up to Rs 40,000.", title="Registered bye-laws 2021")
    documents.verify(db, doc, rig.admin["user"], status="REGISTERED", verification_status="VERIFIED_SECONDARY_SOURCE",
                     note="Certified copy", approval_date=date(2021, 4, 1))
    r = LegalRule(scope=str(rig.sid), society_id=rig.sid, rule_code="SOC-157", version=1, topic="expenditure.committee_limit",
                  rule_category="expenditure", title="Bye-law 157 (registered)", source_level="D", source_document_id=doc.id,
                  legal_status="UNVERIFIED", verification_status="PENDING_VERIFICATION",
                  calculation_method={"type": "max_amount", "value": 40000})
    db.add(r)
    db.commit()
    registry.verify_rule(db, r, rig.admin["user"], "VERIFIED_SECONDARY_SOURCE", "certified copy", "BINDING", None, "3")
    db.commit()
    _repair(rig, 35000)                                        # above the model ₹25,000, below the society's ₹40,000
    rig.scan()
    assert rig.findings("L-EXP-REP-01") == []
    _repair(rig, 45000)
    rig.scan()
    (f,) = rig.findings("L-EXP-REP-01")
    assert f.evidence["threshold_basis"] == "SOCIETY_RULE" and f.evidence["threshold"] == "40000.00"
    assert "registered bye-law (SOC-157)" in f.explanation and f.legal_source["rule_code"] == "SOC-157"
    assert not f.finding_class.startswith("CONFIRMED")


def test_d03_procurement_setting_is_a_society_setting_not_law(rig, db):
    db.add(ProcurementSettings(society_id=rig.sid, committee_limit=D("100000"), gb_resolution_no="GB-7"))
    db.commit()
    _repair(rig, 150000)
    rig.scan()
    (f,) = rig.findings("L-EXP-REP-01")
    assert f.finding_class == "INTERNAL_POLICY_DEVIATION" and f.evidence["threshold"] == "100000.00"
    assert "not a verified legal source" in f.explanation


def test_d03_unverified_statutory_figure_cannot_confirm(rig, db):
    """Even if a statutory figure is loaded, an unverified (or review-blocked) source gives a potential issue at most."""
    r = (db.query(LegalRule).filter(LegalRule.rule_code == "MH-EXP-106C13-LIMIT").order_by(LegalRule.version.desc()).first())
    r.calculation_method = {**(r.calculation_method or {}), "slabs": [[100, 30000], [None, 200000]]}
    db.commit()
    _repair(rig, 150000)
    rig.scan()
    (f,) = rig.findings("L-EXP-REP-01")
    assert f.evidence["threshold_basis"] == "STATUTE" and f.evidence["threshold"] == "30000.00"
    assert "statutory source not yet verified" in f.explanation
    assert f.finding_class == "POTENTIAL_NON_COMPLIANCE"


# ── D-09: maker–checker ─────────────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def dup(rig, db):
    ven = rig.vendor()
    rig.payment(1, "security_charges", 25000, vendor=ven, reference="INV-9")
    second = rig.payment(1, "security_charges", 25000, vendor=ven, reference="INV-9")
    worker.run_once(db, "w", limit=500)
    f = db.query(AgentFinding).filter(AgentFinding.voucher_id == second.id, AgentFinding.rule_code == "R-DUP-02").one()
    return second, f


def test_d09_proposer_cannot_approve_own_cancellation(client, rig, db, dup):
    v, f = dup
    p = client.post(f"{API}/findings/{f.id}/proposals", headers=rig.admin["headers"]).json()
    assert p["action_type"] == "cancel_voucher" and p["requires_other_approver"] is True
    assert p["created_by"] == str(rig.admin["user"].id)
    r = client.post(f"{API}/proposals/{p['id']}/approve", json={"confirm": True}, headers=rig.admin["headers"])
    assert r.status_code == 403 and "Maker–checker" in r.json()["detail"]
    db.refresh(v)
    assert not v.is_cancelled
    assert db.get(AgentProposal, uuid.UUID(p["id"])).status == "PENDING"            # still waiting for a checker
    refused = db.query(AgentAuditLog).filter(AgentAuditLog.action == "proposal_self_approval_refused").one()
    assert refused.actor_id == rig.admin["user"].id and refused.details["proposed_by"] == str(rig.admin["user"].id)
    # A different authorised person approves: executed through AccountsService, with both people on the audit log.
    ok = client.post(f"{API}/proposals/{p['id']}/approve", json={"confirm": True}, headers=rig.chair["headers"])
    assert ok.status_code == 200, ok.text
    assert ok.json()["decided_by"] == str(rig.chair["user"].id)
    db.refresh(v)
    assert v.is_cancelled and v.cancelled_by == rig.chair["user"].id
    approved = db.query(AgentAuditLog).filter(AgentAuditLog.action == "proposal_approved").one()
    assert approved.details["proposed_by"] == str(rig.admin["user"].id)
    assert approved.details["approved_by"] == str(rig.chair["user"].id)
    assert approved.details["action"] == "cancel_voucher" and approved.details["decided_at"]


def test_d09_applies_to_edit_corrections_too(client, rig, db):
    rig.seed_history()
    bad = rig.payment(0, "security_charges", 6050, vendor=rig.clean, reference="CLN-X")
    worker.run_once(db, "w", limit=500)
    f = db.query(AgentFinding).filter(AgentFinding.voucher_id == bad.id, AgentFinding.rule_code == "S-MAP-01").one()
    p = client.post(f"{API}/findings/{f.id}/proposals", headers=rig.chair["headers"]).json()
    assert p["action_type"] == "edit_voucher"
    r = client.post(f"{API}/proposals/{p['id']}/approve", json={"confirm": True}, headers=rig.chair["headers"])
    assert r.status_code == 403
    names = {e.account.name for e in db.get(Voucher, bad.id).entries}
    assert "Security Charges" in names                                                # unchanged
    assert client.post(f"{API}/proposals/{p['id']}/approve", json={"confirm": True},
                       headers=rig.admin["headers"]).status_code == 200


def test_d09_single_authorised_user_gets_a_clear_workflow_restriction(client, rig, db, dup):
    from app.models.user import User
    v, f = dup
    db.get(User, rig.chair["user"].id).is_active = False                            # nobody else may approve
    db.commit()
    p = client.post(f"{API}/findings/{f.id}/proposals", headers=rig.admin["headers"]).json()
    r = client.post(f"{API}/proposals/{p['id']}/approve", json={"confirm": True}, headers=rig.admin["headers"])
    assert r.status_code == 403 and "no other active administrator or committee member" in r.json()["detail"]
    db.refresh(v)
    assert not v.is_cancelled


def test_d09_rejection_by_the_proposer_is_still_allowed(client, rig, db, dup):
    """Withdrawing one's own proposal changes nothing in the books, so it needs no second person."""
    _, f = dup
    p = client.post(f"{API}/findings/{f.id}/proposals", headers=rig.admin["headers"]).json()
    assert client.post(f"{API}/proposals/{p['id']}/reject", json={"reason": "entered twice on purpose"},
                       headers=rig.admin["headers"]).status_code == 200
