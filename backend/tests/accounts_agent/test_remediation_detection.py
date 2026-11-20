"""Regression tests for the functional-audit defects in accounting detection (docs/ACCOUNTS_AGENT_FUNCTIONAL_AUDIT.md).

D-01  R-DUP-04 must not fire when both payments carry different references.
D-02  An exact duplicate must not disappear when its vendor tag is removed or changed; the partner voucher of a pair
      is re-checked when one side changes (also D-14).
D-04  A manual member receipt posted to the wrong flat is detected from the member-ledger reconciliation.
"""
from datetime import timedelta
from decimal import Decimal

import pytest

from app.modules.accounts.models.accounts import Voucher, VoucherEntry
from app.modules.accounts.services.accounts_service import Line
from app.modules.accounts.services.postings import AccountPostings
from app.modules.accounts_agent import worker
from app.modules.accounts_agent.models.agent import AgentFinding
from app.modules.billing.models.billing import ChargeType
from tests.accounts_agent.helpers import D, Rig, codes
from tests.accounts_agent.legal_helpers import LRig


@pytest.fixture
def rig(db):
    return Rig(db, "rmd")


def dup_codes(drafts):
    return [c for c in codes(drafts) if c.startswith("R-DUP")]


# ── D-01 ────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_d01_different_references_are_different_bills(rig):
    ven = rig.vendor("CleanPro")
    rig.payment(1, "housekeeping", 12000, vendor=ven, reference="CP-NOV-26")
    second = rig.payment(0, "housekeeping", 12000, vendor=ven, reference="CP-NOV-OK")
    assert dup_codes(rig.analyse(second)) == []          # the audit's S7 false positive


def test_d01_one_reference_missing_is_still_a_possible_duplicate(rig):
    ven = rig.vendor("CleanPro")
    first = rig.payment(1, "housekeeping", 12000, vendor=ven, reference="CP-NOV-26")
    second = rig.payment(0, "housekeeping", 12000, vendor=ven)
    d = next(x for x in rig.analyse(second) if x.rule_code == "R-DUP-04")
    assert f"{second.voucher_number} carries no bill reference" in d.explanation
    assert d.evidence["references"] == [None, "CP-NOV-26"] and d.evidence["other_voucher"] == first.voucher_number


def test_d01_neither_reference_is_described_accurately(rig):
    ven = rig.vendor("CleanPro")
    rig.payment(1, "housekeeping", 12000, vendor=ven)
    d = next(x for x in rig.analyse(rig.payment(0, "housekeeping", 12000, vendor=ven)) if x.rule_code == "R-DUP-04")
    assert "neither payment carries" in d.explanation


# ── D-02 ────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _edit(rig, v, **changes):
    """Edit a voucher through AccountsService exactly as the Accounts screen does (as the admin)."""
    rig.db.refresh(v)
    data = {"voucher_date": v.voucher_date, "narration": v.narration, "reference": v.reference, "vendor_id": v.vendor_id,
            "entries": [{"account_id": e.account_id, "debit": e.debit, "credit": e.credit, "flat_id": e.flat_id,
                         "vendor_id": e.vendor_id, "narration": e.narration} for e in v.entries],
            "reason": "test edit"}
    data.update(changes)
    out = rig.svc.update_manual_voucher(v.id, data, rig.admin["user"])
    rig.db.commit()
    return out


def test_d02_duplicate_without_vendor_tag_is_still_confirmed(rig):
    ven = rig.vendor()
    rig.payment(0, "security_charges", 25000, vendor=ven, reference="SG-NOV-26")
    dup = rig.payment(0, "security_charges", 25000, reference="SG-NOV-26")        # same bill, entered without the tag
    d = next(x for x in rig.analyse(dup) if x.rule_code == "R-DUP-02")
    assert d.finding_class == "confirmed_validation_failure" and "no vendor tag" in d.explanation and d.confidence < 0.97


def test_d02_conflicting_vendor_tags_downgrade_to_suspected_not_hidden(rig):
    a, b = rig.vendor("SecureCo"), rig.vendor("OtherCo")
    rig.payment(0, "security_charges", 25000, vendor=a, reference="SG-NOV-26")
    dup = rig.payment(0, "security_charges", 25000, vendor=b, reference="SG-NOV-26")
    found = {x.rule_code: x for x in rig.analyse(dup)}
    assert "R-DUP-02" not in found and "different vendors" in found["R-DUP-03"].explanation


def test_d02_same_reference_on_another_day_is_suspected(rig):
    ven = rig.vendor()
    rig.payment(5, "security_charges", 25000, vendor=ven, reference="SG-NOV-26")
    d = next(x for x in rig.analyse(rig.payment(0, "security_charges", 25000, vendor=ven, reference="SG-NOV-26"))
             if x.rule_code == "R-DUP-03")
    assert "5 day(s) apart" in d.explanation


def test_d02_removing_the_vendor_tag_does_not_resolve_the_duplicate(rig, db):
    ven = rig.vendor()
    rig.payment(0, "security_charges", 25000, vendor=ven, reference="SG-NOV-26")
    dup = rig.payment(0, "security_charges", 25000, vendor=ven, reference="SG-NOV-26")
    worker.run_once(db, "w", limit=500)
    f = db.query(AgentFinding).filter(AgentFinding.voucher_id == dup.id, AgentFinding.rule_code == "R-DUP-02").one()
    _edit(rig, dup, vendor_id=None)                                                  # the audit's S10 side effect
    worker.run_once(db, "w", limit=500)
    db.refresh(f)
    assert f.status == "NEW"


def test_d02_editing_the_earlier_voucher_rechecks_the_later_ones_finding(rig, db):
    """D-14: the pair finding lives on the later voucher; changing the earlier one must re-check it."""
    ven = rig.vendor()
    first = rig.payment(1, "security_charges", 7000, vendor=ven)
    second = rig.payment(0, "security_charges", 7000, vendor=ven)
    worker.run_once(db, "w", limit=500)
    f = db.query(AgentFinding).filter(AgentFinding.voucher_id == second.id, AgentFinding.rule_code == "R-DUP-04").one()
    _edit(rig, first, reference="SEC-OCT-BILL", entries=[
        {"account_id": rig.chart["security_charges"].id, "debit": D("7000"), "credit": D("0")},
        {"account_id": rig.chart["bank"].id, "debit": D("0"), "credit": D("7000")}])
    worker.run_once(db, "w", limit=500)
    db.refresh(f)
    # One reference is still missing, so the pair stays flagged (explanation reflects the new evidence)…
    assert f.status == "NEW"
    _edit(rig, second, reference="SEC-NOV-BILL")
    worker.run_once(db, "w", limit=500)
    db.refresh(f)
    # …and once both carry different references it is closed by the agent's re-check, with the reason recorded.
    assert f.status == "RESOLVED" and "No longer detected" in f.resolution_note


def test_d02_re_classification_is_recorded_not_silently_cleared(rig, db):
    a, b = rig.vendor("SecureCo"), rig.vendor("OtherCo")
    rig.payment(0, "security_charges", 25000, vendor=a, reference="SG-NOV-26")
    dup = rig.payment(0, "security_charges", 25000, vendor=a, reference="SG-NOV-26")
    worker.run_once(db, "w", limit=500)
    f2 = db.query(AgentFinding).filter(AgentFinding.voucher_id == dup.id, AgentFinding.rule_code == "R-DUP-02").one()
    _edit(rig, dup, vendor_id=b.id)
    worker.run_once(db, "w", limit=500)
    db.refresh(f2)
    f3 = db.query(AgentFinding).filter(AgentFinding.voucher_id == dup.id, AgentFinding.rule_code == "R-DUP-03").one()
    assert f3.status == "NEW" and "Re-classified as R-DUP-03" in f2.resolution_note


# ── D-04 ────────────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def lrig(db):
    return LRig(db, "mar")


def _posted_bill(r, flat, amount, cycle):
    b = r.bill(flat, cycle, [(ChargeType.MAINTENANCE, "Service Charges", amount, amount)])
    AccountPostings(r.db, r.svc).post_bill(b)
    r.db.commit()
    return b


def _manual_receipt(r, flat, amount, days_ago=1):
    lines = [Line(r.chart["bank"], debit=D(str(amount))), Line(r.chart["members_dues"], credit=D(str(amount)), flat_id=flat.id)]
    v = r.svc.build_voucher(r.sid, "receipt", r.today - timedelta(days=days_ago), lines, narration="Maintenance received",
                            user=r.manager["user"])
    v.approved_by, v.approval_status = r.admin["user"].id, "approved"
    r.db.commit()
    return v


def test_d04_receipt_on_the_wrong_flat_is_detected_with_evidence(lrig, db):
    paid_up, debtor = lrig.flat_rows[0], lrig.flat_rows[4]
    cy = lrig.cycle(lrig.today - timedelta(days=40), lrig.today - timedelta(days=10))
    _posted_bill(lrig, debtor, 2020, cy)
    rv = _manual_receipt(lrig, paid_up, 2020)                    # the debtor's money, credited to the wrong flat
    lines_before = [(e.account_id, e.debit, e.credit, e.flat_id) for e in rv.entries]
    lrig.scan()
    rows = lrig.findings("A-MAR-01")
    assert len(rows) == 1
    f = rows[0]
    assert f.flat_id == paid_up.id and f.finding_class == "SUSPECTED_ACCOUNTING_ANOMALY"
    assert f.voucher_id == rv.id and f.transaction_ref == rv.voucher_number
    assert f.evidence["manual_receipts"][0]["voucher"] == rv.voucher_number
    assert f.evidence["ledger_balance"] == "-2020.00" and f.evidence["billing_outstanding"] == "0.00"
    assert any(debtor.flat_number in p for p in f.evidence["possible_payers"])
    assert "genuine advance" in f.explanation                   # never asserted as an error
    db.refresh(rv)
    assert [(e.account_id, e.debit, e.credit, e.flat_id) for e in rv.entries] == lines_before   # books untouched
    assert lrig.findings("A-MAR-01")[0].flat_id != debtor.id                     # the debtor's own ledger reconciles


def test_d04_correctly_posted_bills_and_cancelled_receipts_raise_nothing(lrig, db):
    cy = lrig.cycle(lrig.today - timedelta(days=40), lrig.today - timedelta(days=10))
    _posted_bill(lrig, lrig.flat_rows[1], 2020, cy)              # billed and unpaid: ledger = billing
    rv = _manual_receipt(lrig, lrig.flat_rows[2], 2020)
    lrig.svc.cancel_manual_voucher(rv.id, "entered by mistake", lrig.admin["user"])   # reversed: not live
    out = lrig.scan()
    assert out["failed_checks"] == []
    assert lrig.findings("A-MAR-01") == [] and lrig.findings("A-MAR-02") == []


def test_d04_bills_never_posted_are_not_flagged_flat_by_flat(lrig):
    cy = lrig.cycle(lrig.today - timedelta(days=40), lrig.today - timedelta(days=10))
    for fl in lrig.flat_rows:
        lrig.bill(fl, cy, [(ChargeType.MAINTENANCE, "Service Charges", 2020, 2020)])   # not on the ledger at all
    lrig.scan()
    assert lrig.findings("A-MAR-01") == [] and lrig.findings("A-MAR-02") == []
