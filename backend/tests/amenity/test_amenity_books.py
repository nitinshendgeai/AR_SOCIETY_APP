"""What an amenity booking earns the society, and holds for it. A booking's charge goes on its flat's next maintenance
bill — owed by the flat, booked to Amenities Income when the bill is issued. The refundable deposit is not income: it is
held as a liability until it is given back (less anything kept), in the cash or bank ledger it came through."""
from datetime import date, time
from decimal import Decimal
from uuid import UUID

import pytest

from app.modules.amenity.models.amenity import AmenityBooking
from app.modules.billing.models.billing import FlatCharge, FlatChargeKind, FlatChargeStatus
from tests.amenity.test_amenity_booking import A, _amenity, _book, soc  # noqa: F401
from tests.billing.test_maintenance_billing import _charge, _cycle

ACC = "/api/v1/accounts"


def _priced(client, soc, charge="500", deposit="2000", **extra):
    a = _amenity(client, soc, is_chargeable=True, **extra)
    r = client.post(f"{A}/{a['id']}/pricing", json={"label": "Standard", "flat_price": float(charge),
                                                      "deposit_amount": float(deposit) if deposit else None,
                                                      "is_default": True}, headers=soc["admin"]["headers"])
    assert r.status_code == 201, r.text
    return a


def _balance(client, soc, key):
    r = client.get(f"{ACC}/chart/{soc['society'].id}", headers=soc["admin"]["headers"])
    assert r.status_code == 200, r.text
    for group in r.json():
        for acc in group["accounts"]:
            if acc["system_key"] == key:
                return Decimal(acc["balance"])
    raise AssertionError(key)


def _charges(db, booking_id, kind="amenity_booking"):
    return db.query(FlatCharge).filter(FlatCharge.source_type == kind, FlatCharge.source_id == UUID(str(booking_id))).all()


def _issue_bills(client, soc):
    h, sid = soc["admin"]["headers"], soc["society"].id
    assert _charge(client, h, sid, amount="1000.00").status_code == 201
    cycle_id = _cycle(client, h, sid).json()["id"]
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=h).status_code == 200
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=h).status_code == 200


def _started(db, booking_id):
    """Make a booking one that is already under way, so it can be completed."""
    b = db.get(AmenityBooking, UUID(str(booking_id)))
    b.booking_date, b.start_time, b.end_time = date.today(), time(0, 0), time(0, 30)
    db.commit()


# ── The charge ────────────────────────────────────────────────────────────────

def test_an_approved_booking_puts_its_charge_on_the_flats_next_bill(client, soc, db):
    a = _priced(client, soc)
    b = _book(client, soc["res"], a["id"]).json()
    assert b["status"] == "approved" and b["charge_amount"] == 500 and b["charge_bill_status"] == "active"
    (fc,) = _charges(db, b["id"])
    assert (fc.kind, fc.charge_type.value, fc.amount, fc.flat_id) == (FlatChargeKind.EXTRA, "amenities", 500, soc["flat"].id)
    assert "Clubhouse booking" in fc.title

    _issue_bills(client, soc)
    db.refresh(fc)
    assert fc.status == FlatChargeStatus.BILLED and fc.bill_id is not None
    assert _balance(client, soc, "amenities_income") == Decimal("-500")        # income, credited
    assert _balance(client, soc, "members_dues") == Decimal("1500")            # owed by the flat with its maintenance
    got = client.get(f"{A}/bookings/{b['id']}", headers=soc["res"]["headers"]).json()
    assert got["charge_bill_status"] == "billed"


def test_nothing_is_charged_until_a_booking_that_needs_approval_is_approved(client, soc, db):
    a = _priced(client, soc, approval_required=True)
    b = _book(client, soc["res"], a["id"]).json()
    assert b["status"] == "pending" and b["charge_bill_status"] is None and _charges(db, b["id"]) == []
    r = client.post(f"{A}/bookings/{b['id']}/approve", json={}, headers=soc["admin"]["headers"])
    assert r.status_code == 200, r.text
    assert len(_charges(db, b["id"])) == 1
    # Approving twice is not possible, and a second booking is charged on its own
    b2 = _book(client, soc["res"], a["id"], day=5).json()
    client.post(f"{A}/bookings/{b2['id']}/reject", json={"reason": "Clash"}, headers=soc["admin"]["headers"])
    assert _charges(db, b2["id"]) == []


def test_cancelling_before_the_bill_takes_the_charge_back_and_after_it_leaves_it_to_the_committee(client, soc, db):
    a = _priced(client, soc)
    first = _book(client, soc["res"], a["id"]).json()
    assert client.post(f"{A}/bookings/{first['id']}/cancel", json={"reason": "Plans changed"},
                       headers=soc["res"]["headers"]).status_code == 200
    assert _charges(db, first["id"])[0].status == FlatChargeStatus.CANCELLED

    second = _book(client, soc["res"], a["id"], day=6).json()
    _issue_bills(client, soc)                                                  # the charge is on a bill now
    assert client.post(f"{A}/bookings/{second['id']}/cancel", json={}, headers=soc["res"]["headers"]).status_code == 200
    assert _charges(db, second["id"])[0].status == FlatChargeStatus.BILLED     # reversed by cancelling the bill
    assert _balance(client, soc, "amenities_income") == Decimal("-500")


def test_damage_and_extras_found_afterwards_are_charged_too(client, soc, db):
    a = _priced(client, soc, deposit=None)
    b = _book(client, soc["res"], a["id"]).json()
    _started(db, b["id"])
    r = client.post(f"{A}/bookings/{b['id']}/complete",
                    json={"damage_noted": True, "damage_notes": "Broken chair", "extra_charges": 750},
                    headers=soc["admin"]["headers"])
    assert r.status_code == 200, r.text
    (extra,) = _charges(db, b["id"], "amenity_booking_extra")
    assert (extra.amount, extra.charge_type.value, extra.reason) == (750, "amenities", "Broken chair")
    _issue_bills(client, soc)
    assert _balance(client, soc, "amenities_income") == Decimal("-1250")       # the booking and the extras


def test_a_free_booking_and_a_booking_with_no_flat_raise_nothing(client, soc, db):
    free = _amenity(client, soc, name="Garden")
    b = _book(client, soc["res"], free["id"]).json()
    assert b["charge_amount"] is None and _charges(db, b["id"]) == []
    paid = _priced(client, soc, name="Hall")
    r = _book(client, soc["admin"], paid["id"])                                # the admin lives in no flat
    assert r.status_code == 201, r.text
    assert r.json()["flat_id"] is None and _charges(db, r.json()["id"]) == []


# ── The deposit ───────────────────────────────────────────────────────────────

def _deposit_booking(client, soc, **extra):
    a = _priced(client, soc, **extra)
    return _book(client, soc["res"], a["id"]).json()


def test_the_deposit_is_held_as_a_liability_not_income(client, soc):
    b = _deposit_booking(client, soc)
    assert b["deposit_amount"] == 2000 and b["deposit_paid"] is False
    r = client.post(f"{A}/bookings/{b['id']}/deposit", json={"payment_mode": "cash", "reference": "Rcpt 14"},
                    headers=soc["admin"]["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["deposit_paid"] is True and r.json()["voucher_number"].startswith("RV/")
    assert _balance(client, soc, "cash") == 2000
    assert _balance(client, soc, "amenity_deposits") == Decimal("-2000")       # owed back to the resident
    assert _balance(client, soc, "amenities_income") == 0


def test_the_deposit_can_go_into_a_chosen_bank(client, soc):
    b = _deposit_booking(client, soc)
    h, sid = soc["admin"]["headers"], str(soc["society"].id)
    ledgers = {a["system_key"] or a["name"]: a for a in client.get(f"{ACC}/ledgers/{sid}", headers=h).json()}
    other = client.post(f"{ACC}/ledgers", headers=h, json={
        "society_id": sid, "group_id": ledgers["bank"]["group_id"], "name": "HDFC Current", "is_bank": True}).json()
    bad = client.post(f"{A}/bookings/{b['id']}/deposit", json={"payment_mode": "upi", "bank_account_id": ledgers["cash"]["id"]},
                      headers=h)
    assert bad.status_code == 422                                               # cash ledger for a bank payment
    ok = client.post(f"{A}/bookings/{b['id']}/deposit", json={"payment_mode": "upi", "bank_account_id": other["id"]},
                     headers=h)
    assert ok.status_code == 200, ok.text
    st = client.get(f"{ACC}/ledgers/{other['id']}/statement", headers=h).json()
    assert st["closing_dr_cr"] == {"amount": "2000.00", "type": "Dr"}


def test_a_deposit_is_taken_once_and_only_when_there_is_one(client, soc):
    h = soc["admin"]["headers"]
    b = _deposit_booking(client, soc)
    assert client.post(f"{A}/bookings/{b['id']}/deposit", json={}, headers=h).status_code == 200
    assert client.post(f"{A}/bookings/{b['id']}/deposit", json={}, headers=h).status_code == 409
    free = _amenity(client, soc, name="Garden")
    nob = _book(client, soc["res"], free["id"]).json()
    assert client.post(f"{A}/bookings/{nob['id']}/deposit", json={}, headers=h).status_code == 422
    pending = _amenity(client, soc, name="Hall", is_chargeable=True, approval_required=True)
    client.post(f"{A}/{pending['id']}/pricing", json={"label": "S", "flat_price": 1.0, "deposit_amount": 100.0,
                                                       "is_default": True}, headers=h)
    wait = _book(client, soc["res"], pending["id"]).json()
    assert client.post(f"{A}/bookings/{wait['id']}/deposit", json={}, headers=h).status_code == 409
    assert client.post(f"{A}/bookings/{b['id']}/deposit", json={},
                       headers=soc["res"]["headers"]).status_code == 403          # a resident can't take it


def test_the_deposit_is_returned_in_full(client, soc, db):
    h = soc["admin"]["headers"]
    b = _deposit_booking(client, soc)
    client.post(f"{A}/bookings/{b['id']}/deposit", json={}, headers=h)
    early = client.post(f"{A}/bookings/{b['id']}/deposit/refund", json={}, headers=h)
    assert early.status_code == 409                                             # the booking is not over
    _started(db, b["id"])
    assert client.post(f"{A}/bookings/{b['id']}/complete", json={}, headers=h).status_code == 200
    r = client.post(f"{A}/bookings/{b['id']}/deposit/refund", json={}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["deposit_refunded"] is True and r.json()["voucher_number"].startswith("PV/")
    assert _balance(client, soc, "cash") == 0 and _balance(client, soc, "amenity_deposits") == 0
    assert client.post(f"{A}/bookings/{b['id']}/deposit/refund", json={}, headers=h).status_code == 409


def test_part_of_the_deposit_can_be_kept_with_a_reason_and_becomes_income(client, soc, db):
    h = soc["admin"]["headers"]
    b = _deposit_booking(client, soc)
    client.post(f"{A}/bookings/{b['id']}/deposit", json={}, headers=h)
    _started(db, b["id"])
    client.post(f"{A}/bookings/{b['id']}/complete", json={}, headers=h)
    assert client.post(f"{A}/bookings/{b['id']}/deposit/refund", json={"retained_amount": "600"},
                       headers=h).status_code == 422                            # needs a reason
    assert client.post(f"{A}/bookings/{b['id']}/deposit/refund", json={"retained_amount": "2500", "reason": "x"},
                       headers=h).status_code == 422                            # more than the deposit
    r = client.post(f"{A}/bookings/{b['id']}/deposit/refund",
                    json={"retained_amount": "600", "reason": "Broken chair"}, headers=h)
    assert r.status_code == 200, r.text
    assert _balance(client, soc, "cash") == 600                                  # 2000 in, 1400 back
    assert _balance(client, soc, "amenity_deposits") == 0
    assert _balance(client, soc, "amenities_income") == Decimal("-600")


def test_a_cancelled_booking_can_forfeit_all_of_its_deposit(client, soc):
    h = soc["admin"]["headers"]
    b = _deposit_booking(client, soc)
    client.post(f"{A}/bookings/{b['id']}/deposit", json={}, headers=h)
    assert client.post(f"{A}/bookings/{b['id']}/cancel", json={"reason": "Late"}, headers=h).status_code == 200
    r = client.post(f"{A}/bookings/{b['id']}/deposit/refund", json={"retained_amount": "2000", "reason": "Late cancellation"},
                    headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["voucher_number"].startswith("JV/")                          # nothing goes out: a journal
    assert _balance(client, soc, "cash") == 2000 and _balance(client, soc, "amenities_income") == Decimal("-2000")
    assert _balance(client, soc, "amenity_deposits") == 0
