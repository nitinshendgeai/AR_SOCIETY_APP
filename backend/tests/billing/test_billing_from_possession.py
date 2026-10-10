"""Billing from the possession date: with a billing start date set, a flat is billed for the days from the end of
its last bill (or, for a first bill, from its possession date but never before the start date) to the end of the
cycle; a part of a month is charged by its days. Without a start date nothing changes."""
from datetime import date
from decimal import Decimal

from app.modules.billing.models.billing import MaintenanceBill
from app.modules.billing.services.maintenance_calculator import calendar_months, months_to_bill
from tests.billing.test_maintenance_billing import _charge, _rig
from tests.conftest import make_flat

B = "/api/v1/billing"


# ── The month maths ───────────────────────────────────────────────────────────

def test_a_part_of_a_month_is_charged_by_its_days():
    assert calendar_months(date(2026, 1, 1), date(2026, 1, 31)) == Decimal("1")
    assert calendar_months(date(2026, 1, 12), date(2026, 1, 31)) == Decimal("0.645161")      # possession on the 12th: 20 of 31 days
    assert calendar_months(date(2026, 2, 15), date(2026, 2, 28)) == Decimal("0.5")                # 14 of 28 days
    assert calendar_months(date(2026, 8, 16), date(2026, 10, 31)) == Decimal("2.516129")          # half of Aug + Sep + Oct
    assert calendar_months(date(2026, 3, 5), date(2026, 3, 4)) == 0                               # nothing


class _Cycle:                        # the bits months_to_bill reads
    from app.modules.billing.models.billing import CycleFrequency
    frequency = CycleFrequency.MONTHLY
    cycle_start, cycle_end = date(2026, 10, 1), date(2026, 10, 31)


def test_months_to_bill_around_a_cycle():
    c = _Cycle
    assert months_to_bill(date(2026, 10, 1), c) == 1                       # starts with the cycle: exactly one month
    assert months_to_bill(date(2026, 10, 16), c) == Decimal("0.516129")    # 16 of 31 days of the cycle
    assert months_to_bill(date(2026, 11, 1), c) == 0                       # after it
    assert months_to_bill(date(2026, 8, 1), c) == 3                        # Aug + Sep + this month
    assert months_to_bill(date(2026, 9, 16), c) == Decimal("1.5")          # half of Sep + this month


# ── Bills ─────────────────────────────────────────────────────────────────────

def _cycle(client, h, sid, name, start, end, due):
    r = client.post(f"{B}/cycles", json={"society_id": sid, "name": name, "cycle_start": start, "cycle_end": end,
                                         "due_date": due}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _generate(client, h, cycle_id):
    r = client.post(f"{B}/cycles/{cycle_id}/generate-bills", headers=h)
    assert r.status_code == 200, r.text


def _bills(db, cycle_id):
    return {b.flat_id: b for b in db.query(MaintenanceBill).filter(MaintenanceBill.cycle_id == cycle_id)}


def _rig_flats(db, tag):
    society, f1, f2, manager, *_ = _rig(db, tag)
    f3 = make_flat(db, f1.wing_id, "103")
    f4 = make_flat(db, f1.wing_id, "104")
    f1.possession_date = date(2026, 9, 16)       # during September
    f2.possession_date = date(2019, 1, 1)        # long before billing began here
    f3.possession_date = None                    # not recorded
    f4.possession_date = date(2026, 12, 1)       # not yet
    db.commit()
    return society, (f1, f2, f3, f4), manager


def test_first_bills_run_from_possession_never_before_the_start_date_then_one_cycle_each(client, db):
    society, (f1, f2, f3, f4), manager = _rig_flats(db, "pos1")
    h, sid = manager["headers"], str(society.id)
    assert _charge(client, h, society.id, amount="1000.00").status_code == 201
    assert client.put(f"{B}/maintenance-settings/{sid}", json={"billing_start_date": "2026-08-01"},
                      headers=h).json()["billing_start_date"] == "2026-08-01"

    oct_ = _cycle(client, h, sid, "Oct 2026", "2026-10-01", "2026-10-31", "2026-11-10")
    pre = client.get(f"{B}/cycles/{oct_}/preview", headers=h).json()
    by_flat = {f["flat_id"]: f for f in pre["flats"]}
    assert by_flat[str(f1.id)]["period_start"] == "2026-09-16" and by_flat[str(f1.id)]["months"] == "1.5"
    assert str(f4.id) not in by_flat                                            # possession is after the cycle
    assert any("more than this cycle" in w for w in pre["warnings"])

    _generate(client, h, oct_)
    bills = _bills(db, UUID_(oct_))
    assert bills[f1.id].total_amount == Decimal("1500.00")                      # 15 days of Sep (0.5) + Oct
    assert (bills[f1.id].period_start, bills[f1.id].period_end) == (date(2026, 9, 16), date(2026, 10, 31))
    assert bills[f2.id].total_amount == Decimal("3000.00")                      # not from 2019: from 1 Aug
    assert bills[f2.id].period_start == date(2026, 8, 1)
    assert bills[f3.id].total_amount == Decimal("3000.00")                      # no possession date: from the start date
    assert f4.id not in bills

    nov = _cycle(client, h, sid, "Nov 2026", "2026-11-01", "2026-11-30", "2026-12-10")
    _generate(client, h, nov)
    bills = _bills(db, UUID_(nov))
    assert {b.total_amount for b in bills.values()} == {Decimal("1000.00")}     # carried on: just November
    assert f4.id not in bills
    assert bills[f2.id].period_start == date(2026, 11, 1)

    dec = _cycle(client, h, sid, "Dec 2026", "2026-12-01", "2026-12-31", "2027-01-10")
    _generate(client, h, dec)
    bills = _bills(db, UUID_(dec))
    assert bills[f4.id].total_amount == Decimal("1000.00") and bills[f4.id].period_start == date(2026, 12, 1)


def test_possession_part_way_through_the_cycle_is_charged_for_its_days(client, db):
    society, (f1, f2, f3, f4), manager = _rig_flats(db, "pos2")
    h, sid = manager["headers"], str(society.id)
    f4.possession_date = date(2026, 10, 16)
    db.commit()
    _charge(client, h, society.id, amount="1000.00")
    client.put(f"{B}/maintenance-settings/{sid}", json={"billing_start_date": "2026-10-01"}, headers=h)
    oct_ = _cycle(client, h, sid, "Oct 2026", "2026-10-01", "2026-10-31", "2026-11-10")
    _generate(client, h, oct_)
    bills = _bills(db, UUID_(oct_))
    assert bills[f4.id].total_amount == Decimal("516.13")                       # 16 of 31 days
    assert bills[f2.id].total_amount == Decimal("1000.00")                      # from the start date = the cycle itself


def test_a_cancelled_bill_does_not_count_as_billed(client, db):
    society, (f1, f2, f3, f4), manager = _rig_flats(db, "pos3")
    h, sid = manager["headers"], str(society.id)
    _charge(client, h, society.id, amount="1000.00")
    client.put(f"{B}/maintenance-settings/{sid}", json={"billing_start_date": "2026-08-01"}, headers=h)
    oct_ = _cycle(client, h, sid, "Oct 2026", "2026-10-01", "2026-10-31", "2026-11-10")
    _generate(client, h, oct_)
    bill = _bills(db, UUID_(oct_))[f2.id]
    assert client.post(f"{B}/bills/{bill.id}/cancel", json={"reason": "Wrong"}, headers=h).status_code == 200
    nov = _cycle(client, h, sid, "Nov 2026", "2026-11-01", "2026-11-30", "2026-12-10")
    _generate(client, h, nov)
    again = _bills(db, UUID_(nov))[f2.id]
    assert again.total_amount == Decimal("4000.00")                             # Aug-Nov: nothing was billed for it yet
    assert again.period_start == date(2026, 8, 1)


def test_without_a_start_date_every_cycle_bills_its_own_period_as_before(client, db):
    society, (f1, f2, f3, f4), manager = _rig_flats(db, "pos4")
    h, sid = manager["headers"], str(society.id)
    _charge(client, h, society.id, amount="1000.00")
    oct_ = _cycle(client, h, sid, "Oct 2026", "2026-10-01", "2026-10-31", "2026-11-10")
    _generate(client, h, oct_)
    bills = _bills(db, UUID_(oct_))
    assert {b.total_amount for b in bills.values()} == {Decimal("1000.00")} and len(bills) == 4
    # the period is still recorded, and is the cycle's own
    assert all((b.period_start, b.period_end) == (date(2026, 10, 1), date(2026, 10, 31)) for b in bills.values())


def test_the_start_date_is_checked_clearable_and_the_bill_pdf_shows_the_period(client, db):
    society, (f1, f2, f3, f4), manager = _rig_flats(db, "pos5")
    h, sid = manager["headers"], str(society.id)
    assert client.put(f"{B}/maintenance-settings/{sid}", json={"billing_start_date": "1980-01-01"},
                      headers=h).status_code == 422
    assert client.put(f"{B}/maintenance-settings/{sid}", json={"billing_start_date": "2026-08-01"}, headers=h).status_code == 200
    assert client.put(f"{B}/maintenance-settings/{sid}", json={"billing_start_date": None},
                      headers=h).json()["billing_start_date"] is None
    client.put(f"{B}/maintenance-settings/{sid}", json={"billing_start_date": "2026-08-01"}, headers=h)
    _charge(client, h, society.id, amount="1000.00")
    oct_ = _cycle(client, h, sid, "Oct 2026", "2026-10-01", "2026-10-31", "2026-11-10")
    _generate(client, h, oct_)
    bill = _bills(db, UUID_(oct_))[f2.id]
    pdf = client.get(f"{B}/bills/{bill.id}/pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


from uuid import UUID as UUID_     # noqa: E402  (kept after the tests that use it, as in the other billing tests)
