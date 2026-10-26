"""Regenerating a cycle's bills: the old ones are deleted and new ones made, while none has been issued. Nothing else may
be left behind (the flats' running dues, one-off charges, interest already counted), and once a bill reaches a resident
the bills stay."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.modules.accounts.models.accounts import Voucher
from app.modules.billing.models.billing import (
    BillingExpenseAllocation, DueTracker, FlatCharge, InvoiceLineItem, MaintenanceBill,
)
from tests.billing.test_expense_links_and_flat_charges import _fine
from tests.billing.test_interest_working import _second_bill
from tests.billing.test_interest_waivers import API, _arrears, _cycle as _cycle12
from tests.billing.test_maintenance_billing import _charge, _cycle, _generated_cycle, _rig

B = "/api/v1/billing"


def _regenerate(client, h, cycle_id):
    return client.post(f"{B}/cycles/{cycle_id}/regenerate-bills", headers=h)


def _bills(client, h, cycle_id):
    return client.get(f"{B}/cycles/{cycle_id}/bills", headers=h).json()


def test_bills_are_replaced_with_new_ones_made_from_the_current_charges(client, db):
    society, flat1, flat2, manager, _r, _o, cycle_id = _generated_cycle(client, db, "rg1")
    h = manager["headers"]
    before = _bills(client, h, cycle_id)
    assert len(before) == 2
    old_ids = {b["id"] for b in before}

    # A charge added after the first generation is picked up by the new bills.
    assert _charge(client, h, society.id, name="Lift", amount="400.00").status_code == 201
    r = _regenerate(client, h, cycle_id)
    assert r.status_code == 200, r.text
    assert r.json()["bills_replaced"] == 2 and r.json()["bills_generated"] == 2

    after = _bills(client, h, cycle_id)
    assert len(after) == 2 and not old_ids & {b["id"] for b in after}
    assert db.query(MaintenanceBill).filter(MaintenanceBill.id.in_([UUID(i) for i in old_ids])).count() == 0
    assert all(Decimal(a["total_amount"]) > Decimal(b["total_amount"]) for a, b in zip(
        sorted(after, key=lambda x: x["flat_id"]), sorted(before, key=lambda x: x["flat_id"])))
    # Invoice numbers are not left with gaps.
    assert sorted(b["invoice_number"] for b in after) == sorted(b["invoice_number"] for b in before)
    cycle = next(c for c in client.get(f"{B}/cycles/{society.id}", headers=h).json() if c["id"] == cycle_id)
    assert cycle["is_finalized"] and cycle["bills_count"] == 2 and cycle["generated_count"] == 2


def test_the_flats_running_dues_are_not_counted_twice(client, db):
    society, flat1, flat2, manager, _r, _o, cycle_id = _generated_cycle(client, db, "rg2")
    h = manager["headers"]
    for _ in range(3):
        assert _regenerate(client, h, cycle_id).status_code == 200
    db.expire_all()
    for flat in (flat1, flat2):
        bill = db.query(MaintenanceBill).filter_by(flat_id=flat.id).one()
        tracker = db.query(DueTracker).filter_by(flat_id=flat.id).one()
        assert tracker.total_billed == bill.total_amount and tracker.outstanding == bill.total_amount
    assert db.query(Voucher).filter_by(society_id=society.id, source_type="maintenance_bill").count() == 0


def test_a_fine_on_a_bill_is_taken_up_again_not_lost(client, db):
    society, flat1, flat2, manager, _r, _o, cycle_id = _generated_cycle(client, db, "rg3")
    h = manager["headers"]
    # the fine is made after the first generation, so it goes to the next bills: regenerate takes it up once
    assert _fine(client, h, society, flat1).status_code == 201
    assert _regenerate(client, h, cycle_id).status_code == 200
    fine = db.query(FlatCharge).filter_by(flat_id=flat1.id).one()
    bill = db.query(MaintenanceBill).filter_by(flat_id=flat1.id).one()
    assert fine.bill_id == bill.id and fine.status.value == "billed"
    assert _regenerate(client, h, cycle_id).status_code == 200
    db.expire_all()
    fine = db.query(FlatCharge).filter_by(flat_id=flat1.id).one()
    bill = db.query(MaintenanceBill).filter_by(flat_id=flat1.id).one()
    assert fine.bill_id == bill.id and fine.status.value == "billed"
    lines = [li.description for li in db.query(InvoiceLineItem).filter_by(bill_id=bill.id)]
    assert len([d for d in lines if "parking" in d.lower()]) == 1, lines


def test_interest_already_counted_on_an_earlier_bill_is_counted_again_not_lost(client, db):
    society, flat, h, bill = _second_bill(client, db, "rg4")
    cycle_id = str(bill.cycle_id)
    first_interest = [li.total for li in bill.line_items if li.description.startswith("Interest on arrears")]
    assert first_interest == [Decimal("36.00")]
    for _ in range(2):
        assert _regenerate(client, h, cycle_id).status_code == 200
    db.expire_all()
    bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle_id), flat_id=flat.id).one()
    assert [li.total for li in bill.line_items if li.description.startswith("Interest on arrears")] == [Decimal("36.00")]
    assert bill.total_amount == Decimal("3686.00")
    earlier = db.query(MaintenanceBill).filter(MaintenanceBill.flat_id == flat.id,
                                               MaintenanceBill.cycle_id != UUID(cycle_id)).one()
    assert earlier.arrears_interest_upto == date.today()     # counted once, up to today


def test_once_a_bill_is_issued_the_bills_cannot_be_regenerated(client, db):
    society, flat1, flat2, manager, _r, _o, cycle_id = _generated_cycle(client, db, "rg5")
    h = manager["headers"]
    assert client.post(f"{B}/cycles/{cycle_id}/issue-all", headers=h).status_code == 200
    r = _regenerate(client, h, cycle_id)
    assert r.status_code == 409 and "issued" in r.json()["detail"]
    assert len(_bills(client, h, cycle_id)) == 2


def test_a_payment_on_a_bill_stops_it(client, db):
    society, flat1, flat2, manager, _r, _o, cycle_id = _generated_cycle(client, db, "rg6")
    h = manager["headers"]
    bill = db.query(MaintenanceBill).filter_by(flat_id=flat1.id).one()
    r = client.post(f"{B}/online-payments", headers=h, data={
        "flat_id": str(flat1.id), "bill_id": str(bill.id), "amount": "100", "payment_date": str(date.today()),
        "payment_mode": "cash"})
    assert r.status_code == 201, r.text
    r = _regenerate(client, h, cycle_id)
    assert r.status_code == 409 and "payment" in r.json()["detail"].lower()


def test_when_new_bills_cannot_be_made_the_old_ones_stay(client, db):
    society, flat1, flat2, manager, _r, _o, cycle_id = _generated_cycle(client, db, "rg7")
    h = manager["headers"]
    ids = {b["id"] for b in _bills(client, h, cycle_id)}
    for charge in client.get(f"{B}/charges/{society.id}", headers=h).json():
        assert client.patch(f"{B}/charges/{charge['id']}", json={"is_active": False}, headers=h).status_code in (200, 204), charge
    r = _regenerate(client, h, cycle_id)
    assert r.status_code == 422
    db.expire_all()
    assert {b["id"] for b in _bills(client, h, cycle_id)} == ids
    tracker = db.query(DueTracker).filter_by(flat_id=flat1.id).one()
    assert tracker.total_billed == db.query(MaintenanceBill).filter_by(flat_id=flat1.id).one().total_amount


def test_a_cycle_with_no_bills_and_a_resident_are_refused(client, db):
    society, flat1, flat2, manager, resident, _o = _rig(db, "rg8")
    h = manager["headers"]
    cycle_id = _cycle(client, h, society.id).json()["id"]
    assert _regenerate(client, h, cycle_id).status_code == 409
    assert _regenerate(client, resident["headers"], cycle_id).status_code == 403


# ── Cancelled bills ───────────────────────────────────────────────────────────

def _cancel(client, h, bill_id):
    r = client.post(f"{B}/bills/{bill_id}/cancel", json={"reason": "Wrong"}, headers=h)
    assert r.status_code == 200, r.text


def _cycle_info(client, h, cycle_id):
    return client.get(f"{B}/cycles/detail/{cycle_id}", headers=h).json()


def test_bills_issued_by_mistake_and_all_cancelled_can_be_regenerated(client, db):
    society, flat1, flat2, manager, _r, _o, cycle_id = _generated_cycle(client, db, "rg9")
    h = manager["headers"]
    assert _cycle_info(client, h, cycle_id)["can_regenerate"] is True
    assert client.post(f"{B}/cycles/{cycle_id}/issue-all", headers=h).status_code == 200
    assert _cycle_info(client, h, cycle_id)["can_regenerate"] is False         # issued: not yet
    issued = _bills(client, h, cycle_id)
    old_numbers = {b["invoice_number"] for b in issued}
    for b in issued:
        _cancel(client, h, b["id"])
    info = _cycle_info(client, h, cycle_id)
    assert info["can_regenerate"] is True and info["bills_count"] == 0           # every bill is cancelled

    r = _regenerate(client, h, cycle_id)
    assert r.status_code == 200, r.text
    assert r.json()["bills_generated"] == 2

    db.expire_all()
    bills = db.query(MaintenanceBill).filter(MaintenanceBill.society_id == society.id).all()
    live = [b for b in bills if b.bill_status.value == "generated"]
    cancelled = [b for b in bills if b.bill_status.value == "cancelled"]
    assert len(live) == 2 and len(cancelled) == 2                                # the cancelled ones stay as a record
    assert {b.invoice_number for b in cancelled} == old_numbers
    assert not old_numbers & {b.invoice_number for b in live}                    # the new bills have new numbers
    for flat in (flat1, flat2):
        bill = next(b for b in live if b.flat_id == flat.id)
        tracker = db.query(DueTracker).filter_by(flat_id=flat.id).one()
        assert tracker.total_billed == bill.total_amount and tracker.outstanding == bill.total_amount
    assert _cycle_info(client, h, cycle_id)["can_regenerate"] is True
    # And they can be issued and everything carries on.
    assert client.post(f"{B}/cycles/{cycle_id}/issue-all", headers=h).status_code == 200


def test_a_generated_bill_that_was_cancelled_is_deleted_and_the_rest_replaced(client, db):
    society, flat1, flat2, manager, _r, _o, cycle_id = _generated_cycle(client, db, "rg10")
    h = manager["headers"]
    first = _bills(client, h, cycle_id)
    _cancel(client, h, first[0]["id"])                 # never issued
    r = _regenerate(client, h, cycle_id)
    assert r.status_code == 200, r.text
    db.expire_all()
    bills = db.query(MaintenanceBill).filter(MaintenanceBill.society_id == society.id).all()
    assert len(bills) == 2 and all(b.bill_status.value == "generated" for b in bills)   # nothing left of the cancelled one


def test_one_issued_bill_still_stops_it_even_when_the_others_are_cancelled(client, db):
    society, flat1, flat2, manager, _r, _o, cycle_id = _generated_cycle(client, db, "rg11")
    h = manager["headers"]
    assert client.post(f"{B}/cycles/{cycle_id}/issue-all", headers=h).status_code == 200
    bills = _bills(client, h, cycle_id)
    _cancel(client, h, bills[0]["id"])
    assert _cycle_info(client, h, cycle_id)["can_regenerate"] is False
    r = _regenerate(client, h, cycle_id)
    assert r.status_code == 409 and "issued" in r.json()["detail"] and "Cancel it first" in r.json()["detail"]
    assert sorted(b["bill_status"] for b in _bills(client, h, cycle_id)) == ["cancelled", "issued"]      # untouched


def test_interest_of_a_cancelled_issued_bill_is_charged_again_by_the_new_bill(client, db):
    society, flat, h, bill = _second_bill(client, db, "rg12")
    cycle_id = str(bill.cycle_id)
    assert client.post(f"{B}/cycles/{cycle_id}/issue-all", headers=h).status_code == 200
    _cancel(client, h, str(bill.id))
    assert _regenerate(client, h, cycle_id).status_code == 200
    db.expire_all()
    new = db.query(MaintenanceBill).filter(MaintenanceBill.cycle_id == UUID(cycle_id),
                                           MaintenanceBill.bill_status == "generated").one()
    assert [li.total for li in new.line_items if li.description.startswith("Interest on arrears")] == [Decimal("36.00")]
