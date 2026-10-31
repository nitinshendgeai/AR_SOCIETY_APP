"""
READ-ONLY report: online payments whose day and month may have been swapped by the advance-maintenance import.

    python scripts/list_swapped_payment_dates.py <SOCIETY_CODE>                       # all payments, writes the CSV
    python scripts/list_swapped_payment_dates.py <SOCIETY_CODE> --from 2026-04-01 --to 2026-04-30
    python scripts/list_swapped_payment_dates.py <SOCIETY_CODE> --out swapped.csv

Run it from the backend/ directory against the database in DATABASE_URL. It changes nothing.

An Excel set to US regional settings saves 4 Sep 2026 in a CSV as 9/4/2026, which the import reads (day first) as
9 Apr 2026. A date with a day above 12 cannot be swapped, so only payments whose day is 1-12 (and differs from the
month) are listed. For each, the CSV shows the date now on file, the date it would be if swapped back, the voucher
that took that date, when the payment was entered, and `plausible`: "yes" when the swapped-back date is neither in
the future nor after the day the payment was entered (a payment cannot be entered before it was made). Review the
list with the members' cheque/bank records; nothing is corrected from here.
"""
import argparse
import csv
import os
import sys
from datetime import date
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session  # noqa: E402

COLUMNS = ["receipt_number", "flat", "amount", "mode", "reference", "bank", "notes", "date_on_file", "date_if_swapped",
           "plausible", "entered_on", "voucher_number", "voucher_date", "status"]


def swapped(d: date) -> Optional[date]:
    """`d` with its day and month exchanged, or None when that is no different or no date (day above 12)."""
    if d.day > 12 or d.day == d.month:
        return None
    return date(d.year, d.day, d.month)


def candidates(db: Session, society_id, date_from: Optional[date] = None, date_to: Optional[date] = None,
               today: Optional[date] = None) -> List[Dict[str, str]]:
    from app.modules.accounts.models.accounts import Voucher
    from app.modules.billing.models.billing import OnlinePaymentSubmission, ReconciliationStatus

    today = today or date.today()
    q = db.query(OnlinePaymentSubmission).filter(
        OnlinePaymentSubmission.society_id == society_id, OnlinePaymentSubmission.is_active == True,  # noqa: E712
        OnlinePaymentSubmission.status != ReconciliationStatus.REJECTED)
    if date_from:
        q = q.filter(OnlinePaymentSubmission.payment_date >= date_from)
    if date_to:
        q = q.filter(OnlinePaymentSubmission.payment_date <= date_to)
    rows = []
    for p in q.order_by(OnlinePaymentSubmission.payment_date, OnlinePaymentSubmission.receipt_number):
        other = swapped(p.payment_date)
        if other is None:
            continue
        entered = p.created_at.date() if getattr(p, "created_at", None) else None
        plausible = other <= today and (entered is None or other <= entered)
        v = (db.query(Voucher).filter(Voucher.society_id == society_id, Voucher.source_type == "online_payment",
                                      Voucher.source_id == p.id, Voucher.is_cancelled == False)  # noqa: E712
             .first())
        flat = p.flat
        label = (f"{flat.wing.name} {flat.flat_number}" if flat is not None and flat.wing else
                 (flat.flat_number if flat is not None else ""))
        rows.append({
            "receipt_number": p.receipt_number, "flat": label, "amount": f"{p.amount:.2f}",
            "mode": p.payment_mode.value, "reference": p.transaction_ref or "", "bank": p.bank_name or "",
            "notes": (p.notes or "").replace("\n", " "), "date_on_file": p.payment_date.strftime("%d-%b-%Y"),
            "date_if_swapped": other.strftime("%d-%b-%Y"), "plausible": "yes" if plausible else "no",
            "entered_on": entered.strftime("%d-%b-%Y") if entered else "",
            "voucher_number": v.voucher_number if v else "", "voucher_date": v.voucher_date.strftime("%d-%b-%Y") if v else "",
            "status": p.status.value,
        })
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="List payments whose day and month may be swapped (read-only).")
    ap.add_argument("society_code")
    ap.add_argument("--from", dest="date_from", type=date.fromisoformat, help="only payments dated on/after (yyyy-mm-dd)")
    ap.add_argument("--to", dest="date_to", type=date.fromisoformat, help="only payments dated on/before (yyyy-mm-dd)")
    ap.add_argument("--out", default="swapped_payment_dates.csv")
    args = ap.parse_args(argv)

    from app.db.session import get_session_factory
    from app.services.society_purge import find_society

    db = get_session_factory()()
    try:
        found = find_society(db, args.society_code)
        if not found:
            print(f"No society with code {args.society_code!r}.", file=sys.stderr)
            return 1
        rows = candidates(db, found.id, args.date_from, args.date_to)
    finally:
        db.close()
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    plausible = sum(r["plausible"] == "yes" for r in rows)
    print(f"{found.name}: {len(rows)} payment(s) could be swapped, {plausible} plausibly. Written to {args.out}. Nothing was changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
