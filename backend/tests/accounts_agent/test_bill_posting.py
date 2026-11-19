"""Maintenance-bill posting checks, on bills issued and posted by the app itself."""
from decimal import Decimal
from uuid import UUID

import pytest

from app.modules.accounts.models.accounts import Voucher, VoucherEntry
from app.modules.accounts_agent.services import engine
from app.modules.billing.models.billing import InvoiceLineItem, MaintenanceBill
from tests.accounts.test_accounts import _issued_bills


@pytest.fixture
def issued(client, db):
    society, flat1, flat2, manager, resident, bill1 = _issued_bills(client, db, "bp")
    v = db.query(Voucher).filter(Voucher.source_type == "maintenance_bill", Voucher.source_id == bill1.id).one()
    return db, society, flat1, flat2, bill1, v


def bill_codes(db, v):
    db.refresh(v)
    return sorted(d.rule_code for d in engine.analyse(db, v) if d.rule_code.startswith("R-BILL"))


def test_a_correctly_posted_bill_raises_nothing(issued):
    db, *_, v = issued
    assert bill_codes(db, v) == []


def test_every_bill_posted_by_the_app_is_clean(issued):
    db, society, *_ = issued
    vs = db.query(Voucher).filter(Voucher.society_id == society.id, Voucher.source_type == "maintenance_bill").all()
    assert len(vs) >= 2
    assert all(bill_codes(db, v) == [] for v in vs)


def test_bill_total_changed_after_posting_is_flagged(issued):
    db, *_, bill, v = issued
    bill.total_amount = bill.total_amount + Decimal("100")
    db.commit()
    codes = bill_codes(db, v)
    assert "R-BILL-02" in codes and "R-BILL-01" in codes
    d = next(x for x in engine.analyse(db, v) if x.rule_code == "R-BILL-02")
    assert d.finding_class == "confirmed_validation_failure" and d.severity == "HIGH"
    assert bill.invoice_number in d.explanation


def test_line_items_that_do_not_add_up_are_flagged(issued):
    db, *_, bill, v = issued
    li = db.query(InvoiceLineItem).filter(InvoiceLineItem.bill_id == bill.id).first()
    li.amount = li.amount + Decimal("50")
    db.commit()
    assert "R-BILL-01" in bill_codes(db, v)


def test_posting_to_another_flat_is_flagged(issued):
    db, _s, flat1, flat2, bill, v = issued
    dues = [e for e in v.entries if e.flat_id == flat1.id]
    dues[0].flat_id = flat2.id
    db.commit()
    assert "R-BILL-03" in bill_codes(db, v)


def test_charge_head_credited_to_the_wrong_ledger_is_flagged(issued):
    db, society, *_, bill, v = issued
    credits = [e for e in v.entries if e.credit > 0]
    other = next(a for a in {e.account_id for e in db.query(VoucherEntry).filter(VoucherEntry.credit > 0)} if a != credits[0].account_id)
    credits[0].account_id = other
    db.commit()
    d = next(x for x in engine.analyse(db, db.get(Voucher, v.id)) if x.rule_code == "R-BILL-04")
    assert "bill says" in d.explanation


def test_live_posting_for_a_cancelled_bill_is_flagged(issued):
    from app.modules.billing.models.billing import BillStatus
    db, *_, bill, v = issued
    bill.bill_status = BillStatus.CANCELLED
    db.commit()
    assert "R-BILL-05" in bill_codes(db, v)


def test_a_cancelled_posting_is_not_checked(issued):
    db, *_, bill, v = issued
    bill.total_amount = bill.total_amount + Decimal("100")
    v.is_cancelled = True
    db.commit()
    assert bill_codes(db, v) == []
