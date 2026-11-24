"""Rounding a bill UP to the next 50: below the next 50 it goes to 50, above it to the next 100. A bill that is already a
multiple of 50 is left alone. It is a society setting, off by default, and it replaces the nearest-rupee rounding when on."""
from decimal import Decimal
from uuid import UUID

import pytest

from app.modules.accounts.models.accounts import Voucher
from app.modules.billing.models.billing import MaintenanceBill
from app.modules.billing.services.maintenance_calculator import round_up_to_step
from tests.accounts.test_accounts import _balance
from tests.billing.test_maintenance_calculation import _charge, _cycle, _preview, _rig, _settings

API = "/api/v1/billing"


@pytest.mark.parametrize("amount, added", [
    ("1234.56", "15.44"),     # below the next 50: up to 1,250
    ("1200.01", "49.99"),     # a paisa over 1,200: up to 1,250
    ("1249.99", "0.01"),
    ("1250.00", "0.00"),      # already a multiple of 50
    ("1250.01", "49.99"),     # past 1,250: up to 1,300
    ("1260.00", "40.00"),     # the other side of 50: up to 1,300
    ("1299.50", "0.50"),
    ("1200.00", "0.00"),
    ("0.30", "49.70"),
])
def test_round_up_to_step_goes_to_the_next_50(amount, added):
    assert round_up_to_step(amount, 50) == Decimal(added)


def test_a_step_of_zero_leaves_the_amount(  ):
    assert round_up_to_step("1234.56", 0) == Decimal("0.00")


def _bill(client, db, tag, amount, **settings):
    society, flats, h = _rig(db, tag, areas=(600,))
    _settings(client, h, society.id, interest_rate_pct="0", **settings)
    _charge(client, h, society.id, "Maintenance", "fixed", amount)
    cycle = _cycle(client, h, society.id)
    assert client.post(f"{API}/cycles/{cycle}/generate-bills", headers=h).status_code == 200
    assert client.post(f"{API}/cycles/{cycle}/issue-all", headers=h).status_code == 200
    bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle), flat_id=flats[0].id).one()
    return society, h, cycle, bill


def test_off_by_default_and_the_setting_is_saved(client, db):
    society, flats, h = _rig(db, "ru1", areas=(600,))
    assert client.get(f"{API}/maintenance-settings/{society.id}", headers=h).json()["round_up_step"] == 0
    assert _settings(client, h, society.id, round_up_step=50)["round_up_step"] == 50
    assert client.get(f"{API}/maintenance-settings/{society.id}", headers=h).json()["round_up_step"] == 50
    assert _settings(client, h, society.id, round_up_step=0)["round_up_step"] == 0


def test_only_0_or_50_is_accepted(client, db):
    society, flats, h = _rig(db, "ru2", areas=(600,))
    r = client.put(f"{API}/maintenance-settings/{society.id}", json={"round_up_step": 25}, headers=h)
    assert r.status_code == 422


def test_bills_are_not_changed_when_off(client, db):
    _s, _h, _c, bill = _bill(client, db, "ru3", "1234.56")
    assert bill.total_amount == Decimal("1234.56") and bill.round_off == Decimal("0.00")


def test_a_bill_goes_up_to_the_next_50_or_100(client, db):
    society, flats, h = _rig(db, "ru4", areas=(600,))
    _settings(client, h, society.id, interest_rate_pct="0", round_up_step=50)
    _charge(client, h, society.id, "Maintenance", "fixed", "1234.56")
    cycle = _cycle(client, h, society.id)
    f = _preview(client, h, cycle)["flats"][0]
    assert f["subtotal"] == "1234.56" and f["round_off"] == "15.44" and f["total"] == "1250.00"
    assert client.post(f"{API}/cycles/{cycle}/generate-bills", headers=h).status_code == 200
    bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle)).one()
    assert bill.round_off == Decimal("15.44") and bill.total_amount == Decimal("1250.00")
    assert bill.outstanding == Decimal("1250.00")


def test_past_the_next_50_it_goes_to_the_100(client, db):
    _s, _h, _c, bill = _bill(client, db, "ru5", "1260", round_up_step=50)
    assert bill.round_off == Decimal("40.00") and bill.total_amount == Decimal("1300.00")


def test_a_multiple_of_50_is_left_alone(client, db):
    _s, _h, _c, bill = _bill(client, db, "ru6", "1250", round_up_step=50)
    assert bill.round_off == Decimal("0.00") and bill.total_amount == Decimal("1250.00")


def test_it_wins_over_the_nearest_rupee_when_both_are_set(client, db):
    _s, _h, _c, bill = _bill(client, db, "ru7", "1234.56", round_up_step=50, round_to_rupee=True)
    assert bill.total_amount == Decimal("1250.00")


def test_the_nearest_rupee_still_works_when_this_is_off(client, db):
    _s, _h, _c, bill = _bill(client, db, "ru8", "1234.56", round_to_rupee=True, round_up_step=0)
    assert bill.total_amount == Decimal("1235.00")


def test_gst_is_part_of_the_amount_that_is_rounded(client, db):
    society, flats, h = _rig(db, "ru9", areas=(600,))
    _settings(client, h, society.id, interest_rate_pct="0", gst_enabled=True, gst_rate_pct="18",
              gst_threshold_monthly="0", round_up_step=50)
    _charge(client, h, society.id, "Maintenance", "fixed", "1000.50")
    cycle = _cycle(client, h, society.id)
    f = _preview(client, h, cycle)["flats"][0]
    # 1,000.50 + 18% GST 180.09 = 1,180.59, up to 1,200.00
    assert f["tax"] == "180.09" and f["round_off"] == "19.41" and f["total"] == "1200.00"


def test_the_voucher_balances_and_the_difference_goes_to_rounding_off(client, db):
    society, h, _c, bill = _bill(client, db, "ru10", "1234.56", round_up_step=50)
    sid = str(society.id)
    v = db.query(Voucher).filter_by(source_type="maintenance_bill", source_id=bill.id).one()
    assert sum(e.debit for e in v.entries) == sum(e.credit for e in v.entries) == Decimal("1250.00")
    assert _balance(client, h, sid, "members_dues") == Decimal("1250.00")
    assert _balance(client, h, sid, "round_off") == Decimal("-15.44")                 # credit: income
