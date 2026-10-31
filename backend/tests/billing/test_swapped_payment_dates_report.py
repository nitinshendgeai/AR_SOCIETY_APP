"""The read-only report of payments whose day and month may have been swapped by the advance import (an Excel on US
regional settings saves 4 Sep 2026 as 9/4/2026, which is read as 9 Apr)."""
import sys
from datetime import date, datetime
from pathlib import Path

from app.modules.billing.models.billing import OnlinePaymentSubmission
from tests.billing.test_advance_import import _post, _row, _rig

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from list_swapped_payment_dates import candidates, swapped  # noqa: E402


def test_only_days_up_to_12_that_differ_from_the_month_can_be_swapped():
    assert swapped(date(2026, 4, 9)) == date(2026, 9, 4)
    assert swapped(date(2026, 10, 23)) is None          # day above 12
    assert swapped(date(2026, 5, 5)) is None            # same either way


def test_report_lists_the_swappable_payments_with_voucher_and_changes_nothing(client, db):
    society, flat1, flat2, manager, *_ = _rig(db, "swp1")
    h = manager["headers"]
    # One read as 9 Apr (really 4 Sep) and one dated 23 Oct, which cannot be swapped
    r0 = _post(client, h, [_row(1, "101", "15000", payment_date="2026-04-09"),
                             _row(2, "102", "15000", payment_date="2026-10-23")], society=society)
    assert r0.status_code == 200, r0.text
    for sub in db.query(OnlinePaymentSubmission).filter_by(society_id=society.id):
        sub.created_at = datetime(2026, 10, 31, 9, 0)
    db.commit()
    before = {s.receipt_number: s.payment_date for s in db.query(OnlinePaymentSubmission)}

    rows = candidates(db, society.id, today=date(2026, 10, 31))

    assert len(rows) == 1
    r = rows[0]
    assert r["flat"] == "Tower A 101" and r["amount"] == "15000.00"
    assert r["date_on_file"] == "09-Apr-2026" and r["date_if_swapped"] == "04-Sep-2026" and r["plausible"] == "yes"
    assert r["voucher_number"].startswith("RV/") and r["voucher_date"] == "09-Apr-2026"
    assert {s.receipt_number: s.payment_date for s in db.query(OnlinePaymentSubmission)} == before
    # the window filters on the date on file
    assert candidates(db, society.id, date(2026, 5, 1), None, today=date(2026, 10, 31)) == []
