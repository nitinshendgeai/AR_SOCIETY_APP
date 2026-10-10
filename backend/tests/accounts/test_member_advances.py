"""Regression coverage for formal member advance accounting."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from app.modules.accounts.models.accounts import Voucher
from app.modules.accounts.models.entities import EntityAccount
from tests.billing.test_defaulters import _two_cycles
from tests.billing.test_maintenance_billing import _cycle

PAY = "/api/v1/billing/online-payments"


def _pay(client, h, flat, amount, mode="cash"):
    r = client.post(
        PAY,
        data={
            "flat_id": str(flat.id),
            "amount": amount,
            "payment_date": str(date.today()),
            "payment_mode": mode,
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_member_advance_posts_to_advance_subledger_and_moves_to_ar(client, db):
    society, flat, _flat2, manager, _resident = _two_cycles(client, db, "acct_adv")
    h = manager["headers"]

    payment = _pay(client, h, flat, "6000.00")
    assert payment["applied_amount"] == "5000.00"
    assert payment["unapplied_amount"] == "1000.00"

    receipt_voucher = db.query(Voucher).filter_by(
        society_id=society.id, source_type="online_payment", source_id=UUID(payment["id"])
    ).one()
    advance_entries = [
        e for e in receipt_voucher.entries
        if e.credit == Decimal("1000.00")
    ]
    assert len(advance_entries) == 1

    advance_account = db.get(EntityAccount, advance_entries[0].entity_account_id)
    assert advance_account is not None
    assert advance_account.subledger_type == "ADVANCE"
    assert advance_account.control_account_id == advance_entries[0].account_id

    cycle_id = _cycle(client, h, society.id, name="Advance application cycle").json()["id"]
    assert client.post(
        f"/api/v1/billing/cycles/{cycle_id}/generate-bills", headers=h
    ).status_code == 200
    assert client.post(
        f"/api/v1/billing/cycles/{cycle_id}/issue-all", headers=h
    ).status_code == 200

    adjustment = db.query(Voucher).filter_by(
        society_id=society.id, source_type="advance_allocation"
    ).one()
    assert adjustment.amount == Decimal("1000.00")

    debit = next(e for e in adjustment.entries if e.debit == Decimal("1000.00"))
    credit = next(e for e in adjustment.entries if e.credit == Decimal("1000.00"))
    debit_account = db.get(EntityAccount, debit.entity_account_id)
    credit_account = db.get(EntityAccount, credit.entity_account_id)
    assert debit_account.subledger_type == "ADVANCE"
    assert credit_account.subledger_type == "AR"
