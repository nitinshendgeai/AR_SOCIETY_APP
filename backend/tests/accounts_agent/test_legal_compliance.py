"""Engine B and the residential-accounting checks against realistic Maharashtra housing-society fixtures."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.modules.accounts.models.accounts import Voucher
from app.modules.accounts_agent import worker
from app.modules.accounts_agent.legal import calendar as cal
from app.modules.accounts_agent.legal import recovery
from app.modules.accounts_agent.legal.models import BudgetLine, ComplianceItem
from app.modules.accounts.services.accounts_service import fiscal_year
from app.modules.vendor.models.vendor import VendorCategory, VendorInvoice, WorkOrder
from tests.accounts_agent.legal_helpers import D, BillStatus, ChargeBasis, ChargeType, LRig

CONFIRMED = ("CONFIRMED_STATUTORY_VALIDATION_FAILURE",)


@pytest.fixture
def rig(db):
    return LRig(db, "cmp")


def one(rig, code):
    rows = rig.findings(code)
    assert len(rows) == 1, f"{code}: {[(f.rule_code, f.title) for f in rig.findings()]}"
    return rows[0]


# ── Charges (106C-12) ────────────────────────────────────────────────────────────────────────────────────────────

def test_interest_rate_above_ceiling_is_potential_not_confirmed(rig):
    rig.settings(interest_rate_pct=18)
    rig.scan()
    f = one(rig, "L-CHG-INT-01")
    assert f.finding_class == "POTENTIAL_NON_COMPLIANCE" and f.engine == "legal"
    assert f.legal_source["rule_code"] == "MH-CHG-INTEREST-CAP" and f.legal_source["verified"] is False
    assert f.legal_source["uncertainty"]
    assert not [x for x in rig.findings() if x.finding_class in CONFIRMED]   # nothing confirmed without verified law


def test_non_occupancy_setting_and_bill_calculation(rig):
    rig.settings(non_occupancy_pct=15)
    rig.config("Service Charges", ChargeType.MAINTENANCE, ChargeBasis.FIXED, 2000, "service_charges", service=True)
    cy = rig.cycle(rig.today - timedelta(days=40), rig.today - timedelta(days=10))
    rig.bill(rig.flat_rows[0], cy, [(ChargeType.MAINTENANCE, "Service Charges", 2000, 2000),
                                    (ChargeType.OTHER, "Non-Occupancy Charges", 400, 400)])
    rig.scan()
    assert one(rig, "L-CHG-NOC-01").finding_class == "POTENTIAL_NON_COMPLIANCE"
    f = one(rig, "L-CHG-NOC-02")
    assert f.flat_id == rig.flat_rows[0].id and "2000.00 × 10% = 200.00" in f.evidence["calculation"]


def test_property_tax_and_water_apportionment(rig):
    rig.config("Property Tax", ChargeType.OTHER, ChargeBasis.FIXED, 500, "property_tax")
    rig.config("Water Charges", ChargeType.WATER, ChargeBasis.BUDGET_EQUAL, 60000, "water_charges")
    rig.config("Service Charges", ChargeType.MAINTENANCE, ChargeBasis.FIXED, 2000, "service_charges", service=True)
    rig.scan()
    rows = rig.findings("L-CHG-APP-01")
    assert {r.evidence["element"] for r in rows} == {"property_tax"}   # service charges equal: fine
    assert all(r.finding_class == "POTENTIAL_NON_COMPLIANCE" and r.legal_source["blocked_by_reviews"] for r in rows)
    # Water shared equally is not a breach of the rule's area bases: both texts share it by inlets, so it is only a
    # prompt to check the fittings, judged by the model bye-laws.
    water = one(rig, "L-CHG-APP-02")
    assert water.evidence["element"] == "water_charges" and water.finding_class == "ADVISORY_OBSERVATION"


def test_model_bye_law_sharing_for_water_insurance_lease_and_education_fund(rig):
    rig.config("Water Charges", ChargeType.WATER, ChargeBasis.BUDGET_EQUAL, 60000, "water_charges")
    rig.config("Building Insurance", ChargeType.OTHER, ChargeBasis.FIXED, 1000, "insurance")
    rig.config("Lease Rent / NA Tax", ChargeType.OTHER, ChargeBasis.BUDGET_EQUAL, 50000, "lease_rent_na_tax")
    rig.config("Education Fund", ChargeType.OTHER, ChargeBasis.PER_SQFT, 1, "education_fund")
    rig.scan()
    rows = {r.evidence["element"]: r for r in rig.findings("L-CHG-APP-02")}
    assert set(rows) == {"water_charges", "insurance", "lease_rent_na_tax", "education_fund"}
    assert all(r.finding_class == "ADVISORY_OBSERVATION" and r.severity == "LOW"
               and r.legal_rule_code == "MH-MODEL-CHG-APPORTIONMENT" for r in rows.values())
    assert rows["insurance"].evidence["bye_law"] == "66(a)(xi)" and rows["insurance"].evidence["pdf_page"] == "28"
    assert "built-up area" in rows["insurance"].explanation and "PDF page 28" in rows["insurance"].explanation
    assert rows["education_fund"].evidence["bye_law"] == "13(d), 66(a)(xiv)"
    assert "inlets" in rows["water_charges"].explanation
    assert rig.findings("L-CHG-APP-01") == []


def test_sharing_that_matches_the_model_bye_laws_is_not_flagged(rig):
    rig.config("Water Charges", ChargeType.WATER, ChargeBasis.BUDGET_AREA, 60000, "water_charges")
    rig.config("Building Insurance", ChargeType.OTHER, ChargeBasis.BUDGET_AREA, 200000, "insurance")
    rig.config("Lease Rent / NA Tax", ChargeType.OTHER, ChargeBasis.PER_SQFT, 2, "lease_rent_na_tax")
    rig.config("Education Fund", ChargeType.OTHER, ChargeBasis.BUDGET_EQUAL, 40000, "education_fund")
    rig.scan()
    assert rig.findings("L-CHG-APP-01") == [] and rig.findings("L-CHG-APP-02") == []


def _fund_bills(rig, lines, area=370, cost="2500"):
    """Five flats of `area` sq ft, one 31-day bill each carrying `lines` = [(charge type, head name, amount)]."""
    if cost:
        rig.settings(construction_cost_per_sqft=cost)
    for fl in rig.flat_rows:
        fl.area_sqft = area
    rig.db.commit()
    cy = rig.cycle(rig.today - timedelta(days=40), rig.today - timedelta(days=10))
    for fl in rig.flat_rows:
        rig.bill(fl, cy, [(ctype, head, amount, amount) for ctype, head, amount in lines])


def test_sinking_fund_billed_as_percent_of_service_charges_is_below_the_bye_law_minimum(rig):
    rig.config("Sinking Fund", ChargeType.SINKING_FUND, ChargeBasis.SERVICE_CHARGE_PCT, "0.25", "sinking_fund")
    _fund_bills(rig, [(ChargeType.SINKING_FUND, "Sinking Fund", 10)])     # 0.25% of ~₹4,000 of service charges
    rig.scan()
    f = one(rig, "L-FND-SNK-04")
    assert f.finding_class == "POTENTIAL_NON_COMPLIANCE" and f.evidence["bye_law"] == "13(c)"
    # 5 flats x 370 sq ft x ₹2,500 x 0.25% x 31/365
    assert abs(Decimal(f.evidence["required"]) - Decimal("982.02")) < Decimal("0.05")
    assert f.evidence["collected"] == "50.00" and f.evidence["bills_counted"] == 5


def test_fund_billed_at_the_minimum_on_construction_cost_is_not_flagged(rig):
    rig.config("Sinking Fund", ChargeType.SINKING_FUND, ChargeBasis.CONSTRUCTION_COST_PCT, "0.25", "sinking_fund")
    rig.config("Repair Fund", ChargeType.REPAIR_FUND, ChargeBasis.CONSTRUCTION_COST_PCT, "0.75", "repair_fund")
    # minimums for a 31-day bill on 370 sq ft at ₹2,500/sq ft: sinking ~196.40, repair ~589.21
    _fund_bills(rig, [(ChargeType.SINKING_FUND, "Sinking Fund", 200), (ChargeType.REPAIR_FUND, "Repair Fund", 600)])
    rig.scan()
    assert rig.findings("L-FND-SNK-04") == [] and rig.findings("L-FND-REP-02") == []
    assert rig.findings("L-FND-SNK-01") == [] and rig.findings("L-FND-REP-01") == []


def test_repair_fund_below_the_minimum_is_advisory_only(rig):
    rig.config("Repair Fund", ChargeType.REPAIR_FUND, ChargeBasis.SERVICE_CHARGE_PCT, "0.75", "repair_fund")
    _fund_bills(rig, [(ChargeType.REPAIR_FUND, "Repair Fund", 30)])
    rig.scan()
    f = one(rig, "L-FND-REP-02")
    assert f.finding_class == "ADVISORY_OBSERVATION" and f.legal_rule_code == "MH-FUND-REPAIR-RATE"   # model reference
    assert f.evidence["bye_law"] == "13(a)"


def test_rate_below_the_minimum_is_reported_once_not_twice(rig):
    rig.config("Sinking Fund", ChargeType.SINKING_FUND, ChargeBasis.CONSTRUCTION_COST_PCT, "0.10", "sinking_fund")
    _fund_bills(rig, [(ChargeType.SINKING_FUND, "Sinking Fund", 80)])
    rig.scan()
    assert one(rig, "L-FND-SNK-01") and rig.findings("L-FND-SNK-04") == []


def test_fund_minimum_cannot_be_tested_without_the_construction_cost(rig):
    rig.config("Sinking Fund", ChargeType.SINKING_FUND, ChargeBasis.SERVICE_CHARGE_PCT, "0.25", "sinking_fund")
    _fund_bills(rig, [(ChargeType.SINKING_FUND, "Sinking Fund", 10)], cost=None)
    rig.scan()
    f = one(rig, "L-FND-MIN-01")
    assert f.finding_class == "ADVISORY_OBSERVATION" and rig.findings("L-FND-SNK-04") == []


def test_wrong_maintenance_allocation_on_bills(rig):
    rig.config("Service Charges", ChargeType.MAINTENANCE, ChargeBasis.FIXED, 2000, "service_charges", service=True)
    cy = rig.cycle(rig.today - timedelta(days=40), rig.today - timedelta(days=10))
    for i, fl in enumerate(rig.flat_rows):
        rate = 2500 if i == 2 else 2000
        rig.bill(fl, cy, [(ChargeType.MAINTENANCE, "Service Charges", rate, rate)])
    rig.scan()
    f = one(rig, "A-BIL-ALC-01")
    assert f.finding_class == "SUSPECTED_ACCOUNTING_ANOMALY" and f.flat_id == rig.flat_rows[2].id


def test_incorrect_overdue_interest_and_superseded_ceiling(rig):
    fl = rig.flat_rows[0]
    old = rig.cycle(rig.today - timedelta(days=100), rig.today - timedelta(days=70), name="Old")
    rig.bill(fl, old, [(ChargeType.MAINTENANCE, "Service Charges", 10000, 10000)])
    cy = rig.cycle(rig.today - timedelta(days=40), rig.today - timedelta(days=10), name="New")
    # 10,000 arrears overdue ~30 days: 12% p.a. gives ~₹99; ₹500 is far beyond it.
    rig.bill(fl, cy, [(ChargeType.MAINTENANCE, "Service Charges", 2000, 2000),
                      (ChargeType.PENALTY, "Interest on arrears", 500, 500)], previous_dues=10000)
    rig.bill(rig.flat_rows[1], cy, [(ChargeType.PENALTY, "Interest on arrears", 50, 50)], previous_dues=0)
    rig.scan()
    f = one(rig, "L-CHG-INT-02")
    assert f.finding_class == "POTENTIAL_NON_COMPLIANCE" and f.evidence["cap_pct"] == 12
    assert one(rig, "A-BIL-INT-02").flat_id == rig.flat_rows[1].id


def test_sinking_and_repair_fund_contribution_rates(rig):
    rig.config("Sinking Fund", ChargeType.SINKING_FUND, ChargeBasis.CONSTRUCTION_COST_PCT, "0.10", "sinking_fund")
    rig.config("Repair Fund", ChargeType.REPAIR_FUND, ChargeBasis.CONSTRUCTION_COST_PCT, "0.50", "repair_fund")
    rig.scan()
    assert one(rig, "L-FND-SNK-01").finding_class == "POTENTIAL_NON_COMPLIANCE"
    assert one(rig, "L-FND-REP-01").finding_class == "ADVISORY_OBSERVATION"   # model bye-law reference only


# ── Member ledger ────────────────────────────────────────────────────────────────────────────────────────────────

def test_incorrect_member_ledger_and_duplicate_bill(rig):
    cy = rig.cycle(rig.today - timedelta(days=40), rig.today - timedelta(days=10))
    rig.bill(rig.flat_rows[0], cy, [(ChargeType.MAINTENANCE, "Service Charges", 2000, 2000)], paid=500, outstanding=2000)
    rig.bill(rig.flat_rows[1], cy, [(ChargeType.MAINTENANCE, "Service Charges", 2000, 2000)])
    rig.bill(rig.flat_rows[1], cy, [(ChargeType.MAINTENANCE, "Service Charges", 2000, 2000)])
    rig.scan()
    assert one(rig, "A-BIL-OUT-01").finding_class == "CONFIRMED_ACCOUNTING_ERROR"
    assert one(rig, "A-BIL-DUP-01").flat_id == rig.flat_rows[1].id


# ── Vendors and approvals (106C-13, resolutions) ─────────────────────────────────────────────────────────────────

def test_vendor_paid_beyond_resolution_then_additional_approval(rig, db):
    ven = rig.vendor("PaintCo")
    rig.resolution(resolution_number="MC-7", vendor_id=ven.id, approved_amount=D("200000"), category="contract",
                   meeting_date=rig.today - timedelta(days=90), purpose="Painting contract")
    for d, amt in ((60, 100000), (40, 100000), (20, 60000)):
        rig.payment(d, "repairs_general", amt, vendor=ven, reference=f"PB-{d}")
    rig.scan()
    f = one(rig, "L-EXP-RES-01")
    assert f.evidence["difference"] == "60000.00" and f.finding_class == "POTENTIAL_NON_COMPLIANCE"
    assert f.vendor_id == ven.id
    rig.resolution(resolution_number="MC-9", vendor_id=ven.id, approved_amount=D("60000"), category="contract",
                   meeting_date=rig.today - timedelta(days=25), purpose="Additional painting work")
    rig.scan()
    assert rig.findings("L-EXP-RES-01") == []
    assert rig.findings("L-EXP-RES-01", open_only=False)[0].status == "RESOLVED"


def test_unapproved_repair_expense_and_general_body_approval(rig):
    v = rig.payment(15, "repairs_building", 150000, reference="TERRACE-1", narration="Terrace waterproofing")
    rig.scan()
    f = one(rig, "L-EXP-REP-01")
    # The only figure loaded is the model bye-law 157 slab: it is labelled as such and never treated as binding law
    # (functional audit D-03), so the finding is an advisory observation, not a potential violation.
    assert f.voucher_id == v.id and f.finding_class == "ADVISORY_OBSERVATION"
    assert f.evidence["threshold_basis"] == "MODEL_REFERENCE" and f.evidence["threshold"] == "25000.00"
    assert "MODEL figure" in f.explanation and "committee's limit is" not in f.explanation
    assert f.legal_source["rule_code"] == "MH-EXP-BYELAW157"
    rig.resolution(resolution_number="SGM-2", meeting_type="SGM", account_id=rig.chart["repairs_building"].id,
                   approved_amount=D("150000"), meeting_date=rig.today - timedelta(days=60), purpose="Waterproofing")
    rig.scan()
    assert rig.findings("L-EXP-REP-01") == []


def test_work_order_above_committee_limit_without_general_body(rig, db):
    ven = rig.vendor("CivilCo")
    wo = WorkOrder(society_id=rig.sid, vendor_id=ven.id, wo_number="WO-1", title="Structural repairs",
                   category=list(VendorCategory)[0], sanctioned_amount=D("300000"))
    db.add(wo)
    db.commit()
    rig.scan()
    f = one(rig, "L-EXP-WO-02")
    assert f.finding_class == "ADVISORY_OBSERVATION" and f.evidence["threshold"] == "25000.00"
    assert f.evidence["threshold_basis"] == "MODEL_REFERENCE" and "MODEL figure" in f.explanation


def test_duplicate_vendor_invoice_and_missing_invoice(rig, db):
    ven = rig.vendor("LiftCo")
    for _ in range(2):
        db.add(VendorInvoice(society_id=rig.sid, vendor_id=ven.id, invoice_number="LC/101", invoice_date=rig.today,
                             amount=D("8000"), total_amount=D("8000")))
    db.commit()
    v = rig.payment(5, "lift_maintenance", 9100, vendor=ven, reference=None)
    rig.scan()
    assert one(rig, "A-VEN-DUP-01").vendor_id == ven.id
    f = one(rig, "A-VEN-DOC-01")
    assert f.voucher_id == v.id and f.finding_class == "MISSING_DOCUMENTATION"


# ── Funds (106C-11), borrowing, transfer ─────────────────────────────────────────────────────────────────────────

def test_unauthorised_fund_usage_and_overdrawn_fund(rig):
    v = rig.payment(10, "sinking_fund", 50000, reference="SF-USE", narration="Lift repair from sinking fund")
    rig.scan()
    f = one(rig, "L-FND-USE-01")
    assert f.voucher_id == v.id and f.evidence["required_authority"] == "GENERAL_BODY"
    assert one(rig, "A-FND-BAL-01").finding_class == "SUSPECTED_ACCOUNTING_ANOMALY"


def test_fund_usage_with_committee_resolution_is_not_enough_for_sinking_fund(rig):
    rig.payment(10, "sinking_fund", 50000, reference="SF-USE")
    rig.resolution(resolution_number="MC-3", account_id=rig.chart["sinking_fund"].id, approved_amount=D("50000"),
                   category="fund_utilisation", purpose="Use sinking fund")
    rig.scan()
    assert len(rig.findings("L-FND-USE-01")) == 1                     # committee ≠ General Body
    rig.resolution(resolution_number="AGM-1", meeting_type="AGM", account_id=rig.chart["sinking_fund"].id,
                   approved_amount=D("50000"), category="fund_utilisation", purpose="Use sinking fund")
    rig.scan()
    assert rig.findings("L-FND-USE-01") == []


def test_invalid_transfer_premium(rig):
    v = rig.journal(10, "bank", "transfer_premium", 50000, narration="Transfer of flat 101")
    rig.scan()
    f = one(rig, "L-TRF-01")
    assert f.voucher_id == v.id and f.finding_class == "POTENTIAL_NON_COMPLIANCE"


# ── Budget (internal policy, not legal authority) ────────────────────────────────────────────────────────────────

def test_budget_overrun_is_internal_policy_not_illegality(rig, db):
    db.add(BudgetLine(society_id=rig.sid, fiscal_year=fiscal_year(rig.today), account_id=rig.chart["office_expenses"].id,
                      approved_amount=D("1000")))
    db.commit()
    rig.payment(3, "office_expenses", 5000, reference="ST-1")
    rig.scan()
    f = one(rig, "G-BUD-01")
    assert f.finding_class == "INTERNAL_POLICY_DEVIATION" and "not by itself an absence of legal authority" in f.explanation


# ── Legal sources, calendar, audit documentation ─────────────────────────────────────────────────────────────────

def test_legal_source_conflicts_and_missing_bye_laws(rig):
    rig.scan()
    conflicts = rig.findings("L-SRC-CON-01")
    assert len(conflicts) == 2 and all(f.finding_class == "LEGAL_SOURCE_CONFLICT" for f in conflicts)
    assert one(rig, "L-SRC-BYL-01").finding_class == "MISSING_DOCUMENTATION"


def test_compliance_calendar_applicability_and_overdue(rig, db):
    rig.registered(date(2005, 6, 1))                     # an established society: last year's obligations apply
    rig.scan()
    items = {(i.code, i.financial_period): i for i in db.query(ComplianceItem).filter(ComplianceItem.society_id == rig.sid)}
    last = fiscal_year(date(rig.today.year - (0 if rig.today.month >= 4 else 1) - 1, 4, 1))
    assert items[("GST_RETURNS", last)].applicability == cal.PV            # never assumed
    agm = items[("AGM", last)]
    if agm.due_date < rig.today:
        f = [x for x in rig.findings("L-CAL-01") if x.evidence["item"] == "AGM"]
        assert f and f[0].finding_class == "POTENTIAL_NON_COMPLIANCE"
        with pytest.raises(Exception):
            cal.update_item(db, agm, rig.admin["user"], {"completion_status": "COMPLETED"})   # evidence required
        cal.update_item(db, agm, rig.admin["user"], {"completion_status": "COMPLETED", "evidence_ref": "AGM minutes 28-09"})
        db.commit()
        rig.scan()
        assert not [x for x in rig.findings("L-CAL-01") if x.evidence["item"] == "AGM"]
    rig.settings(gst_enabled=True)
    db.query(ComplianceItem).filter(ComplianceItem.society_id == rig.sid).delete()
    db.commit()
    cal.ensure_items(db, rig.sid, rig.today)
    assert db.query(ComplianceItem).filter(ComplianceItem.society_id == rig.sid, ComplianceItem.code == "GST_RETURNS") \
        .first().applicability == "APPLICABLE"


def test_missing_audit_documentation(rig):
    rig.registered(date(2005, 6, 1))
    rig.scan()
    if rig.today > date(rig.today.year, 9, 30) or rig.today.month < 4:
        assert one(rig, "L-AUD-01").finding_class == "MISSING_DOCUMENTATION"
        rig.upload("Audit report", document_type="AUDIT_REPORT", title="Audit report", file_name="audit.txt")
        rig.scan()
        assert rig.findings("L-AUD-01") == []


# ── Recovery readiness (154B-29 / 106C-14) ───────────────────────────────────────────────────────────────────────

def test_recovery_checklist_never_acts(rig, db):
    fl = rig.flat_rows[0]
    cy = rig.cycle(rig.today - timedelta(days=160), rig.today - timedelta(days=130), due=rig.today - timedelta(days=125))
    b = rig.bill(fl, cy, [(ChargeType.MAINTENANCE, "Service Charges", 6000, 6000)])
    rep = recovery.arrears(db, rig.sid, rig.today)
    row = next(r for r in rep["flats"] if r["flat_id"] == str(fl.id))
    assert row["defaulter"] and row["ageing"] == {"91-180": "6000.00"}
    chk = recovery.checklist(db, rig.sid, fl.id, rig.today)
    assert chk["readiness"] == "INCOMPLETE" and "does not issue notices" in chk["note"]
    status = {i["item"]: i["status"] for i in chk["checklist"]}
    assert status["Managing Committee resolution authorising the recovery application"] == "MISSING"
    rig.resolution(resolution_number="MC-REC", category="recovery", purpose="Recovery of dues from defaulters")
    chk = recovery.checklist(db, rig.sid, fl.id, rig.today)
    assert {i["item"]: i["status"] for i in chk["checklist"]}[
        "Managing Committee resolution authorising the recovery application"] == "OK"
    rig.scan()
    assert one(rig, "L-REC-01").finding_class == "ADVISORY_OBSERVATION"
    db.refresh(b)
    assert b.bill_status == BillStatus.ISSUED and b.outstanding == D("6000.00")    # nothing changed


# ── Scan behaviour ───────────────────────────────────────────────────────────────────────────────────────────────

def test_scan_is_idempotent_and_reads_only(rig, db):
    v = rig.payment(10, "sinking_fund", 50000, reference="SF")
    before = (v.amount, v.is_cancelled, [(e.account_id, e.debit, e.credit) for e in v.entries])
    first = rig.scan()
    second = rig.scan()
    assert first["new_findings"] > 0 and second["new_findings"] == 0 and not first["failed_checks"]
    db.refresh(v)
    assert (v.amount, v.is_cancelled, [(e.account_id, e.debit, e.credit) for e in v.entries]) == before


def test_worker_runs_daily_scan_per_society(rig, db):
    from app.modules.accounts_agent.services.engine import get_settings
    other = LRig(db, "cmp2")
    get_settings(db, rig.sid), get_settings(db, other.sid)
    db.commit()
    assert worker.scan_due(db) >= 2
    assert worker.scan_due(db) == 0                                   # not again within 24 h
