"""Advance maintenance imported from a sheet: a receipt each, kept in its own liability ledger, set off against the
bills when they are raised."""
from datetime import date, timedelta
from decimal import Decimal

from app.modules.accounts.models.accounts import Account, Voucher
from app.modules.accounts.models.entities import EntityAccount
from app.modules.billing.models.billing import MaintenanceBill
from app.modules.billing.services.allocations import PaymentAllocator
from tests.billing.test_maintenance_billing import _charge, _cycle, _rig

URL = "/api/v1/billing/advance-import"
TODAY = str(date.today())


def _post(client, h, rows, dry_run=False, society=None):
    body = {"rows": rows, "dry_run": dry_run}
    if society is not None:
        body["society_id"] = str(society.id)
    return client.post(URL, headers=h, json=body)


def _row(line, flat, amount, mode="neft", **over):
    return {"line": line, "wing": "Tower A", "flat_number": flat, "amount": amount, "payment_date": TODAY,
            "payment_mode": mode, "transaction_ref": f"UTR{line}", **over}


def test_advances_are_recorded_in_their_own_ledger_and_set_off_against_the_bills(client, db):
    society, flat1, flat2, manager, *_ = _rig(db, "adv1")
    h = manager["headers"]
    r = _post(client, h, [_row(2, "101", "6000"), _row(3, "102", "2,000.00", mode="cash")], society=society)
    assert r.status_code == 200, r.text
    assert [x["status"] for x in r.json()] == ["recorded", "recorded"] and r.json()[0]["receipt_number"]

    ledger = db.query(Account).filter_by(society_id=society.id, system_key="advance_maintenance").one()
    assert ledger.name == "Advance Maintenance from Members" and ledger.group.nature == "liability"
    assert ledger.group.system_key == "current_liabilities"
    vouchers = db.query(Voucher).filter_by(society_id=society.id, source_type="online_payment").all()
    assert len(vouchers) == 2
    for v in vouchers:
        credit = next(e for e in v.entries if e.credit > 0)
        assert credit.account_id == ledger.id
        sub = db.get(EntityAccount, credit.entity_account_id)
        assert sub.subledger_type == "ADVANCE" and sub.control_account_id == ledger.id
    alloc = PaymentAllocator(db)
    assert alloc.advance(flat1.id) == Decimal("6000.00") and alloc.advance(flat2.id) == Decimal("2000.00")

    # The bills are raised later: each flat's advance is set off against its bill, the rest stays as its balance.
    _charge(client, h, society.id, amount="2500.00")
    cycle_id = _cycle(client, h, society.id).json()["id"]
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=h).status_code == 200
    assert client.post(f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=h).status_code == 200
    db.expire_all()
    b1 = db.query(MaintenanceBill).filter_by(flat_id=flat1.id).one()
    b2 = db.query(MaintenanceBill).filter_by(flat_id=flat2.id).one()
    assert b1.outstanding == 0 and b2.outstanding == Decimal("500.00")
    assert alloc.advance(flat1.id) == Decimal("3500.00") and alloc.advance(flat2.id) == 0


def test_a_dry_run_writes_nothing_and_the_same_file_twice_does_not_double_the_advance(client, db):
    society, flat1, _f2, manager, *_ = _rig(db, "adv2")
    h = manager["headers"]
    rows = [_row(2, "101", "5000")]
    r = _post(client, h, rows, dry_run=True, society=society).json()
    assert r[0]["status"] == "ready"
    assert PaymentAllocator(db).advance(flat1.id) == 0
    assert _post(client, h, rows, society=society).json()[0]["status"] == "recorded"
    again = _post(client, h, rows, society=society).json()[0]
    assert again["status"] == "error" and "Already recorded" in again["message"]
    assert PaymentAllocator(db).advance(flat1.id) == Decimal("5000.00")
    twice = _post(client, h, [_row(2, "102", "100"), _row(3, "102", "100", transaction_ref="UTR2")], society=society).json()
    assert [x["status"] for x in twice] == ["recorded", "error"]


def test_bad_rows_are_reported_and_the_rest_go_in(client, db):
    society, flat1, _f2, manager, *_ = _rig(db, "adv3")
    h = manager["headers"]
    tomorrow = str(date.today() + timedelta(days=1))
    r = _post(client, h, [
        _row(2, "999", "100"),
        _row(3, "101", "abc"),
        _row(4, "101", "0"),
        _row(5, "101", "100", mode="barter"),
        _row(6, "101", "100", payment_date=tomorrow),
        _row(7, "101", "100", payment_date=""),
        _row(8, "101", "750", mode="Cheque"),
    ], society=society).json()
    assert [x["status"] for x in r] == ["error"] * 6 + ["recorded"]
    assert "No flat 999" in r[0]["message"] and "future" in r[4]["message"]
    assert PaymentAllocator(db).advance(flat1.id) == Decimal("750.00")


def test_only_managers_can_import_and_only_their_own_society(client, db):
    from tests.conftest import make_user
    society, flat1, _f2, manager, resident, other = _rig(db, "adv4")
    assert _post(client, resident["headers"], [], society=society).status_code == 403
    r = _post(client, manager["headers"], [{**_row(2, "101", "100"), "wing": "Nowhere"}], society=society).json()
    assert r[0]["status"] == "error"
