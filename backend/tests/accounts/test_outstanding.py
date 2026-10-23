"""Outstandings, Tally style: what members owe (receivable) and what the society owes vendors (payable), aged in days
past the due date, party by party with the bills behind each."""
from datetime import date, timedelta
from decimal import Decimal

from app.modules.accounts.services.outstanding import bucket_of
from tests.billing.test_defaulters import _two_cycles
from tests.billing.test_maintenance_billing import _rig
from tests.conftest import make_user

A = "/api/v1/accounts"
TODAY = date.today()


def test_buckets_are_days_past_the_due_date():
    assert [bucket_of(d) for d in (0, 1, 30, 31, 60, 61, 90, 91, 400)] == [
        "not_due", "d1_30", "d1_30", "d31_60", "d31_60", "d61_90", "d61_90", "over_90", "over_90"]


def test_receivable_ages_each_flats_dues_with_the_bills_behind(client, db):
    society, flat1, flat2, manager, _res = _two_cycles(client, db, "os1")
    h, sid = manager["headers"], str(society.id)
    rep = client.get(f"{A}/outstanding/{sid}", params={"kind": "receivable"}, headers=h).json()
    assert rep["kind"] == "receivable" and rep["as_of"] == TODAY.isoformat()
    t = rep["totals"]
    assert t["parties"] == 2 and t["bills"] == 4 and t["outstanding"] == "10000.00" and t["overdue"] == "5000.00"
    assert t["buckets"] == {"not_due": "5000.00", "d1_30": "0.00", "d31_60": "2500.00", "d61_90": "0.00",
                            "over_90": "2500.00"}
    assert [p["name"] for p in rep["parties"]] == [p["name"] for p in sorted(rep["parties"], key=lambda p: p["name"])]
    p1 = next(p for p in rep["parties"] if p["key"] == str(flat1.id))
    assert p1["sub"] == "Asha Rao" and p1["total"] == "5000.00" and p1["bill_count"] == 2
    assert p1["buckets"]["over_90"] == "2500.00" and p1["buckets"]["not_due"] == "2500.00"
    assert p1["days_overdue"] == 200
    assert p1["oldest_due_date"] == (TODAY - timedelta(days=200)).isoformat()
    oldest = p1["bills"][0]
    assert oldest["bucket"] == "over_90" and oldest["days_overdue"] == 200 and oldest["outstanding"] == "2500.00"
    p2 = next(p for p in rep["parties"] if p["key"] == str(flat2.id))
    assert p2["buckets"]["d31_60"] == "2500.00"


def test_receivable_is_the_default_kind(client, db):
    society, _f1, _f2, manager, _res = _two_cycles(client, db, "os2")
    h, sid = manager["headers"], str(society.id)
    assert client.get(f"{A}/outstanding/{sid}", headers=h).json()["kind"] == "receivable"


def _vendor(client, admin, sid, name):
    return client.post("/api/v1/vendors/", json={
        "society_id": sid, "company_name": name, "mobile": "9876543210", "category": "security"},
        headers=admin["headers"]).json()["id"]


def _bill(client, h, sid, vendor_id, number, total, invoice_date, due_date=None):
    body = {"society_id": sid, "vendor_id": vendor_id, "invoice_number": number, "invoice_date": invoice_date.isoformat(),
            "amount": total, "gst_amount": "0", "total_amount": total}
    if due_date:
        body["due_date"] = due_date.isoformat()
    r = client.post("/api/v1/vendors/invoices", json=body, headers=h)
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_payable_ages_unpaid_vendor_bills_by_due_date(client, db):
    society, *_, manager, _res, _other = _rig(db, "os3")
    h, sid = manager["headers"], str(society.id)
    admin = make_user(db, "admin@os3.com", role="Society Admin")
    shield = _vendor(client, admin, sid, "Shield Security")
    lift = _vendor(client, admin, sid, "Lift Care")
    _bill(client, h, sid, shield, "SS/1", "10000", TODAY - timedelta(days=120), TODAY - timedelta(days=100))
    part = _bill(client, h, sid, shield, "SS/2", "8000", TODAY - timedelta(days=50), TODAY - timedelta(days=45))
    assert client.post(f"/api/v1/vendors/invoices/{part['id']}/payments", json={
        "amount": "3000", "paid_date": (TODAY - timedelta(days=10)).isoformat(), "payment_mode": "neft",
        "payment_ref": "U1"}, headers=h).status_code == 200
    _bill(client, h, sid, lift, "LC/1", "5000", TODAY - timedelta(days=5), TODAY + timedelta(days=25))
    _bill(client, h, sid, lift, "LC/2", "700", TODAY - timedelta(days=20))                 # no credit period given
    paid = _bill(client, h, sid, lift, "LC/3", "900", TODAY - timedelta(days=60), TODAY - timedelta(days=50))
    assert client.post(f"/api/v1/vendors/invoices/{paid['id']}/payments", json={
        "amount": "900", "paid_date": (TODAY - timedelta(days=40)).isoformat(), "payment_mode": "neft",
        "payment_ref": "U2"}, headers=h).status_code == 200

    rep = client.get(f"{A}/outstanding/{sid}", params={"kind": "payable"}, headers=h).json()
    t = rep["totals"]
    assert t["parties"] == 2 and t["bills"] == 4                          # the fully paid bill is gone
    assert t["outstanding"] == "20700.00"                                 # 10,000 + (8,000 - 3,000) + 5,000 + 700
    assert t["buckets"] == {"not_due": "5000.00", "d1_30": "700.00", "d31_60": "5000.00", "d61_90": "0.00",
                            "over_90": "10000.00"}
    assert t["overdue"] == "15700.00"
    assert [p["name"] for p in rep["parties"]] == ["Lift Care", "Shield Security"]
    sh = rep["parties"][1]
    assert sh["total"] == "15000.00" and sh["days_overdue"] == 100 and sh["bill_count"] == 2
    assert {b["ref"]: b["outstanding"] for b in sh["bills"]} == {"SS/1": "10000.00", "SS/2": "5000.00"}
    lc2 = next(b for p in rep["parties"] for b in p["bills"] if b["ref"] == "LC/2")
    assert lc2["no_due_date"] and lc2["due_date"] == (TODAY - timedelta(days=20)).isoformat()
    assert lc2["bucket"] == "d1_30"


def test_outstanding_prints_and_is_for_managers_only(client, db):
    society, flat1, flat2, manager, resident = _two_cycles(client, db, "os4")
    h, sid = manager["headers"], str(society.id)
    for kind in ("receivable", "payable"):
        pdf = client.get(f"{A}/outstanding/{sid}", params={"kind": kind, "format": "pdf"}, headers=h)
        assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert client.get(f"{A}/outstanding/{sid}", params={"kind": "bogus"}, headers=h).status_code == 422
    assert client.get(f"{A}/outstanding/{sid}", headers=resident["headers"]).status_code == 403
    empty = client.get(f"{A}/outstanding/{sid}", params={"kind": "payable"}, headers=h).json()
    assert empty["parties"] == [] and empty["totals"]["outstanding"] == "0.00"
