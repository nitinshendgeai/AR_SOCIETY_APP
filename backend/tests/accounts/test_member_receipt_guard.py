"""A resident's payment is recorded in Billing, which sets it off against the flat's bills and posts the receipt. A loose
Receipt voucher that credits Members' Dues would reduce what the books say the flat owes while its bills stay unpaid
(and keep earning interest and reminders), so it is refused for a flat with unpaid bills."""
from datetime import date
from decimal import Decimal

from app.modules.billing.models.billing import MaintenanceBill
from tests.accounts.test_accounts import API, _balance, _issued_bills, _ledgers

B = "/api/v1/billing"


def _receipt(client, h, sid, L, flat_id, amount, expect=201):
    r = client.post(f"{API}/vouchers", headers=h, json={
        "society_id": sid, "voucher_type": "receipt", "voucher_date": str(date.today()),
        "entries": [{"account_id": L["bank"]["id"], "debit": str(amount)},
                    {"account_id": L["members_dues"]["id"], "credit": str(amount), "flat_id": str(flat_id)}]})
    assert r.status_code == expect, r.text
    return r.json()


def test_a_receipt_voucher_cannot_settle_a_flat_with_unpaid_bills(client, db):
    society, flat1, _flat2, manager, _res, bill1 = _issued_bills(client, db, "mrg1")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    before = _balance(client, h, sid, "members_dues")

    detail = _receipt(client, h, sid, L, flat1.id, 3000, expect=422)["detail"]
    assert "unpaid bills" in detail and "Online Payments" in detail
    assert _balance(client, h, sid, "members_dues") == before and _balance(client, h, sid, "bank") == 0
    db.refresh(bill1)
    assert Decimal(bill1.paid_amount) == 0


def test_the_same_money_recorded_in_billing_settles_the_bill_and_the_books(client, db):
    society, flat1, _flat2, manager, _res, bill1 = _issued_bills(client, db, "mrg2")
    h, sid = manager["headers"], str(society.id)
    r = client.post(f"{B}/online-payments", headers=h, data={
        "flat_id": str(flat1.id), "amount": "1000.00", "payment_date": str(date.today()), "payment_mode": "cash",
        "bill_id": str(bill1.id)})
    assert r.status_code == 201, r.text
    db.refresh(bill1)
    assert Decimal(bill1.paid_amount) == 1000


def test_once_the_bills_are_paid_a_receipt_voucher_is_an_advance_and_allowed(client, db):
    society, flat1, _flat2, manager, _res, bill1 = _issued_bills(client, db, "mrg3")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    due = Decimal(bill1.outstanding)
    assert client.post(f"{B}/online-payments", headers=h, data={
        "flat_id": str(flat1.id), "amount": str(due), "payment_date": str(date.today()), "payment_mode": "cash",
        "bill_id": str(bill1.id)}).status_code == 201
    _receipt(client, h, sid, L, flat1.id, 500)


def test_a_cancelled_bill_is_not_unpaid(client, db):
    society, flat1, _flat2, manager, _res, bill1 = _issued_bills(client, db, "mrg4")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    assert client.post(f"{B}/bills/{bill1.id}/cancel", json={"reason": "Duplicate"}, headers=h).status_code == 200
    _receipt(client, h, sid, L, flat1.id, 500)


def test_other_vouchers_on_members_dues_are_not_in_the_way(client, db):
    society, flat1, _flat2, manager, _res, _bill = _issued_bills(client, db, "mrg5")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    # A waiver: a journal, not money received
    r = client.post(f"{API}/vouchers", headers=h, json={
        "society_id": sid, "voucher_type": "journal", "voucher_date": str(date.today()),
        "entries": [{"account_id": L["fines_penalties"]["id"], "debit": "50"},
                    {"account_id": L["members_dues"]["id"], "credit": "50", "flat_id": str(flat1.id)}]})
    assert r.status_code == 201, r.text
    # Other income needs no flat and no bill
    r = client.post(f"{API}/vouchers", headers=h, json={
        "society_id": sid, "voucher_type": "receipt", "voucher_date": str(date.today()),
        "entries": [{"account_id": L["bank"]["id"], "debit": "700"},
                    {"account_id": L["interest_sb"]["id"], "credit": "700"}]})
    assert r.status_code == 201, r.text


def test_a_flat_without_bills_is_not_blocked(client, db):
    """The guard looks at the flat chosen: here the bills belong to the other flat's society-mates only."""
    society, flat1, flat2, manager, _res, _bill = _issued_bills(client, db, "mrg6")
    h, sid = manager["headers"], str(society.id)
    L = _ledgers(client, h, sid)
    for b in db.query(MaintenanceBill).filter_by(flat_id=flat2.id):
        assert client.post(f"{B}/bills/{b.id}/cancel", json={"reason": "Wrong flat"}, headers=h).status_code == 200
    _receipt(client, h, sid, L, flat2.id, 300)
    _receipt(client, h, sid, L, flat1.id, 300, expect=422)             # flat 1 still has its bill
