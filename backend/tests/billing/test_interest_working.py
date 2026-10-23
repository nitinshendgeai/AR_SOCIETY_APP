"""The interest working printed on a bill: which earlier bills the interest was charged on, the unpaid amount, the days
and the rate, adding up to the Interest line. And printing a bill with or without the previous bill's receipts."""
import json
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from app.modules.billing.models.billing import MaintenanceBill
from app.modules.billing.services.bill_pdf import generate_maintenance_bill_pdf
from app.modules.billing.services.billing_service import BillingService
from app.modules.billing.services.maintenance_calculator import _split_interest
from tests.billing.test_bill_pdf import _text
from tests.billing.test_interest_waivers import API, TODAY, _arrears, _cycle, _waive

# Arrears here: one ₹3,650 bill that fell due 30 days ago, 12% p.a. → ₹36.00


def _second_bill(client, db, tag, **waiver):
    society, flat, h, admin = _arrears(client, db, tag)
    if waiver:
        assert _waive(client, admin, society, flat, **waiver).status_code == 201
    cycle = _cycle(client, h, society.id, name="Current")
    assert client.post(f"{API}/cycles/{cycle}/generate-bills", headers=h).status_code == 200
    bill = db.query(MaintenanceBill).filter_by(cycle_id=UUID(cycle), flat_id=flat.id).one()
    return society, flat, h, bill


def _pdf_text(db, bill, with_receipts=True):
    svc = BillingService(db)
    pdf = generate_maintenance_bill_pdf(bill, svc.get_maintenance_settings(bill.society_id), compress=False,
                                        **svc._bill_print_context(bill, with_receipts=with_receipts))
    return " ".join(_text(pdf).replace("|", " ").split())


def test_working_is_saved_with_the_bill_and_adds_up_to_the_interest_line(client, db):
    _s, _f, _h, bill = _second_bill(client, db, "iwk1")
    rows = json.loads(bill.interest_working)
    assert len(rows) == 1
    r = rows[0]
    assert r["principal"] == "3650.00" and r["days"] == 30 and r["rate"] == "12.00" and r["interest"] == "36.00"
    assert r["to"] == TODAY.isoformat() and r["from"] == (TODAY - timedelta(days=30)).isoformat()
    interest_line = [li for li in bill.line_items if li.description.startswith("Interest on arrears")][0]
    assert Decimal(r["interest"]) == Decimal(interest_line.total)


def test_working_shows_the_adjusted_rate_when_a_waiver_applies(client, db):
    _s, _f, _h, bill = _second_bill(client, db, "iwk2", mode="rate", rate_pct="6")
    r = json.loads(bill.interest_working)[0]
    assert r["rate"] == "6.00" and r["interest"] == "18.00"


def test_no_interest_means_no_working(client, db):
    _s, _f, _h, bill = _second_bill(client, db, "iwk3", mode="waive")
    assert bill.interest_working is None
    assert "Interest working" not in _pdf_text(db, bill)


def test_working_is_printed_on_the_bill(client, db):
    _s, _f, _h, bill = _second_bill(client, db, "iwk4")
    text = _pdf_text(db, bill)
    assert "Interest working" in text
    assert "Bill No. Unpaid (Rs.) From To Days Rate % p.a. Interest (Rs.)" in text
    assert "3,650.00" in text and "Total interest 36.00" in text


def test_split_is_whole_paise_and_adds_up_to_the_total():
    rows = [{"bill": str(i), "raw": Decimal("3.335")} for i in range(3)]      # 10.005 → billed 10.01
    out = _split_interest(rows, Decimal("10.01"))
    assert sum(Decimal(r["interest"]) for r in out) == Decimal("10.01")
    assert all(Decimal(r["interest"]) in (Decimal("3.33"), Decimal("3.34")) for r in out)
    assert _split_interest([], Decimal("5.00")) == [] and _split_interest(rows, Decimal("0.00")) == []


def test_bill_pdf_route_can_leave_out_the_previous_receipts(client, db):
    _s, _f, h, bill = _second_bill(client, db, "iwk5")
    with_r = client.get(f"{API}/bills/{bill.id}/pdf", headers=h)
    without = client.get(f"{API}/bills/{bill.id}/pdf?with_receipts=false", headers=h)
    assert with_r.status_code == without.status_code == 200
    assert "Receipts: Towards" in _pdf_text(db, bill, True)
    assert "Receipts: Towards" not in _pdf_text(db, bill, False)
    assert without.content[:4] == b"%PDF"
    cycle = str(bill.cycle_id)
    assert client.get(f"{API}/cycles/{cycle}/bills.pdf?with_receipts=false", headers=h).status_code == 200
