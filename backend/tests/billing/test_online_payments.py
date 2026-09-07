"""Online Payment Submissions — resident payment screenshots captured by
the FMC Manager for bank reconciliation."""
import io
import pytest
from datetime import date
from tests.conftest import make_user, make_society, make_wing, make_flat


def _rig(db):
    society = make_society(db, "Payments Society")
    wing = make_wing(db, society.id, "Wing A")
    flat = make_flat(db, wing.id, "A-101")
    manager = make_user(db, "manager@pay.com", role="Manager")
    admin = make_user(db, "admin@pay.com", role="Society Admin")
    resident = make_user(db, "resident@pay.com", role="Resident")
    return society, wing, flat, manager, admin, resident


def _screenshot_file(name="upi.jpg", content=b"\xff\xd8\xff\xe0fakejpegbytes", content_type="image/jpeg"):
    return {"screenshot": (name, io.BytesIO(content), content_type)}


def _submit(client, flat_id, headers, **overrides):
    data = {
        "flat_id": str(flat_id),
        "amount": "5500.00",
        "payment_date": str(date.today()),
        "payment_mode": "upi",
        "transaction_ref": "UTR123456789",
        "bank_name": "HDFC Bank",
        "notes": "May maintenance",
    }
    data.update(overrides)
    return client.post("/api/v1/billing/online-payments", data=data,
                        files=_screenshot_file(), headers=headers)


def test_manager_can_submit_online_payment(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    r = _submit(client, flat.id, manager["headers"])
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["receipt_number"].startswith("OPS-")
    assert body["flat_number"] == "A-101"
    assert body["wing_name"] == "Wing A"
    assert body["amount"] == "5500.00"


def test_admin_can_submit_online_payment(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    r = _submit(client, flat.id, admin["headers"])
    assert r.status_code == 201


def test_resident_cannot_submit_online_payment(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    r = _submit(client, flat.id, resident["headers"])
    assert r.status_code == 403


def test_missing_screenshot_rejected(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    data = {
        "flat_id": str(flat.id), "amount": "1000",
        "payment_date": str(date.today()), "payment_mode": "upi",
    }
    r = client.post("/api/v1/billing/online-payments", data=data, headers=manager["headers"])
    assert r.status_code == 422


def test_unknown_flat_returns_404(client, db):
    import uuid
    society, wing, flat, manager, admin, resident = _rig(db)
    r = _submit(client, uuid.uuid4(), manager["headers"])
    assert r.status_code == 404


def test_receipt_numbers_are_sequential_per_society(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    r1 = _submit(client, flat.id, manager["headers"])
    r2 = _submit(client, flat.id, manager["headers"])
    assert r1.json()["receipt_number"] != r2.json()["receipt_number"]


def test_list_online_payments(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    _submit(client, flat.id, manager["headers"])
    _submit(client, flat.id, manager["headers"])
    r = client.get(f"/api/v1/billing/online-payments/society/{society.id}", headers=manager["headers"])
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_filters_by_status(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    created = _submit(client, flat.id, manager["headers"]).json()
    client.patch(f"/api/v1/billing/online-payments/{created['id']}/status",
                 json={"status": "reconciled"}, headers=admin["headers"])
    r_pending = client.get(f"/api/v1/billing/online-payments/society/{society.id}?status=pending",
                           headers=manager["headers"])
    r_reconciled = client.get(f"/api/v1/billing/online-payments/society/{society.id}?status=reconciled",
                              headers=manager["headers"])
    assert len(r_pending.json()) == 0
    assert len(r_reconciled.json()) == 1


def test_get_screenshot_bytes(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    created = _submit(client, flat.id, manager["headers"]).json()
    r = client.get(f"/api/v1/billing/online-payments/{created['id']}/screenshot", headers=manager["headers"])
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content == b"\xff\xd8\xff\xe0fakejpegbytes"


def test_list_response_excludes_binary_screenshot(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    _submit(client, flat.id, manager["headers"])
    r = client.get(f"/api/v1/billing/online-payments/society/{society.id}", headers=manager["headers"])
    assert "screenshot_data" not in r.json()[0]


def test_update_status_to_reconciled(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    created = _submit(client, flat.id, manager["headers"]).json()
    r = client.patch(f"/api/v1/billing/online-payments/{created['id']}/status",
                     json={"status": "reconciled", "review_notes": "Matched bank statement line 42"},
                     headers=admin["headers"])
    assert r.status_code == 200
    assert r.json()["status"] == "reconciled"
    assert r.json()["review_notes"] == "Matched bank statement line 42"
    assert r.json()["reviewed_by"] is not None


def test_update_status_to_rejected(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    created = _submit(client, flat.id, manager["headers"]).json()
    r = client.patch(f"/api/v1/billing/online-payments/{created['id']}/status",
                     json={"status": "rejected", "review_notes": "Duplicate submission"},
                     headers=manager["headers"])
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


def test_get_receipt_pdf(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    created = _submit(client, flat.id, manager["headers"]).json()
    r = client.get(f"/api/v1/billing/online-payments/{created['id']}/receipt", headers=manager["headers"])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_export_csv(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    _submit(client, flat.id, manager["headers"])
    r = client.get(f"/api/v1/billing/online-payments/society/{society.id}/export", headers=manager["headers"])
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    text = r.content.decode("utf-8")
    assert "Receipt Number" in text
    assert "OPS-" in text


def test_oversized_screenshot_rejected(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    big = b"0" * (9 * 1024 * 1024)
    data = {
        "flat_id": str(flat.id), "amount": "1000",
        "payment_date": str(date.today()), "payment_mode": "cash",
    }
    files = {"screenshot": ("big.jpg", io.BytesIO(big), "image/jpeg")}
    r = client.post("/api/v1/billing/online-payments", data=data, files=files, headers=manager["headers"])
    assert r.status_code == 422


def test_unsupported_mime_type_rejected(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    data = {
        "flat_id": str(flat.id), "amount": "1000",
        "payment_date": str(date.today()), "payment_mode": "cash",
    }
    files = {"screenshot": ("file.exe", io.BytesIO(b"MZ"), "application/x-msdownload")}
    r = client.post("/api/v1/billing/online-payments", data=data, files=files, headers=manager["headers"])
    assert r.status_code == 422


def test_online_payments_form_granted_to_manager_and_admin(client, db):
    manager = make_user(db, "mgr2@pay.com", role="Manager")
    admin = make_user(db, "adm2@pay.com", role="Society Admin")
    resident = make_user(db, "res2@pay.com", role="Resident")
    r_mgr = client.get("/api/v1/roles/forms/mine", headers=manager["headers"])
    r_adm = client.get("/api/v1/roles/forms/mine", headers=admin["headers"])
    r_res = client.get("/api/v1/roles/forms/mine", headers=resident["headers"])
    codes_mgr = set(r_mgr.json()["form_codes"])
    codes_adm = set(r_adm.json()["form_codes"])
    codes_res = set(r_res.json()["form_codes"])
    assert "online_payments" in codes_mgr
    assert "online_payments" in codes_adm
    assert "online_payments" not in codes_res
