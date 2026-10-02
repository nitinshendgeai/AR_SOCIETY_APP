"""A member's payment is set off against the flat's open maintenance bills,
oldest first; what's left is an advance, set off against the next bill
issued. Rejected payments and cancelled bills release their set-offs."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.modules.billing.models.billing import (
    DueTracker, MaintenanceBill, OnlinePaymentSubmission, PaymentMode, ReconciliationStatus,
)
from tests.billing.test_defaulters import _two_cycles
from tests.billing.test_maintenance_billing import _cycle
from tests.billing.test_online_payments import _pdf_text_stream

PAY = "/api/v1/billing/online-payments"


def _bills(db, flat):
    """The flat's bills, oldest due first, fresh from the database."""
    db.expire_all()
    return db.query(MaintenanceBill).filter(MaintenanceBill.flat_id == flat.id).order_by(MaintenanceBill.due_date).all()


def _pay(client, h, flat, amount, mode="cash", **extra):
    r = client.post(PAY, data={"flat_id": str(flat.id), "amount": amount, "payment_date": str(date.today()),
                               "payment_mode": mode, **extra}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def test_payment_settles_open_bills_oldest_first(client, db):
    society, flat1, _f2, manager, resident = _two_cycles(client, db, "pa1")
    h = manager["headers"]
    old, new = _bills(db, flat1)
    p = _pay(client, h, flat1, "4000.00")
    assert [(a["invoice_number"], a["amount"]) for a in p["allocations"]] == [
        (old.invoice_number, "2500.00"), (new.invoice_number, "1500.00")]
    assert p["applied_amount"] == "4000.00" and p["unapplied_amount"] == "0.00"
    old, new = _bills(db, flat1)
    assert old.bill_status.value == "paid" and str(old.outstanding) == "0.00"
    assert new.bill_status.value == "partially_paid" and str(new.outstanding) == "1000.00"
    tracker = db.query(DueTracker).filter_by(flat_id=flat1.id).one()
    assert str(tracker.outstanding) == "1000.00" and str(tracker.total_paid) == "4000.00"

    # The bill lists the part set off against it; the receipt names both bills
    detail = client.get(f"/api/v1/billing/bills/{new.id}", headers=h).json()
    assert [(x["receipt_number"], x["amount"]) for x in detail["payments"]] == [(p["receipt_number"], "1500.00")]
    pdf = client.get(f"{PAY}/{p['id']}/receipt", headers=h)
    assert pdf.status_code == 200
    text = _pdf_text_stream(pdf.content)
    assert b"ON BILLING" in text
    assert f"Bill No. {old.invoice_number}".encode() in text and f"Bill No. {new.invoice_number}".encode() in text


def test_advance_is_set_off_against_the_next_bill(client, db):
    society, flat1, _f2, manager, _res = _two_cycles(client, db, "pa2")
    h = manager["headers"]
    p = _pay(client, h, flat1, "6000.00")
    assert p["applied_amount"] == "5000.00" and p["unapplied_amount"] == "1000.00"
    assert all(b.bill_status.value == "paid" for b in _bills(db, flat1))
    db.expire_all()
    assert str(db.query(DueTracker).filter_by(flat_id=flat1.id).one().advance_balance) == "1000.00"
    unapplied = client.get(f"{PAY}/society/{society.id}/unapplied", headers=h).json()
    assert unapplied["amount"] == "1000.00" and unapplied["flats_with_open_bills"] == 0

    cycle_id = _cycle(client, h, society.id, name="Next cycle").json()["id"]
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=h).status_code == 200
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=h).status_code == 200
    third = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id), flat_id=flat1.id).one()
    assert str(third.paid_amount) == "1000.00" and third.bill_status.value == "partially_paid"
    p = client.get(f"{PAY}/{p['id']}", headers=h).json()
    assert p["unapplied_amount"] == "0.00" and len(p["allocations"]) == 3


def test_rejected_payment_unpays_its_bills(client, db):
    society, flat1, _f2, manager, _res = _two_cycles(client, db, "pa3")
    h = manager["headers"]
    p = _pay(client, h, flat1, "3000.00", mode="cheque", transaction_ref="004512")
    assert _bills(db, flat1)[0].bill_status.value == "paid"

    r = client.patch(f"{PAY}/{p['id']}/status", json={"status": "rejected", "review_notes": "Cheque bounced"},
                     headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["applied_amount"] == "0.00"
    assert all(a["released_at"] for a in r.json()["allocations"])
    old, new = _bills(db, flat1)
    assert old.bill_status.value == "issued" and str(old.outstanding) == "2500.00"
    assert new.bill_status.value == "issued" and str(new.outstanding) == "2500.00"
    assert str(db.query(DueTracker).filter_by(flat_id=flat1.id).one().outstanding) == "5000.00"

    # Cleared after all: set off again
    r = client.patch(f"{PAY}/{p['id']}/status", json={"status": "reconciled"}, headers=h)
    assert r.json()["applied_amount"] == "3000.00"
    old, new = _bills(db, flat1)
    assert old.bill_status.value == "paid" and str(new.outstanding) == "2000.00"


def test_cancelled_bill_returns_its_set_off_to_credit(client, db):
    society, flat1, _f2, manager, _res = _two_cycles(client, db, "pa4")
    h = manager["headers"]
    p = _pay(client, h, flat1, "1000.00")
    old, new = _bills(db, flat1)
    assert str(old.paid_amount) == "1000.00"
    r = client.post(f"/api/v1/billing/bills/{old.id}/cancel", json={"reason": "Billed in error"}, headers=h)
    assert r.status_code == 200, r.text
    # The ₹1,000 moves to the other open bill
    old, new = _bills(db, flat1)
    assert old.bill_status.value == "cancelled" and str(new.paid_amount) == "1000.00"
    p = client.get(f"{PAY}/{p['id']}", headers=h).json()
    live = [a for a in p["allocations"] if not a["released_at"]]
    assert [(a["invoice_number"], a["amount"]) for a in live] == [(new.invoice_number, "1000.00")]


def test_chosen_bill_and_earlier_on_account_payments(client, db):
    society, flat1, _f2, manager, _res = _two_cycles(client, db, "pa5")
    h = manager["headers"]
    old, new = _bills(db, flat1)
    # Against a chosen bill: that bill only
    p = _pay(client, h, flat1, "500.00", bill_id=str(new.id))
    assert [a["invoice_number"] for a in p["allocations"]] == [new.invoice_number]
    assert str(_bills(db, flat1)[0].paid_amount) == "0.00"

    # A payment recorded on account before set-off existed
    db.add(OnlinePaymentSubmission(
        society_id=society.id, wing_id=flat1.wing_id, flat_id=flat1.id, receipt_number="OLD-0001",
        amount=Decimal("2000.00"), payment_date=date.today(), payment_mode=PaymentMode.CASH,
        status=ReconciliationStatus.RECONCILED))
    db.commit()
    u = client.get(f"{PAY}/society/{society.id}/unapplied", headers=h).json()
    assert u["flats_with_open_bills"] == 1 and u["amount_against_open_bills"] == "2000.00"
    r = client.post(f"{PAY}/society/{society.id}/apply", headers=h)
    assert r.status_code == 200 and r.json() == {"flats": 1, "bills": 1, "amount": "2000.00"}
    old, new = _bills(db, flat1)
    assert str(old.paid_amount) == "2000.00" and str(old.outstanding) == "500.00"
    assert client.get(f"{PAY}/society/{society.id}/unapplied", headers=h).json()["amount"] == "0.00"

    # Residents can't
    assert client.post(f"{PAY}/society/{society.id}/apply", headers=_res["headers"]).status_code == 403


def test_very_large_advance_is_kept(client, db):
    society, flat1, _f2, manager, _res = _two_cycles(client, db, "pa6")
    p = _pay(client, manager["headers"], flat1, "250000000.00")
    assert p["applied_amount"] == "5000.00" and p["unapplied_amount"] == "249995000.00"
    db.expire_all()
    assert str(db.query(DueTracker).filter_by(flat_id=flat1.id).one().advance_balance) == "249995000.00"
