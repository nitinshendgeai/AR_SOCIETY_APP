"""Work orders, quotations and sanctions as the model bye-laws require
(bye-law 157): the committee's limit by society size, tenders above the
general body's limit, the general body's sanction, the lowest quotation or a
recorded reason, no committee member interested, and money paid only within
what was sanctioned — advance before completion, retention until the defect
liability period ends."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID as _UUID

import pytest

from tests.conftest import make_flat, make_society, make_user, make_wing

V = "/api/v1/vendors"
TODAY = date.today()


def _in(db, user, society):
    user["user"].society_id = _UUID(str(society.id))
    db.commit()
    return user


@pytest.fixture
def rig(db):
    society = make_society(db, "Work Order Society")
    other = make_society(db, "Other WO Society")
    sec = _in(db, make_user(db, "wosec@v.com", role="Committee Secretary", full_name="Asha Secretary"), society)
    mgr = _in(db, make_user(db, "womgr@v.com", role="Manager"), society)
    oadmin = _in(db, make_user(db, "wooadm@v.com", role="Society Admin"), other)
    return dict(society=society, other=other, sec=sec["headers"], sec_user=sec["user"], mgr=mgr["headers"],
                oadmin=oadmin["headers"])


_n = iter(range(1, 10_000))


def _vendor(client, rig, name=None, **kw):
    i = next(_n)
    body = {"society_id": str(rig["society"].id), "company_name": name or f"Vendor {i}",
            "mobile": f"98{i:08d}", "category": "plumbing", **kw}
    r = client.post(f"{V}/", json=body, headers=rig["sec"])
    assert r.status_code == 201, r.text
    return r.json()


def _wo(client, rig, who="mgr", **kw):
    body = {"society_id": str(rig["society"].id), "title": "Replace terrace water tank", "category": "plumbing",
            "scope_of_work": "Remove old tank\nInstall 2000 L tank", **kw}
    r = client.post(f"{V}/work-orders", json=body, headers=rig[who])
    assert r.status_code == 201, r.text
    return r.json()


def _quote(client, rig, wo_id, vendor_id, amount, when=None, path="work-orders", **kw):
    amount = Decimal(amount)
    body = {"vendor_id": vendor_id, "quotation_date": str(when or TODAY - timedelta(days=20)),
            "amount": str(amount), "gst_amount": "0.00", "total_amount": str(amount), **kw}
    return client.post(f"{V}/{path}/{wo_id}/quotations", json=body, headers=rig["mgr"])


def _sanction(client, rig, wo_id, quotation_id, path="work-orders", **kw):
    body = {"quotation_id": quotation_id, "committee_resolution_no": "MC/12/2026",
            "committee_meeting_date": str(TODAY - timedelta(days=10)), "no_interest_declared": True, **kw}
    return client.post(f"{V}/{path}/{wo_id}/sanction", json=body, headers=rig["sec"])


def _ready(client, rig, amount="20000", **wo_kw):
    """A sanctioned work order from one vendor's quotation."""
    v = _vendor(client, rig)
    wo = _wo(client, rig, **wo_kw)
    r = _quote(client, rig, wo["id"], v["id"], amount)
    assert r.status_code == 201, r.text
    q = r.json()["quotations"][0]
    r = _sanction(client, rig, wo["id"], q["id"])
    assert r.status_code == 200, r.text
    return v, r.json()


def _bill(client, rig, wo, vendor_id, total, number=None, **kw):
    body = {"society_id": str(rig["society"].id), "vendor_id": vendor_id, "work_order_id": wo["id"],
            "invoice_number": number or f"B-{next(_n)}", "invoice_date": str(TODAY - timedelta(days=3)),
            "amount": str(total), "gst_amount": "0.00", "total_amount": str(total), **kw}
    return client.post(f"{V}/invoices", json=body, headers=rig["mgr"])


def _pay(client, rig, invoice_id, amount):
    return client.post(f"{V}/invoices/{invoice_id}/payments", json={
        "amount": str(amount), "paid_date": str(TODAY), "payment_mode": "neft", "payment_ref": "UTR1"},
        headers=rig["mgr"])


# ── Limits ───────────────────────────────────────────────────────────────────

def test_committee_limit_follows_the_bye_law_slab_for_the_society_size(client, db, rig):
    sid = rig["society"].id
    r = client.get(f"{V}/procurement-settings/{sid}", headers=rig["mgr"])
    assert r.status_code == 200, r.text
    assert r.json()["committee_limit"] == "25000" and r.json()["tender_limit"] == "25000"
    wing = make_wing(db, sid)
    for i in range(30):
        make_flat(db, wing.id, f"{100 + i}")
    j = client.get(f"{V}/procurement-settings/{sid}", headers=rig["mgr"]).json()
    assert j["members"] == 30 and j["committee_limit"] == "50000" and j["min_quotations"] == 3
    for i in range(30, 60):
        make_flat(db, wing.id, f"{100 + i}")
    assert client.get(f"{V}/procurement-settings/{sid}", headers=rig["mgr"]).json()["committee_limit"] == "100000"


def test_other_limits_need_a_general_body_resolution(client, rig):
    sid = rig["society"].id
    body = {"committee_limit": "300000", "tender_limit": "50000", "min_quotations": 3}
    assert client.put(f"{V}/procurement-settings/{sid}", json=body, headers=rig["mgr"]).status_code == 403
    r = client.put(f"{V}/procurement-settings/{sid}", json=body, headers=rig["sec"])
    assert r.status_code == 422 and "general body" in r.json()["detail"]
    r = client.put(f"{V}/procurement-settings/{sid}", json={
        **body, "gb_resolution_no": "AGM/5/2026", "gb_meeting_date": str(TODAY - timedelta(days=30))},
        headers=rig["sec"])
    assert r.status_code == 200, r.text
    assert r.json()["committee_limit"] == "300000.00" and r.json()["tender_limit"] == "50000.00"
    assert client.put(f"{V}/procurement-settings/{sid}", json={"min_quotations": 1},
                      headers=rig["sec"]).status_code == 422


# ── Sanction ─────────────────────────────────────────────────────────────────

def test_small_work_is_sanctioned_by_the_committee(client, rig):
    v = _vendor(client, rig)
    wo = _wo(client, rig)
    assert wo["status"] == "draft" and wo["wo_number"] == f"WO-{TODAY.year}-0001"
    q = _quote(client, rig, wo["id"], v["id"], "18000", quotation_ref="Q-77").json()["quotations"][0]
    r = _sanction(client, rig, wo["id"], q["id"])
    assert r.status_code == 200, r.text
    j =client.get(f"{V}/work-orders/{wo['id']}", headers=rig["mgr"]).json()
    assert j["status"] == "sanctioned" and j["sanction_level"] == "committee"
    assert j["vendor_name"] == v["company_name"] and j["sanctioned_amount"] == "18000.00"
    assert j["committee_resolution_no"] == "MC/12/2026" and j["gb_resolution_no"] is None
    assert j["quotations"][0]["is_selected"] and j["sanctioned_by_name"] == "Asha Secretary"


def test_the_manager_cannot_sanction_and_the_declaration_is_required(client, rig):
    v = _vendor(client, rig)
    wo = _wo(client, rig)
    q = _quote(client, rig, wo["id"], v["id"], "5000").json()["quotations"][0]
    r = client.post(f"{V}/work-orders/{wo['id']}/sanction", json={
        "quotation_id": q["id"], "committee_resolution_no": "1", "committee_meeting_date": str(TODAY),
        "no_interest_declared": True}, headers=rig["mgr"])
    assert r.status_code == 403
    r = _sanction(client, rig, wo["id"], q["id"], no_interest_declared=False)
    assert r.status_code == 422 and "interest" in r.json()["detail"]
    r = _sanction(client, rig, wo["id"], q["id"], committee_resolution_no=" ")
    assert r.status_code == 422
    r = _sanction(client, rig, wo["id"], q["id"], committee_meeting_date=str(TODAY + timedelta(days=1)))
    assert r.status_code == 422 and "future" in r.json()["detail"]


def test_above_the_committee_limit_needs_the_general_body(client, rig):
    sid = rig["society"].id
    client.put(f"{V}/procurement-settings/{sid}", json={
        "committee_limit": "25000", "tender_limit": "100000", "min_quotations": 3,
        "gb_resolution_no": "AGM/1", "gb_meeting_date": str(TODAY - timedelta(days=60))}, headers=rig["sec"])
    v = _vendor(client, rig)
    wo = _wo(client, rig)
    q = _quote(client, rig, wo["id"], v["id"], "60000").json()["quotations"][0]
    assert wo["requirements"]["needs_general_body"] is False
    r = _sanction(client, rig, wo["id"], q["id"])
    assert r.status_code == 422 and "general body" in r.json()["detail"] and "25,000" in r.json()["detail"]
    r = _sanction(client, rig, wo["id"], q["id"], gb_resolution_no="SGM/3",
                  gb_meeting_date=str(TODAY - timedelta(days=5)))
    assert r.status_code == 200, r.text
    assert r.json()["sanction_level"] == "general_body" and r.json()["tenders_opened_on"] is None


def test_above_the_tender_limit_needs_tenders_opened_and_the_general_body(client, rig):
    vs = [_vendor(client, rig) for _ in range(3)]
    wo = _wo(client, rig, estimated_cost="90000")
    assert wo["requirements"]["needs_tenders"] and wo["requirements"]["min_quotations"] == 3
    q1 = _quote(client, rig, wo["id"], vs[0]["id"], "80000").json()["quotations"][0]
    _quote(client, rig, wo["id"], vs[1]["id"], "85000")
    gb = dict(gb_resolution_no="SGM/4", gb_meeting_date=str(TODAY - timedelta(days=2)))
    r = _sanction(client, rig, wo["id"], q1["id"], tenders_opened_on=str(TODAY - timedelta(days=12)), **gb)
    assert r.status_code == 422 and "at least 3 vendors" in r.json()["detail"]
    _quote(client, rig, wo["id"], vs[2]["id"], "88000", when=TODAY - timedelta(days=11))
    r = _sanction(client, rig, wo["id"], q1["id"], **gb)
    assert r.status_code == 422 and "opened" in r.json()["detail"]
    r = _sanction(client, rig, wo["id"], q1["id"], tenders_opened_on=str(TODAY - timedelta(days=12)), **gb)
    assert r.status_code == 422 and vs[2]["company_name"] in r.json()["detail"]   # came in after opening
    r = _sanction(client, rig, wo["id"], q1["id"], tenders_opened_on=str(TODAY - timedelta(days=10)))
    assert r.status_code == 422 and "general body" in r.json()["detail"]
    r = _sanction(client, rig, wo["id"], q1["id"], tenders_opened_on=str(TODAY - timedelta(days=10)),
                  gb_resolution_no="SGM/4", gb_meeting_date=str(TODAY - timedelta(days=11)))
    assert r.status_code == 422 and "after the tenders" in r.json()["detail"]
    r = _sanction(client, rig, wo["id"], q1["id"], tenders_opened_on=str(TODAY - timedelta(days=10)), **gb)
    assert r.status_code == 200, r.text
    assert r.json()["sanction_level"] == "general_body" and r.json()["tenders_opened_on"]


def test_not_taking_the_lowest_quotation_needs_a_reason(client, rig):
    a, b = _vendor(client, rig, "Cheap Co"), _vendor(client, rig, "Better Co")
    wo = _wo(client, rig)
    _quote(client, rig, wo["id"], a["id"], "9000")
    j = _quote(client, rig, wo["id"], b["id"], "12000").json()
    lowest = next(q for q in j["quotations"] if q["is_lowest"])
    assert lowest["vendor_name"] == "Cheap Co"
    dear = next(q for q in j["quotations"] if not q["is_lowest"])
    r = _sanction(client, rig, wo["id"], dear["id"])
    assert r.status_code == 422 and "Cheap Co quoted less" in r.json()["detail"]
    r = _sanction(client, rig, wo["id"], dear["id"], selection_reason="Cheap Co has no plumbing licence")
    assert r.status_code == 200 and r.json()["selection_reason"].startswith("Cheap Co has")


def test_a_committee_members_concern_cannot_be_given_work(client, db, rig):
    rig["sec_user"].phone = "+91 98200 11122"
    db.commit()
    v = _vendor(client, rig, "Secretary's Brother Ltd", mobile="9820011122")
    wo = _wo(client, rig)
    q = _quote(client, rig, wo["id"], v["id"], "8000").json()["quotations"][0]
    r = _sanction(client, rig, wo["id"], q["id"])
    assert r.status_code == 422 and "Asha Secretary" in r.json()["detail"]


def test_quotation_rules(client, rig):
    a, b = _vendor(client, rig), _vendor(client, rig)
    wo = _wo(client, rig)
    assert _quote(client, rig, wo["id"], a["id"], "1000").status_code == 201
    assert _quote(client, rig, wo["id"], a["id"], "900").status_code == 409          # one per vendor
    bad = _quote(client, rig, wo["id"], b["id"], "1000", total_amount="1100")
    assert bad.status_code == 422                                                     # total ≠ amount + GST
    r = _quote(client, rig, wo["id"], b["id"], "800", when=TODAY - timedelta(days=40),
               valid_until=str(TODAY - timedelta(days=30)))
    assert r.status_code == 201
    expired = next(q for q in r.json()["quotations"] if q["vendor_id"] == b["id"])
    r = _sanction(client, rig, wo["id"], expired["id"])
    assert r.status_code == 422 and "expired" in r.json()["detail"]
    client.post(f"{V}/{b['id']}/blacklist", json={"reason": "Abandoned a job"}, headers=rig["sec"])
    c = _vendor(client, rig)
    client.post(f"{V}/{c['id']}/blacklist", json={"reason": "Fraud"}, headers=rig["sec"])
    assert _quote(client, rig, wo["id"], c["id"], "700").status_code == 422
    r = _sanction(client, rig, wo["id"], expired["id"])
    assert r.status_code == 422 and "blacklisted" in r.json()["detail"]
    r = client.delete(f"{V}/work-orders/{wo['id']}/quotations/{expired['id']}", headers=rig["mgr"])
    assert r.status_code == 200 and len(r.json()["quotations"]) == 1


# ── Issue, bills, payments, completion, retention, closure ───────────────────

def test_work_order_money_stays_within_the_sanction(client, rig):
    v, wo = _ready(client, rig, "20000", advance_amount="5000", retention_pct="10", defect_liability_months=12)
    other = _vendor(client, rig)
    assert _bill(client, rig, wo, v["id"], "5000").status_code == 422               # not issued yet
    assert client.post(f"{V}/work-orders/{wo['id']}/issue", json={"issued_on": str(TODAY - timedelta(days=11))},
                       headers=rig["sec"]).status_code == 422                       # before the sanction
    r = client.post(f"{V}/work-orders/{wo['id']}/issue", json={}, headers=rig["sec"])
    assert r.status_code == 200 and r.json()["status"] == "issued"
    assert _bill(client, rig, wo, other["id"], "1000").status_code == 422            # another vendor
    r = _bill(client, rig, wo, v["id"], "25000")
    assert r.status_code == 422 and "revised" in r.json()["detail"]
    b1 = _bill(client, rig, wo, v["id"], "15000")
    assert b1.status_code == 201, b1.text
    b1 = b1.json()
    assert b1["wo_number"] == wo["wo_number"]
    # Before completion only the advance
    r = _pay(client, rig, b1["id"], "6000")
    assert r.status_code == 422 and "advance" in r.json()["detail"]
    assert _pay(client, rig, b1["id"], "5000").status_code == 200
    # Completion certified by the committee
    assert client.post(f"{V}/work-orders/{wo['id']}/complete", json={
        "completed_on": str(TODAY), "completion_notes": "Checked"}, headers=rig["mgr"]).status_code == 403
    r = client.post(f"{V}/work-orders/{wo['id']}/complete", json={
        "completed_on": str(TODAY), "completion_notes": "Tank installed and tested, no leaks"}, headers=rig["sec"])
    assert r.status_code == 200 and r.json()["certified_by_name"] == "Asha Secretary"
    b2 = _bill(client, rig, wo, v["id"], "5000").json()
    j = client.get(f"{V}/work-orders/{wo['id']}", headers=rig["mgr"]).json()
    assert j["billed"] == "20000.00" and j["retention_held"] == "2000.00" and j["payable_now"] == "13000.00"
    assert _pay(client, rig, b1["id"], "10000").status_code == 200
    r = _pay(client, rig, b2["id"], "5000")
    assert r.status_code == 422 and "retention" in r.json()["detail"]
    assert _pay(client, rig, b2["id"], "3000").status_code == 200
    r = client.post(f"{V}/work-orders/{wo['id']}/close", headers=rig["sec"])
    assert r.status_code == 409 and b2["invoice_number"] in r.json()["detail"]
    r = client.post(f"{V}/work-orders/{wo['id']}/release-retention", json={}, headers=rig["sec"])
    assert r.status_code == 422 and "defect liability" in r.json()["detail"]


def test_retention_is_released_after_the_defect_liability_period(client, db, rig):
    v, wo = _ready(client, rig, "10000", retention_pct="5", defect_liability_months=6)
    from app.modules.vendor.models.vendor import WorkOrder
    row = db.get(WorkOrder, _UUID(wo["id"]))
    row.committee_meeting_date = TODAY - timedelta(days=300)
    db.commit()
    client.post(f"{V}/work-orders/{wo['id']}/issue", json={"issued_on": str(TODAY - timedelta(days=290))},
                headers=rig["sec"])
    done = TODAY - timedelta(days=250)
    client.post(f"{V}/work-orders/{wo['id']}/complete", json={"completed_on": str(done),
                                                             "completion_notes": "Done"}, headers=rig["sec"])
    bill = _bill(client, rig, wo, v["id"], "10000").json()
    assert _pay(client, rig, bill["id"], "9500").status_code == 200
    assert _pay(client, rig, bill["id"], "500").status_code == 422
    early = done + timedelta(days=100)
    r = client.post(f"{V}/work-orders/{wo['id']}/release-retention", json={"released_on": str(early)},
                    headers=rig["sec"])
    assert r.status_code == 422
    r = client.post(f"{V}/work-orders/{wo['id']}/release-retention", json={}, headers=rig["sec"])
    assert r.status_code == 200 and r.json()["retention_held"] == "0.00"
    assert _pay(client, rig, bill["id"], "500").status_code == 200
    r = client.post(f"{V}/work-orders/{wo['id']}/close", headers=rig["sec"])
    assert r.status_code == 200 and r.json()["status"] == "closed"


def test_a_revised_sanction_lets_more_be_billed(client, rig):
    v, wo = _ready(client, rig, "20000")
    client.post(f"{V}/work-orders/{wo['id']}/issue", json={}, headers=rig["sec"])
    assert _bill(client, rig, wo, v["id"], "24000").status_code == 422
    body = {"amount": "24000", "reason": "Extra plumbing found rotten", "committee_resolution_no": "MC/14",
            "committee_meeting_date": str(TODAY)}
    assert client.post(f"{V}/work-orders/{wo['id']}/revise-sanction", json=body,
                       headers=rig["mgr"]).status_code == 403
    r = client.post(f"{V}/work-orders/{wo['id']}/revise-sanction", json=body, headers=rig["sec"])
    assert r.status_code == 200 and r.json()["sanctioned_amount"] == "24000.00"
    assert _bill(client, rig, wo, v["id"], "24000").status_code == 201
    # Over the committee's limit, the general body must sanction the revision
    r = client.post(f"{V}/work-orders/{wo['id']}/revise-sanction", json={**body, "amount": "30000"},
                    headers=rig["sec"])
    assert r.status_code == 422 and "general body" in r.json()["detail"]
    r = client.post(f"{V}/work-orders/{wo['id']}/revise-sanction", json={**body, "amount": "1000"},
                    headers=rig["sec"])
    assert r.status_code == 422 and "already recorded" in r.json()["detail"]


def test_bills_default_to_the_work_orders_expense_head(client, rig):
    ledgers = {a["system_key"]: a for a in client.get(f"/api/v1/accounts/ledgers/{rig['society'].id}",
                                                      headers=rig["sec"]).json()}
    head = ledgers["repairs_plumbing"]
    v, wo = _ready(client, rig, "5000", expense_account_id=head["id"])
    assert wo["expense_account_name"] == head["name"]
    client.post(f"{V}/work-orders/{wo['id']}/issue", json={}, headers=rig["sec"])
    assert _bill(client, rig, wo, v["id"], "5000").json()["expense_account_id"] == head["id"]


def test_cancel_and_print(client, rig):
    v, wo = _ready(client, rig, "7000")
    draft = _wo(client, rig)
    assert client.get(f"{V}/work-orders/{draft['id']}/pdf", headers=rig["mgr"]).status_code == 409
    r = client.get(f"{V}/work-orders/{wo['id']}/pdf", headers=rig["mgr"])
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert client.post(f"{V}/work-orders/{draft['id']}/cancel", json={"reason": " "},
                       headers=rig["sec"]).status_code == 422
    r = client.post(f"{V}/work-orders/{draft['id']}/cancel", json={"reason": "Not needed"}, headers=rig["sec"])
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    client.post(f"{V}/work-orders/{wo['id']}/issue", json={}, headers=rig["sec"])
    _bill(client, rig, wo, v["id"], "1000")
    r = client.post(f"{V}/work-orders/{wo['id']}/cancel", json={"reason": "x"}, headers=rig["sec"])
    assert r.status_code == 409
    r = client.patch(f"{V}/work-orders/{wo['id']}", json={"title": "New"}, headers=rig["mgr"])
    assert r.status_code == 409


def test_sanctioned_terms_are_locked(client, rig):
    _, wo = _ready(client, rig, "7000", retention_pct="5")
    r = client.patch(f"{V}/work-orders/{wo['id']}", json={"retention_pct": "0"}, headers=rig["mgr"])
    assert r.status_code == 409
    r = client.patch(f"{V}/work-orders/{wo['id']}", json={"location": "B wing terrace"}, headers=rig["mgr"])
    assert r.status_code == 200 and r.json()["location"] == "B wing terrace"
    r = client.patch(f"{V}/work-orders/{wo['id']}", json={"title": None}, headers=rig["mgr"])
    assert r.status_code == 422


def test_work_orders_stay_in_their_society(client, rig):
    _, wo = _ready(client, rig, "3000")
    assert client.get(f"{V}/work-orders/{wo['id']}", headers=rig["oadmin"]).status_code == 404
    assert client.get(f"{V}/work-orders/society/{rig['society'].id}", headers=rig["oadmin"]).status_code == 403
    r = client.get(f"{V}/work-orders/society/{rig['society'].id}?status=sanctioned", headers=rig["mgr"])
    assert r.status_code == 200 and [w["id"] for w in r.json()] == [wo["id"]]
    assert client.get(f"{V}/work-orders/society/{rig['society'].id}?status=nope",
                      headers=rig["mgr"]).status_code == 422


# ── Annual contracts take the same sanction ──────────────────────────────────

def test_an_annual_contract_starts_only_after_it_is_sanctioned(client, rig):
    a, b = _vendor(client, rig), _vendor(client, rig)
    r = client.post(f"{V}/contracts", json={
        "society_id": str(rig["society"].id), "vendor_id": a["id"], "contract_name": "Lift AMC 2026-27",
        "category": "lift", "start_date": str(TODAY), "end_date": str(TODAY + timedelta(days=364)),
        "service_frequency": "monthly"}, headers=rig["mgr"])
    assert r.status_code == 201, r.text
    c = r.json()
    r = client.post(f"{V}/contracts/{c['id']}/activate", headers=rig["sec"])
    assert r.status_code == 409 and "sanction" in r.json()["detail"]
    _quote(client, rig, c["id"], a["id"], "24000", path="contracts")
    j = _quote(client, rig, c["id"], b["id"], "21000", path="contracts").json()
    chosen = next(q for q in j["quotations"] if q["vendor_id"] == b["id"])
    r = _sanction(client, rig, c["id"], chosen["id"], path="contracts")
    assert r.status_code == 200, r.text
    assert r.json()["vendor_id"] == b["id"] and r.json()["annual_value"] == "21000.00"
    assert _quote(client, rig, c["id"], a["id"], "1", path="contracts").status_code == 409
    r = client.post(f"{V}/contracts/{c['id']}/activate", headers=rig["sec"])
    assert r.status_code == 200 and r.json()["status"] == "active"
    listed = client.get(f"{V}/contracts/society/{rig['society'].id}", headers=rig["mgr"]).json()
    assert listed[0]["committee_resolution_no"] == "MC/12/2026"


# ── Vendor master edits ──────────────────────────────────────────────────────

def test_vendor_details_can_be_edited(client, rig):
    a = _vendor(client, rig, "Alpha Plumbers")
    b = _vendor(client, rig, "Beta Plumbers")
    r = client.patch(f"{V}/{a['id']}", json={"city": " Thane ", "pincode": "400601", "pan_number": "abcde1234f"},
                     headers=rig["sec"])
    assert r.status_code == 200 and r.json()["city"] == "Thane" and r.json()["pan_number"] == "ABCDE1234F"
    assert client.patch(f"{V}/{a['id']}", json={"company_name": "beta plumbers"},
                        headers=rig["sec"]).status_code == 409
    assert client.patch(f"{V}/{a['id']}", json={"pincode": "12"}, headers=rig["sec"]).status_code == 422
    assert client.patch(f"{V}/{a['id']}", json={"mobile": None}, headers=rig["sec"]).status_code == 422
    assert client.patch(f"{V}/{a['id']}", json={"status": "blacklisted"}, headers=rig["sec"]).status_code == 422
    assert client.patch(f"{V}/{a['id']}", json={"city": "X"}, headers=rig["mgr"]).status_code == 403
    client.post(f"{V}/{b['id']}/blacklist", json={"reason": "Poor work"}, headers=rig["sec"])
    r = client.patch(f"{V}/{b['id']}", json={"status": "active"}, headers=rig["sec"])
    assert r.status_code == 200 and r.json()["status"] == "active" and r.json()["blacklist_reason"] is None
    assert client.patch(f"{V}/{a['id']}", json={"city": "X"}, headers=rig["oadmin"]).status_code == 404
