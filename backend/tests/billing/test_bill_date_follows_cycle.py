"""A bill, and its entry in the accounts (the outstanding), carry the billing cycle's start date - a bill for July to
September is dated 1 July however late it is generated - and never a day later than the day it is generated."""
from datetime import date, timedelta
from uuid import UUID

from app.modules.accounts.models.accounts import Voucher
from app.modules.billing.models.billing import DueTracker, MaintenanceBill
from tests.billing.test_maintenance_billing import _charge, _rig

API = "/api/v1/billing"


def _bills_for(client, db, tag, start, end):
    society, flat1, flat2, manager, resident, other = _rig(db, tag)
    h = manager["headers"]
    _charge(client, h, society.id, amount="2500.00")
    cycle = client.post(f"{API}/cycles", json={
        "society_id": str(society.id), "name": f"{tag} cycle", "cycle_start": str(start), "cycle_end": str(end),
        "due_date": str(end + timedelta(days=10))}, headers=h).json()["id"]
    assert client.post(f"{API}/cycles/{cycle}/generate-bills", headers=h).status_code == 200
    assert client.post(f"{API}/cycles/{cycle}/issue-all", headers=h).status_code == 200
    db.expire_all()
    return society, flat1, db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle), flat_id=flat1.id).one()


def test_the_bill_and_its_accounts_entry_are_dated_the_cycle_start(client, db):
    start = date.today() - timedelta(days=40)
    society, flat1, bill = _bills_for(client, db, "bd1", start, start + timedelta(days=29))
    assert bill.bill_date == start                                   # not the day it was generated
    voucher = db.query(Voucher).filter_by(source_type="maintenance_bill", source_id=bill.id).one()
    assert voucher.voucher_date == start                             # the outstanding is booked in the cycle's month
    tracker = db.query(DueTracker).filter_by(flat_id=flat1.id).one()
    assert tracker.last_bill_date == start


def test_a_cycle_that_starts_in_the_future_is_dated_today(client, db):
    start = date.today() + timedelta(days=5)
    _s, _f, bill = _bills_for(client, db, "bd2", start, start + timedelta(days=29))
    assert bill.bill_date == date.today()                            # never a future-dated bill
    voucher = db.query(Voucher).filter_by(source_type="maintenance_bill", source_id=bill.id).one()
    assert voucher.voucher_date == date.today()
