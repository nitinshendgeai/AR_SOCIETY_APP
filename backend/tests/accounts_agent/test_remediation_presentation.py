"""Regression tests for the functional-audit defects behind the Flutter screens (D-12, D-13, D-15, D-17 … D-20)."""
from datetime import date

import pytest

from app.modules.accounts_agent import worker
from app.modules.accounts_agent.legal import assistant
from app.modules.accounts_agent.models.agent import AgentFinding
from app.modules.vendor.services.work_orders import member_count_with_basis, procurement_limits
from tests.accounts_agent.helpers import Rig
from tests.accounts_agent.legal_helpers import LRig

API = "/api/v1/accounts-agent"


@pytest.fixture
def rig(db):
    return Rig(db, "p4")


def _mapping_finding(rig, db):
    rig.seed_history()
    bad = rig.payment(0, "security_charges", 6050, vendor=rig.clean, reference="CLN-X", approved=False)
    bad.approval_status = "pending"                              # entered, not yet approved
    db.commit()
    worker.run_once(db, "w", limit=500)
    return bad, db.query(AgentFinding).filter(AgentFinding.voucher_id == bad.id, AgentFinding.rule_code == "S-MAP-01").one()


# ── D-17 / D-18: original evidence and readable names ───────────────────────────────────────────────────────────

def test_d17_finding_keeps_the_voucher_as_detected_and_flags_later_changes(client, rig, db):
    bad, f = _mapping_finding(rig, db)
    d = client.get(f"{API}/findings/{f.id}", headers=rig.admin["headers"]).json()
    snap = d["voucher_at_detection"]
    assert snap["voucher_number"] == bad.voucher_number
    assert any(e["account"] == "Security Charges" for e in snap["entries"])
    assert d["voucher_changed_since_detection"] is False
    assert "_voucher_at_detection" not in d["evidence"]                    # internal key not shown as evidence
    # The voucher is corrected (through AccountsService), so "current" and "at detection" now differ.
    rig.svc.update_manual_voucher(bad.id, {
        "voucher_date": bad.voucher_date, "narration": bad.narration, "reference": bad.reference, "vendor_id": bad.vendor_id,
        "entries": [{"account_id": rig.chart["housekeeping"].id, "debit": 6050, "credit": 0},
                    {"account_id": rig.chart["bank"].id, "debit": 0, "credit": 6050}], "reason": "remap"}, rig.admin["user"])
    db.commit()
    d = client.get(f"{API}/findings/{f.id}", headers=rig.admin["headers"]).json()
    assert d["voucher_changed_since_detection"] is True
    assert any(e["account"] == "Security Charges" for e in d["voucher_at_detection"]["entries"])
    assert any(e["account"] == "Housekeeping & Cleaning" for e in d["voucher"]["entries"])


def test_d18_evidence_shows_names_not_ids(client, rig, db):
    _, f = _mapping_finding(rig, db)
    d = client.get(f"{API}/findings/{f.id}", headers=rig.admin["headers"]).json()
    shown = " ".join(f"{e['label']} {e['value']}" for e in d["evidence_display"])
    assert "Housekeeping & Cleaning" in shown
    import re
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", shown)
    pairs = [(e["label"], e["value"]) for e in d["evidence_display"]]
    assert len(pairs) == len(set(pairs))                                 # the same fact is not listed twice


# ── D-19: a finding on an unapproved voucher says so ────────────────────────────────────────────────────────────

def test_d19_list_carries_the_voucher_approval_status(client, rig, db):
    bad, f = _mapping_finding(rig, db)
    items = client.get(f"{API}/findings", headers=rig.admin["headers"], params={"page_size": 100}).json()["items"]
    row = next(i for i in items if i["id"] == str(f.id))
    assert row["voucher_approval_status"] == "pending"


# ── D-12: fund and bank balances on the health card ─────────────────────────────────────────────────────────────

def test_d12_health_card_has_fund_and_bank_balances(client, db):
    r = LRig(db, "p4h")
    r.payment(5, "sinking_fund", 40000, reference="SF-1")            # money drawn from the sinking fund
    out = client.get(f"{API}/compliance/overview", headers=r.admin["headers"]).json()["financial_health"]
    banks = {b["name"]: b for b in out["bank_and_cash"]}
    funds = {x["name"]: x for x in out["funds"]}
    assert any(float(b["balance"]) == -40000 for b in banks.values())
    sink = next(x for n, x in funds.items() if "Sinking" in n)
    assert float(sink["balance"]) == -40000 and sink["overdrawn"] is True
    assert out["balances_basis"].startswith("Approved vouchers")


# ── D-13: unverified legal answers say so first ─────────────────────────────────────────────────────────────────

def test_d13_assistant_marks_unverified_answers(db):
    r = LRig(db, "p4a")
    out = assistant.ask(db, r.sid, "Can we use the sinking fund for repairs?")
    assert out["intent"] == "fund_use" and out["verified_law"] is False and out["answer_unverified"] is True
    assert out["answer"].startswith("UNVERIFIED")


# ── D-15: cross-society refusals say what happened ──────────────────────────────────────────────────────────────

def test_d15_cross_society_read_message(client, db):
    a, b = Rig(db, "p4x"), Rig(db, "p4y")
    for path in ("/findings", "/dashboard", "/compliance/overview"):
        r = client.get(f"{API}{path}", headers=b.admin["headers"], params={"society_id": str(a.sid)})
        assert r.status_code == 403 and "own society" in r.json()["detail"], path


# ── D-20: member count for the committee slab ───────────────────────────────────────────────────────────────────

def test_d20_members_are_owners_or_the_recorded_membership(db):
    from app.models.resident import Resident, ResidentType
    r = LRig(db, "p4m")                                      # five flats, nobody recorded yet
    assert member_count_with_basis(db, r.sid) == (5, "active flats (no owners recorded)")
    for fl in r.flat_rows[:2]:                              # two flats sold: two members
        db.add(Resident(flat_id=fl.id, full_name=f"Owner {fl.flat_number}", resident_type=ResidentType.OWNER, is_active=True))
        db.add(Resident(flat_id=fl.id, full_name=f"Co {fl.flat_number}", resident_type=ResidentType.CO_OWNER, is_active=True))
    db.add(Resident(flat_id=r.flat_rows[2].id, full_name="Family only", resident_type=ResidentType.FAMILY, is_active=True))
    db.commit()
    assert member_count_with_basis(db, r.sid) == (2, "flats with an active owner")
    from app.modules.accounts_agent.legal.models import LegalProfile
    db.add(LegalProfile(society_id=r.sid, number_of_members=60, registration_date=date(2001, 1, 1)))
    db.commit()
    limits = procurement_limits(db, r.sid)
    assert limits["members"] == 60 and limits["bye_law_limit"] == "100000"
    assert limits["members_basis"] == "recorded in the society's legal profile"
