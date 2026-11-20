"""The built-in Maharashtra housing-society rule pack and the legal review items that come with it.

READ THIS BEFORE CHANGING A VALUE
---------------------------------
None of these rules is verified against a primary source. While this pack was built the original Government Gazette
(Maharashtra Co-operative Societies (Amendment) Rules, 2026 — Gazette Extraordinary Part IV-B, 22 June 2026, notification
dated 18 June 2026), the Co-operation Department's Acts & Rules portal and the Commissioner's model bye-law PDF were all
unreachable from the build environment, so no clause text was read. Every value below comes from figures the app
already used in its billing and procurement configuration (see billing/models/billing.py MaintenanceSettings,
billing/services/standard_elements.py, vendor/services/work_orders.py) or is left EMPTY where no figure was known.

Consequences, enforced in code (registry.classify):
- every rule ships as PENDING_VERIFICATION or LEGAL_REVIEW_REQUIRED, so a breach is at most POTENTIAL_NON_COMPLIANCE;
- a model bye-law figure is MODEL_REFERENCE and only produces ADVISORY_OBSERVATIONs;
- a rule named by an open blocking review (the two Gazette discrepancies) cannot produce a confirmed violation;
- a platform administrator verifies a rule only against an uploaded primary-source document (routes: legal/rules/{id}/verify).

A changed figure is a NEW version (registry.new_version), never an edit of a shipped row.
"""
from datetime import date
from typing import Dict, List

from app.modules.accounts_agent.legal.models import JURISDICTION_MH

CENTRAL = "IN"
GAZETTE_2026 = "Maharashtra Co-operative Societies (Amendment) Rules, 2026 — Gazette Extraordinary Part IV-B, 22-06-2026"
RULES_1961 = "Maharashtra Co-operative Societies Rules, 1961"
ACT_1960 = "Maharashtra Co-operative Societies Act, 1960"
MODEL_BYELAWS = "Model Bye-laws of Co-operative Housing Societies (Commissioner for Co-operation, Maharashtra)"
NOT_READ = ("Not verified: the primary Gazette / Government publication could not be retrieved when this rule was "
            "loaded. The figure is the one the app already used in its configuration. Verify the clause, page and "
            "effective date against the original Gazette before relying on it.")
GAZETTE_PUBLISHED = date(2026, 6, 22)
PRE_2026_UNTIL = date(2026, 6, 21)


def _r(code, topic, category, title, level, *, scope=JURISDICTION_MH, version=1, legal_status="UNVERIFIED",
       verification="PENDING_VERIFICATION", source=None, authority=None, act_section=None, rule_number=None,
       bye_law=None, clause=None, calc=None, evidence=None, severity="MEDIUM", applicability=None, effective_from=None,
       effective_until=None, publication=None, text=None, note=NOT_READ, expression=None) -> Dict:
    return dict(scope=scope, rule_code=code, version=version, topic=topic, rule_category=category, title=title,
                source_level=level, legal_status=legal_status, verification_status=verification,
                source_document_title=source, source_authority=authority, act_section=act_section,
                rule_number=rule_number, bye_law_number=bye_law, clause_reference=clause, calculation_method=calc,
                required_evidence=evidence, severity=severity,
                applicability_conditions=applicability or {"society_type": "housing"},
                effective_from=effective_from, effective_until=effective_until, publication_date=publication,
                original_text=text, verification_note=note, validation_expression=expression,
                jurisdiction=CENTRAL if scope == CENTRAL else JURISDICTION_MH, human_review_required=True)


GOVT = "Co-operation, Marketing and Textiles Department, Government of Maharashtra"

RULE_PACK: List[Dict] = [
    # ── Charges (Rule 106C-12) ───────────────────────────────────────────────────────────────────────────────────────
    _r("MH-CHG-INTEREST-CAP", "charges.interest_on_arrears.max_rate_pct", "charges",
       "Interest on defaulted charges — ceiling (older model bye-law figure)", "H", legal_status="SUPERSEDED",
       source=MODEL_BYELAWS, authority="Commissioner for Co-operation", bye_law="(to be verified)",
       calc={"type": "max_pct", "value": 21, "unit": "% p.a.", "interest": "simple"}, effective_until=PRE_2026_UNTIL,
       severity="HIGH", note="Older model bye-law ceiling the app's billing notes cite as superseded by the 2026 "
                              "amendment. " + NOT_READ),
    _r("MH-CHG-INTEREST-CAP", "charges.interest_on_arrears.max_rate_pct", "charges",
       "Interest on defaulted charges — ceiling", "A", version=2, source=GAZETTE_2026, authority=GOVT,
       rule_number="106C-12 (sub-rule to be verified)", act_section="154B (Chapter XIII-B)",
       calc={"type": "max_pct", "value": 12, "unit": "% p.a.", "interest": "simple"},
       evidence=["Registered bye-law clause on interest", "General Body resolution fixing the rate"],
       severity="HIGH", publication=GAZETTE_PUBLISHED, effective_from=GAZETTE_PUBLISHED,
       expression="settings.interest_rate_pct <= value"),
    _r("MH-CHG-NONOCC-CAP", "charges.non_occupancy.max_pct", "charges",
       "Non-occupancy charges — ceiling as % of service charges", "A", source=GAZETTE_2026, authority=GOVT,
       rule_number="106C-12 (sub-rule to be verified)",
       calc={"type": "max_pct", "value": 10, "of": "service charges (excluding municipal taxes)"},
       evidence=["General Body resolution fixing the non-occupancy rate"], severity="HIGH",
       publication=GAZETTE_PUBLISHED, effective_from=GAZETTE_PUBLISHED,
       expression="settings.non_occupancy_pct <= value"),
    _r("MH-CHG-APPORTIONMENT", "charges.apportionment", "charges",
       "Levy and apportionment of each charge head among members", "A", source=GAZETTE_2026, authority=GOVT,
       rule_number="106C-12", verification="LEGAL_REVIEW_REQUIRED",
       calc={"type": "apportionment", "allowed_bases": {
           "service_charges": ["fixed", "budget_equal"], "common_electricity": ["fixed", "budget_equal"],
           "lift_maintenance": ["fixed", "budget_equal"], "security": ["fixed", "budget_equal"],
           "housekeeping": ["fixed", "budget_equal"], "fire_safety": ["fixed", "budget_equal"],
           "pest_control": ["fixed", "budget_equal"], "cctv": ["fixed", "budget_equal"],
           "property_tax": ["per_sqft", "budget_area"], "water_charges": ["per_sqft", "budget_area"],
           "repair_fund": ["service_charge_pct", "construction_cost_pct"],
           "sinking_fund": ["service_charge_pct", "construction_cost_pct"], "parking": ["parking", "fixed"]}},
       evidence=["Registered bye-law clauses on apportionment", "General Body resolution on the basis of each head"],
       publication=GAZETTE_PUBLISHED, effective_from=GAZETTE_PUBLISHED,
       note="Allowed bases follow the app's standard element notes (service charges equally, property tax as levied, "
            "water by inlets/area). The share-of-charges sub-rule is numbered differently in the English and Marathi "
            "Gazette text (see the open review). " + NOT_READ),
    # ── Funds (Rule 106C-11) ─────────────────────────────────────────────────────────────────────────────────────────
    _r("MH-FUND-SINKING-RATE", "funds.sinking_fund.rate", "funds",
       "Sinking fund contribution — minimum rate on construction cost", "A", source=GAZETTE_2026, authority=GOVT,
       rule_number="106C-11 (to be verified)", bye_law="13(c) (model)",
       calc={"type": "min_pct", "value": 0.25, "unit": "% p.a.", "basis": "construction_cost_pct",
             "of": "architect-certified construction cost excluding land"},
       evidence=["Architect's construction-cost certificate", "General Body resolution on the rate"],
       publication=GAZETTE_PUBLISHED, effective_from=GAZETTE_PUBLISHED),
    _r("MH-FUND-REPAIR-RATE", "funds.repair_fund.rate", "funds",
       "Repairs & maintenance fund contribution — reference rate", "H", legal_status="MODEL_REFERENCE",
       source=MODEL_BYELAWS, bye_law="67(a)(iii) (model)",
       calc={"type": "reference_pct", "value": 0.75, "unit": "% p.a.", "basis": "construction_cost_pct"},
       severity="LOW"),
    _r("MH-FUND-UTILISATION", "funds.utilisation", "funds",
       "Use of designated funds only for their purpose, with the required approval", "A", source=GAZETTE_2026,
       authority=GOVT, rule_number="106C-11 (to be verified)",
       calc={"type": "fund_purpose", "funds": {
           "sinking_fund": {"authority": "GENERAL_BODY", "purpose": "major structural repairs or reconstruction"},
           "major_repair_fund": {"authority": "GENERAL_BODY", "purpose": "major repairs"},
           "repair_fund": {"authority": "MANAGING_COMMITTEE", "purpose": "repairs and maintenance of the buildings"},
           "education_fund": {"authority": "MANAGING_COMMITTEE", "purpose": "co-operative education and training"},
           "reserve_fund": {"authority": "GENERAL_BODY", "purpose": "as the General Body decides"},
           "building_fund": {"authority": "GENERAL_BODY", "purpose": "as the General Body decides"}}},
       evidence=["Resolution approving the utilisation", "Work order / bills for the work"], severity="HIGH",
       publication=GAZETTE_PUBLISHED, effective_from=GAZETTE_PUBLISHED,
       note="Approval authority per fund is a working assumption pending verification of Rule 106C-11. " + NOT_READ),
    _r("MH-FUND-EDUCATION-106C7", "funds.education_training.contribution", "funds",
       "Co-operative education and training contribution", "A", source=GAZETTE_2026, authority=GOVT,
       rule_number="106C-7", verification="LEGAL_REVIEW_REQUIRED", calc={"type": "unknown"},
       publication=GAZETTE_PUBLISHED, effective_from=GAZETTE_PUBLISHED,
       note="No figure loaded. Requires the Gazette text. " + NOT_READ),
    # ── Expenditure (Rule 106C-13, model bye-law 157) ─────────────────────────────────────────────────────────────────
    _r("MH-EXP-106C13-LIMIT", "expenditure.committee_limit", "expenditure",
       "Maintenance / repair expenditure the Managing Committee may incur — membership slabs", "A",
       source=GAZETTE_2026, authority=GOVT, rule_number="106C-13", verification="LEGAL_REVIEW_REQUIRED",
       calc={"type": "membership_slab_limit", "slabs": None, "scope": ["repairs", "maintenance"],
             "measures": ["one_time", "cumulative_financial_year"]},
       evidence=["Managing Committee resolution", "General Body resolution above the limit"], severity="HIGH",
       publication=GAZETTE_PUBLISHED, effective_from=GAZETTE_PUBLISHED,
       note="Slab amounts NOT loaded: the English and Marathi texts appear to differ at the ~1,000-member boundary "
            "(see the open review). Until verified the engine uses the society's own procurement limits and the "
            "model bye-law 157 reference. " + NOT_READ),
    _r("MH-EXP-BYELAW157", "expenditure.committee_limit", "expenditure",
       "Committee spending limit by society size (model bye-law 157)", "H", legal_status="MODEL_REFERENCE",
       source=MODEL_BYELAWS, bye_law="157 (model)",
       calc={"type": "membership_slab_limit", "slabs": [[25, 25000], [50, 50000], [None, 100000]],
             "scope": ["repairs", "maintenance", "works"]},
       evidence=["Committee resolution sanctioning the work", "General Body resolution above the limit"],
       note="The app's procurement module already applies these slabs. Applies to a society only if its registered "
            "bye-laws adopted bye-law 157 unchanged. " + NOT_READ),
    # ── Borrowing (Rule 106C-10) ─────────────────────────────────────────────────────────────────────────────────────
    _r("MH-BORROW-106C10", "borrowing.authority", "borrowing", "Borrowing only with the required General Body approval",
       "A", source=GAZETTE_2026, authority=GOVT, rule_number="106C-10",
       calc={"type": "requires_resolution", "authority": "GENERAL_BODY", "ledger": "loans"},
       evidence=["General Body resolution approving the borrowing"], publication=GAZETTE_PUBLISHED,
       effective_from=GAZETTE_PUBLISHED),
    # ── Recovery (Section 154B-29, Rule 106C-14) ──────────────────────────────────────────────────────────────────────
    _r("MH-REC-154B29", "recovery.certificate", "recovery",
       "Recovery certificate for dues — application readiness", "A", source=GAZETTE_2026, authority=GOVT,
       act_section="154B-29", rule_number="106C-14",
       calc={"type": "checklist", "defaulter_after_months": 3},
       evidence=["Member-wise statement of account (ledger) reconciled with bills and receipts",
                 "Copies of the bills raised for the period claimed",
                 "Demand / reminder notice(s) served on the member, with proof of service",
                 "Managing Committee resolution authorising the recovery application",
                 "Interest worked out at the rate fixed under the bye-laws",
                 "Copy of the registered bye-law clauses relied on"],
       severity="HIGH", publication=GAZETTE_PUBLISHED, effective_from=GAZETTE_PUBLISHED,
       note="The defaulter period (3 months) is the figure the app's defaulters list already uses. " + NOT_READ),
    # ── Transfer & admission ─────────────────────────────────────────────────────────────────────────────────────────
    _r("MH-TRF-PREMIUM-CAP", "transfer.premium.max_amount", "transfer", "Transfer premium — ceiling", "B",
       legal_status="UNVERIFIED", verification="LEGAL_REVIEW_REQUIRED", source="Government order (to be identified)",
       calc={"type": "max_amount", "value": 25000},
       note="Widely cited ceiling of ₹25,000; the governing order and any revision must be identified. Treated as an "
            "advisory figure until verified; do not rely on outdated model bye-law rates. " + NOT_READ),
    _r("MH-ADM-ENTRANCE-FEE", "admission.entrance_fee", "transfer", "Entrance fee on admission", "H",
       legal_status="MODEL_REFERENCE", source=MODEL_BYELAWS, calc={"type": "reference_amount", "value": 100},
       severity="LOW"),
    # ── Central tax (scope IN): professional verification is always required ─────────────────────────────────────────
    _r("IN-GST-MEMBER-THRESHOLD", "tax.gst.member_contribution", "tax",
       "GST on members' contributions above a monthly threshold", "A", scope=CENTRAL,
       source="CGST notifications (to be identified)", authority="Government of India",
       calc={"type": "threshold", "monthly_per_member": 7500, "rate_pct": 18, "turnover_registration": 2000000},
       severity="MEDIUM", applicability={"society_type": "housing", "requires": "GST registration"},
       note="Figures are the app's existing GST configuration defaults. Applicability depends on registration and "
            "turnover: professional verification required. " + NOT_READ),
]

REVIEW_PACK: List[Dict] = [
    dict(dedupe_key="gazette-2026:106C-12:numbering", review_type="NUMBERING_DISCREPANCY", blocking=True,
         title="Rule 106C-12: the share-of-charges sub-rule is numbered differently in English and Marathi",
         description="The English and Marathi texts of the 2026 Amendment Rules number the subsection on the share "
                     "of charges differently. Which numbering is authoritative, and whether the wording also differs, "
                     "must be settled against the Marathi original before Rule 106C-12 is applied as a confirmed rule.",
         rule_codes=["MH-CHG-APPORTIONMENT", "MH-CHG-NONOCC-CAP", "MH-CHG-INTEREST-CAP"]),
    dict(dedupe_key="gazette-2026:106C-13:slab-boundary", review_type="LANGUAGE_DISCREPANCY", blocking=True,
         title="Rule 106C-13: membership slab boundary around 1,000 members differs between texts",
         description="The maintenance / repair expenditure slabs by membership appear to disagree at the ~1,000-member "
                     "boundary between the English and Marathi texts (for example 'up to 1,000' in one and 'above "
                     "1,000' in the other). The slab amounts are not loaded until the boundary is verified.",
         rule_codes=["MH-EXP-106C13-LIMIT"]),
    dict(dedupe_key="gazette-2026:primary-source", review_type="RULE_VERIFICATION", blocking=False,
         title="Verify the 2026 Amendment Rules against the original Government Gazette",
         description="The rule pack was loaded without access to the original Gazette (Part IV-B, 22 June 2026; "
                     "notification of 18 June 2026). Upload the Gazette PDF as a primary source and verify each "
                     "106C-* rule (text, page, effective date). Until then every such rule is PENDING_VERIFICATION. A "
                     "third-party hosted copy is a research copy only.",
         rule_codes=[r["rule_code"] for r in RULE_PACK if (r.get("rule_number") or "").startswith("106C")]),
]
