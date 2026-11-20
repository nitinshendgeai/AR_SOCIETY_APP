"""Month-over-month flat bill check: a flat's bill against its own recent bills, corrected for society-wide moves."""
from datetime import timedelta
from decimal import Decimal

import pytest

from app.modules.accounts.services.postings import AccountPostings
from app.modules.accounts_agent.services import engine
from app.modules.billing.models.billing import (
    BillingCycle, BillStatus, ChargeType, CycleFrequency, InvoiceLineItem, MaintenanceBill,
)
from tests.accounts_agent.helpers import Rig
from tests.conftest import make_flat, make_wing

HEADS = (("Maintenance", ChargeType.MAINTENANCE, 2500), ("Sinking Fund", ChargeType.SINKING_FUND, 500),
         ("Water", ChargeType.WATER, 300))


class Society:
    """A society billed every 28 days: `months` cycles, `flats` flats, each billed the standard heads.
    `amount(m, f, head)` returns what flat f is charged for head in cycle m (None: the head is left off)."""

    def __init__(self, db, tag, flats=6, months=4, amount=None, period_days=None):
        self.rig = Rig(db, tag)
        self.db, self.months = db, months
        wing = make_wing(db, self.rig.sid, "W")
        self.flats = [make_flat(db, wing.id, str(100 + i)) for i in range(flats)]
        self.bills = {}
        amount = amount or (lambda m, f, head: dict((h[0], h[2]) for h in HEADS)[head])
        for m in range(months):
            start = self.rig.today - timedelta(days=28 * (months - 1 - m))
            days = (period_days or (lambda m_, f_: 28))
            cycle = BillingCycle(society_id=self.rig.sid, name=f"C{m}", cycle_start=start, cycle_end=start + timedelta(days=27),
                                 due_date=start + timedelta(days=10), frequency=CycleFrequency.MONTHLY, is_finalized=True)
            db.add(cycle)
            db.flush()
            for f, flat in enumerate(self.flats):
                lines = [(n, t, amount(m, f, n)) for n, t, _ in HEADS if amount(m, f, n) is not None]
                total = sum(Decimal(a) for _, _, a in lines)
                bill = MaintenanceBill(
                    society_id=self.rig.sid, cycle_id=cycle.id, flat_id=flat.id, invoice_number=f"INV-{m}-{f}",
                    bill_status=BillStatus.ISSUED, bill_date=start, due_date=cycle.due_date,
                    period_start=start, period_end=start + timedelta(days=days(m, f) - 1),
                    subtotal=total, tax_amount=0, total_amount=total, outstanding=total)
                db.add(bill)
                db.flush()
                for n, t, a in lines:
                    db.add(InvoiceLineItem(bill_id=bill.id, charge_type=t, description=n, quantity=1, unit_rate=a, amount=a,
                                           tax_percent=0, tax_amount=0, total=a))
                self.bills[(m, f)] = bill
        db.commit()

    def findings(self, f, month=None):
        """The month-over-month findings on flat f's bill of the latest (or given) month, as the agent raises them."""
        m = self.months - 1 if month is None else month
        bill = self.bills[(m, f)]
        voucher = AccountPostings(self.db).post_bill(bill)
        self.db.commit()
        self.db.refresh(voucher)
        return [d for d in engine.analyse(self.db, voucher) if d.rule_code.startswith("S-BILLMOM")]


@pytest.fixture
def mk(db):
    n = {"i": 0}

    def make(**kw):
        n["i"] += 1
        return Society(db, f"bm{n['i']}", **kw)
    return make


def test_a_steady_bill_raises_nothing(mk):
    s = mk()
    assert all(s.findings(f) == [] for f in range(2))


def test_one_flats_head_doubling_is_flagged_with_the_calculation(mk):
    s = mk(amount=lambda m, f, h: 5000 if (h, m, f) == ("Maintenance", 3, 2) else dict((x[0], x[2]) for x in HEADS)[h])
    [d] = s.findings(2)
    assert d.rule_code == "S-BILLMOM-01" and d.severity == "HIGH" and d.finding_class == "strongly_suspected_anomaly"
    assert d.evidence["previous"] == [2500.0, 2500.0, 2500.0] and d.evidence["actual"] == 5000.0
    assert d.evidence["deviation_pct"] == 100.0 and "tolerance 10%" in d.explanation and "already allowed for" in d.explanation


def test_a_moderate_change_is_a_statistical_deviation_never_a_confirmed_error(mk):
    s = mk(amount=lambda m, f, h: 3250 if (h, m, f) == ("Maintenance", 3, 0) else dict((x[0], x[2]) for x in HEADS)[h])   # +30 %
    [d] = s.findings(0)
    assert d.finding_class == "statistical_deviation" and d.severity == "MEDIUM"


def test_a_society_wide_rate_revision_is_not_reported(mk):
    s = mk(amount=lambda m, f, h: 3000 if (h == "Maintenance" and m == 3) else dict((x[0], x[2]) for x in HEADS)[h])   # +20 % for all
    assert all(s.findings(f) == [] for f in range(3))


def test_a_flat_that_missed_a_revision_is_flagged_against_its_peers(mk):
    def amt(m, f, h):
        base = dict((x[0], x[2]) for x in HEADS)[h]
        return (base * 1.2 if (h == "Maintenance" and m == 3 and f != 4) else base)      # flat 4 was not revised
    s = mk(amount=amt)
    [d] = s.findings(4)
    assert d.rule_code == "S-BILLMOM-01" and d.evidence["peer_ratio"] == pytest.approx(1.2)
    assert d.evidence["peers_this_cycle"] == 5            # the other five flats; the flat under test is not counted


def test_a_head_left_off_one_flat_is_flagged_when_the_others_have_it(mk):
    s = mk(amount=lambda m, f, h: None if (h, m, f) == ("Sinking Fund", 3, 1) else dict((x[0], x[2]) for x in HEADS)[h])
    [d] = s.findings(1)
    assert d.rule_code == "S-BILLMOM-02" and d.severity == "MEDIUM" and d.finding_class == "statistical_deviation"
    assert d.evidence["peers_with_head"] == 5 and d.evidence["cohort"] == 5       # the other five flats


def test_a_head_dropped_for_every_flat_is_not_reported(mk):
    s = mk(amount=lambda m, f, h: None if (h == "Water" and m == 3) else dict((x[0], x[2]) for x in HEADS)[h])
    assert all(s.findings(f) == [] for f in range(2))


def test_a_new_head_on_one_flat_is_only_an_observation(mk):
    def amt(m, f, h):
        return 2500 if (h == "Water" and m == 3 and f == 3) else dict((x[0], x[2]) for x in HEADS)[h]
    # Water exists on every flat, so use a head only this flat has: re-describe it on the last bill.
    s = mk()
    bill = s.bills[(3, 3)]
    li = next(l for l in bill.line_items if l.description == "Water")
    li.description = "Non-Occupancy Charges"
    s.db.commit()
    found = {d.rule_code: d for d in s.findings(3)}
    assert found["S-BILLMOM-03"].severity == "INFORMATIONAL" and found["S-BILLMOM-03"].finding_class == "informational"
    assert "S-BILLMOM-02" in found                        # and the Water head it replaced is missing


def test_bills_for_a_different_length_of_period_are_not_compared(mk):
    s = mk(amount=lambda m, f, h: 7500 if (h == "Maintenance" and m == 3 and f == 2) else dict((x[0], x[2]) for x in HEADS)[h],
           period_days=lambda m, f: 84 if (m == 3 and f == 2) else 28)         # that flat's last bill covers a quarter
    assert s.findings(2) == []


def test_a_head_whose_own_history_is_not_steady_is_not_compared(mk):
    s = mk(amount=lambda m, f, h: ({0: 200, 1: 450, 2: 300, 3: 900}[m] if (h == "Water" and f == 0) else dict((x[0], x[2]) for x in HEADS)[h]))
    assert s.findings(0) == []


def test_with_a_single_earlier_bill_a_change_is_flagged_but_never_as_strongly_suspected(mk):
    s = mk(months=2, amount=lambda m, f, h: 5000 if (h, m, f) == ("Maintenance", 1, 0) else dict((x[0], x[2]) for x in HEADS)[h])
    [d] = s.findings(0)
    assert d.severity == "MEDIUM" and d.finding_class == "statistical_deviation"


def test_no_earlier_bill_in_the_window_means_no_claim(mk):
    s = mk(months=1)
    assert s.findings(0) == []


def test_penalty_and_one_off_lines_are_never_compared(mk):
    s = mk()
    bill = s.bills[(3, 0)]
    s.db.add(InvoiceLineItem(bill_id=bill.id, charge_type=ChargeType.PENALTY, description="Interest on arrears @ 21%", quantity=1,
                             unit_rate=900, amount=900, tax_percent=0, tax_amount=0, total=900))
    s.db.add(InvoiceLineItem(bill_id=bill.id, charge_type=ChargeType.SPECIAL_ASSESSMENT, description="Lift replacement levy", quantity=1,
                             unit_rate=5000, amount=5000, tax_percent=0, tax_amount=0, total=5000))
    s.db.commit()
    assert s.findings(0) == []


def test_findings_are_confined_to_the_flats_own_society(mk):
    a, b = mk(), mk(amount=lambda m, f, h: 9999 if (h == "Maintenance" and m == 3 and f == 0) else dict((x[0], x[2]) for x in HEADS)[h])
    assert a.findings(0) == []                          # society B's oddity does not leak into A's comparison
    assert [d.rule_code for d in b.findings(0)] == ["S-BILLMOM-01"]


def test_the_check_costs_a_fixed_handful_of_queries_per_bill_not_one_per_head_or_flat(mk):
    from sqlalchemy import event
    from app.modules.accounts_agent.services.bill_checks import detect_bill_month_change
    from app.modules.accounts_agent.services.context import Ctx
    from app.modules.accounts_agent.services.engine import get_settings
    from app.modules.accounts_agent.services.learning import Profile, account_meta
    s = mk(flats=12)
    voucher = AccountPostings(s.db).post_bill(s.bills[(3, 0)])
    s.db.commit()
    s.db.refresh(voucher)
    ctx = Ctx(db=s.db, voucher=voucher, meta=account_meta(s.db, s.rig.sid), settings=get_settings(s.db, s.rig.sid),
              profile=Profile(s.db, s.rig.sid))
    seen = []
    bind = s.db.get_bind()
    listener = lambda conn, cur, stmt, *a: seen.append(stmt)          # noqa: E731
    event.listen(bind, "before_cursor_execute", listener)
    try:
        detect_bill_month_change(ctx)
    finally:
        event.remove(bind, "before_cursor_execute", listener)
    assert len(seen) <= 8, f"{len(seen)} queries: " + " | ".join(x[:60] for x in seen)
