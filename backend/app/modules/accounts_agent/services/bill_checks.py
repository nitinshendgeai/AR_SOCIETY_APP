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


# ── Flat-wise consistency with the flat's previous bill ───────────────────────
#
# A flat's bill should charge the same elements, posted to the same ledgers, as its previous bill — this month and every
# month after. Only ELEMENT and LEDGER changes are flagged; amounts are not compared (usage-based elements such as water
# differ every month by design).
#
# Which ledger an element went to last time is read from the books, not re-derived: the previous bill is run through
# today's element → ledger mapping and compared with the voucher actually posted for it. Any difference is a mapping
# change between the two bills (the previous posting's agreement with its own bill was checked by R-BILL-04 at the time).
#
# A change that hits every flat at once (the society re-mapped an element, or dropped a charge) is reported once for the
# billing cycle, not once per flat.

SUSPECTED = "strongly_suspected_anomaly"
CONSISTENCY_RULES = ("R-BILL-06", "R-BILL-07")


def _elements(bill: MaintenanceBill) -> Dict[str, object]:
    """The bill's elements by name. Interest/penalty lines are left out: they come and go with the member's arrears."""
    from app.modules.billing.models.billing import ChargeType
    return {li.description: li for li in bill.line_items if li.charge_type != ChargeType.PENALTY}


def previous_bill(db, bill: MaintenanceBill):
    """The flat's latest issued bill from an earlier billing cycle (or None for its first bill)."""
    from app.modules.billing.models.billing import BillingCycle
    start = bill.cycle.cycle_start if bill.cycle else bill.bill_date
    return (db.query(MaintenanceBill).join(BillingCycle, BillingCycle.id == MaintenanceBill.cycle_id)
            .filter(MaintenanceBill.society_id == bill.society_id, MaintenanceBill.flat_id == bill.flat_id,
                    MaintenanceBill.id != bill.id, MaintenanceBill.bill_status.in_(POSTED_BILL_STATUSES),
                    BillingCycle.cycle_start < start)
            .order_by(BillingCycle.cycle_start.desc(), MaintenanceBill.bill_date.desc()).first())


def _posted_credits(c: Ctx, v: Voucher) -> Dict[str, Decimal]:
    """{ledger key: net credit} of a bill's voucher, Members' Dues left out (as in check_bill_posting)."""
    out: Dict[str, Decimal] = {}
    meta = c.meta
    for e in v.entries:
        key = meta.get(e.account_id, {}).get("system_key") or f"ledger:{e.account_id}"
        if key != "members_dues":
            out[key] = out.get(key, ZERO) + money(e.credit) - money(e.debit)
    return {k: x for k, x in out.items() if x}


def _ledger_name(c: Ctx, key: str) -> str:
    if key.startswith("ledger:"):
        from uuid import UUID
        return c.name(UUID(key[7:]))
    return next((m["name"] for m in c.meta.values() if m.get("system_key") == key), key.replace("_", " ").title())


def ledger_changes(c: Ctx, prev: MaintenanceBill, prev_voucher: Voucher, now_elements: Dict[str, object]) -> List[dict]:
    """[{element, old, new}] for elements of both bills whose ledger is not the one they were posted to last time.
    `old` is None when the books show the element moved but not unambiguously from which ledger."""
    from app.modules.accounts.services.chart_of_accounts import bill_line_ledger_key
    posting = AccountPostings(c.db)
    _, derived = expected_posting(c.db, prev)                 # previous bill under TODAY's mapping
    actual = _posted_credits(c, prev_voucher)                 # what was really posted for it
    if derived == actual:
        return []
    lost = {k: actual.get(k, ZERO) - derived.get(k, ZERO) for k in set(actual) | set(derived)}
    old_ledgers = {k: x for k, x in lost.items() if x > 0}    # credited last time, not under today's mapping
    new_ledgers = {k for k, x in lost.items() if x < 0}       # today's mapping credits them, last time did not
    out = []
    for name, li in _elements(prev).items():
        if name not in now_elements:
            continue                                          # element itself gone: reported by R-BILL-07
        new = bill_line_ledger_key(li, posting._element_code(prev.society_id, li.description))
        if new not in new_ledgers:
            continue
        exact = [k for k, x in old_ledgers.items() if x == money(li.amount)]
        out.append({"element": name, "old": exact[0] if len(exact) == 1 else (next(iter(old_ledgers)) if len(old_ledgers) == 1 else None),
                    "new": new, "amount_last_bill": str(money(li.amount))})
    return out


def _already_reported(c: Ctx, rule: str, group: str) -> bool:
    """Has this change already been reported for another flat in the same cycle?"""
    from app.modules.accounts_agent.models.agent import AgentFinding
    rows = (c.db.query(AgentFinding.evidence).filter(AgentFinding.society_id == c.voucher.society_id,
                                                     AgentFinding.rule_code == rule,
                                                     AgentFinding.voucher_id != c.voucher.id).all())
    return any((ev or {}).get("group") == group for (ev,) in rows)


def check_bill_consistency(c: Ctx) -> List[Draft]:
    v: Voucher = c.voucher
    if (v.source_type != "maintenance_bill" or not v.source_id or v.is_cancelled or v.reversal_of_id
            or c.event_type not in ("voucher.created", "voucher.edited")):
        return []
    bill = c.db.query(MaintenanceBill).filter(MaintenanceBill.id == v.source_id,
                                              MaintenanceBill.society_id == v.society_id).first()
    if bill is None or bill.bill_status not in POSTED_BILL_STATUSES:
        return []
    prev = previous_bill(c.db, bill)
    if prev is None:
        return []                                             # the flat's first bill: nothing to compare with
    now_el, prev_el = _elements(bill), _elements(prev)
    flat = bill.flat
    from app.modules.billing.services.bill_pdf import flat_label
    where = flat_label(flat) if flat else "this flat"
    base_ev = {"invoice": bill.invoice_number, "previous_invoice": prev.invoice_number,
               "previous_bill_id": str(prev.id), "cycle_id": str(bill.cycle_id), "flat_id": str(bill.flat_id)}
    out: List[Draft] = []

    # ── elements added / dropped ─────────────────────────────────────────────
    missing, added = sorted(set(prev_el) - set(now_el)), sorted(set(now_el) - set(prev_el))
    if missing or added:
        group = f"elements:{bill.cycle_id}:{'|'.join(missing)}:{'|'.join(added)}"
        if not _already_reported(c, "R-BILL-07", group):
            parts = ([f"not charged this time: {', '.join(missing)}"] if missing else []) + \
                    ([f"new this time: {', '.join(added)}"] if added else [])
            out.append(Draft(
                "R-BILL-07", "bill_consistency", SUSPECTED, "MEDIUM", 0.8, "Bill elements differ from the previous bill",
                f"{where}'s bill {bill.invoice_number} does not charge the same elements as its previous bill "
                f"{prev.invoice_number}: {'; '.join(parts)}. A flat is normally billed the same elements every cycle; check that "
                "the change is intended (a charge started or ended, the flat's occupancy changed). If several flats have exactly "
                "this change in the same cycle, it is reported once.",
                f"Same elements as {prev.invoice_number}: {', '.join(sorted(prev_el)) or 'none'}",
                f"Elements on {bill.invoice_number}: {', '.join(sorted(now_el)) or 'none'}",
                "Confirm the charge set; if an element is missing or wrong, correct the flat's charges and re-issue the bill.",
                {**base_ev, "missing_elements": missing, "new_elements": added, "group": group}, subject="elements"))

    # ── same element, different ledger ───────────────────────────────────────
    prev_v = (c.db.query(Voucher).filter(Voucher.society_id == v.society_id, Voucher.source_type == "maintenance_bill",
                                         Voucher.source_id == prev.id, Voucher.is_cancelled == False)  # noqa: E712
              .order_by(Voucher.created_at.desc()).first())
    if prev_v is not None:
        changes = ledger_changes(c, prev, prev_v, now_el)
        if changes:
            sig = "|".join(f"{x['element']}:{x['old']}>{x['new']}" for x in sorted(changes, key=lambda x: x["element"]))
            group = f"ledgers:{bill.cycle_id}:{sig}"
            if not _already_reported(c, "R-BILL-06", group):
                said = [f"'{x['element']}' went to '{_ledger_name(c, x['old']) if x['old'] else 'another ledger'}' on "
                        f"{prev.invoice_number}, now to '{_ledger_name(c, x['new'])}'" for x in changes]
                out.append(Draft(
                    "R-BILL-06", "bill_consistency", SUSPECTED, "MEDIUM", 0.85, "Element posted to a different ledger than last bill",
                    f"{where}'s bill {bill.invoice_number}: " + "; ".join(said) + ". The element-to-ledger mapping changed "
                    "between the two bills, so the same charge now lands in a different account (for funds such as Sinking "
                    "Fund this changes the fund balance). The change applies to every flat billed with this element; it is "
                    "reported once per billing cycle.",
                    "Each element posted to the same ledger as on the previous bill", "; ".join(said),
                    "Check the element's ledger in billing settings. If the change was a mistake, restore the mapping and "
                    "re-post the affected bills; if intended, mark this finding resolved with the reason.",
                    {**base_ev, "changes": [{**x, "old_ledger": _ledger_name(c, x["old"]) if x["old"] else None,
                                             "new_ledger": _ledger_name(c, x["new"])} for x in changes],
                     "group": group}, subject="ledgers"))
    return out
