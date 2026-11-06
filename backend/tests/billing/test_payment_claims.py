"""Resident payment claims: a resident reports a payment, the office confirms or rejects it."""
import io
from datetime import date, timedelta

from app.models.notification import Notification
from app.models.resident import Resident, ResidentType
from app.modules.billing.models.billing import MaintenanceBill, MaintenanceSettings, OnlinePaymentSubmission, PaymentClaim
from tests.billing.test_online_payments import _rig_with_bill
from tests.conftest import make_flat, make_society, make_user, make_wing, place_in

B = "/api/v1/billing"
JPG = b"\xff\xd8\xff\xe0fakejpegbytes"


def _rig(db, client, tag):
    society = make_society(db, f"Claims {tag}")
    wing = make_wing(db, society.id, "A")
    flat = make_flat(db, wing.id, "101")
    other_flat = make_flat(db, wing.id, "102")
    admin = place_in(db, make_user(db, f"claims.admin.{tag}@t.com", role="Society Admin"), society)
    manager = place_in(db, make_user(db, f"claims.mgr.{tag}@t.com", role="Manager"), society)
    resident = place_in(db, make_user(db, f"claims.res.{tag}@t.com", role="Resident"), society)
    neighbour = place_in(db, make_user(db, f"claims.nb.{tag}@t.com", role="Resident"), society)
    for who, f in ((resident, flat), (neighbour, other_flat)):
        db.add(Resident(flat_id=f.id, user_id=who["user"].id, full_name="R", resident_type=ResidentType.OWNER, is_primary=True))
    db.commit()
    bill = _rig_with_bill(db, client, admin, flat, amount="5500.00")
    return society, flat, other_flat, admin, manager, resident, neighbour, bill


def _claim(client, who, bill=None, **over):
    data = {"amount": "5500.00", "payment_date": str(date.today()), "payment_mode": "upi", "transaction_ref": "UTR900001",
            "notes": "May maintenance"}
    if bill is not None:
        data["bill_id"] = str(bill.id)
    data.update(over)
    files = {"screenshot": ("upi.jpg", io.BytesIO(JPG), "image/jpeg")} if over.get("_shot", True) else None
    data.pop("_shot", None)
    return client.post(f"{B}/payment-claims", data=data, files=files, headers=who["headers"])


def test_a_resident_reports_a_payment_and_the_office_is_told(client, db):
    society, flat, other, admin, manager, resident, nb, bill = _rig(db, client, "a")
    r = _claim(client, resident, bill)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending" and body["amount"] == "5500.00" and body["has_screenshot"] is True
    assert body["flat_label"] == "A-101" and body["bill_invoice_number"] == bill.invoice_number
    told = lambda u: db.query(Notification).filter(Notification.user_id == u["user"].id, Notification.module == "payment_claim").count()
    assert told(manager) == 1 and told(admin) == 1 and told(resident) == 0
    db.refresh(bill)
    assert str(bill.outstanding) == "5500.00"


def test_a_claim_records_nothing_until_confirmed(client, db):
    society, flat, other, admin, manager, resident, nb, bill = _rig(db, client, "b")
    before = db.query(OnlinePaymentSubmission).filter(OnlinePaymentSubmission.flat_id == flat.id).count()
    _claim(client, resident, bill)
    assert db.query(OnlinePaymentSubmission).filter(OnlinePaymentSubmission.flat_id == flat.id).count() == before
    db.refresh(bill)
    assert str(bill.paid_amount) == "0.00"


def test_confirming_records_the_payment_and_pays_the_bill(client, db):
    society, flat, other, admin, manager, resident, nb, bill = _rig(db, client, "c")
    cid = _claim(client, resident, bill).json()["id"]
    r = client.post(f"{B}/payment-claims/{cid}/confirm", json={}, headers=manager["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed" and r.json()["receipt_number"]
    db.expire_all()
    bill = db.get(MaintenanceBill, bill.id)
    assert str(bill.outstanding) == "0.00" and bill.bill_status.value == "paid"
    sub = db.query(OnlinePaymentSubmission).filter(OnlinePaymentSubmission.transaction_ref == "UTR900001").one()
    assert sub.screenshot_data == JPG and str(sub.amount) == "5500.00"
    told = db.query(Notification).filter(Notification.user_id == resident["user"].id, Notification.module == "payment_claim").one()
    assert "confirmed" in told.title.lower()
    # and it cannot be confirmed twice
    assert client.post(f"{B}/payment-claims/{cid}/confirm", json={}, headers=manager["headers"]).status_code == 409


def test_rejecting_needs_a_reason_and_the_resident_reads_it(client, db):
    society, flat, other, admin, manager, resident, nb, bill = _rig(db, client, "d")
    cid = _claim(client, resident, bill).json()["id"]
    assert client.post(f"{B}/payment-claims/{cid}/reject", json={"reason": ""}, headers=manager["headers"]).status_code == 422
    r = client.post(f"{B}/payment-claims/{cid}/reject", json={"reason": "UTR not found in the bank statement"}, headers=manager["headers"])
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    mine = client.get(f"{B}/payment-claims/mine", headers=resident["headers"]).json()
    assert mine[0]["status"] == "rejected" and "UTR not found" in mine[0]["review_notes"]
    db.refresh(bill)
    assert str(bill.paid_amount) == "0.00"
    # the same reference can be reported again after a rejection
    assert _claim(client, resident, bill).status_code == 201


def test_residents_only_see_and_report_for_their_own_flat(client, db):
    society, flat, other, admin, manager, resident, nb, bill = _rig(db, client, "e")
    assert _claim(client, nb, bill).status_code in (403, 404)                 # someone else's bill
    assert _claim(client, resident, flat_id=str(other.id)).status_code == 403  # someone else's flat
    cid = _claim(client, resident, bill).json()["id"]
    assert client.get(f"{B}/payment-claims/mine", headers=nb["headers"]).json() == []
    assert client.get(f"{B}/payment-claims/{cid}/screenshot", headers=nb["headers"]).status_code == 404
    assert client.get(f"{B}/payment-claims/{cid}/screenshot", headers=resident["headers"]).content == JPG
    assert client.get(f"{B}/payment-claims/{cid}/screenshot", headers=manager["headers"]).content == JPG


def test_residents_cannot_confirm_reject_or_list_the_societys_claims(client, db):
    society, flat, other, admin, manager, resident, nb, bill = _rig(db, client, "f")
    cid = _claim(client, resident, bill).json()["id"]
    assert client.post(f"{B}/payment-claims/{cid}/confirm", json={}, headers=resident["headers"]).status_code == 403
    assert client.post(f"{B}/payment-claims/{cid}/reject", json={"reason": "x"}, headers=resident["headers"]).status_code == 403
    assert client.get(f"{B}/payment-claims/society/{society.id}", headers=resident["headers"]).status_code == 403
    listed = client.get(f"{B}/payment-claims/society/{society.id}?status=pending", headers=manager["headers"])
    assert listed.status_code == 200 and [c["id"] for c in listed.json()] == [cid]


def test_other_societies_offices_cannot_touch_the_claim(client, db):
    society, flat, other, admin, manager, resident, nb, bill = _rig(db, client, "g")
    cid = _claim(client, resident, bill).json()["id"]
    other_society = make_society(db, "Claims g other")
    foreign = place_in(db, make_user(db, "claims.foreign.g@t.com", role="Manager"), other_society)
    assert client.post(f"{B}/payment-claims/{cid}/confirm", json={}, headers=foreign["headers"]).status_code in (403, 404)
    assert client.get(f"{B}/payment-claims/society/{society.id}", headers=foreign["headers"]).status_code in (403, 404)


def test_validation(client, db):
    society, flat, other, admin, manager, resident, nb, bill = _rig(db, client, "h")
    assert _claim(client, resident, bill, amount="0").status_code == 422
    assert _claim(client, resident, bill, amount="99999").status_code == 422                    # more than is owed
    assert _claim(client, resident, bill, payment_date=str(date.today() + timedelta(days=1))).status_code == 422
    assert _claim(client, resident, bill, payment_date=str(date.today() - timedelta(days=400))).status_code == 422
    assert _claim(client, resident, bill, _shot=False).status_code == 422                       # UPI needs a screenshot
    assert _claim(client, resident, bill, transaction_ref="").status_code == 422                # and a reference
    assert _claim(client, resident, bill, payment_mode="online_gateway").status_code == 422
    assert _claim(client, resident, bill, payment_mode="cash", transaction_ref="", _shot=False).status_code == 201


def test_a_reference_already_reported_or_recorded_cannot_be_reported_again(client, db):
    society, flat, other, admin, manager, resident, nb, bill = _rig(db, client, "i")
    assert _claim(client, resident, bill).status_code == 201
    assert _claim(client, resident, bill).status_code == 409
    done = client.post(f"{B}/online-payments", data={
        "flat_id": str(other.id), "amount": "100.00", "payment_date": str(date.today()), "payment_mode": "upi",
        "transaction_ref": "UTR-OFFICE-1"}, files={"screenshot": ("a.jpg", io.BytesIO(JPG), "image/jpeg")},
        headers=manager["headers"])
    assert done.status_code == 201
    assert _claim(client, resident, bill, transaction_ref="UTR-OFFICE-1").status_code == 409


def test_payment_info_is_what_the_bill_prints(client, db):
    society, flat, other, admin, manager, resident, nb, bill = _rig(db, client, "j")
    r = client.put(f"{B}/maintenance-settings/{society.id}", json={
        "upi_id": "society@okbank", "bank_name": "HDFC", "bank_account_number": "50100123456789", "bank_ifsc": "HDFC0000001",
        "bank_account_name": "Sunrise CHS"}, headers=admin["headers"])
    assert r.status_code == 200, r.text
    info = client.get(f"{B}/payment-info", headers=resident["headers"])
    assert info.status_code == 200
    assert info.json()["upi_id"] == "society@okbank" and info.json()["bank_ifsc"] == "HDFC0000001"
    assert client.get(f"{B}/payment-info").status_code in (401, 403)      # no sign-in, no details
