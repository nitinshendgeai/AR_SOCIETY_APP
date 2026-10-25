"""
Outstandings, the way Tally keeps them: what members owe the society (receivable) and what the society owes its
vendors (payable), each aged by how long it is past its due date, party by party with the bills behind each party.

Read-only: members' dues come from the maintenance bills (the same figures as the defaulters list), vendors' from the
bills received and not yet paid. Both are "as on today".
"""
import re
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.modules.accounts.services.accounts_service import money
from app.modules.billing.services.bill_pdf import flat_label
from app.modules.billing.services.defaulters import MemberDues, bill_label, member_contact
from app.modules.vendor.models.vendor import VendorInvoice

ZERO = Decimal("0.00")

# key, label, last day-past-due the bucket takes (None: no bound)
BUCKETS = [
    ("not_due", "Not yet due", 0),
    ("d1_30", "1–30 days", 30),
    ("d31_60", "31–60 days", 60),
    ("d61_90", "61–90 days", 90),
    ("over_90", "Over 90 days", None),
]


def bucket_of(days_overdue: int) -> str:
    for key, _label, upto in BUCKETS:
        if upto is None or days_overdue <= upto:
            return key
    return BUCKETS[-1][0]


def _natural(s: str):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", s or "")]


def _party(key: str, name: str, sub: Optional[str], bills: List[dict], **extra) -> dict:
    buckets = {k: ZERO for k, _l, _u in BUCKETS}
    for b in bills:
        buckets[b["bucket"]] += Decimal(b["outstanding"])
    oldest = min(bills, key=lambda b: b["due_date"])
    return {
        "key": key, "name": name, "sub": sub, "total": str(money(sum(buckets.values(), ZERO))),
        "buckets": {k: str(money(v)) for k, v in buckets.items()},
        "oldest_due_date": oldest["due_date"], "days_overdue": max(b["days_overdue"] for b in bills),
        "bill_count": len(bills), "bills": bills, **extra,
    }


class OutstandingService:
    def __init__(self, db: Session):
        self.db = db

    def report(self, society_id: UUID, kind: str, as_of: Optional[date] = None) -> dict:
        as_of = as_of or date.today()
        if kind == "receivable":
            parties = self._receivable(society_id, as_of)
        else:
            parties = self._payable(society_id, as_of)
        totals = {k: ZERO for k, _l, _u in BUCKETS}
        for p in parties:
            for k, v in p["buckets"].items():
                totals[k] += Decimal(v)
        grand = sum(totals.values(), ZERO)
        return {
            "kind": kind, "as_of": as_of.isoformat(),
            "bucket_labels": [{"key": k, "label": label} for k, label, _u in BUCKETS],
            "totals": {"parties": len(parties), "bills": sum(p["bill_count"] for p in parties),
                       "outstanding": str(money(grand)),
                       "overdue": str(money(grand - totals["not_due"])),
                       "buckets": {k: str(money(v)) for k, v in totals.items()}},
            "parties": parties,
        }

    def _receivable(self, society_id: UUID, as_of: date) -> List[dict]:
        out = []
        for fd in MemberDues(self.db).flats(society_id, as_of):
            name, phone = member_contact(fd.flat)
            bills = []
            for ub in fd.bills:
                days = max(0, (as_of - ub.bill.due_date).days)
                bills.append({
                    "ref": ub.bill.invoice_number, "label": bill_label(ub.bill),
                    "date": ub.bill.bill_date.isoformat(), "due_date": ub.bill.due_date.isoformat(),
                    "outstanding": str(money(ub.outstanding)), "days_overdue": days, "bucket": bucket_of(days),
                })
            order = ((fd.flat.wing.name if fd.flat.wing else ""), _natural(fd.flat.flat_number))
            out.append((order, _party(str(fd.flat.id), flat_label(fd.flat), name if name != "-" else None, bills,
                                      phone=phone, on_account=str(money(fd.on_account)))))
        out.sort(key=lambda t: t[0])
        return [p for _o, p in out]

    def _payable(self, society_id: UUID, as_of: date) -> List[dict]:
        invoices = (self.db.query(VendorInvoice).options(joinedload(VendorInvoice.vendor))
                    .filter(VendorInvoice.society_id == society_id, VendorInvoice.is_paid == False,  # noqa: E712
                            VendorInvoice.is_active == True)  # noqa: E712
                    .order_by(VendorInvoice.due_date, VendorInvoice.invoice_date).all())
        by_vendor: Dict[UUID, List[dict]] = {}
        names: Dict[UUID, str] = {}
        for i in invoices:
            # What is still to pay: the bill less the TDS taken when it was booked less what has been paid
            left = max(Decimal(i.total_amount) - Decimal(i.tds_amount or 0) - Decimal(i.paid_amount), ZERO)
            if left <= 0:
                continue
            due = i.due_date or i.invoice_date          # no credit period given: due on the bill date
            days = max(0, (as_of - due).days)
            names[i.vendor_id] = i.vendor.company_name if i.vendor else "(vendor removed)"
            by_vendor.setdefault(i.vendor_id, []).append({
                "ref": i.invoice_number, "label": (i.description or "")[:60] or None,
                "date": i.invoice_date.isoformat(), "due_date": due.isoformat(),
                "outstanding": str(money(left)), "days_overdue": days, "bucket": bucket_of(days),
                "no_due_date": i.due_date is None,
            })
        parties = [_party(str(vid), names[vid], None, bills) for vid, bills in by_vendor.items()]
        parties.sort(key=lambda p: p["name"].lower())
        return parties
