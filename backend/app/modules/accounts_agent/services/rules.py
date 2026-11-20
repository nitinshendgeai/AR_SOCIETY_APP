"""Deterministic accounting validators.

Each validator returns a list of Drafts. A rule here states a fact that follows from the accounting rules the app already
enforces (see AccountsService._balanced / _manual_lines), so a failure is a CONFIRMED validation failure — normally
impossible through the services, which is exactly why it is worth detecting (direct database edits, imports, bugs).
They deliberately mirror, never extend, the existing business rules.
"""
from collections import Counter
from typing import List

from app.models.flat import Flat
from app.models.wing import Wing
from app.modules.accounts.models.accounts import FinancialYearClosing, Voucher
from app.modules.accounts.services.accounts_service import fiscal_year
from app.modules.accounts_agent.services.context import Ctx, Draft, ZERO, fmt, money

CONFIRMED = "confirmed_validation_failure"
SUSPECTED = "strongly_suspected_anomaly"

# Auto-posted vouchers whose source document can be re-checked, and where it lives.
SOURCE_MODELS = {
    "maintenance_bill": ("app.modules.billing.models.billing", "MaintenanceBill"),
    "payment_receipt": ("app.modules.billing.models.billing", "PaymentReceipt"),
    "online_payment": ("app.modules.billing.models.billing", "OnlinePaymentSubmission"),
    "vendor_invoice": ("app.modules.vendor.models.vendor", "VendorInvoice"),
    "vendor_payment": ("app.modules.vendor.models.vendor", "VendorPaymentTransaction"),
}


def check_balance(c: Ctx) -> List[Draft]:
    out: List[Draft] = []
    v = c.voucher
    live = [e for e in c.entries if money(e.debit) or money(e.credit)]
    if len(live) < 2:
        out.append(Draft("R-BAL-03", "debit_credit", CONFIRMED, "CRITICAL", 1.0, "Voucher has missing entries",
                         f"{v.voucher_number} has {len(live)} non-zero line(s). Every voucher needs at least one debit and "
                         "one credit line.", "At least two lines (one debit, one credit)", f"{len(live)} line(s)",
                         "Review the voucher and re-enter the missing lines or cancel it.", {"lines": len(live)}))
    for e in c.entries:
        dr, cr = money(e.debit), money(e.credit)
        if dr < 0 or cr < 0 or (dr and cr) or (not dr and not cr):
            out.append(Draft("R-BAL-04", "debit_credit", CONFIRMED, "HIGH", 1.0, "Invalid debit/credit values on a line",
                             f"Line {e.line_no} of {v.voucher_number} on {c.name(e.account_id)} has debit {fmt(dr)} and "
                             f"credit {fmt(cr)}. A line is either a debit or a credit of a positive amount.",
                             "Exactly one of debit/credit, positive", f"Dr {fmt(dr)} / Cr {fmt(cr)}",
                             "Correct the line.", {"line_no": e.line_no, "debit": str(dr), "credit": str(cr)},
                             subject=f"line{e.line_no}"))
    if c.total_dr != c.total_cr:
        out.append(Draft("R-BAL-01", "debit_credit", CONFIRMED, "CRITICAL", 1.0, "Debits do not equal credits",
                         f"{v.voucher_number}: total debits {fmt(c.total_dr)} differ from total credits {fmt(c.total_cr)} "
                         f"by {fmt(abs(c.total_dr - c.total_cr))}. Every voucher must balance.",
                         "Total debits = total credits", f"Dr {fmt(c.total_dr)} vs Cr {fmt(c.total_cr)}",
                         "Correct the lines so the voucher balances.",
                         {"total_debit": str(c.total_dr), "total_credit": str(c.total_cr)}))
    elif c.entries and money(v.amount) != c.total_dr:
        out.append(Draft("R-BAL-02", "debit_credit", CONFIRMED, "HIGH", 1.0, "Voucher total does not match its lines",
                         f"{v.voucher_number} states an amount of {fmt(v.amount)} but its lines total {fmt(c.total_dr)}.",
                         "Voucher amount = sum of debit lines", f"{fmt(v.amount)} vs {fmt(c.total_dr)}",
                         "Correct the voucher amount or lines.",
                         {"voucher_amount": str(money(v.amount)), "lines_total": str(c.total_dr)}))
    return out


def check_accounts(c: Ctx) -> List[Draft]:
    out: List[Draft] = []
    v = c.voucher
    seen = set()
    for e in c.entries:
        if e.account_id in seen:
            continue
        seen.add(e.account_id)
        m = c.meta.get(e.account_id)
        if m is None:
            out.append(Draft("R-ACC-01", "ledger_validation", CONFIRMED, "CRITICAL", 1.0,
                             "Line posted to a ledger outside this society",
                             f"{v.voucher_number} has a line on a ledger that does not belong to this society's chart of accounts.",
                             "Every line on one of this society's ledgers", "Foreign or missing ledger",
                             "Escalate immediately: this is a society-isolation breach.",
                             {"account_id": str(e.account_id)}, subject=str(e.account_id)))
        elif not m["active"] and c.event_type in ("voucher.created", "voucher.edited"):
            out.append(Draft("R-ACC-02", "ledger_validation", CONFIRMED, "MEDIUM", 0.95, "Inactive ledger used",
                             f"{v.voucher_number} posts to '{m['name']}', which is inactive. The books refuse new entries on inactive ledgers.",
                             "Only active ledgers", f"Inactive ledger '{m['name']}'",
                             "Re-activate the ledger if intended, or move the line to the correct ledger.",
                             {"ledger": m["name"]}, subject=str(e.account_id)))
    return out


def check_type_rules(c: Ctx) -> List[Draft]:
    """Cash/bank rules of the four voucher types a person enters (AccountsService._manual_lines). Applied only to
    manual vouchers; automatic postings follow their own posting rules."""
    v = c.voucher
    if not c.is_manual or v.reversal_of_id or v.voucher_type not in ("receipt", "payment", "contra", "journal"):
        return []
    dr = [e for e in c.entries if money(e.debit)]
    cr = [e for e in c.entries if money(e.credit)]
    cb = lambda e: c.meta.get(e.account_id, {}).get("cash_bank", False)   # noqa: E731
    problem = None
    if v.voucher_type == "receipt" and not (all(cb(e) for e in dr) and not any(cb(e) for e in cr)):
        problem = "A receipt must debit cash or bank and credit the ledger the money came from."
    elif v.voucher_type == "payment" and not (all(cb(e) for e in cr) and not any(cb(e) for e in dr)):
        problem = "A payment must credit cash or bank and debit the ledger the money went to."
    elif v.voucher_type == "contra" and not all(cb(e) for e in c.entries):
        problem = "A contra moves money between cash and bank ledgers only."
    elif v.voucher_type == "journal" and any(cb(e) for e in c.entries):
        problem = "A journal never touches cash or bank."
    if not problem:
        return []
    return [Draft("R-TYPE-01", "ledger_validation", CONFIRMED, "HIGH", 0.98, "Ledgers inconsistent with the voucher type",
                  f"{v.voucher_number} is a {v.voucher_type} voucher. {problem}", "Ledgers as the voucher type requires",
                  "Cash/bank on the wrong side or in the wrong voucher type",
                  "Re-enter the voucher with the correct type or ledgers.", {"voucher_type": v.voucher_type})]


def check_subledgers(c: Ctx) -> List[Draft]:
    out: List[Draft] = []
    v = c.voucher
    flat_ids = {e.flat_id for e in c.entries if e.flat_id}
    good_flats = set()
    if flat_ids:
        good_flats = {r[0] for r in c.db.query(Flat.id).join(Wing, Wing.id == Flat.wing_id)
                      .filter(Flat.id.in_(flat_ids), Wing.society_id == v.society_id)}
    vendor_ids = {x for x in [v.vendor_id, *[e.vendor_id for e in c.entries]] if x}
    vendors = {}
    if vendor_ids:
        from app.modules.vendor.models.vendor import Vendor
        vendors = {r.id: r for r in c.db.query(Vendor).filter(Vendor.id.in_(vendor_ids))}
    for e in c.entries:
        m = c.meta.get(e.account_id, {})
        key = m.get("system_key")
        if key == "members_dues" and not e.flat_id:
            out.append(Draft("R-SUB-01", "sub_ledger", CONFIRMED, "HIGH", 0.98, "Members' Dues line without a flat",
                             f"Line {e.line_no} of {v.voucher_number} is on Members' Dues but names no flat, so the member "
                             "sub-ledger cannot be updated.", "Every Members' Dues line carries a flat", "No flat",
                             "Tag the line with the correct flat.", {"line_no": e.line_no}, subject=f"line{e.line_no}"))
        if e.flat_id and key != "members_dues":
            out.append(Draft("R-SUB-02", "sub_ledger", CONFIRMED, "MEDIUM", 0.95, "Flat tagged on the wrong ledger",
                             f"Line {e.line_no} of {v.voucher_number} carries a flat but is on '{m.get('name')}', not Members' Dues.",
                             "Flats are tagged only on Members' Dues", f"Flat on '{m.get('name')}'",
                             "Remove the flat or move the line to Members' Dues.", {"line_no": e.line_no},
                             subject=f"line{e.line_no}"))
        if e.flat_id and e.flat_id not in good_flats:
            out.append(Draft("R-SUB-03", "sub_ledger", CONFIRMED, "CRITICAL", 1.0, "Flat belongs to another society",
                             f"Line {e.line_no} of {v.voucher_number} references a flat outside this society.",
                             "Flat in this society", "Foreign flat", "Escalate: society-isolation breach.",
                             {"line_no": e.line_no}, subject=f"flat{e.line_no}"))
        if e.vendor_id and key != "sundry_creditors":
            out.append(Draft("R-SUB-04", "vendor_mapping", CONFIRMED, "MEDIUM", 0.95, "Vendor tagged on the wrong ledger",
                             f"Line {e.line_no} of {v.voucher_number} names a vendor but is on '{m.get('name')}', not Sundry Creditors.",
                             "Vendors are tagged only on Sundry Creditors", f"Vendor on '{m.get('name')}'",
                             "Remove the vendor tag or move the line to Sundry Creditors.", {"line_no": e.line_no},
                             subject=f"vendor{e.line_no}"))
    for vid in vendor_ids:
        vendor = vendors.get(vid)
        if vendor is None or vendor.society_id != v.society_id:
            out.append(Draft("R-VND-01", "vendor_mapping", CONFIRMED, "CRITICAL", 1.0, "Vendor not found in this society",
                             f"{v.voucher_number} references a vendor that is not in this society's Vendor Master.",
                             "Vendor from this society's master", "Unknown or foreign vendor",
                             "Escalate: society-isolation breach or orphaned reference.", {"vendor_id": str(vid)},
                             subject=str(vid)))
        elif not vendor.is_active and c.event_type in ("voucher.created", "voucher.edited"):
            out.append(Draft("R-VND-02", "vendor_mapping", CONFIRMED, "MEDIUM", 0.9, "Payment mapped to an inactive vendor",
                             f"{v.voucher_number} references vendor '{vendor.company_name}', who is inactive.",
                             "Active vendor", "Inactive vendor", "Confirm the vendor should still be paid or re-map it.",
                             {"vendor": vendor.company_name}, subject=str(vid)))
    if v.vendor_id and v.voucher_type != "payment" and v.source_type is None:
        out.append(Draft("R-VND-03", "vendor_mapping", CONFIRMED, "HIGH", 0.95, "Vendor on a non-payment voucher",
                         f"{v.voucher_number} is a {v.voucher_type} voucher but names a vendor; only payments are made to vendors.",
                         "Vendor only on payment vouchers", f"Vendor on a {v.voucher_type}",
                         "Remove the vendor or re-enter the voucher as a payment.", {}))
    return out


def check_integrity(c: Ctx) -> List[Draft]:
    out: List[Draft] = []
    v = c.voucher
    if v.fiscal_year != fiscal_year(v.voucher_date):
        out.append(Draft("R-FY-01", "integrity", CONFIRMED, "HIGH", 1.0, "Financial year does not match the voucher date",
                         f"{v.voucher_number} is dated {v.voucher_date:%d %b %Y} (FY {fiscal_year(v.voucher_date)}) but is filed under FY {v.fiscal_year}.",
                         f"FY {fiscal_year(v.voucher_date)}", f"FY {v.fiscal_year}", "Correct the voucher date or year.",
                         {"voucher_date": v.voucher_date.isoformat(), "fiscal_year": v.fiscal_year}))
    if v.voucher_type != "closing" and c.event_type == "voucher.created":
        closing = (c.db.query(FinancialYearClosing).filter(
            FinancialYearClosing.society_id == v.society_id, FinancialYearClosing.fiscal_year == v.fiscal_year,
            FinancialYearClosing.reopened_at.is_(None), FinancialYearClosing.is_active == True).first())  # noqa: E712
        if closing and v.created_at and closing.closed_at and v.created_at > closing.closed_at:
            out.append(Draft("R-FY-02", "integrity", CONFIRMED, "HIGH", 0.95, "Posted into a closed financial year",
                             f"{v.voucher_number} was created after FY {v.fiscal_year} was closed. Closed years are locked; new activity belongs in the open year.",
                             "No new vouchers in a closed year", f"Created after the closing of FY {v.fiscal_year}",
                             "Review how it was posted; reverse it in the open year if it should not stand.",
                             {"fiscal_year": v.fiscal_year}))
    # NOTE: no "approved without approver" rule. Existing pathways (recurring-expense recording, bank reconciliation)
    # legitimately create approved payment vouchers with no approver; flagging them would contradict current rules.
    if v.source_type and not v.source_id:
        out.append(Draft("R-SRC-01", "integrity", CONFIRMED, "MEDIUM", 0.95, "Automatic posting without a source document",
                         f"{v.voucher_number} says it was posted from '{v.source_type}' but names no source document.",
                         "Source type and id together", "Source id missing", "Re-run the posting sync for the source.", {}))
    elif v.source_type in SOURCE_MODELS and v.source_id:
        import importlib
        mod, cls = SOURCE_MODELS[v.source_type]
        model = getattr(importlib.import_module(mod), cls)
        src = c.db.query(model).filter(model.id == v.source_id).first()
        if src is None:
            out.append(Draft("R-SRC-02", "integrity", CONFIRMED, "MEDIUM", 0.9, "Source document not found",
                             f"{v.voucher_number} was posted from {v.source_type} {v.source_id}, which no longer exists.",
                             "An existing source document", "Missing source", "Check whether the source was removed in error.",
                             {"source_type": v.source_type}))
        elif getattr(src, "society_id", v.society_id) != v.society_id:
            out.append(Draft("R-SRC-03", "integrity", CONFIRMED, "CRITICAL", 1.0, "Source document belongs to another society",
                             f"{v.voucher_number} was posted from a document of a different society.",
                             "Source in the same society", "Cross-society source", "Escalate: society-isolation breach.",
                             {"source_type": v.source_type}))
    return out


def check_reversal(c: Ctx) -> List[Draft]:
    v = c.voucher
    if not v.reversal_of_id:
        return []
    out: List[Draft] = []
    orig = c.db.query(Voucher).filter(Voucher.id == v.reversal_of_id).first()
    if orig is None:
        return [Draft("R-REV-01", "reversal", CONFIRMED, "HIGH", 0.95, "Reversal of a voucher that does not exist",
                      f"{v.voucher_number} claims to reverse a voucher that cannot be found.", "An existing original",
                      "Missing original", "Investigate the reversal.", {})]
    if orig.society_id != v.society_id:
        return [Draft("R-REV-02", "reversal", CONFIRMED, "CRITICAL", 1.0, "Reversal of another society's voucher",
                      f"{v.voucher_number} reverses a voucher of a different society.", "Same society",
                      "Cross-society reversal", "Escalate: society-isolation breach.", {})]
    mirror = Counter((str(e.account_id), str(money(e.credit)), str(money(e.debit)), str(e.flat_id or ""), str(e.vendor_id or ""))
                     for e in orig.entries)
    actual = Counter((str(e.account_id), str(money(e.debit)), str(money(e.credit)), str(e.flat_id or ""), str(e.vendor_id or ""))
                     for e in v.entries)
    if mirror != actual:
        out.append(Draft("R-REV-03", "reversal", CONFIRMED, "HIGH", 0.95, "Reversal does not mirror the original",
                         f"{v.voucher_number} reverses {orig.voucher_number}, but its lines are not the exact opposite of the original's.",
                         "Each original debit becomes a credit and vice versa", "Lines differ from the mirror image",
                         "Review the reversal; it may leave part of the original in force.",
                         {"original": orig.voucher_number}))
    others = (c.db.query(Voucher.id).filter(Voucher.society_id == v.society_id, Voucher.reversal_of_id == orig.id,
                                            Voucher.id != v.id, Voucher.is_cancelled == False).count())  # noqa: E712
    if others:
        out.append(Draft("R-REV-04", "reversal", CONFIRMED, "HIGH", 0.95, "Voucher reversed more than once",
                         f"{orig.voucher_number} has been reversed by {others + 1} vouchers; reversing twice undoes the books twice.",
                         "One reversal per original", f"{others + 1} reversals", "Cancel the extra reversal.",
                         {"original": orig.voucher_number}))
    return out


def check_journal(c: Ctx) -> List[Draft]:
    v = c.voucher
    if v.voucher_type == "journal" and c.is_manual and not v.reversal_of_id and not (v.narration or "").strip():
        return [Draft("R-JRN-01", "unusual_journal", "informational", "INFORMATIONAL", 0.9, "Journal adjustment without a narration",
                      f"{v.voucher_number} is a manual journal with no narration; adjustments should say why they were made.",
                      "A narration explaining the adjustment", "Empty narration", "Add a narration.", {})]
    return []


def _ref(v: Voucher) -> str:
    return (v.reference or "").strip().lower()


def vendor_of(v: Voucher):
    """The party a voucher is tagged to: the voucher's own vendor tag, else a vendor tag on one of its lines."""
    return v.vendor_id or next((e.vendor_id for e in v.entries if e.vendor_id), None)


def content_key(v: Voucher) -> list:
    """The accounting substance of a voucher, WITHOUT vendor tags: ledgers, amounts and flats. Vendor tags are
    descriptive and can be removed or changed by an edit, so they must never be what makes two vouchers different."""
    return sorted((str(e.account_id), str(money(e.debit)), str(money(e.credit)), str(e.flat_id or "")) for e in v.entries)


def check_duplicates(c: Ctx) -> List[Draft]:
    """Duplicate detection. The evidence compared is: voucher type, amount, date, ledger lines (ignoring vendor tags),
    reference and source document. The vendor tag only raises or lowers confidence; it is never the sole identifier.

    - Two different source documents, or two different non-empty references, are two different transactions.
    - R-DUP-01  same source document posted twice                                 → CONFIRMED
    - R-DUP-02  same date, same lines, same non-empty reference, vendor tags agree  → CONFIRMED
                (a tag missing on one side still agrees; the explanation says so)
    - R-DUP-04  payment to the same vendor, same amount, within 3 days, and AT LEAST ONE of the two has no
                reference                                                           → SUSPECTED
    - R-DUP-03  same lines within the window otherwise (incl. same reference on different dates, conflicting or
                missing vendor tags)                                                → SUSPECTED
    Every pair finding is keyed on the pair (not on the rule's inputs), so an edit to a vendor tag re-classifies the
    pair but never silently clears a genuine duplicate."""
    from datetime import timedelta
    v = c.voucher
    if v.voucher_type == "closing" or v.reversal_of_id or v.is_cancelled or v.approval_status == "rejected":
        return []
    out: List[Draft] = []
    window = max(1, int(c.settings.duplicate_window_days))
    mine, my_ref, my_vendor = content_key(v), _ref(v), vendor_of(v)
    cands = (c.db.query(Voucher).filter(
        Voucher.society_id == v.society_id, Voucher.id != v.id, Voucher.is_cancelled == False,  # noqa: E712
        Voucher.approval_status != "rejected", Voucher.reversal_of_id.is_(None), Voucher.reversed_at.is_(None),
        Voucher.voucher_type == v.voucher_type, Voucher.amount == v.amount,
        Voucher.voucher_date >= v.voucher_date - timedelta(days=window),
        Voucher.voucher_date <= v.voucher_date + timedelta(days=window))
        .order_by(Voucher.created_at).limit(50).all())
    for o in cands:
        if _order(o) > _order(v):
            continue                                  # only the LATER voucher of a pair is flagged (and may be cancelled)
        pair = ":".join(sorted([str(v.id), str(o.id)]))
        days = abs((o.voucher_date - v.voucher_date).days)
        o_ref, o_vendor = _ref(o), vendor_of(o)
        ev = {"other_voucher": o.voucher_number, "other_voucher_id": str(o.id), "amount": str(money(v.amount)),
              "dates": [v.voucher_date.isoformat(), o.voucher_date.isoformat()],
              "references": [v.reference or None, o.reference or None],
              "vendor_ids": [str(my_vendor) if my_vendor else None, str(o_vendor) if o_vendor else None]}
        if v.source_id and o.source_id and v.source_type == o.source_type and v.source_id == o.source_id:
            out.append(Draft("R-DUP-01", "duplicate", CONFIRMED, "HIGH", 0.99, "Same source posted twice",
                             f"{v.voucher_number} and {o.voucher_number} both post the same {v.source_type} document; it is in the books twice.",
                             "One live voucher per source document", "Two live vouchers", "Cancel the later voucher.",
                             ev, subject=pair, voucher_id=v.id))
            continue
        if v.source_id and o.source_id and v.source_id != o.source_id:
            continue                                  # two different source documents are different transactions
        if my_ref and o_ref and my_ref != o_ref:
            continue                                  # two different references: evidence of two different bills
        same_ref = bool(my_ref) and my_ref == o_ref
        same_lines = content_key(o) == mine
        vendors_conflict = bool(my_vendor and o_vendor and my_vendor != o_vendor)
        vendors_agree = not vendors_conflict
        tag_note = "" if (my_vendor and o_vendor) or not (my_vendor or o_vendor) else \
            " One of the two has no vendor tag; the match rests on the date, amount, ledgers and reference."
        if same_lines and same_ref and v.voucher_date == o.voucher_date and vendors_agree:
            conf = 0.97 if (my_vendor and o_vendor) or not (my_vendor or o_vendor) else 0.92
            out.append(Draft("R-DUP-02", "duplicate", CONFIRMED, "HIGH", conf, "Confirmed duplicate voucher",
                             f"{v.voucher_number} duplicates {o.voucher_number}: same date, amount, ledgers and reference "
                             f"('{v.reference}').{tag_note}",
                             "A reference is used once", "Identical voucher with the same reference",
                             "Cancel the later voucher.", {**ev, "reference": v.reference}, subject=pair))
        elif v.voucher_type == "payment" and my_vendor and my_vendor == o_vendor and days <= 3 \
                and not (my_ref and o_ref):
            missing = "neither payment carries" if not (my_ref or o_ref) else \
                f"{o.voucher_number if not o_ref else v.voucher_number} carries no"
            out.append(Draft("R-DUP-04", "duplicate", SUSPECTED, "MEDIUM", 0.7, "Possible duplicate payment",
                             f"{v.voucher_number} pays the same vendor the same amount ({fmt(v.amount)}) as {o.voucher_number} "
                             f"within {days} day(s), and {missing} bill reference, so nothing shows they settle different bills.",
                             "Each payment settles a different bill", "Same vendor, same amount, days apart",
                             "Check the vendor's bills and record the bill reference; cancel the payment if it was entered "
                             "twice.", ev, subject=pair))
        elif same_lines:
            if same_ref:
                why = (f"same amount, ledgers and reference ('{v.reference}')" +
                       (f", {days} day(s) apart" if days else "") +
                       (", but tagged to different vendors" if vendors_conflict else ""))
            elif my_ref or o_ref:
                why = f"same amount and ledgers within {days} day(s); only one of them carries a reference"
            else:
                why = f"same amount and ledgers within {days} day(s); neither carries a reference"
            out.append(Draft("R-DUP-03", "duplicate", SUSPECTED, "MEDIUM", 0.75 if same_ref else 0.65,
                             "Potential duplicate voucher",
                             f"{v.voucher_number} and {o.voucher_number} have the {why}. It may be a genuine repeat — "
                             "the evidence is the similarity, not proof.",
                             "Repeated entries are intentional", "Near-identical vouchers",
                             "Compare the two and cancel one if it is a duplicate.", ev, subject=pair))
    return out


def _order(v: Voucher) -> tuple:
    """Which of two vouchers came first: creation time, then number and id as tie-breakers."""
    from datetime import datetime
    return (v.created_at or datetime.min, v.voucher_number or "", str(v.id))


def line_signature_key(e) -> tuple:
    return (str(e.account_id), str(money(e.debit)), str(money(e.credit)), str(e.flat_id or ""), str(e.vendor_id or ""))


from app.modules.accounts_agent.services.bill_checks import check_bill_consistency, check_bill_posting  # noqa: E402

DETERMINISTIC = (check_balance, check_accounts, check_type_rules, check_subledgers, check_integrity, check_reversal,
                 check_journal, check_duplicates, check_bill_posting, check_bill_consistency)
