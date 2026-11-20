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
from typing import Dict, List, Optional, Tuple

from app.modules.accounts.models.accounts import Voucher
from app.modules.accounts.services.chart_of_accounts import bill_line_ledger_key
from app.modules.accounts.services.postings import POSTED_BILL_STATUSES, AccountPostings
from app.modules.accounts_agent.services.context import Ctx, Draft, ZERO, fmt, money
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.modules.accounts_agent.services import stats as st
from app.modules.accounts_agent.services.learning import months_before
from app.modules.billing.models.billing import ChargeType, InvoiceLineItem, MaintenanceBill

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


# ── Month-over-month: this flat's bill against its own recent bills ─────────────────────────────────────────────────
#
# A flat's recurring charge heads normally repeat month after month. One that changes while the society's other flats did
# not (a wrong area, a wrong rate, a head left out, a head added) is worth a second look. Everything that legitimately
# moves is kept out of the comparison:
#   * one-off and variable lines: penalties / interest, special assessments, "other" additional charges, and any line that
#     shares out actual expenses (allocation) — never compared;
#   * bills for a different length of period (a quarterly cycle, a flat that joined part-way): not comparable, skipped;
#   * a society-wide revision: if the same head moved by the same proportion for the other flats of the cycle, the change
#     is expected and not reported;
#   * a head whose own recent history is not steady: it is variable for this flat, so no "normal" exists to compare with.
# Only the last three months of the flat's own bills are used (the agent's learning window). It never compares one flat
# with another's amount — flats pay different amounts (area, parking) — only each flat with itself, corrected by the peers'
# proportional movement. Every finding is a statistical deviation (or an observation), never a confirmed error.

COMPARED_TYPES = (ChargeType.MAINTENANCE, ChargeType.WATER, ChargeType.PARKING, ChargeType.SINKING_FUND,
                  ChargeType.REPAIR_FUND, ChargeType.AMENITIES)
MAX_PRIOR_BILLS = 3            # = the three-month window of a monthly society
PERIOD_TOLERANCE_DAYS = 4      # a 28-day and a 31-day month are the same length of billing
PEER_MIN = 5                   # fewer comparable flats than this: no claim about what "the society" did
NEW_HEAD_PEER_SHARE = 0.5      # a head on at least half the flats is a society-wide head, not a flat's oddity


def _period_days(b: MaintenanceBill) -> Optional[int]:
    return (b.period_end - b.period_start).days + 1 if b.period_start and b.period_end else None


def _comparable(a: MaintenanceBill, b: MaintenanceBill) -> bool:
    da, db = _period_days(a), _period_days(b)
    return da is None or db is None or abs(da - db) <= PERIOD_TOLERANCE_DAYS


def _heads(bill: MaintenanceBill) -> Dict[str, Decimal]:
    out: Dict[str, Decimal] = {}
    for li in bill.line_items:
        if li.charge_type not in COMPARED_TYPES or li.allocation_id or (li.description or "").lower().startswith("interest"):
            continue
        out[li.description] = out.get(li.description, ZERO) + money(li.amount)
    return out


def _same_cohort(q, bill: MaintenanceBill):
    """The OTHER flats billed in the same cycle for the same period, in a state that counts. The flat under test is left
    out, so its own (possibly wrong) amount can never soften the comparison against what its peers did."""
    q = q.filter(MaintenanceBill.society_id == bill.society_id, MaintenanceBill.cycle_id == bill.cycle_id,
                 MaintenanceBill.flat_id != bill.flat_id, MaintenanceBill.bill_status.in_(POSTED_BILL_STATUSES))
    q = q.filter(MaintenanceBill.period_start == bill.period_start if bill.period_start else MaintenanceBill.period_start.is_(None))
    return q.filter(MaintenanceBill.period_end == bill.period_end if bill.period_end else MaintenanceBill.period_end.is_(None))


def _cohort_size(db, bill: MaintenanceBill) -> int:
    return _same_cohort(db.query(func.count(MaintenanceBill.id)), bill).scalar() or 0


def _cohort_heads(db, bill: MaintenanceBill) -> Dict[str, Tuple[int, float]]:
    """{head: (other flats whose bill carries it, their average amount)} for the bill's cohort — ONE grouped aggregate for
    every head at once (no rows come back to Python, and no per-head queries)."""
    q = _same_cohort(db.query(InvoiceLineItem.description, func.count(InvoiceLineItem.id), func.avg(InvoiceLineItem.amount))
                     .join(MaintenanceBill, MaintenanceBill.id == InvoiceLineItem.bill_id), bill)
    return {name: (int(n or 0), float(avg or 0)) for name, n, avg in q.group_by(InvoiceLineItem.description).all()}


def detect_bill_month_change(c: Ctx) -> List[Draft]:
    v: Voucher = c.voucher
    if (v.source_type != "maintenance_bill" or not v.source_id or v.is_cancelled or v.reversal_of_id
            or c.event_type != "voucher.created"):
        return []
    db = c.db
    bill = (db.query(MaintenanceBill).options(selectinload(MaintenanceBill.line_items))
            .filter(MaintenanceBill.id == v.source_id, MaintenanceBill.society_id == v.society_id).first())
    if bill is None or bill.bill_status not in POSTED_BILL_STATUSES:
        return []
    priors = (db.query(MaintenanceBill).options(selectinload(MaintenanceBill.line_items))
              .filter(MaintenanceBill.society_id == bill.society_id, MaintenanceBill.flat_id == bill.flat_id,
                      MaintenanceBill.id != bill.id, MaintenanceBill.cycle_id != bill.cycle_id,
                      MaintenanceBill.bill_status.in_(POSTED_BILL_STATUSES), MaintenanceBill.bill_date < bill.bill_date,
                      MaintenanceBill.bill_date >= months_before(bill.bill_date, 3))
              .order_by(MaintenanceBill.bill_date.desc()).limit(MAX_PRIOR_BILLS * 2).all())
    priors = [p for p in priors if _comparable(p, bill)][:MAX_PRIOR_BILLS]
    if not priors:
        return []                                    # no history in the window: nothing is invented
    from app.modules.billing.services.bill_pdf import flat_label
    flat = flat_label(bill.flat) if bill.flat else "this flat"
    tol = float(c.settings.recurring_tolerance_pct) / 100.0
    cur, history = _heads(bill), [_heads(p) for p in priors]
    note = (" Learning confidence is limited, so treat this with caution." if c.profile.label in ("none", "limited") else "")
    out: List[Draft] = []
    size: Optional[int] = None
    now_cohort = prev_cohort = None                  # fetched at most once per bill, and only if a head needs them

    for name in sorted(set(cur) | set().union(*history)):
        amounts = [float(h[name]) for h in history if name in h]
        now = float(cur[name]) if name in cur else None
        steady = len(amounts) == len(priors) and (
            len(amounts) < 2 or (st.med(amounts) > 0 and (max(amounts) - min(amounts)) / st.med(amounts) <= tol))

        if now is not None and amounts and steady and st.med(amounts) > 0:
            expected = st.med(amounts)
            if now_cohort is None:
                now_cohort, prev_cohort = _cohort_heads(db, bill), _cohort_heads(db, priors[0])
            n_now, avg_now = now_cohort.get(name, (0, 0.0))
            n_prev, avg_prev = prev_cohort.get(name, (0, 0.0))
            peer_ratio = (avg_now / avg_prev) if (n_now >= PEER_MIN and n_prev >= PEER_MIN and avg_prev > 0) else None
            adjusted = expected * peer_ratio if peer_ratio else expected
            dev = st.relative_deviation(now, adjusted)
            if dev is None or dev < tol:
                continue
            strong = dev >= 1.0 and len(priors) >= 2
            sev = "HIGH" if strong else ("MEDIUM" if dev >= 0.25 else "LOW")
            peers = (f" The society's other flats moved {abs(peer_ratio - 1) * 100:.1f}% on this head over the same months "
                     f"({n_now} flats this cycle, {n_prev} last), which is already allowed for." if peer_ratio else
                     f" There are too few other flats on this head (fewer than {PEER_MIN}) to tell whether the society revised it.")
            out.append(Draft(
                "S-BILLMOM-01", "bill_month_change", "strongly_suspected_anomaly" if strong else "statistical_deviation", sev,
                round(min(0.85, 0.4 + 0.1 * len(priors) + (0.15 if peer_ratio else 0)), 2),
                f"{flat}: '{name}' changed on the bill",
                f"Bill {bill.invoice_number}: '{name}' is {fmt(now)}. This flat's last {len(priors)} bill(s) in the three-month window "
                f"carried {', '.join(fmt(a) for a in amounts)} for it, so about {fmt(adjusted)} was expected "
                f"(|{fmt(now)} − {fmt(adjusted)}| ÷ {fmt(adjusted)} = {dev * 100:.1f}%; tolerance {tol * 100:.0f}%).{peers}{note}",
                f"About {fmt(adjusted)}", fmt(now),
                "Check the flat's area, rate and charge setup; correct the bill (cancel and re-issue) if it is wrong, or ignore it if the change is intended.",
                {"invoice": bill.invoice_number, "head": name, "previous": amounts, "expected": round(adjusted, 2), "actual": now,
                 "deviation_pct": round(dev * 100, 2), "tolerance_pct": tol * 100, "peer_ratio": peer_ratio,
                 "peers_this_cycle": n_now, "peers_last_cycle": n_prev, "months_compared": len(priors)}, subject=name[:80]))

        elif now is None and amounts and steady:
            size = _cohort_size(db, bill) if size is None else size
            now_cohort = _cohort_heads(db, bill) if now_cohort is None else now_cohort
            n_with = now_cohort.get(name, (0, 0.0))[0]
            if size >= PEER_MIN and n_with / size < NEW_HEAD_PEER_SHARE:
                continue                                 # most flats dropped it too: the society changed its charges
            out.append(Draft(
                "S-BILLMOM-02", "bill_month_change", "statistical_deviation", "MEDIUM" if size >= PEER_MIN else "LOW",
                round(min(0.8, 0.4 + 0.1 * len(priors)), 2), f"{flat}: '{name}' is missing from the bill",
                f"Bill {bill.invoice_number} has no '{name}' charge. This flat's last {len(priors)} bill(s) carried it "
                f"({', '.join(fmt(a) for a in amounts)}), and " +
                (f"{n_with} of {size} flats billed this cycle still have it." if size >= PEER_MIN else
                 "there are too few flats this cycle to compare with.") + f" A missing head can mean under-billing.{note}",
                f"'{name}' charged as before", "Not on this bill", "Check why the head was left off (a charge setup or occupancy change?) and correct the bill if it was an error.",
                {"invoice": bill.invoice_number, "head": name, "previous": amounts, "peers_with_head": n_with, "cohort": size},
                subject=name[:80]))

        elif now is not None and not amounts and len(priors) >= 2:
            size = _cohort_size(db, bill) if size is None else size
            now_cohort = _cohort_heads(db, bill) if now_cohort is None else now_cohort
            n_with = now_cohort.get(name, (0, 0.0))[0]
            if size >= PEER_MIN and n_with / size >= NEW_HEAD_PEER_SHARE:
                continue                                 # most flats have it now: a new society-wide head
            out.append(Draft(
                "S-BILLMOM-03", "bill_month_change", "informational", "INFORMATIONAL", 0.6, f"{flat}: new charge '{name}'",
                f"Bill {bill.invoice_number} carries '{name}' ({fmt(now)}), which this flat's previous {len(priors)} bills did not, "
                f"and most other flats do not have it either. That is normal for a new allotment or occupancy change; it is noted so it is seen once.",
                "The same heads as the previous bills", f"New head '{name}'", "Confirm the charge is intended for this flat.",
                {"invoice": bill.invoice_number, "head": name, "amount": now, "peers_with_head": n_with, "cohort": size}, subject=name[:80]))
    return out
