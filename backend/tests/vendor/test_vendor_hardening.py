"""Vendors: what the forms send is checked; numbers are per society; nothing
crosses a society; bills add up and can't be double-entered."""
import pytest
from datetime import date, timedelta
from uuid import UUID as _UUID

from tests.conftest import make_user, make_society

V = "/api/v1/vendors"


def _in(db, user, society):
    user["user"].society_id = _UUID(str(society.id))
    db.commit()
    return user


@pytest.fixture
def rig(db):
    society = make_society(db, "Vendor Hardening Society")
    other = make_society(db, "Other Vendor Society")
    admin = _in(db, make_user(db, "vhadm@v.com", role="Society Admin"), society)
    mgr = _in(db, make_user(db, "vhmgr@v.com", role="Manager"), society)
    oadmin = _in(db, make_user(db, "vhoadm@v.com", role="Society Admin"), other)
    return dict(society=society, other=other, admin=admin, mgr=mgr, oadmin=oadmin, h=admin["headers"])


def _vendor(client, rig, who="admin", society="society", **kw):
    body = {"society_id": str(rig[society].id), "company_name": "CleanPro", "mobile": "9876500301",
            "category": "housekeeping", **kw}
    return client.post(f"{V}/", json=body, headers=rig[who]["headers"])


def _invoice(client, rig, vendor_id, who="admin", **kw):
    body = {"society_id": str(rig["society"].id), "vendor_id": vendor_id, "invoice_number": "INV-1",
            "invoice_date": str(date.today()), "amount": "1000.00", "gst_amount": "180.00", "total_amount": "1180.00", **kw}
    return client.post(f"{V}/invoices", json=body, headers=rig[who]["headers"])


def test_vendor_fields_are_checked_and_tidied(client, rig):
    assert _vendor(client, rig, company_name="  ").status_code == 422
    assert _vendor(client, rig, company_name="c" * 256).status_code == 422
    assert _vendor(client, rig, mobile="12ab").status_code == 422
    assert _vendor(client, rig, email="nope").status_code == 422
    assert _vendor(client, rig, gst_number="123").status_code == 422
    assert _vendor(client, rig, pan_number="12345").status_code == 422
    assert _vendor(client, rig, bank_ifsc="ABCD").status_code == 422
    assert _vendor(client, rig, bank_account="12").status_code == 422
    r = _vendor(client, rig, company_name=" Clean  Pro ", email=" Sales@Clean.COM ", gst_number="27aaaaa0000a1z5",
                pan_number="abcde1234f", bank_ifsc="hdfc0001234", city="  ", contact_person=" Ravi ")
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["company_name"] == "Clean Pro" and j["email"] == "sales@clean.com"
    assert j["gst_number"] == "27AAAAA0000A1Z5" and j["bank_ifsc"] == "HDFC0001234" and j["contact_person"] == "Ravi"


def test_duplicate_vendor_name_and_gst_are_refused(client, rig):
    assert _vendor(client, rig, gst_number="27AAAAA0000A1Z5").status_code == 201
    assert _vendor(client, rig, company_name="cleanpro", mobile="9876500302").status_code == 409
    r = _vendor(client, rig, company_name="Other Co", gst_number="27AAAAA0000A1Z5")
    assert r.status_code == 409 and "GST" in r.json()["detail"]


def test_numbers_are_per_society(client, rig):
    a = _vendor(client, rig).json()
    b = _vendor(client, rig, who="oadmin", society="other")
    assert b.status_code == 201, b.text
    assert a["vendor_code"] == b.json()["vendor_code"] == "VND-0001"
    assert _vendor(client, rig, company_name="Second", mobile="9876500399").json()["vendor_code"] == "VND-0002"
    # Contracts and service requests too
    today = date.today()
    contract = lambda who, society, vid: client.post(f"{V}/contracts", json={
        "society_id": str(rig[society].id), "vendor_id": vid, "contract_name": "AMC", "category": "housekeeping",
        "start_date": str(today), "end_date": str(today + timedelta(days=365)), "service_frequency": "monthly"},
        headers=rig[who]["headers"])
    c1 = contract("admin", "society", a["id"])
    c2 = contract("oadmin", "other", b.json()["id"])
    assert c1.status_code == 201 and c2.status_code == 201, (c1.text, c2.text)
    sr = lambda who, society: client.post(f"{V}/service-requests", json={
        "society_id": str(rig[society].id), "title": "Fix pump", "category": "housekeeping"}, headers=rig[who]["headers"])
    s1, s2 = sr("admin", "society"), sr("oadmin", "other")
    assert s1.status_code == 201 and s2.status_code == 201, (s1.text, s2.text)
    assert s1.json()["request_number"] == s2.json()["request_number"] == "SRQ-00001"


def test_nothing_crosses_a_society(client, rig):
    vid = _vendor(client, rig).json()["id"]
    oh = rig["oadmin"]["headers"]
    sid = rig["society"].id
    assert client.get(f"{V}/{vid}", headers=oh).status_code == 404
    assert client.post(f"{V}/{vid}/blacklist", json={"reason": "x"}, headers=oh).status_code == 404
    assert client.post(f"{V}/{vid}/services", json={"service_name": "x", "category": "housekeeping"}, headers=oh).status_code == 404
    for path in (f"society/{sid}", f"society/{sid}/category/housekeeping", f"contracts/society/{sid}",
                 f"contracts/expiring/{sid}", f"service-requests/society/{sid}", f"service-requests/open/{sid}",
                 f"invoices/society/{sid}"):
        assert client.get(f"{V}/{path}", headers=oh).status_code == 403, path
    assert client.get(f"{V}/invoices/vendor/{vid}", headers=oh).status_code == 404
    assert _vendor(client, rig, who="oadmin").status_code == 403
    # A bill for another society's vendor, or a request naming one
    ov = _vendor(client, rig, who="oadmin", society="other").json()["id"]
    assert _invoice(client, rig, ov).status_code == 422
    r = client.post(f"{V}/service-requests", json={"society_id": str(sid), "title": "T", "category": "housekeeping",
                                                   "vendor_id": ov}, headers=rig["h"])
    assert r.status_code == 422


def test_blacklisted_vendors_cant_be_assigned_and_blacklist_needs_a_reason(client, rig):
    vid = _vendor(client, rig).json()["id"]
    sr = client.post(f"{V}/service-requests", json={"society_id": str(rig["society"].id), "title": "T",
                                                    "category": "housekeeping"}, headers=rig["h"]).json()["id"]
    assert client.post(f"{V}/{vid}/blacklist", json={"reason": " "}, headers=rig["h"]).status_code == 422
    assert client.post(f"{V}/{vid}/blacklist", json={"reason": "Poor work"}, headers=rig["h"]).status_code == 200
    r = client.post(f"{V}/service-requests/{sr}/assign-vendor", json={"vendor_id": vid}, headers=rig["h"])
    assert r.status_code == 422 and "blacklisted" in r.json()["detail"]


def test_contract_and_request_forms_are_checked(client, rig):
    vid = _vendor(client, rig).json()["id"]
    today = date.today()
    body = {"society_id": str(rig["society"].id), "vendor_id": vid, "contract_name": "AMC", "category": "housekeeping",
            "start_date": str(today), "end_date": str(today + timedelta(days=30)), "service_frequency": "monthly"}
    h = rig["h"]
    assert client.post(f"{V}/contracts", json={**body, "end_date": str(today)}, headers=h).status_code == 422
    assert client.post(f"{V}/contracts", json={**body, "contract_name": " "}, headers=h).status_code == 422
    assert client.post(f"{V}/contracts", json={**body, "annual_value": "-5"}, headers=h).status_code == 422
    assert client.post(f"{V}/contracts", json={**body, "renewal_notice_days": 9999}, headers=h).status_code == 422
    assert client.post(f"{V}/contracts", json={**body, "document_url": "not a link"}, headers=h).status_code == 422
    assert client.post(f"{V}/service-requests", json={"society_id": str(rig["society"].id), "title": "  ",
                                                      "category": "housekeeping"}, headers=h).status_code == 422
    assert client.post(f"{V}/visits", json={"society_id": str(rig["society"].id), "vendor_id": vid,
                                            "visit_date": str(today), "check_in_time": "2026-01-01T10:00:00",
                                            "check_out_time": "2026-01-01T09:00:00"}, headers=h).status_code == 422
    ok = client.post(f"{V}/visits", json={"society_id": str(rig["society"].id), "vendor_id": vid,
                                          "visit_date": str(today), "check_in_time": "2026-01-01T09:00:00",
                                          "check_out_time": "2026-01-01T10:00:00", "work_done": " Cleaned "}, headers=h)
    assert ok.status_code == 201, ok.text


def test_bills_add_up_and_are_not_double_entered(client, rig):
    vid = _vendor(client, rig).json()["id"]
    assert _invoice(client, rig, vid, total_amount="1000.00").status_code == 422      # total != amount + gst
    assert _invoice(client, rig, vid, amount="-1", total_amount="179.00").status_code == 422
    assert _invoice(client, rig, vid, gst_amount="-1", total_amount="999.00").status_code == 422
    assert _invoice(client, rig, vid, amount="10.123", gst_amount="0", total_amount="10.123").status_code == 422
    assert _invoice(client, rig, vid, invoice_number=" ").status_code == 422
    assert _invoice(client, rig, vid, due_date=str(date.today() - timedelta(days=2))).status_code == 422
    assert _invoice(client, rig, vid, doc_url="nope").status_code == 422
    ok = _invoice(client, rig, vid)
    assert ok.status_code == 201, ok.text
    again = _invoice(client, rig, vid, invoice_number="inv-1")
    assert again.status_code == 409 and "already" in again.json()["detail"]
    # Tidy float-free money round-trips
    assert _invoice(client, rig, vid, invoice_number="INV-2", amount="100.30", gst_amount="0.00",
                    total_amount="100.30").status_code == 201


def test_payments_are_checked_and_scoped(client, rig):
    vid = _vendor(client, rig).json()["id"]
    inv = _invoice(client, rig, vid).json()["id"]
    pay = lambda **kw: client.post(f"{V}/invoices/{inv}/payments", json={"amount": "500.00", "paid_date": str(date.today()),
                                                                          "payment_mode": "cash", **kw}, headers=rig["h"])
    assert pay(amount="0").status_code == 422
    assert pay(amount="1.234").status_code == 422
    assert pay(amount="5000").status_code == 422                      # more than is owed
    assert pay(paid_date=str(date.today() + timedelta(days=2))).status_code == 422
    assert pay(paid_date=str(date.today() - timedelta(days=5))).status_code == 422   # before the invoice
    assert pay(payment_ref="r" * 101).status_code == 422
    assert client.post(f"{V}/invoices/{inv}/payments", json={"amount": "500.00", "paid_date": str(date.today()),
                                                              "payment_mode": "cash"}, headers=rig["oadmin"]["headers"]
                       ).status_code == 404
    assert client.get(f"{V}/invoices/{inv}", headers=rig["oadmin"]["headers"]).status_code == 404
    assert pay().status_code == 200


def test_list_paging_is_bounded(client, rig):
    sid = rig["society"].id
    assert client.get(f"{V}/society/{sid}?limit=100000", headers=rig["mgr"]["headers"]).status_code == 422
    assert client.get(f"{V}/invoices/society/{sid}?skip=-1", headers=rig["mgr"]["headers"]).status_code == 422


def test_a_bill_with_gst_is_split_by_state_and_never_answers_500(client, rig, db):
    """The app sends only the GST amount. It is split CGST + SGST for a vendor in the society's state and IGST for
    another state; a bill that does not add up is a 422, never a server error."""
    from app.models.society import Society
    rig["society"].gst_number = "27AAAAA0000A1Z5"
    db.commit()
    same = _vendor(client, rig, gst_number="27BBBBB1111B1Z6").json()["id"]
    a = _invoice(client, rig, same)
    assert a.status_code == 201, a.text
    assert (a.json()["cgst_amount"], a.json()["sgst_amount"], a.json()["igst_amount"]) == ("90.00", "90.00", "0.00")

    other = _vendor(client, rig, company_name="Karnataka Lifts", mobile="9876500302", gst_number="29CCCCC2222C1Z7").json()["id"]
    b = _invoice(client, rig, other, invoice_number="INV-9")
    assert b.status_code == 201, b.text
    assert (b.json()["cgst_amount"], b.json()["sgst_amount"], b.json()["igst_amount"]) == ("0.00", "0.00", "180.00")

    # no GSTIN on file: treated as in-state; the caller may also say which
    c = _vendor(client, rig, company_name="Local Plumber", mobile="9876500303").json()["id"]
    assert _invoice(client, rig, c, invoice_number="INV-3").json()["cgst_amount"] == "90.00"
    d = _invoice(client, rig, c, invoice_number="INV-4", gst_component="IGST")
    assert d.status_code == 201 and d.json()["igst_amount"] == "180.00"
    assert _invoice(client, rig, c, invoice_number="INV-5", gst_component="BOTH").status_code == 422
    # a bill without GST is unaffected
    assert _invoice(client, rig, c, invoice_number="INV-6", gst_amount="0.00", total_amount="1000.00").status_code == 201
