"""Element → ledger: the society's own rule, default-ledger fallbacks, and the sign-off map."""
from datetime import date, timedelta

import pytest

from app.modules.accounts.services.chart_of_accounts import bill_line_ledger_key
from app.modules.accounts_agent.legal import ledger_mapping as lm
from app.modules.billing.models.billing import ChargeType, MaintenanceElement
from tests.accounts_agent.legal_helpers import D, ChargeBasis, LRig

API = "/api/v1/accounts-agent"


@pytest.fixture
def rig(db):
    return LRig(db, "led")


def one(rig, code):
    rows = rig.findings(code)
    assert len(rows) == 1, f"{code}: {[(f.rule_code, f.title) for f in rig.findings()]}"
    return rows[0]


def _billed(rig, *lines):
    cy = rig.cycle(rig.today - timedelta(days=30), rig.today - timedelta(days=1))
    for fl in rig.flat_rows[:2]:
        rig.bill(fl, cy, list(lines))


def _verified_bylaws(client, rig):
    r = client.post(f"{API}/legal/documents", headers=rig.admin["headers"],
                    data={"document_type": "REGISTERED_BYELAWS", "title": "Registered bye-laws"},
                    files={"file": ("bylaws.txt", b"Bye-law No. 67. Lift charges are credited to the Repair Fund.", "text/plain")})
    doc = r.json()
    assert client.post(f"{API}/legal/documents/{doc['id']}/verify", headers=rig.admin["headers"], json={
        "status": "REGISTERED", "verification_status": "VERIFIED_SECONDARY_SOURCE", "note": "certified copy",
        "approval_date": "2020-05-01"}).status_code == 200
    return doc


def _ledger_rule(client, rig, doc, element, account, code="SOC-LED-LIFT"):
    return client.post(f"{API}/legal/rules", headers=rig.admin["headers"], json={
        "rule_code": code, "title": f"{element} ledger", "topic": f"ledger.element.{element}", "rule_category": "ledger",
        "source_level": "D", "source_document_id": doc["id"], "bye_law_number": "67", "page_number": "21",
        "calculation_method": {"type": "element_ledger", "account_id": str(account.id)}})


def test_source_labels_follow_the_posting_function():
    cases = [(ChargeType.PENALTY, "Interest on arrears @12%", None, "special"),
             (ChargeType.OTHER, "Non-Occupancy Charges", None, "special"),
             (ChargeType.MAINTENANCE, "Lift", "lift_maintenance", "element"),
             (ChargeType.OTHER, "Municipal tax", None, "keyword"),
             (ChargeType.OTHER, "Gym fee", "gym_custom", "charge_type"),
             (ChargeType.MAINTENANCE, "Misc", None, "charge_type")]
    for ct, desc, code, src in cases:
        key, got = lm.ledger_source(ct, desc, code)
        assert got == src, desc
        assert key == bill_line_ledger_key(type("L", (), {"charge_type": ct, "description": desc})(), code)


# 1. The society's own element → ledger rule ─────────────────────────────────────────────────────────────────────

def test_society_rule_governs_only_once_verified_and_flags_the_difference(client, rig, db):
    rig.config("Lift Maintenance", ChargeType.MAINTENANCE, ChargeBasis.FIXED, 300, "lift_maintenance", service=True)
    _billed(rig, (ChargeType.MAINTENANCE, "Lift Maintenance", 300, 300))       # standard table: Service Charges
    doc = _verified_bylaws(client, rig)
    r = _ledger_rule(client, rig, doc, "lift_maintenance", rig.chart["repair_fund"])
    assert r.status_code == 201, r.text
    rig.scan()
    assert rig.findings("A-LED-01") == []                                        # unverified: does not govern
    m = client.get(f"{API}/ledger-mapping", headers=rig.manager["headers"]).json()
    row = next(x for x in m["rows"] if x["element_code"] == "lift_maintenance")
    assert row["pending_society_rule"]["rule_code"] == "SOC-LED-LIFT" and row["status"] == "ok"
    assert client.post(f"{API}/legal/rules/{r.json()['id']}/verify", headers=rig.admin["headers"], json={
        "verification_status": "VERIFIED_SECONDARY_SOURCE", "note": "checked", "page_number": "21",
        "legal_status": "BINDING"}).status_code == 200
    rig.scan()
    f = one(rig, "A-LED-01")
    assert f.evidence["posted_ledger"] == "Service Charges" and f.evidence["rule_ledger"] == "Repairs & Maintenance Fund"
    assert f.evidence["amount"] == "600.00" and len(f.evidence["bills"]) == 2
    assert f.finding_class == "POTENTIAL_NON_COMPLIANCE"           # a bye-law difference is for review, not "confirmed"
    m = client.get(f"{API}/ledger-mapping", headers=rig.manager["headers"]).json()
    row = next(x for x in m["rows"] if x["element_code"] == "lift_maintenance")
    assert row["status"] == "differs_from_society_rule" and row["society_rule_ledger"] == "Repairs & Maintenance Fund"


def test_rule_that_agrees_with_the_standard_table_is_quiet(client, rig):
    rig.config("Lift Maintenance", ChargeType.MAINTENANCE, ChargeBasis.FIXED, 300, "lift_maintenance", service=True)
    _billed(rig, (ChargeType.MAINTENANCE, "Lift Maintenance", 300, 300))
    doc = _verified_bylaws(client, rig)
    r = _ledger_rule(client, rig, doc, "lift_maintenance", rig.chart["service_charges"])
    client.post(f"{API}/legal/rules/{r.json()['id']}/verify", headers=rig.admin["headers"], json={
        "verification_status": "VERIFIED_SECONDARY_SOURCE", "note": "checked", "page_number": "21"})
    rig.scan()
    assert rig.findings("A-LED-01") == []


def test_ledger_rule_must_name_own_element_and_ledger(client, rig, db):
    other = LRig(db, "led2")
    doc = _verified_bylaws(client, rig)
    assert _ledger_rule(client, rig, doc, "no_such_element", rig.chart["repair_fund"], "SOC-X1").status_code == 422
    assert _ledger_rule(client, rig, doc, "lift_maintenance", other.chart["repair_fund"], "SOC-X2").status_code == 422
    bad = client.post(f"{API}/legal/rules", headers=rig.admin["headers"], json={
        "rule_code": "SOC-X3", "title": "Lift ledger", "topic": "ledger.element.lift_maintenance", "rule_category": "ledger",
        "source_level": "D", "source_document_id": doc["id"], "calculation_method": {"type": "max_pct", "value": 3}})
    assert bad.status_code == 422


# 2. Default-ledger fallbacks ──────────────────────────────────────────────────────────────────────────────────────

def test_custom_element_falls_back_to_catch_all(rig, db):
    el = MaintenanceElement(society_id=rig.sid, code="gym_custom", name="Gym", category=ChargeType.OTHER,
                            default_basis=ChargeBasis.FIXED)
    db.add(el)
    db.commit()
    c = rig.config("Gym Charges", ChargeType.OTHER, ChargeBasis.FIXED, 200)
    c.element_id = el.id
    db.commit()
    _billed(rig, (ChargeType.OTHER, "Gym Charges", 200, 200))
    rig.scan()
    f = one(rig, "A-LED-02")
    assert f.severity == "MEDIUM" and f.evidence["ledger"] == "Other Charges Recovered" and f.evidence["element"] == "gym_custom"


def test_head_without_element_and_orphan_line(rig):
    rig.config("Club Fee", ChargeType.MAINTENANCE, ChargeBasis.FIXED, 100)        # no element; maintenance default
    rig.config("Generator Fund", ChargeType.OTHER, ChargeBasis.FIXED, 50)          # no element, not yet billed
    _billed(rig, (ChargeType.MAINTENANCE, "Club Fee", 100, 100), (ChargeType.OTHER, "Old Renamed Head", 80, 80))
    rig.scan()
    f = one(rig, "A-LED-02")
    assert f.finding_class == "ADVISORY_OBSERVATION" and f.evidence["ledger"] == "Service Charges"
    assert one(rig, "A-LED-03").evidence["description"] == "Old Renamed Head"
    assert one(rig, "A-LED-04").evidence["charge_head"] == "Generator Fund"


def test_standard_elements_and_interest_are_not_fallbacks(rig):
    rig.config("Service Charges", ChargeType.MAINTENANCE, ChargeBasis.FIXED, 2000, "service_charges", service=True)
    rig.config("Sinking Fund", ChargeType.SINKING_FUND, ChargeBasis.SERVICE_CHARGE_PCT, "0.25", "sinking_fund")
    _billed(rig, (ChargeType.MAINTENANCE, "Service Charges", 2000, 2000), (ChargeType.SINKING_FUND, "Sinking Fund", 5, 5),
            (ChargeType.PENALTY, "Interest on arrears @ 12%", 20, 20))
    rig.scan()
    assert not [f for f in rig.findings() if f.rule_code.startswith("A-LED")]


# 3. The map and its sign-off ──────────────────────────────────────────────────────────────────────────────────────

def test_map_report_and_sign_off(client, rig):
    rig.config("Service Charges", ChargeType.MAINTENANCE, ChargeBasis.FIXED, 2000, "service_charges", service=True)
    rig.config("Club Fee", ChargeType.MAINTENANCE, ChargeBasis.FIXED, 100)
    _billed(rig, (ChargeType.MAINTENANCE, "Service Charges", 2000, 2000))
    m = client.get(f"{API}/ledger-mapping", headers=rig.manager["headers"]).json()
    rows = {r["charge_head"]: r for r in m["rows"]}
    assert rows["Service Charges"]["source"] == "element" and rows["Service Charges"]["posted_ledger"] == "Service Charges"
    assert rows["Service Charges"]["recent_postings"] == [{"ledger": "Service Charges", "amount": "4000.00"}]
    assert rows["Club Fee"]["status"] == "no_element" and rows["Club Fee"]["source"] == "charge_type"
    assert m["signed_off"] is None and not m["signed_off_current"] and m["ledgers"]
    body = {"role": "AUDITOR", "note": "Reviewed with the statutory auditor", "fingerprint": m["fingerprint"]}
    assert client.post(f"{API}/ledger-mapping/sign-off", headers=rig.manager["headers"], json=body).status_code == 403
    r = client.post(f"{API}/ledger-mapping/sign-off", headers=rig.admin["headers"], json=body)
    assert r.status_code == 200 and r.json()["signed_off"]["role"] == "AUDITOR"
    assert client.get(f"{API}/ledger-mapping", headers=rig.manager["headers"]).json()["signed_off_current"] is True
    rig.config("Parking", ChargeType.PARKING, ChargeBasis.PARKING, 500, "parking")      # the map changes
    m2 = client.get(f"{API}/ledger-mapping", headers=rig.manager["headers"]).json()
    assert m2["signed_off_current"] is False and m2["signed_off"]["role"] == "AUDITOR"
    stale = client.post(f"{API}/ledger-mapping/sign-off", headers=rig.admin["headers"], json=body)
    assert stale.status_code == 409                                           # must review the map as it is now


def test_map_is_society_scoped(client, rig, db):
    other = LRig(db, "led3")
    other.config("Secret Head", ChargeType.MAINTENANCE, ChargeBasis.FIXED, 1, "service_charges")
    m = client.get(f"{API}/ledger-mapping", headers=rig.admin["headers"]).json()
    assert all(r["charge_head"] != "Secret Head" for r in m["rows"])
    assert all(l["id"] not in {str(a.id) for a in other.chart.values()} for l in m["ledgers"])
    assert client.get(f"{API}/ledger-mapping?society_id={other.sid}", headers=rig.admin["headers"]).status_code == 403
