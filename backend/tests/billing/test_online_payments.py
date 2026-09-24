"""Online Payment Submissions — resident payment screenshots captured by
the FMC Manager for bank reconciliation."""
import base64
import io
import re
import zlib
import pytest
from datetime import date
from tests.conftest import make_user, make_society, make_wing, make_flat


def _pdf_text_stream(pdf_bytes: bytes) -> bytes:
    """Decompress the (single-page) content stream reportlab wrote, so a
    test can assert on the literal text operands rather than raw PDF bytes
    — reportlab's default page compression means the drawn strings aren't
    substrings of the raw response body."""
    match = re.search(rb"stream\r?\n(.*?)endstream", pdf_bytes, re.DOTALL)
    payload = match.group(1).rstrip(b"\r\n")
    if payload.endswith(b"~>"):
        payload = payload[:-2]
    return zlib.decompress(base64.a85decode(payload))


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


def _submit_no_screenshot(client, flat_id, headers, **overrides):
    data = {
        "flat_id": str(flat_id),
        "amount": "5500.00",
        "payment_date": str(date.today()),
        "payment_mode": "cash",
    }
    data.update(overrides)
    return client.post("/api/v1/billing/online-payments", data=data, headers=headers)


def _rig_with_bill(db, client, admin, flat, amount="5500.00"):
    """Generate + issue a single bill for `flat` and return the ORM row."""
    from app.modules.billing.models.billing import MaintenanceBill

    society_id = flat.wing.society_id
    today = date.today()
    client.post("/api/v1/billing/charges", json={
        "society_id": str(society_id), "charge_type": "maintenance",
        "name": "Monthly", "default_amount": amount, "tax_percent": "0",
    }, headers=admin["headers"])
    r_cycle = client.post("/api/v1/billing/cycles", json={
        "society_id": str(society_id), "name": "Cycle",
        "cycle_start": str(today), "cycle_end": str(today),
        "due_date": str(today),
    }, headers=admin["headers"])
    cycle_id = r_cycle.json()["id"]
    client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=admin["headers"])
    bill = db.query(MaintenanceBill).filter(MaintenanceBill.flat_id == flat.id).first()
    client.post(f"/api/v1/billing/bills/{bill.id}/issue", headers=admin["headers"])
    db.refresh(bill)
    return bill


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


def test_purpose_defaults_to_maintenance(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    r = _submit(client, flat.id, manager["headers"])
    assert r.json()["purpose"] == "maintenance"


def test_purpose_can_be_set_explicitly(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    r = _submit(client, flat.id, manager["headers"], purpose="parking")
    assert r.json()["purpose"] == "parking"


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


def test_receipt_pdf_states_on_account_purpose(client, db):
    # The whole point of `purpose` is that it shows up on the printed
    # receipt as "on account of <purpose>".
    society, wing, flat, manager, admin, resident = _rig(db)
    created = _submit(client, flat.id, manager["headers"], purpose="parking").json()
    r = client.get(f"/api/v1/billing/online-payments/{created['id']}/receipt", headers=manager["headers"])
    assert b"on account of Parking charges" in _pdf_text_stream(r.content)


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


# ── On-bill payments (single form, "On Bill" option) ────────────────────────

def test_cash_payment_does_not_require_screenshot(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    r = _submit_no_screenshot(client, flat.id, manager["headers"])
    assert r.status_code == 201
    assert r.json()["status"] == "reconciled"


def test_cheque_payment_optional_screenshot_stays_pending(client, db):
    # Cash has nothing to check against a bank statement; cheque still can
    # bounce, so it stays PENDING even without a screenshot.
    society, wing, flat, manager, admin, resident = _rig(db)
    r = _submit_no_screenshot(client, flat.id, manager["headers"], payment_mode="cheque")
    assert r.status_code == 201
    assert r.json()["status"] == "pending"


def test_online_mode_without_screenshot_still_rejected(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    r = _submit_no_screenshot(client, flat.id, manager["headers"], payment_mode="upi")
    assert r.status_code == 422


def test_on_bill_payment_updates_bill_and_due_tracker(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    bill = _rig_with_bill(db, client, admin, flat, amount="5500.00")

    r = _submit_no_screenshot(client, flat.id, manager["headers"],
                               amount="5500.00", bill_id=str(bill.id))
    assert r.status_code == 201
    body = r.json()
    assert body["bill_id"] == str(bill.id)
    assert body["bill_invoice_number"] == bill.invoice_number

    r_bill = client.get(f"/api/v1/billing/bills/{bill.id}", headers=admin["headers"])
    assert r_bill.json()["bill_status"] == "paid"
    assert r_bill.json()["outstanding"] == "0.00"

    r_due = client.get(f"/api/v1/billing/dues/flat/{flat.id}/{society.id}", headers=admin["headers"])
    assert r_due.json()["total_paid"] == 5500.0


def test_on_bill_partial_payment_leaves_bill_partially_paid(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    bill = _rig_with_bill(db, client, admin, flat, amount="5500.00")

    r = _submit_no_screenshot(client, flat.id, manager["headers"],
                               amount="2000.00", bill_id=str(bill.id))
    assert r.status_code == 201

    r_bill = client.get(f"/api/v1/billing/bills/{bill.id}", headers=admin["headers"])
    assert r_bill.json()["bill_status"] == "partially_paid"
    assert r_bill.json()["outstanding"] == "3500.00"


def test_on_bill_payment_exceeding_outstanding_rejected(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    bill = _rig_with_bill(db, client, admin, flat, amount="5500.00")

    r = _submit_no_screenshot(client, flat.id, manager["headers"],
                               amount="9000.00", bill_id=str(bill.id))
    assert r.status_code == 422


def test_on_bill_payment_for_already_paid_bill_rejected(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    bill = _rig_with_bill(db, client, admin, flat, amount="5500.00")
    _submit_no_screenshot(client, flat.id, manager["headers"],
                           amount="5500.00", bill_id=str(bill.id))

    r2 = _submit_no_screenshot(client, flat.id, manager["headers"],
                                amount="1.00", bill_id=str(bill.id))
    assert r2.status_code == 409


def test_on_bill_payment_from_wrong_flat_rejected(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    other_flat = make_flat(db, wing.id, "A-102")
    bill = _rig_with_bill(db, client, admin, flat, amount="5500.00")

    r = _submit_no_screenshot(client, other_flat.id, manager["headers"],
                               amount="1000.00", bill_id=str(bill.id))
    assert r.status_code == 422


def test_receipt_pdf_shows_bill_number_when_on_bill(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    bill = _rig_with_bill(db, client, admin, flat, amount="5500.00")
    created = _submit_no_screenshot(client, flat.id, manager["headers"],
                                     amount="5500.00", bill_id=str(bill.id)).json()

    r = client.get(f"/api/v1/billing/online-payments/{created['id']}/receipt", headers=manager["headers"])
    text = _pdf_text_stream(r.content)
    assert bill.invoice_number.encode() in text
    assert b"against Bill" in text


def test_outstanding_only_filters_paid_bills(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    bill = _rig_with_bill(db, client, admin, flat, amount="5500.00")
    _submit_no_screenshot(client, flat.id, manager["headers"],
                           amount="5500.00", bill_id=str(bill.id))

    r_all = client.get(f"/api/v1/billing/bills/flat/{flat.id}", headers=admin["headers"])
    r_outstanding = client.get(f"/api/v1/billing/bills/flat/{flat.id}?outstanding_only=true",
                               headers=admin["headers"])
    assert len(r_all.json()) == 1
    assert len(r_outstanding.json()) == 0


def test_screenshot_endpoint_404s_when_no_screenshot_attached(client, db):
    society, wing, flat, manager, admin, resident = _rig(db)
    created = _submit_no_screenshot(client, flat.id, manager["headers"]).json()
    r = client.get(f"/api/v1/billing/online-payments/{created['id']}/screenshot", headers=manager["headers"])
    assert r.status_code == 404
