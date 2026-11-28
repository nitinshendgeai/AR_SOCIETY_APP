"""Correcting the date a payment was received on (a day and month entered the wrong way round, say): the receipt voucher
moves to the new date, what the payment settled is set off again for the same amounts, and nothing else changes."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from app.modules.accounts.models.accounts import Voucher
from app.modules.billing.models.billing import MaintenanceBill, OnlinePaymentSubmission
from app.modules.billing.services.allocations import PaymentAllocator
from tests.billing.test_advance_import import _post, _row
from tests.billing.test_maintenance_billing import _charge, _cycle, _rig
from tests.conftest import make_user, place_in

PAY = "/api/v1/billing/online-payments"


def _admin(db, society, tag):
    admin = make_user(db, f"admin@pd{tag}.com", role="Society Admin")
    place_in(db, admin, society)
    return admin


def _redate(client, h, sub_id, new, reason="Day and month were entered the wrong way round"):
    return client.patch(f"{PAY}/{sub_id}/date", json={"payment_date": str(new), "reason": reason}, headers=h)


def _live_vouchers(db, sub_id):
    db.expire_all()
    return [v for v in db.query(Voucher).filter_by(source_type="online_payment", source_id=sub_id)
            if not v.is_cancelled]


def test_an_advance_receipt_moves_to_the_right_date_and_keeps_its_amount(client, db):
    society, flat1, _f2, manager, *_ = _rig(db, "pd1")
    admin = _admin(db, society, "pd1")
    old, new = date.today() - timedelta(days=100), date.today() - timedelta(days=10)
    r = _post(client, manager["headers"], [_row(2, "101", "15000", payment_date=str(old))], society=society)
    assert r.json()[0]["status"] == "recorded", r.text
    sub = db.query(OnlinePaymentSubmission).filter_by(flat_id=flat1.id).one()
    [first] = _live_vouchers(db, sub.id)
    assert first.voucher_date == old

    # a manager cannot move dates in the books
    assert _redate(client, manager["headers"], sub.id, new).status_code == 403
    assert _redate(client, admin["headers"], sub.id, date.today() + timedelta(days=1)).status_code == 422
    assert _redate(client, admin["headers"], sub.id, new, reason="x").status_code == 422

    res = _redate(client, admin["headers"], sub.id, new)
    assert res.status_code == 200, res.text
    assert res.json()["payment_date"] == str(new)
    db.expire_all()
    sub = db.get(OnlinePaymentSubmission, sub.id)
    assert sub.payment_date == new and sub.amount == Decimal("15000.00")
    [moved] = _live_vouchers(db, sub.id)
    assert moved.voucher_date == new and moved.id != first.id and moved.amount == Decimal("15000.00")
    old_voucher = db.get(Voucher, first.id)
    assert old_voucher.is_cancelled and "corrected from" in (old_voucher.cancel_reason or "")
    assert PaymentAllocator(db).advance(flat1.id) == Decimal("15000.00")          # still the flat's advance
    # the same date again changes nothing
    assert _redate(client, admin["headers"], sub.id, new).status_code == 200
    assert len(_live_vouchers(db, sub.id)) == 1


def test_a_payment_already_set_off_against_a_bill_is_set_off_again_for_the_same_amount(client, db):
    society, flat1, _f2, manager, *_ = _rig(db, "pd2")
    admin = _admin(db, society, "pd2")
    h = manager["headers"]
    old, new = date.today() - timedelta(days=100), date.today() - timedelta(days=10)
    _post(client, h, [_row(2, "101", "6000", payment_date=str(old))], society=society)
    _charge(client, h, society.id, amount="2500.00")
    cycle_id = _cycle(client, h, society.id).json()["id"]
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=h).status_code == 200
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=h).status_code == 200
    db.expire_all()
    bill = db.query(MaintenanceBill).filter_by(flat_id=flat1.id, cycle_id=UUID(cycle_id)).one()
    assert bill.outstanding == 0
    sub = db.query(OnlinePaymentSubmission).filter_by(flat_id=flat1.id).one()

    assert _redate(client, admin["headers"], sub.id, new).status_code == 200
    db.expire_all()
    bill = db.get(MaintenanceBill, bill.id)
    assert bill.outstanding == 0 and bill.paid_amount == bill.total_amount          # still paid by the same payment
    live = [a for a in db.get(OnlinePaymentSubmission, sub.id).allocations if a.is_live]
    assert [Decimal(a.amount) for a in live] == [bill.total_amount]
    assert PaymentAllocator(db).advance(flat1.id) == Decimal("6000.00") - bill.total_amount
    assert [v.voucher_date for v in _live_vouchers(db, sub.id)] == [new]
