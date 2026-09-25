"""Vendor bills (VendorInvoice) and payments against them — the society's
payable side, mirroring the resident-facing online-payments flow."""
from datetime import date
from tests.conftest import make_user, make_society


def _rig(db):
    society = make_society(db, "Vendor Pay Society")
    manager = make_user(db, "manager@vendorpay.com", role="Manager")
    admin = make_user(db, "admin@vendorpay.com", role="Society Admin")
    resident = make_user(db, "resident@vendorpay.com", role="Resident")
    return society, manager, admin, resident


def _create_vendor(client, headers, society_id, name="CleanPro"):
    r = client.post(
        "/api/v1/vendors/",
        json={"society_id": str(society_id), "company_name": name,
              "mobile": "9876543210", "category": "housekeeping"},
        headers=headers,
    )
    return r.json()["id"]


def _create_invoice(client, headers, society_id, vendor_id, total_amount="10000.00", **overrides):
    data = {
        "society_id": str(society_id), "vendor_id": vendor_id,
        "invoice_number": "INV-VND-001", "invoice_date": str(date.today()),
        "amount": total_amount, "gst_amount": "0", "total_amount": total_amount,
    }
    data.update(overrides)
    return client.post("/api/v1/vendors/invoices", json=data, headers=headers)


def test_manager_can_create_vendor_invoice(client, db):
    society, manager, admin, resident = _rig(db)
    vendor_id = _create_vendor(client, admin["headers"], society.id)
    r = _create_invoice(client, manager["headers"], society.id, vendor_id)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["total_amount"] == "10000.00"
    assert body["outstanding"] == "10000.00"
    assert body["is_paid"] is False


def test_resident_cannot_create_vendor_invoice(client, db):
    society, manager, admin, resident = _rig(db)
    vendor_id = _create_vendor(client, admin["headers"], society.id)
    r = _create_invoice(client, resident["headers"], society.id, vendor_id)
    assert r.status_code == 403


def test_full_payment_marks_invoice_paid(client, db):
    society, manager, admin, resident = _rig(db)
    vendor_id = _create_vendor(client, admin["headers"], society.id)
    inv_id = _create_invoice(client, manager["headers"], society.id, vendor_id).json()["id"]

    r = client.post(f"/api/v1/vendors/invoices/{inv_id}/payments", json={
        "amount": "10000.00", "paid_date": str(date.today()),
        "payment_mode": "neft", "payment_ref": "UTR12345",
    }, headers=manager["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_paid"] is True
    assert body["paid_amount"] == "10000.00"
    assert body["outstanding"] == "0.00"
    assert body["payment_mode"] == "neft"
    assert body["payment_ref"] == "UTR12345"


def test_partial_payment_leaves_invoice_unpaid_with_reduced_outstanding(client, db):
    society, manager, admin, resident = _rig(db)
    vendor_id = _create_vendor(client, admin["headers"], society.id)
    inv_id = _create_invoice(client, manager["headers"], society.id, vendor_id, total_amount="10000.00").json()["id"]

    r1 = client.post(f"/api/v1/vendors/invoices/{inv_id}/payments", json={
        "amount": "4000.00", "paid_date": str(date.today()), "payment_mode": "cash",
    }, headers=manager["headers"])
    assert r1.status_code == 200
    assert r1.json()["is_paid"] is False
    assert r1.json()["outstanding"] == "6000.00"

    r2 = client.post(f"/api/v1/vendors/invoices/{inv_id}/payments", json={
        "amount": "6000.00", "paid_date": str(date.today()), "payment_mode": "cheque",
    }, headers=manager["headers"])
    assert r2.status_code == 200
    assert r2.json()["is_paid"] is True
    assert r2.json()["outstanding"] == "0.00"


def test_payment_exceeding_outstanding_rejected(client, db):
    society, manager, admin, resident = _rig(db)
    vendor_id = _create_vendor(client, admin["headers"], society.id)
    inv_id = _create_invoice(client, manager["headers"], society.id, vendor_id, total_amount="5000.00").json()["id"]

    r = client.post(f"/api/v1/vendors/invoices/{inv_id}/payments", json={
        "amount": "9999.00", "paid_date": str(date.today()), "payment_mode": "cash",
    }, headers=manager["headers"])
    assert r.status_code == 422


def test_payment_against_already_paid_invoice_rejected(client, db):
    society, manager, admin, resident = _rig(db)
    vendor_id = _create_vendor(client, admin["headers"], society.id)
    inv_id = _create_invoice(client, manager["headers"], society.id, vendor_id, total_amount="1000.00").json()["id"]

    r1 = client.post(f"/api/v1/vendors/invoices/{inv_id}/payments", json={
        "amount": "1000.00", "paid_date": str(date.today()), "payment_mode": "cash",
    }, headers=manager["headers"])
    assert r1.json()["is_paid"] is True

    r2 = client.post(f"/api/v1/vendors/invoices/{inv_id}/payments", json={
        "amount": "1.00", "paid_date": str(date.today()), "payment_mode": "cash",
    }, headers=manager["headers"])
    assert r2.status_code == 409


def test_negative_or_zero_payment_rejected(client, db):
    society, manager, admin, resident = _rig(db)
    vendor_id = _create_vendor(client, admin["headers"], society.id)
    inv_id = _create_invoice(client, manager["headers"], society.id, vendor_id, total_amount="1000.00").json()["id"]

    r = client.post(f"/api/v1/vendors/invoices/{inv_id}/payments", json={
        "amount": "0.00", "paid_date": str(date.today()), "payment_mode": "cash",
    }, headers=manager["headers"])
    assert r.status_code == 422


def test_list_society_invoices_filters_by_paid_status(client, db):
    society, manager, admin, resident = _rig(db)
    vendor_id = _create_vendor(client, admin["headers"], society.id)
    inv1 = _create_invoice(client, manager["headers"], society.id, vendor_id,
                            total_amount="1000.00", invoice_number="INV-A").json()["id"]
    _create_invoice(client, manager["headers"], society.id, vendor_id,
                     total_amount="2000.00", invoice_number="INV-B")
    client.post(f"/api/v1/vendors/invoices/{inv1}/payments", json={
        "amount": "1000.00", "paid_date": str(date.today()), "payment_mode": "cash",
    }, headers=manager["headers"])

    unpaid = client.get(f"/api/v1/vendors/invoices/society/{society.id}",
                         params={"is_paid": False}, headers=manager["headers"])
    assert len(unpaid.json()) == 1
    assert unpaid.json()[0]["invoice_number"] == "INV-B"

    paid = client.get(f"/api/v1/vendors/invoices/society/{society.id}",
                       params={"is_paid": True}, headers=manager["headers"])
    assert len(paid.json()) == 1
    assert paid.json()[0]["invoice_number"] == "INV-A"

    all_invoices = client.get(f"/api/v1/vendors/invoices/society/{society.id}",
                               headers=manager["headers"])
    assert len(all_invoices.json()) == 2


def test_get_vendor_invoices_includes_vendor_name(client, db):
    society, manager, admin, resident = _rig(db)
    vendor_id = _create_vendor(client, admin["headers"], society.id, "ElectraFix")
    _create_invoice(client, manager["headers"], society.id, vendor_id)
    r = client.get(f"/api/v1/vendors/invoices/vendor/{vendor_id}", headers=manager["headers"])
    assert r.status_code == 200
    assert r.json()[0]["vendor_name"] == "ElectraFix"


def test_resident_cannot_record_vendor_payment(client, db):
    society, manager, admin, resident = _rig(db)
    vendor_id = _create_vendor(client, admin["headers"], society.id)
    inv_id = _create_invoice(client, manager["headers"], society.id, vendor_id).json()["id"]
    r = client.post(f"/api/v1/vendors/invoices/{inv_id}/payments", json={
        "amount": "100.00", "paid_date": str(date.today()), "payment_mode": "cash",
    }, headers=resident["headers"])
    assert r.status_code == 403
