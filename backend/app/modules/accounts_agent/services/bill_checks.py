"""Maintenance-bill posting checks.

Two questions, answered from the society's own data with the same arithmetic the app uses (never a second opinion on rates):

1. Is the BILL internally consistent?  (line items add up to the bill's subtotal, tax and total — the arithmetic of
   MaintenanceCalculator: total = subtotal + tax + round-off.)
2. Does the VOUCHER posted for the bill say what the bill says?  The expected posting mirrors AccountPostings.post_bill:
   Dr Members' Dues (the bill's flat) for total_amount + penalty_amount; Cr each charge head's ledger for the line amounts,
   Cr GST Payable for the tax, Cr/Dr Round-off for any remainder. The agent re-derives it and compares.

It does not recompute rates or areas (that is the billing module's job and depends on settings the agent has no business
re-deciding): it checks that the books agree with the bill the society actually issued. Applied when the voucher is
created or edited, to live vouchers posted from a maintenance bill.
"""
from decimal import Decimal
from typing import Dict, List

from app.modules.accounts.models.accounts import Voucher
from app.modules.accounts.services.chart_of_accounts import bill_line_ledger_key
from app.modules.accounts.services.postings import POSTED_BILL_STATUSES, AccountPostings
from app.modules.accounts_agent.services.context import Ctx, Draft, ZERO, fmt, money
from app.modules.billing.models.billing import MaintenanceBill

CONFIRMED = "confirmed_validation_failure"


def expected_posting(db, bill: MaintenanceBill) -> tuple:
    """(total debited to Members' Dues, {ledger key: net credit}) exactly as post_bill builds them."""
    posting = AccountPostings(db)
    credits: Dict[str, Decimal] = {}
    for li in bill.line_items:
        key = bill_line_ledger_key(li, posting._element_code(bill.society_id, li.description))
        credits[key] = credits.get(key, ZERO) + money(li.amount)
        if money(li.tax_amount):
            credits["gst_payable"] = credits.get("gst_payable", ZERO) + money(li.tax_amount)
    if money(bill.penalty_amount):
        credits["interest_on_arrears"] = credits.get("interest_on_arrears", ZERO) + money(bill.penalty_amount)
    total = money(bill.total_amount) + money(bill.penalty_amount)
    diff = total - sum(credits.values(), ZERO)
    if diff:
        credits["round_off"] = credits.get("round_off", ZERO) + diff
    return total, {k: v for k, v in credits.items() if v}


def check_bill_posting(c: Ctx) -> List[Draft]:
    v: Voucher = c.voucher
    if (v.source_type != "maintenance_bill" or not v.source_id or v.is_cancelled or v.reversal_of_id
            or c.event_type not in ("voucher.created", "voucher.edited")):
        return []
    bill = c.db.query(MaintenanceBill).filter(MaintenanceBill.id == v.source_id,
                                              MaintenanceBill.society_id == v.society_id).first()
    if bill is None:
        return []                                   # missing / foreign source: reported by R-SRC-02 / R-SRC-03
    out: List[Draft] = []
    ref = bill.invoice_number

    # ── 1. the bill's own arithmetic ─────────────────────────────────────────
    lines_amount = sum((money(li.amount) for li in bill.line_items), ZERO)
    lines_tax = sum((money(li.tax_amount) for li in bill.line_items), ZERO)
    problems = []
    if lines_amount != money(bill.subtotal):
        problems.append(f"charge lines add up to {fmt(lines_amount)} but the bill's subtotal is {fmt(bill.subtotal)}")
    if lines_tax != money(bill.tax_amount):
        problems.append(f"line GST adds up to {fmt(lines_tax)} but the bill's GST is {fmt(bill.tax_amount)}")
    if not money(bill.penalty_amount) and not money(bill.discount_amount):
        want = money(bill.subtotal) + money(bill.tax_amount) + money(bill.round_off)
        if want != money(bill.total_amount):
            problems.append(f"subtotal + GST + round-off is {fmt(want)} but the bill's total is {fmt(bill.total_amount)}")
    for li in bill.line_items:
        if money(li.amount) + money(li.tax_amount) != money(li.total):
            problems.append(f"line '{li.description}': {fmt(li.amount)} + GST {fmt(li.tax_amount)} is not its total {fmt(li.total)}")
            break
    if problems:
        out.append(Draft("R-BILL-01", "bill_posting", CONFIRMED, "MEDIUM", 0.95, "Maintenance bill does not add up",
                         f"Bill {ref}: " + "; ".join(problems) + ". The books were posted from this bill, so they inherit the difference.",
                         "Lines, GST, round-off and total agree", "; ".join(problems),
                         "Open the bill, find which figure is wrong, and correct it (cancel and re-issue if already issued).",
                         {"invoice": ref, "lines_amount": str(lines_amount), "bill_subtotal": str(money(bill.subtotal)),
                          "bill_total": str(money(bill.total_amount))}, subject="arith"))

    # ── 2. the voucher against the bill ─────────────────────────────────────
    exp_total, exp_credits = expected_posting(c.db, bill)
    dues_lines = [e for e in v.entries if c.meta.get(e.account_id, {}).get("system_key") == "members_dues"]
    act_dues = sum((money(e.debit) - money(e.credit) for e in dues_lines), ZERO)
    act: Dict[str, Decimal] = {}
    for e in v.entries:
        key = c.meta.get(e.account_id, {}).get("system_key") or f"ledger:{e.account_id}"
        if key == "members_dues":
            continue
        act[key] = act.get(key, ZERO) + money(e.credit) - money(e.debit)
    act = {k: x for k, x in act.items() if x}

    if act_dues != exp_total:
        out.append(Draft("R-BILL-02", "bill_posting", CONFIRMED, "HIGH", 0.97, "Posting does not match the bill's total",
                         f"Bill {ref} is for {fmt(exp_total)}, but {v.voucher_number} debits Members' Dues {fmt(act_dues)} "
                         f"(difference {fmt(abs(act_dues - exp_total))}). The member's ledger and the bill now disagree.",
                         f"Members' Dues debited {fmt(exp_total)}", f"Members' Dues debited {fmt(act_dues)}",
                         "Re-check the bill and its posting; correct the source and re-post.",
                         {"invoice": ref, "bill_total": str(exp_total), "posted": str(act_dues)}, subject="total"))
    if any(e.flat_id != bill.flat_id for e in dues_lines) or not dues_lines:
        out.append(Draft("R-BILL-03", "bill_posting", CONFIRMED, "HIGH", 0.97, "Posted to a different flat than the bill",
                         f"Bill {ref} belongs to one flat, but the Members' Dues line of {v.voucher_number} names another (or none). "
                         "The wrong member's account carries the charge.",
                         "The bill's own flat on the Members' Dues line", "A different flat",
                         "Correct the flat on the posting through the bill, and re-post.", {"invoice": ref}, subject="flat"))
    if act != exp_credits:
        names = {}
        diffs = []
        for key in sorted(set(act) | set(exp_credits)):
            a, e_ = act.get(key, ZERO), exp_credits.get(key, ZERO)
            if a != e_:
                diffs.append(f"{key.replace('_', ' ')}: bill says {fmt(e_)}, books say {fmt(a)}")
        out.append(Draft("R-BILL-04", "bill_posting", CONFIRMED, "HIGH", 0.95, "Charge heads posted differently from the bill",
                         f"Bill {ref}: " + "; ".join(diffs[:6]) + ". Each charge head should be credited with what the bill charged for it.",
                         "Each ledger credited with the bill's charge for it", "; ".join(diffs[:3]),
                         "Check the charge-head to ledger mapping for the differing head and re-post.",
                         {"invoice": ref, "differences": diffs[:10]}, subject="heads"))
    if bill.bill_status not in POSTED_BILL_STATUSES:
        out.append(Draft("R-BILL-05", "bill_posting", CONFIRMED, "MEDIUM", 0.9, "Live posting for a bill that is not issued",
                         f"Bill {ref} is '{getattr(bill.bill_status, 'value', bill.bill_status)}', yet {v.voucher_number} stands in the books.",
                         "A live posting only for an issued bill", f"Bill status {getattr(bill.bill_status, 'value', bill.bill_status)}",
                         "If the bill was cancelled, cancel its posting; if it should be issued, issue it.", {"invoice": ref}, subject="status"))
    return out
