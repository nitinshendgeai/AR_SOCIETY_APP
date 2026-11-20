"""Legal & compliance API: society isolation, role checks, jurisdiction-law guard, remediation never executes."""
from datetime import timedelta

import pytest

from app.modules.accounts.models.accounts import Voucher
from app.modules.accounts_agent.models.agent import AgentFinding, AgentProposal
from tests.accounts_agent.legal_helpers import D, LRig
from tests.security.world import platform_admin

API = "/api/v1/accounts-agent"


@pytest.fixture
def two(db):
    return LRig(db, "apiA"), LRig(db, "apiB")


def _upload(client, rig, text="Bye-law No. 65. Charges.", **form):
    data = {"document_type": "REGISTERED_BYELAWS", "title": "Registered bye-laws", **form}
    return client.post(f"{API}/legal/documents", data=data, files={"file": ("bylaws.txt", text.encode(), "text/plain")},
                       headers=rig.admin["headers"])


def test_document_library_is_society_scoped(client, two):
    a, b = two
    r = _upload(client, a)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["status"] == "UNVERIFIED" and not doc["operative"]
    assert client.get(f"{API}/legal/documents/{doc['id']}", headers=b.admin["headers"]).status_code == 404
    assert client.get(f"{API}/legal/documents/{doc['id']}/file", headers=b.admin["headers"]).status_code == 404
    assert client.get(f"{API}/legal/documents/{doc['id']}/clauses", headers=b.admin["headers"]).status_code == 404
    assert all(d["id"] != doc["id"] for d in client.get(f"{API}/legal/documents", headers=b.admin["headers"]).json())
    assert client.post(f"{API}/legal/documents/{doc['id']}/verify", headers=b.admin["headers"],
                       json={"status": "REGISTERED", "verification_status": "VERIFIED_SECONDARY_SOURCE", "note": "x y z",
                             "approval_date": "2020-01-01"}).status_code == 404
    raw = client.get(f"{API}/legal/documents/{doc['id']}/file", headers=a.manager["headers"])
    assert raw.status_code == 200 and raw.content == b"Bye-law No. 65. Charges." and raw.headers["x-content-sha256"]


def test_forged_society_id_is_refused(client, two):
    a, b = two
    assert client.get(f"{API}/compliance/overview?society_id={b.sid}", headers=a.admin["headers"]).status_code == 403
    assert client.post(f"{API}/compliance/scan?society_id={b.sid}", headers=a.admin["headers"]).status_code == 403
    assert client.get(f"{API}/resolutions?society_id={b.sid}", headers=a.manager["headers"]).status_code == 403


def test_resolutions_budgets_and_findings_isolated(client, two, db):
    a, b = two
    ven_b = b.vendor("OtherCo")
    r = client.post(f"{API}/resolutions", headers=a.admin["headers"], json={
        "resolution_number": "MC-1", "meeting_type": "COMMITTEE", "meeting_date": str(a.today), "purpose": "x",
        "vendor_id": str(ven_b.id)})
    assert r.status_code == 422                                          # another society's vendor
    r = client.post(f"{API}/resolutions", headers=a.admin["headers"], json={
        "resolution_number": "MC-1", "meeting_type": "COMMITTEE", "meeting_date": str(a.today), "purpose": "Lift AMC",
        "approved_amount": "50000"})
    assert r.status_code == 201
    rid = r.json()["id"]
    assert client.put(f"{API}/resolutions/{rid}", headers=b.admin["headers"], json={"purpose": "x"}).status_code == 404
    assert client.post(f"{API}/resolutions/{rid}/verify", headers=b.admin["headers"], json={}).status_code == 404
    assert client.put(f"{API}/budgets", headers=a.admin["headers"], json={
        "fiscal_year": "2026-27", "lines": [{"account_id": str(b.chart["office_expenses"].id), "approved_amount": "10"}]}
    ).status_code == 422
    a.settings(interest_rate_pct=18)
    assert client.post(f"{API}/compliance/scan", headers=a.admin["headers"]).status_code == 200
    assert db.query(AgentFinding).filter(AgentFinding.society_id == b.sid, AgentFinding.rule_code == "L-CHG-INT-01").count() == 0
    fa = db.query(AgentFinding).filter(AgentFinding.society_id == a.sid, AgentFinding.rule_code == "L-CHG-INT-01").one()
    assert client.get(f"{API}/findings/{fa.id}", headers=b.admin["headers"]).status_code == 404
    assert client.post(f"{API}/findings/{fa.id}/proposals", headers=b.admin["headers"]).status_code == 404
    listed = client.get(f"{API}/findings?engine=legal&classification=POTENTIAL_NON_COMPLIANCE", headers=a.manager["headers"]).json()
    assert any(i["id"] == str(fa.id) and i["classification"] == "POTENTIAL_NON_COMPLIANCE" for i in listed["items"])


def test_society_rules_never_leak(client, two, db):
    a, b = two
    doc = _upload(client, a).json()
    r = client.post(f"{API}/legal/rules", headers=a.admin["headers"], json={
        "rule_code": "SOC-A-INT", "topic": "charges.interest_on_arrears.max_rate_pct", "rule_category": "charges",
        "title": "Bye-law 70", "source_level": "D", "source_document_id": doc["id"],
        "calculation_method": {"type": "max_pct", "value": 10}})
    assert r.status_code == 201
    rule_id = r.json()["id"]
    assert client.get(f"{API}/legal/rules/{rule_id}", headers=b.admin["headers"]).status_code == 404
    assert all(x["rule_code"] != "SOC-A-INT" for x in client.get(f"{API}/legal/rules", headers=b.admin["headers"]).json()["items"])
    # B cannot cite A's document for its own rule.
    assert client.post(f"{API}/legal/rules", headers=b.admin["headers"], json={
        "rule_code": "SOC-B", "topic": "charges.other", "rule_category": "charges", "title": "B rule", "source_level": "D",
        "source_document_id": doc["id"]}).status_code == 404
    # A's rule cannot be verified while its document is unverified.
    r = client.post(f"{API}/legal/rules/{rule_id}/verify", headers=a.admin["headers"], json={
        "verification_status": "VERIFIED_SECONDARY_SOURCE", "note": "checked", "page_number": "4"})
    assert r.status_code == 422


def test_jurisdiction_law_is_platform_only(client, two, db):
    a, _ = two
    files = {"file": ("gazette.txt", b"Rule 106C-12", "text/plain")}
    r = client.post(f"{API}/legal/jurisdiction-documents", headers=a.admin["headers"], files=files,
                    data={"document_type": "GAZETTE_NOTIFICATION", "title": "Gazette"})
    assert r.status_code == 403
    rules = client.get(f"{API}/legal/rules", headers=a.admin["headers"]).json()["items"]
    state = next(x for x in rules if x["rule_code"] == "MH-FUND-SINKING-RATE")
    r = client.post(f"{API}/legal/rules/{state['id']}/verify", headers=a.admin["headers"],
                    json={"verification_status": "VERIFIED_SECONDARY_SOURCE", "note": "trust me", "page_number": "1"})
    assert r.status_code == 403
    rev = next(x for x in client.get(f"{API}/legal/reviews", headers=a.admin["headers"]).json() if not x["society_specific"])
    assert client.post(f"{API}/legal/reviews/{rev['id']}/decide", headers=a.admin["headers"],
                       json={"status": "RESOLVED", "note": "not an issue"}).status_code == 403
    pa = platform_admin(db, "pa-api@agent.test")
    r = client.post(f"{API}/legal/jurisdiction-documents", headers=pa["headers"], files=files,
                    data={"document_type": "GAZETTE_NOTIFICATION", "title": "Gazette", "is_primary_source": "true"})
    assert r.status_code == 201 and r.json()["is_primary_source"] is True
    # Visible (read-only) to the society, as jurisdiction-wide law.
    assert client.get(f"{API}/legal/documents/{r.json()['id']}", headers=a.manager["headers"]).status_code == 200


def test_remediation_proposal_never_changes_books(client, two, db):
    a, _ = two
    v = a.payment(10, "sinking_fund", 50000, reference="SF")
    client.post(f"{API}/compliance/scan", headers=a.admin["headers"])
    f = db.query(AgentFinding).filter(AgentFinding.society_id == a.sid, AgentFinding.rule_code == "L-FND-USE-01").one()
    assert client.post(f"{API}/findings/{f.id}/proposals", headers=a.manager["headers"]).status_code == 403
    p = client.post(f"{API}/findings/{f.id}/proposals", headers=a.admin["headers"])
    assert p.status_code == 201, p.text
    p = p.json()
    assert p["action_type"] == "remediation" and p["executable"] is False
    for k in ("existing_entry", "identified_issue", "accounting_rule", "legal_provision", "society_resolution",
              "affected", "supporting_documents", "approval_requirement"):
        assert k in p["before"]
    assert p["after"]["executes_automatically"] is False
    assert client.post(f"{API}/proposals/{p['id']}/approve", headers=a.manager["headers"], json={"confirm": True}).status_code == 403
    assert client.post(f"{API}/proposals/{p['id']}/approve", headers=a.admin["headers"], json={}).status_code == 422
    r = client.post(f"{API}/proposals/{p['id']}/approve", headers=a.admin["headers"], json={"confirm": True})
    assert r.status_code == 200 and r.json()["status"] == "ACKNOWLEDGED" and r.json()["result"]["executed"] is False
    db.expire_all()
    v2 = db.get(Voucher, v.id)
    assert not v2.is_cancelled and v2.amount == D("50000.00") and v2.edited_at is None
    assert client.post(f"{API}/proposals/{p['id']}/approve", headers=a.admin["headers"], json={"confirm": True}).status_code == 409


def test_overview_assistant_calendar_recovery(client, two):
    a, _ = two
    a.settings(non_occupancy_pct=5)
    client.post(f"{API}/compliance/scan", headers=a.admin["headers"])
    ov = client.get(f"{API}/compliance/overview", headers=a.manager["headers"])
    assert ov.status_code == 200
    body = ov.json()
    assert {s["key"] for s in body["sections"]} >= {"bye_law_compliance", "funds", "statutory", "governance"}
    assert body["llm_required"] is False and body["legal_library"]["rules_verified"] == 0
    ans = client.post(f"{API}/assistant/ask", headers=a.manager["headers"],
                      json={"question": "What is the applicable non-occupancy charge calculation?"}).json()
    assert ans["intent"] == "non_occupancy" and ans["sources"] and ans["verified_law"] is False and ans["uncertainty"]
    assert ans["sources"][0]["rule_code"] == "MH-CHG-NONOCC-CAP"
    none = client.post(f"{API}/assistant/ask", headers=a.manager["headers"], json={"question": "Tell me a joke"}).json()
    assert none["intent"] is None and none["sources"] == []
    cal = client.get(f"{API}/compliance/calendar", headers=a.manager["headers"]).json()
    assert any(i["code"] == "TDS_RETURNS" and i["professional_verification_required"] for i in cal)
    item = next(i for i in cal if i["code"] == "AGM")
    assert client.put(f"{API}/compliance/calendar/{item['id']}", headers=a.manager["headers"],
                      json={"completion_status": "COMPLETED", "evidence_ref": "x"}).status_code == 403
    assert client.get(f"{API}/recovery/arrears", headers=a.manager["headers"]).status_code == 200
    assert client.get(f"{API}/recovery/checklist/{a.flat_rows[0].id}", headers=a.manager["headers"]).status_code == 403
    assert client.get(f"{API}/recovery/checklist/{a.flat_rows[0].id}", headers=a.admin["headers"]).status_code == 200
    app = client.get(f"{API}/legal/applicable?topic=charges.interest_on_arrears.max_rate_pct&on_date=2026-05-01",
                     headers=a.manager["headers"]).json()
    assert app["governing"]["version"] == 1 and app["finding_class_if_breached"] == "ADVISORY_OBSERVATION"


def test_recovery_checklist_other_society_flat(client, two):
    a, b = two
    assert client.get(f"{API}/recovery/checklist/{b.flat_rows[0].id}", headers=a.admin["headers"]).status_code == 404


def test_resident_has_no_access(client, two, db):
    from tests.conftest import make_user
    a, _ = two
    res = make_user(db, "res@legalapi.com", role="Resident")
    res["user"].society_id = a.sid
    db.commit()
    for path in ("compliance/overview", "legal/documents", "legal/rules", "resolutions", "recovery/arrears"):
        assert client.get(f"{API}/{path}", headers=res["headers"]).status_code == 403


def test_findings_by_dashboard_section(client, two):
    a, _ = two
    a.settings(interest_rate_pct=18)
    a.payment(10, "sinking_fund", 50000, reference="SF")
    client.post(f"{API}/compliance/scan", headers=a.admin["headers"])
    funds = client.get(f"{API}/findings?section=funds", headers=a.manager["headers"]).json()["items"]
    assert funds and {i["category"] for i in funds} <= {"funds", "fund_monitoring", "borrowing"}
    bye = client.get(f"{API}/findings?section=bye_law_compliance", headers=a.manager["headers"]).json()["items"]
    assert any(i["rule_code"] == "L-CHG-INT-01" for i in bye)


def test_society_rule_created_and_verified_as_the_app_does(client, two):
    """The exact requests the Flutter "Add society rule" form and the Verify action send."""
    a, _ = two
    doc = _upload(client, a, text="Bye-law No. 70. Interest at 10 per cent per annum on arrears.").json()
    body = {"rule_code": "SOC-BL70", "title": "Bye-law 70 interest", "topic": "charges.interest_on_arrears.max_rate_pct",
            "rule_category": "charges", "source_level": "D", "source_document_id": doc["id"],
            "calculation_method": {"type": "max_pct", "value": 10}, "bye_law_number": "70", "page_number": "14",
            "effective_from": "2024-04-01", "severity": "MEDIUM"}
    r = client.post(f"{API}/legal/rules", headers=a.admin["headers"], json=body)
    assert r.status_code == 201, r.text
    rule = r.json()
    assert rule["verification_status"] == "PENDING_VERIFICATION" and rule["society_specific"]
    verify = {"verification_status": "VERIFIED_SECONDARY_SOURCE", "note": "checked", "page_number": "14", "legal_status": "BINDING"}
    # Not while its document is unverified.
    assert client.post(f"{API}/legal/rules/{rule['id']}/verify", headers=a.admin["headers"], json=verify).status_code == 422
    assert client.post(f"{API}/legal/documents/{doc['id']}/verify", headers=a.admin["headers"], json={
        "status": "REGISTERED", "verification_status": "VERIFIED_SECONDARY_SOURCE", "note": "certified copy",
        "approval_date": "2020-05-01"}).status_code == 200
    assert client.post(f"{API}/legal/rules/{rule['id']}/verify", headers=a.manager["headers"], json=verify).status_code == 403
    r = client.post(f"{API}/legal/rules/{rule['id']}/verify", headers=a.admin["headers"], json=verify)
    assert r.status_code == 200 and r.json()["verification_status"] == "VERIFIED_SECONDARY_SOURCE"
    app = client.get(f"{API}/legal/applicable?topic=charges.interest_on_arrears.max_rate_pct",
                     headers=a.manager["headers"]).json()
    assert app["effective_value"] == 10                       # the stricter bye-law now governs
    assert client.post(f"{API}/legal/rules", headers=a.admin["headers"], json=body).status_code == 409   # one code, versions after


def test_society_rule_revised_as_the_app_does(client, two):
    """The request the Flutter "Revise rule" screen sends: a new version with a new figure and a change note."""
    a, _ = two
    doc = _upload(client, a, text="Bye-law No. 70. Interest at 10 per cent per annum on arrears.").json()
    client.post(f"{API}/legal/documents/{doc['id']}/verify", headers=a.admin["headers"], json={
        "status": "REGISTERED", "verification_status": "VERIFIED_SECONDARY_SOURCE", "note": "certified copy",
        "approval_date": "2020-05-01"})
    rule = client.post(f"{API}/legal/rules", headers=a.admin["headers"], json={
        "rule_code": "SOC-REV", "title": "Bye-law 70 interest", "topic": "charges.interest_on_arrears.max_rate_pct",
        "rule_category": "charges", "source_level": "D", "source_document_id": doc["id"], "page_number": "14",
        "effective_from": "2024-04-01", "calculation_method": {"type": "max_pct", "value": 10}}).json()
    client.post(f"{API}/legal/rules/{rule['id']}/verify", headers=a.admin["headers"], json={
        "verification_status": "VERIFIED_SECONDARY_SOURCE", "note": "checked", "page_number": "14"})
    body = {"effective_from": "2026-10-01", "change_note": "GB resolution 7/2026 lowered the rate",
            "calculation_method": {"type": "max_pct", "value": 9}, "page_number": "15"}
    assert client.post(f"{API}/legal/rules/{rule['id']}/versions", headers=a.manager["headers"], json=body).status_code == 403
    r = client.post(f"{API}/legal/rules/{rule['id']}/versions", headers=a.admin["headers"], json=body)
    assert r.status_code == 201, r.text
    assert r.json()["version"] == 2 and r.json()["verification_status"] == "PENDING_VERIFICATION"
    detail = client.get(f"{API}/legal/rules/{rule['id']}", headers=a.manager["headers"]).json()
    v1, v2 = detail["versions"]
    assert v1["legal_status"] == "SUPERSEDED" and v1["effective_until"] == "2026-09-30"
    assert v2["change_note"] == "GB resolution 7/2026 lowered the rate"
    old = client.get(f"{API}/legal/applicable?topic=charges.interest_on_arrears.max_rate_pct&on_date=2025-06-01",
                     headers=a.manager["headers"]).json()
    assert old["effective_value"] == 10                   # earlier dates still use version 1
    assert client.post(f"{API}/legal/rules/{rule['id']}/versions", headers=a.admin["headers"], json=body).status_code == 409
