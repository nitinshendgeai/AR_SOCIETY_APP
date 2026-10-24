"""Rounding bills to the whole rupee: off by default; when on, each bill's amount is rounded to the nearest rupee
(half a rupee up), the difference is a "Round off" on the bill, and it is posted to the Rounding Off ledger so the
bill voucher still balances."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.modules.accounts.models.accounts import Voucher
from app.modules.billing.models.billing import MaintenanceBill
from app.modules.billing.services.bill_pdf import generate_maintenance_bill_pdf
from app.modules.billing.services.billing_service import BillingService
from app.modules.billing.services.maintenance_calculator import round_to_rupee
from tests.accounts.test_accounts import _balance
from tests.billing.test_bill_pdf import _text
from tests.billing.test_maintenance_calculation import _charge, _cycle, _preview, _rig, _settings

API = "/api/v1/billing"


def _issued(client, db, tag, amount, *, rounding=True, **settings):
    society, flats, h = _rig(db, tag, areas=(600,))
    _settings(client, h, society.id, interest_rate_pct="0", round_to_rupee=rounding, **settings)
    _charge(client, h, society.id, "Maintenance", "fixed", amount)
    cycle = _cycle(client, h, society.id)
    assert client.post(f"{API}/cycles/{cycle}/generate-bills", headers=h).status_code == 200
    assert client.post(f"{API}/cycles/{cycle}/issue-all", headers=h).status_code == 200
    bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle), flat_id=flats[0].id).one()
    return society, h, cycle, bill


def test_round_to_rupee_is_the_nearest_with_half_up():
    assert round_to_rupee("1234.56") == Decimal("0.44")
    assert round_to_rupee("1234.49") == Decimal("-0.49")
    assert round_to_rupee("1234.50") == Decimal("0.50")
    assert round_to_rupee("1234.00") == Decimal("0.00")
    assert round_to_rupee("0.30") == Decimal("-0.30")


def test_setting_is_off_by_default_and_can_be_turned_on(client, db):
    society, _flats, h = _rig(db, "rr0", areas=(600,))
    assert client.get(f"{API}/maintenance-settings/{society.id}", headers=h).json()["round_to_rupee"] is False
    assert _settings(client, h, society.id, round_to_rupee=True)["round_to_rupee"] is True
    assert client.get(f"{API}/maintenance-settings/{society.id}", headers=h).json()["round_to_rupee"] is True


def test_bills_run_to_the_paisa_when_not_rounding(client, db):
    _s, _h, _c, bill = _issued(client, db, "rr1", "1234.56", rounding=False)
    assert bill.total_amount == Decimal("1234.56") and bill.round_off == Decimal("0.00")


def test_rounding_adds_the_difference_to_the_bill_and_the_preview_shows_it(client, db):
    society, flats, h = _rig(db, "rr2", areas=(600,))
    _settings(client, h, society.id, interest_rate_pct="0", round_to_rupee=True)
    _charge(client, h, society.id, "Maintenance", "fixed", "1234.56")
    cycle = _cycle(client, h, society.id)
    f = _preview(client, h, cycle)["flats"][0]
    assert f["subtotal"] == "1234.56" and f["round_off"] == "0.44" and f["total"] == "1235.00"
    assert client.post(f"{API}/cycles/{cycle}/generate-bills", headers=h).status_code == 200
    bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle)).one()
    assert bill.subtotal == Decimal("1234.56") and bill.round_off == Decimal("0.44")
    assert bill.total_amount == Decimal("1235.00") and bill.outstanding == Decimal("1235.00")
    detail = client.get(f"{API}/bills/{bill.id}", headers=h).json()
    assert detail["round_off"] == "0.44" and detail["total_amount"] == "1235.00"


def test_rounding_down_is_a_negative_round_off(client, db):
    _s, _h, _c, bill = _issued(client, db, "rr3", "1234.49")
    assert bill.round_off == Decimal("-0.49") and bill.total_amount == Decimal("1234.00")


def test_gst_is_part_of_the_amount_that_is_rounded(client, db):
    society, flats, h = _rig(db, "rr4", areas=(600,))
    _settings(client, h, society.id, interest_rate_pct="0", gst_enabled=True, gst_rate_pct="18",
              gst_threshold_monthly="0", round_to_rupee=True)
    _charge(client, h, society.id, "Maintenance", "fixed", "1000.50")
    cycle = _cycle(client, h, society.id)
    f = _preview(client, h, cycle)["flats"][0]
    # 1,000.50 + 18% GST 180.09 = 1,180.59, rounded up to 1,181.00
    assert f["tax"] == "180.09" and f["round_off"] == "0.41" and f["total"] == "1181.00"


def test_the_bill_voucher_balances_and_the_difference_goes_to_rounding_off(client, db):
    society, h, _c, bill = _issued(client, db, "rr5", "1234.56")
    sid = str(society.id)
    v = db.query(Voucher).filter_by(source_type="maintenance_bill", source_id=bill.id).one()
    assert sum(e.debit for e in v.entries) == sum(e.credit for e in v.entries) == Decimal("1235.00")
    assert _balance(client, h, sid, "members_dues") == Decimal("1235.00")
    assert _balance(client, h, sid, "round_off") == Decimal("-0.44")                  # credit: income


def test_rounding_down_posts_a_debit_to_rounding_off(client, db):
    society, h, _c, bill = _issued(client, db, "rr6", "1234.49")
    sid = str(society.id)
    assert _balance(client, h, sid, "members_dues") == Decimal("1234.00")
    assert _balance(client, h, sid, "round_off") == Decimal("0.49")


def test_the_printed_bill_shows_the_round_off_and_a_whole_rupee_total(client, db):
    _s, _h, _c, bill = _issued(client, db, "rr7", "1234.56")
    svc = BillingService(db)
    pdf = generate_maintenance_bill_pdf(bill, svc.get_maintenance_settings(bill.society_id), compress=False,
                                        **svc._bill_print_context(bill))
    text = " ".join(_text(pdf).replace("|", " ").split())
    assert "Round off 0.44" in text
    assert "Total Maintenance Payable Amount Rs. 1,235.00" in text


def test_a_bill_without_rounding_prints_no_round_off_line(client, db):
    _s, _h, _c, bill = _issued(client, db, "rr8", "1234.56", rounding=False)
    svc = BillingService(db)
    pdf = generate_maintenance_bill_pdf(bill, svc.get_maintenance_settings(bill.society_id), compress=False,
                                        **svc._bill_print_context(bill))
    text = " ".join(_text(pdf).replace("|", " ").split())
    assert "Round off" not in text and "Rs. 1,234.56" in text


def test_paying_the_rounded_amount_settles_the_bill(client, db):
    society, h, _c, bill = _issued(client, db, "rr9", "1234.56")
    r = client.post(f"{API}/payments", json={
        "bill_id": str(bill.id), "amount": "1235.00", "payment_date": str(date.today()), "payment_mode": "cash"},
        headers=h)
    assert r.status_code in (200, 201), r.text
    db.refresh(bill)
    assert bill.outstanding == Decimal("0.00") and bill.bill_status.value == "paid"
