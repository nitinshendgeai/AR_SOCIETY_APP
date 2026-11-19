"""Accounting detection: what the agent flags — and, as important, what it must NOT flag."""
from datetime import timedelta
from decimal import Decimal

import pytest

from app.modules.accounts.services.accounts_service import Line
from app.modules.accounts.models.accounts import VoucherEntry
from app.modules.accounts_agent.services import learning
from tests.accounts_agent.helpers import D, Rig, codes


@pytest.fixture
def rig(db):
    return Rig(db, "det")


# ── Learning window ───────────────────────────────────────────────────────────

def test_learning_window_is_exactly_three_months_and_ignores_older_vouchers(rig, db):
    rig.payment(10, "office_expenses", 500)
    rig.payment(120, "office_expenses", 99999)          # four months old: outside the baseline, but untouched
    run = rig.learn()
    assert (run.window_end - run.window_start).days in range(89, 93)
    assert run.voucher_count == 1
    assert run.confidence_label == "limited"
    assert "Limited learning confidence" in run.summary["note"]
    from app.modules.accounts.models.accounts import Voucher
    assert db.query(Voucher).filter(Voucher.society_id == rig.sid).count() == 2      # older record still there


def test_no_history_invents_nothing(rig):
    run = rig.learn()
    assert run.voucher_count == 0 and run.pattern_count == 0 and run.confidence_label == "none"
    v = rig.payment(0, "office_expenses", 90000)
    assert codes(rig.analyse(v)) == []                  # no baseline → no statistical claim


# ── Balance / structure ───────────────────────────────────────────────────────

def test_balanced_voucher_is_clean(rig):
    rig.seed_history()
    assert codes(rig.analyse(rig.payment(0, "office_expenses", 1030, narration="Pens"))) == []


def test_unbalanced_voucher_is_a_confirmed_critical_failure(rig, db):
    v = rig.payment(3, "office_expenses", 1000)
    entry = db.query(VoucherEntry).filter(VoucherEntry.voucher_id == v.id, VoucherEntry.debit > 0).one()
    entry.debit = D("1200")                              # a direct database edit that the services would refuse
    db.commit()
    drafts = rig.analyse(v)
    d = next(x for x in drafts if x.rule_code == "R-BAL-01")
    assert d.severity == "CRITICAL" and d.finding_class == "confirmed_validation_failure"
    assert "1,200.00" in d.explanation and "1,000.00" in d.explanation


def test_missing_entries_and_invalid_lines(rig, db):
    v = rig.payment(3, "office_expenses", 1000)
    db.query(VoucherEntry).filter(VoucherEntry.voucher_id == v.id, VoucherEntry.credit > 0).delete()
    db.commit()
    assert "R-BAL-03" in codes(rig.analyse(v))
    e = db.query(VoucherEntry).filter(VoucherEntry.voucher_id == v.id).first()
    e.credit = D("5")
    db.commit()
    assert "R-BAL-04" in codes(rig.analyse(v))


# ── Duplicates ────────────────────────────────────────────────────────────────

def test_duplicate_voucher_with_same_reference_is_confirmed(rig):
    ven = rig.vendor()
    rig.payment(2, "security_charges", 25000, vendor=ven, reference="INV-77")
    dup = rig.payment(2, "security_charges", 25000, vendor=ven, reference="INV-77")
    d = next(x for x in rig.analyse(dup) if x.rule_code == "R-DUP-02")
    assert d.finding_class == "confirmed_validation_failure" and d.category == "duplicate"


def test_duplicate_payment_without_reference_is_only_a_potential_duplicate(rig):
    ven = rig.vendor()
    rig.payment(3, "security_charges", 7000, vendor=ven)
    second = rig.payment(2, "security_charges", 7000, vendor=ven)
    found = {x.rule_code: x for x in rig.analyse(second)}
    assert "R-DUP-02" not in found
    assert found["R-DUP-04"].finding_class == "strongly_suspected_anomaly" and found["R-DUP-04"].severity == "MEDIUM"


def test_same_amount_a_month_apart_is_not_a_duplicate(rig):
    ven = rig.vendor()
    rig.payment(35, "security_charges", 25000, vendor=ven)
    assert not [c for c in codes(rig.analyse(rig.payment(3, "security_charges", 25000, vendor=ven))) if c.startswith("R-DUP")]


def test_same_source_posted_twice_is_confirmed(rig, db):
    import uuid
    src = uuid.uuid4()
    lines = lambda: [Line(rig.chart["office_expenses"], debit=D("100")), Line(rig.chart["bank"], credit=D("100"))]  # noqa: E731
    a = rig.svc.build_voucher(rig.sid, "payment", rig.today, lines(), source_type="vendor_payment", source_id=src)
    b = rig.svc.build_voucher(rig.sid, "payment", rig.today, lines(), source_type="vendor_payment", source_id=src)
    db.commit()
    assert "R-DUP-01" in codes(rig.analyse(b))


# ── Statistical: unusual expense, recurring, mapping ──────────────────────────

def test_unusual_expense_is_flagged_with_the_calculation(rig):
    rig.seed_history()
    v = rig.payment(0, "office_expenses", 25000)         # ~24x the usual stationery bill
    d = next(x for x in rig.analyse(v) if x.rule_code == "S-AMT-01")
    assert d.finding_class == "strongly_suspected_anomaly" and d.severity == "HIGH"
    assert d.evidence["median"] == pytest.approx(1015, abs=30) and d.evidence["prior_count"] == 8
    assert "modified z-score" in d.explanation and "median" in d.explanation


def test_moderate_outlier_is_a_statistical_deviation_never_a_confirmed_error(rig):
    rig.seed_history()
    d = next(x for x in rig.analyse(rig.payment(0, "office_expenses", 1500)) if x.rule_code == "S-AMT-01")
    assert d.finding_class == "statistical_deviation" and d.severity in ("LOW", "MEDIUM")


def test_ordinary_amount_and_unfamiliar_description_are_not_flagged(rig):
    rig.seed_history()
    v = rig.payment(0, "office_expenses", 1045, narration="Purchase of premium laminated whiteboard markers")
    assert codes(rig.analyse(v)) == []


def test_recurring_expense_deviation_explains_the_calculation(rig):
    rig.seed_history()
    v = rig.payment(0, "security_charges", 31000, vendor=rig.sec, reference="SEC-NEW")
    d = next(x for x in rig.analyse(v) if x.rule_code == "S-REC-01")
    assert d.evidence["expected"] == 25000 and d.evidence["actual"] == 31000
    assert d.evidence["deviation_pct"] == pytest.approx(24.0)
    assert "24.0%" in d.explanation and "tolerance is 10%" in d.explanation


def test_recurring_expense_at_the_usual_amount_is_clean(rig):
    rig.seed_history()
    assert codes(rig.analyse(rig.payment(0, "security_charges", 25000, vendor=rig.sec, reference="SEC-OK"))) == []


def test_incorrect_ledger_mapping_for_a_vendor(rig):
    rig.seed_history()
    v = rig.payment(0, "security_charges", 6050, vendor=rig.clean, reference="CLN-X")   # CleanCo is always Housekeeping
    d = next(x for x in rig.analyse(v) if x.rule_code == "S-MAP-01")
    assert d.evidence["usual_ledger"] == "Housekeeping & Cleaning" and d.evidence["usual_share"] == 1.0


def test_invalid_vendor_mapping_cross_society_vendor(rig, db):
    other = Rig(db, "det-other")
    foreign = other.vendor("ForeignCo")
    v = rig.payment(2, "office_expenses", 100)
    v.vendor_id = foreign.id
    db.commit()
    d = next(x for x in rig.analyse(v) if x.rule_code == "R-VND-01")
    assert d.severity == "CRITICAL"


# ── Type rules, reversals, integrity ──────────────────────────────────────────

def test_payment_that_does_not_credit_cash_or_bank_is_flagged(rig, db):
    v = rig.svc.build_voucher(rig.sid, "payment", rig.today, [
        Line(rig.chart["office_expenses"], debit=D("100")), Line(rig.chart["audit_fees"], credit=D("100"))],
        user=rig.manager["user"])
    db.commit()
    assert "R-TYPE-01" in codes(rig.analyse(v))


def test_valid_reversal_is_not_flagged_but_a_broken_one_is(rig, db):
    orig = rig.payment(5, "office_expenses", 800)
    rev = rig.svc.reverse(orig, "test", rig.manager["user"])
    db.commit()
    assert not [c for c in codes(rig.analyse(rev)) if c.startswith(("R-REV", "R-DUP", "R-TYPE", "S-"))]
    entry = rev.entries[0]
    entry.debit, entry.credit = entry.credit, entry.debit          # no longer the mirror image
    entry.debit = D("1")
    db.commit()
    assert "R-REV-03" in codes(rig.analyse(rev))


def test_approved_payment_without_approver_is_not_flagged(rig):
    """Recurring-expense recording and bank reconciliation legitimately post approved payments with no approver: the agent
    must not contradict that existing rule (documented in ACCOUNTS_AGENT_IMPLEMENTATION_REPORT.md)."""
    v = rig.payment(2, "office_expenses", 300, approved=False)
    v.approval_status, v.approved_by = "approved", None
    rig.db.commit()
    assert codes(rig.analyse(v)) == []


def test_manual_journal_without_narration_is_informational(rig):
    v = rig.journal(2, "office_expenses", "audit_fees", 500, narration="")
    d = next(x for x in rig.analyse(v) if x.rule_code == "R-JRN-01")
    assert d.severity == "INFORMATIONAL"


def test_unusually_frequent_repeat_is_flagged_as_a_low_statistical_deviation(rig):
    ven = rig.vendor("WaterCo")
    for days in (80, 66, 52, 38, 24, 10):                  # every two weeks
        rig.payment(days, "garden", 5000, vendor=ven, reference=f"W-{days}")
    rig.learn()
    d = next(x for x in rig.analyse(rig.payment(8, "garden", 5000, vendor=ven, reference="W-EARLY")) if x.rule_code == "S-FREQ-01")
    assert d.finding_class == "statistical_deviation" and d.severity == "LOW" and d.evidence["normal_gap_days"] == 14
