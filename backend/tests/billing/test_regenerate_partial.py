"""Regenerating a cycle's bills while some of them are issued: the unissued and cancelled bills are deleted and made
again from all of the period's approved expenses; an issued or paid bill stays, and so does its flat's share of each
actual-expense pool - the new bills share only what the standing bills did not take."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.models.flat import Flat
from app.modules.billing.models.billing import (
    BillingExpenseAllocation, DueTracker, InvoiceLineItem, MaintenanceBill,
)
from tests.billing.test_bill_pdf import _bill_pdf
from tests.billing.test_budget_suggestions import _bill
from tests.billing.test_period_expense_billing import _setup

B = "/api/v1/billing"
D = Decimal


def _regenerate(client, h, cycle_id):
    return client.post(f"{B}/cycles/{cycle_id}/regenerate-bills", headers=h)


def _cancel(client, h, bill_id):
    r = client.post(f"{B}/bills/{bill_id}/cancel", json={"reason": "Wrong"}, headers=h)
    assert r.status_code == 200, r.text


def _info(client, h, cycle_id):
    return client.get(f"{B}/cycles/detail/{cycle_id}", headers=h).json()


def _bill_of(db, society, cycle_id, number):
    flat = next(f for f in db.query(Flat).filter(Flat.wing.has(society_id=society.id)) if f.flat_number == number)
    return db.query(MaintenanceBill).filter(MaintenanceBill.cycle_id == UUID(cycle_id),
                                            MaintenanceBill.flat_id == flat.id).all()


def _live(db, cycle_id):
    return {b.flat.flat_number: b for b in db.query(MaintenanceBill).filter(
        MaintenanceBill.cycle_id == UUID(cycle_id), MaintenanceBill.bill_status != "cancelled")}


def _head_line(bill, head_name):
    return sum(li.amount for li in bill.line_items if li.description == head_name)


def test_regenerate_takes_up_expenses_booked_after_the_bills_were_made(client, db):
    society, admin, manager, head, cycle_id, *_ = _setup(client, db, "rp1")
    _bill(client, admin, society.id, "housekeeping", "4000.00", date.today())
    assert client.post(f"{B}/cycles/{cycle_id}/generate-bills", headers=manager).status_code == 200
    _bill(client, admin, society.id, "housekeeping", "4000.00", date.today())     # booked after
    r = _regenerate(client, manager, cycle_id)
    assert r.status_code == 200, r.text
    assert r.json()["bills_replaced"] == 3 and r.json()["bills_generated"] == 3 and r.json()["bills_kept"] == 0
    db.expire_all()
    live = _live(db, cycle_id)
    assert sum(_head_line(b, head["name"]) for b in live.values()) == D("8000.00")
    assert db.query(BillingExpenseAllocation).one().pool_amount == D("8000.00")


def test_an_issued_bill_stays_and_the_others_share_the_rest_of_the_expenses(client, db):
    society, admin, manager, head, cycle_id, *_ = _setup(client, db, "rp2")
    _bill(client, admin, society.id, "housekeeping", "4000.00", date.today())
    assert client.post(f"{B}/cycles/{cycle_id}/generate-bills", headers=manager).status_code == 200
    live = _live(db, cycle_id)
    assert {k: _head_line(b, head["name"]) for k, b in live.items()} == {"101": D("1000.00"), "102": D("1000.00"),
                                                                          "201": D("2000.00")}
    big = live["201"]
    assert client.post(f"{B}/bills/{big.id}/issue", headers=manager).status_code == 200
    big_id, big_number = big.id, big.invoice_number
    assert _info(client, manager, cycle_id)["can_regenerate"] is True            # two bills are still unissued

    _bill(client, admin, society.id, "housekeeping", "4000.00", date.today())     # booked after
    r = _regenerate(client, manager, cycle_id)
    assert r.status_code == 200, r.text
    assert r.json() == {"bills_replaced": 2, "bills_generated": 2, "bills_kept": 1, "cycle_id": cycle_id}

    db.expire_all()
    live = _live(db, cycle_id)
    assert live["201"].id == big_id and live["201"].invoice_number == big_number          # the issued bill is untouched
    assert _head_line(live["201"], head["name"]) == D("2000.00")
    assert {k: _head_line(live[k], head["name"]) for k in ("101", "102")} == {"101": D("3000.00"),
                                                                                "102": D("3000.00")}
    # all of the month's 8,000 is billed, once
    assert sum(_head_line(b, head["name"]) for b in live.values()) == D("8000.00")

    info = _info(client, manager, cycle_id)
    assert info["bills_count"] == 3 and D(info["total_billed"]) == sum((b.total_amount for b in live.values()), D(0))
    for number, bill in live.items():
        tracker = db.query(DueTracker).filter_by(flat_id=bill.flat_id).one()
        assert tracker.total_billed == bill.total_amount and tracker.outstanding == bill.total_amount
    # The working the issued bill was made from stays as it was; the new bills have their own, for the balance.
    allocations = db.query(BillingExpenseAllocation).all()
    assert sorted(a.pool_amount for a in allocations) == [D("4000.00"), D("6000.00")]
    assert sorted(a.eligible_flats for a in allocations) == [2, 3]
    assert all(li.allocation_id for b in live.values() for li in b.line_items if li.description == head["name"])
    # Invoice numbers are not left with gaps beyond the replaced ones, and each printed bill states its working.
    _bill_obj, text = _bill_pdf(db, live["101"].id)
    assert "not on bills already issued" in text and "Rs. 8,000.00 in all" in text
    _bill_obj, text = _bill_pdf(db, big_id)
    assert "Rs. 4,000.00 in all" in text


def test_a_cancelled_issued_bill_is_made_again_and_takes_its_share_back(client, db):
    society, admin, manager, head, cycle_id, *_ = _setup(client, db, "rp3")
    _bill(client, admin, society.id, "housekeeping", "4000.00", date.today())
    assert client.post(f"{B}/cycles/{cycle_id}/generate-bills", headers=manager).status_code == 200
    assert client.post(f"{B}/cycles/{cycle_id}/issue-all", headers=manager).status_code == 200
    assert _info(client, manager, cycle_id)["can_regenerate"] is False             # everything issued
    r = _regenerate(client, manager, cycle_id)
    assert r.status_code == 409 and "issued" in r.json()["detail"]

    db.expire_all()
    big = _live(db, cycle_id)["201"]
    old_id, old_number = big.id, big.invoice_number
    _cancel(client, manager, str(big.id))
    assert _info(client, manager, cycle_id)["can_regenerate"] is True
    r = _regenerate(client, manager, cycle_id)
    assert r.status_code == 200, r.text
    assert r.json()["bills_generated"] == 1 and r.json()["bills_kept"] == 2

    db.expire_all()
    bills = _bill_of(db, society, cycle_id, "201")
    assert len(bills) == 2                                                            # the cancelled one stays as a record
    old = next(b for b in bills if b.id == old_id)
    new = next(b for b in bills if b.id != old_id)
    assert old.bill_status.value == "cancelled" and old.invoice_number == old_number
    assert new.bill_status.value == "generated" and _head_line(new, head["name"]) == D("2000.00")
    assert sum(_head_line(b, head["name"]) for b in _live(db, cycle_id).values()) == D("4000.00")


def test_an_unissued_cancelled_bill_is_deleted_while_an_issued_one_stays(client, db):
    society, admin, manager, head, cycle_id, *_ = _setup(client, db, "rp4")
    _bill(client, admin, society.id, "housekeeping", "4000.00", date.today())
    assert client.post(f"{B}/cycles/{cycle_id}/generate-bills", headers=manager).status_code == 200
    live = _live(db, cycle_id)
    assert client.post(f"{B}/bills/{live['101'].id}/issue", headers=manager).status_code == 200
    gone_id = live["102"].id
    _cancel(client, manager, str(gone_id))                                              # never issued
    assert _regenerate(client, manager, cycle_id).status_code == 200
    db.expire_all()
    assert db.query(MaintenanceBill).filter(MaintenanceBill.id == gone_id).count() == 0   # deleted, not kept
    live = _live(db, cycle_id)
    assert set(live) == {"101", "102", "201"}
    assert sum(_head_line(b, head["name"]) for b in live.values()) == D("4000.00")
    assert live["101"].bill_status.value == "issued" and _head_line(live["101"], head["name"]) == D("1000.00")


def test_with_no_new_spend_the_expenses_are_still_billed_once_in_all(client, db):
    society, admin, manager, head, cycle_id, *_ = _setup(client, db, "rp5")
    _bill(client, admin, society.id, "housekeeping", "4000.00", date.today())
    assert client.post(f"{B}/cycles/{cycle_id}/generate-bills", headers=manager).status_code == 200
    live = _live(db, cycle_id)
    assert client.post(f"{B}/bills/{live['101'].id}/issue", headers=manager).status_code == 200
    r = _regenerate(client, manager, cycle_id)                          # no new spend: the other two share the 3,000 left
    assert r.status_code == 200, r.text
    db.expire_all()
    live = _live(db, cycle_id)
    assert _head_line(live["101"], head["name"]) == D("1000.00")
    assert _head_line(live["102"], head["name"]) + _head_line(live["201"], head["name"]) == D("3000.00")
    assert sum(_head_line(b, head["name"]) for b in live.values()) == D("4000.00")
