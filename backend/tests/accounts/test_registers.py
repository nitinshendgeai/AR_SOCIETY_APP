"""The cash and bank book, the invoice register and the bills register, each naming who made the entry; and the
maker/checker rule on vouchers waiting for approval."""
from decimal import Decimal

from tests.accounts.test_accounts import _issued_bills, _ledgers
from tests.billing.test_maintenance_billing import _rig
from tests.conftest import make_user

A = "/api/v1/accounts"


def _payment(client, h, sid, L, amount="450"):
    return client.post(f"{A}/vouchers", headers=h, json={
        "society_id": sid, "voucher_type": "payment", "voucher_date": "2026-09-15", "narration": "Plumber",
        "entries": [{"account_id": L["security_charges"]["id"], "debit": amount},
                    {"account_id": L["cash"]["id"], "credit": amount}]})


def test_cash_bank_book_has_only_approved_entries_with_who_entered_and_approved(client, db):
    society, *_, manager, _res, _other = _rig(db, "rg1")
    admin = make_user(db, "admin@rg1.com", role="Society Admin", full_name="Asha Admin")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)

    v = _payment(client, h, sid, L).json()
    assert v["approval_status"] == "pending"
    book = client.get(f"{A}/registers/cash-bank/{sid}", headers=h).json()
    cash = next(s for s in book["sections"] if s["kind"] == "cash")
    assert cash["lines"] == [] and cash["closing"] == "0.00"                    # waiting for approval: not in the book

    assert client.post(f"{A}/vouchers/{v['id']}/approve", json={"note": "ok"}, headers=admin["headers"]).status_code == 200
    book = client.get(f"{A}/registers/cash-bank/{sid}", headers=h).json()
    cash = next(s for s in book["sections"] if s["kind"] == "cash")
    assert len(cash["lines"]) == 1
    line = cash["lines"][0]
    assert line["payment"] == "450.00" and line["receipt"] == "0.00" and line["balance"] == "-450.00"
    assert line["entered_by"] == manager["user"].full_name and line["approved_by"] == "Asha Admin"
    assert cash["closing"] == "-450.00" and book["totals"]["payments"] == "450.00"

    # One account only, and the printed book
    only = client.get(f"{A}/registers/cash-bank/{sid}", params={"account_id": L["cash"]["id"]}, headers=h).json()
    assert [s["kind"] for s in only["sections"]] == ["cash"]
    pdf = client.get(f"{A}/registers/cash-bank/{sid}", params={"format": "pdf"}, headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_ledger_statement_leaves_out_vouchers_waiting_for_approval(client, db):
    society, *_, manager, _res, _other = _rig(db, "rg2")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    _payment(client, h, sid, L)
    st = client.get(f"{A}/ledgers/{L['cash']['id']}/statement", headers=h).json()
    assert st["lines"] == [] and st["closing"] == "0.00"


def test_invoice_register_lists_issued_bills_with_who_generated_them(client, db):
    society, flat1, flat2, manager, _res, bill1 = _issued_bills(client, db, "rg3")
    h, sid = manager["headers"], str(society.id)
    reg = client.get(f"{A}/registers/invoices/{sid}", headers=h).json()
    assert reg["totals"]["count"] == 2 and Decimal(reg["totals"]["total"]) == Decimal("6708")
    row = next(r for r in reg["rows"] if r["invoice_number"] == bill1.invoice_number)
    assert row["entered_by"] == manager["user"].full_name and row["status"] == "issued"
    assert Decimal(row["outstanding"]) == Decimal(row["total"])
    assert client.get(f"{A}/registers/invoices/{sid}", params={"q": "nomatch"}, headers=h).json()["rows"] == []
    assert client.get(f"{A}/registers/invoices/{sid}", params={"status": "paid"}, headers=h).json()["rows"] == []
    pdf = client.get(f"{A}/registers/invoices/{sid}", params={"format": "pdf"}, headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_bills_register_lists_vendor_bills_with_who_entered_them_and_what_is_left(client, db):
    society, *_, manager, _res, _other = _rig(db, "rg4")
    h, sid = manager["headers"], str(society.id)
    admin = make_user(db, "admin@rg4.com", role="Society Admin")
    vendor_id = client.post("/api/v1/vendors/", json={
        "society_id": sid, "company_name": "Shield Security", "mobile": "9876543210", "category": "security",
    }, headers=admin["headers"]).json()["id"]
    inv = client.post("/api/v1/vendors/invoices", json={
        "society_id": sid, "vendor_id": vendor_id, "invoice_number": "SS/112", "invoice_date": "2026-09-05",
        "amount": "40000", "gst_amount": "7200", "total_amount": "47200"}, headers=h).json()
    assert client.post(f"/api/v1/vendors/invoices/{inv['id']}/payments", json={
        "amount": "20000", "paid_date": "2026-09-10", "payment_mode": "neft", "payment_ref": "UTR9"},
        headers=h).status_code == 200

    reg = client.get(f"{A}/registers/bills/{sid}", headers=h).json()
    assert reg["totals"]["count"] == 1
    row = reg["rows"][0]
    assert row["invoice_number"] == "SS/112" and row["vendor"] == "Shield Security"
    assert row["entered_by"] == manager["user"].full_name and row["status"] == "part_paid"
    assert row["total"] == "47200.00" and row["paid"] == "20000.00" and row["outstanding"] == "27200.00"
    assert client.get(f"{A}/registers/bills/{sid}", params={"status": "paid"}, headers=h).json()["rows"] == []
    assert client.get(f"{A}/registers/bills/{sid}", params={"vendor_id": vendor_id}, headers=h).json()["totals"]["count"] == 1
    pdf = client.get(f"{A}/registers/bills/{sid}", params={"format": "pdf"}, headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def _join(db, member, society):
    """Put a test user in the society (users made by make_user have none, which reads as a platform admin)."""
    member["user"].society_id = society.id
    db.commit()
    return member


def test_whoever_entered_a_voucher_cannot_approve_it_while_someone_else_can(client, db):
    society, *_ = _rig(db, "rg5")
    admin = _join(db, make_user(db, "admin@rg5.com", role="Society Admin", full_name="Asha Admin"), society)
    chair = _join(db, make_user(db, "chair@rg5.com", role="Committee Chairman", full_name="Raj Chair"), society)
    h, sid = admin["headers"], str(society.id)
    v = _payment(client, h, sid, _ledgers(client, h, sid)).json()                # the admin enters it

    pending = client.get(f"{A}/vouchers/{sid}/pending-approvals", headers=h).json()
    assert [p["id"] for p in pending] == [v["id"]] and pending[0]["can_approve"] is False
    r = client.post(f"{A}/vouchers/{v['id']}/approve", json={}, headers=h)
    assert r.status_code == 403 and "can't approve" in r.json()["detail"]

    assert client.get(f"{A}/vouchers/{sid}/pending-approvals", headers=chair["headers"]).json()[0]["can_approve"] is True
    ok = client.post(f"{A}/vouchers/{v['id']}/approve", json={"note": "Checked"}, headers=chair["headers"])
    assert ok.status_code == 200 and ok.json()["approval_status"] == "approved"
    assert ok.json()["approved_by_name"] == "Raj Chair" and ok.json()["created_by_name"] == "Asha Admin"


def test_a_sole_approver_may_approve_their_own_entry_and_the_note_says_so(client, db):
    society, *_ = _rig(db, "rg6")
    admin = _join(db, make_user(db, "admin@rg6.com", role="Society Admin", full_name="Asha Admin"), society)
    h, sid = admin["headers"], str(society.id)
    v = _payment(client, h, sid, _ledgers(client, h, sid)).json()
    assert client.get(f"{A}/vouchers/{sid}/pending-approvals", headers=h).json()[0]["can_approve"] is True
    ok = client.post(f"{A}/vouchers/{v['id']}/approve", json={"note": "Seen"}, headers=h)
    assert ok.status_code == 200 and ok.json()["approval_status"] == "approved"
    assert "no other approver" in ok.json()["approval_note"]
