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
       effective_until=None, publication=None, text=None, note=NOT_READ, expression=None, page=None) -> Dict:
    return dict(scope=scope, rule_code=code, version=version, topic=topic, rule_category=category, title=title,
                source_level=level, legal_status=legal_status, verification_status=verification,
                source_document_title=source, source_authority=authority, act_section=act_section,
                rule_number=rule_number, bye_law_number=bye_law, clause_reference=clause, page_number=page,
                calculation_method=calc,
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

# ── Model and draft bye-law references (read from the uploaded PDFs, November 2026) ───────────────────────────────────────
# These are NOT the text of any society's registered bye-laws and not the Gazette. They are recorded so that the agent
# and the committee can see what the model bye-laws say, with the bye-law number and PDF page, and where the 2026 draft
# differs. Two properties keep them from changing any finding:
#   * every one uses its own "reference.*" or "draft2026.*" topic, so registry.resolve() for the topics the engine tests
#     (charges.*, funds.*, expenditure.*) still returns the rules above;
#   * model rules are level H / MODEL_REFERENCE (advisory only) and draft rules are legal_status DRAFT, which
#     registry.in_force() never treats as in force.
# Bye-law numbers differ between editions: each rule gives the number in the 91-page 2014 edition first and the
# 49-page edition in the clause reference. PDF pages are physical pages of the file, not the printed page numbers.
MODEL_2014 = "Model Bye-laws of Co-operative Housing Society (Tenant Co-partnership Housing Society), 2014 (91-page edition)"
DRAFT_2026 = "Draft Housing (Tenant Co-partnership) Bye-laws, 2026 (183-page draft, not adopted)"
BYELAW_READ = ("Text read from the uploaded PDF; bye-law number and PDF page recorded. Still unverified: a platform "
               "administrator must verify it against the uploaded document in the Legal library. It applies to a "
               "society only if that society's registered bye-laws adopted it unchanged, and bye-law numbers differ "
               "between editions.")
DRAFT_READ = ("DRAFT: not adopted and not in force. Recorded for reference and for comparison with the model bye-laws "
              "only; the engine never applies a rule with this status. Text read from the uploaded PDF.")


def _model(code, topic, category, title, *, bye_law, clause, page, text, calc, evidence=None):
    return _r(code, topic, category, title, "H", legal_status="MODEL_REFERENCE", source=MODEL_2014,
              authority="Commissioner for Co-operation", bye_law=bye_law, clause=clause, page=page, text=text, calc=calc,
              evidence=evidence, severity="LOW", note=BYELAW_READ)


def _draft(code, topic, category, title, *, bye_law, clause, page, text, calc, evidence=None):
    return _r(code, topic, category, title, "H", legal_status="DRAFT", source=DRAFT_2026, authority=GOVT,
              bye_law=bye_law, clause=clause, page=page, text=text, calc=calc, evidence=evidence, severity="LOW",
              note=DRAFT_READ)


BYELAW_RULES: List[Dict] = [
    # ── Model bye-laws (2014) ────────────────────────────────────────────────────────────────────────────────────────
    _model("MH-MODEL-FUND-REPAIR-RATE", "reference.funds.repair_fund.minimum", "funds",
           "Repairs & maintenance fund: minimum 0.75% a year of each flat's certified construction cost",
           bye_law="13(a); 66(a)(iii)", clause="13(a), 14(b), 66(a)(iii)  [49-page edition: 13(a), 14(b), 69(a)(iii)]",
           page="11, 28",
           text="The Repairs and Maintenance Fund, at the rate fixed at the general body subject to the minimum of 0.75 "
                "per cent per annum of the construction cost of each flat, incurred during the construction of the "
                "building of the Society and certified by the Architect, for meeting expenses of normal recurring "
                "repairs of the Society's buildings/property.",
           calc={"type": "reference_min_pct", "value": 0.75, "unit": "% p.a.", "basis": "construction_cost_pct",
                 "of": "architect-certified construction cost of each flat", "levied": "per flat, by its own cost",
                 "purpose": "normal recurring repairs and maintenance of the Society's property"},
           evidence=["Architect's construction-cost certificate", "General Body resolution fixing the rate"]),
    _model("MH-MODEL-FUND-SINKING-RATE", "reference.funds.sinking_fund.minimum", "funds",
           "Sinking fund: minimum 0.25% a year of each flat's certified construction cost, excluding land",
           bye_law="13(c); 14(c); 15", clause="13(c), 14(c)  [49-page edition: 13(c), 14(c), 15]", page="11",
           text="The Sinking Fund at the rate decided at the meeting of the general body, subject to the minimum of 0.25 "
                "per cent per annum of the construction cost of each flat incurred during the construction of the "
                "building of the Society and certified by the Architect, excluding the proportionate cost of the land.",
           calc={"type": "reference_min_pct", "value": 0.25, "unit": "% p.a.", "basis": "construction_cost_pct",
                 "of": "architect-certified construction cost of each flat, excluding the proportionate cost of land",
                 "levied": "per flat, by its own cost",
                 "utilisation": "reconstruction or heavy repairs certified by the Architect, on General Body approval",
                 "investment": "long-term deposit (49-page edition, bye-law 15)"},
           evidence=["Architect's construction-cost certificate (land excluded)", "General Body resolution fixing the rate"]),
    _model("MH-MODEL-FUND-MAJOR-REPAIR", "reference.funds.major_repair_fund", "funds",
           "Major repairs fund: as and when required, pro rata on area, used only with General Body permission",
           bye_law="13(b)", clause="13(b)  [49-page edition: 13(b), 14(f)]", page="11",
           text="Major Repairs Funds, as and when required and decided by the General Body at the rate fixed pro-rata on "
                "area basis.",
           calc={"type": "area_basis", "basis": "area", "decided_by": "GENERAL_BODY",
                 "utilisation": "prior permission of the General Body"}),
    _model("MH-MODEL-FUND-EDU-TRAINING", "reference.funds.education_training.contribution", "funds",
           "Education and training fund: ₹10 per flat or unit per month, or as the General Body decides",
           bye_law="13(d); 66(a)(xiv)", clause="13(d), 66(a)(xiv)", page="11, 28",
           text="To create Education and Training Fund from contribution by the Members Rs 10 per month / per unit or as "
                "decided by the General Body.",
           calc={"type": "reference_amount", "value": 10, "unit": "INR per flat/unit per month", "levied": "equally"}),
    _model("MH-MODEL-CHG-APPORTIONMENT", "reference.charges.apportionment", "charges",
           "How each charge head is shared among the members (model bye-law)",
           bye_law="64-66", clause="64, 65, 66(a)  [49-page edition: 67, 68, 69(a)]", page="27, 28",
           text="Property taxes: As fixed by the Local Authority. Water Charges: On the basis of total number and size of "
                "inlets provided in each flat. Expenses on repairs and maintenance of the lift, including charges for "
                "running the lift: Equally by all the Members of the building in which lift is provided, irrespective of "
                "the fact whether they use the lift or not. Service Charges: Equally divided by number of flats / units. "
                "Insurance Charges: The built up areas of each flat. Lease Rent: The built up area of each flat / unit. "
                "Non-Agricultural tax: The built up area of each flat / unit. Education & Training Fund: Rs. 10 per "
                "Flat/unit per month. Election Fund: Equally by the Members.",
           calc={"type": "apportionment_reference", "bases": {
               "service_charges": "equally by number of flats/units (includes staff salaries, audit, legal, stationery, "
                                  "committee expenses and common electricity: bye-law 65)",
               "lift_maintenance": "equally by the members of the building in which the lift is provided",
               "water_charges": "number and size of inlets in each flat",
               "property_tax": "as fixed by the local authority",
               "insurance": "built-up area of each flat (extra premium for commercial storage borne by those responsible)",
               "lease_rent": "built-up area of each flat", "non_agricultural_tax": "built-up area of each flat",
               "repair_fund": "minimum 0.75% p.a. of the construction cost of each flat",
               "sinking_fund": "bye-law 13(c): minimum 0.25% p.a. of the construction cost of each flat, excluding land",
               "parking": "rate fixed by the General Body", "education_training_fund": "₹10 per flat/unit per month",
               "election_fund": "equally by the members", "other": "as decided by the General Body"}},
           evidence=["Registered bye-law clauses on apportionment", "General Body resolution on each head"]),
    _model("MH-MODEL-REPAIRS-AT-COST", "reference.charges.society_repairs_scope", "charges",
           "Repairs and maintenance the Society carries out at its own cost (model bye-law list)",
           bye_law="67(a)", clause="67(a)  [49-page edition: 160(a), PDF 43, a shorter list]", page="28, 29",
           text="(v) Water storage tanks ... (xvi) Lifts ... (xviii) Generators ... (xix) Security Appliances (CCTV, "
                "Intercom, Group Mobile, Mass Data Sharing Devices, Siren Bell) ... (xxii) Common areas not specifically "
                "allotted, Swimming Pool, Gym, Sauna Bath, Coffee House ... (xxv) Garden (xxvi) Community hall",
           calc={"type": "scope_list", "items": [
               "water pumps", "water storage tanks", "drainage and septic tanks", "lifts", "generators",
               "security appliances (CCTV, intercom, siren)", "rain water harvesting", "sewerage, storm water drain and "
               "water treatment plant", "common areas, swimming pool, gym", "common parking space", "solar devices",
               "garden", "community hall"],
                 "note": "Heads of repair and maintenance of the property; the repairs and maintenance fund (13(a)) meets "
                         "'normal recurring repairs'. Whether a given contract is paid from that fund is for the General "
                         "Body and the auditor."}),
    _model("MH-MODEL-CHG-INTEREST-70", "reference.charges.interest_on_arrears", "charges",
           "Interest on delayed charges: simple interest at 21% a year or a lower General Body rate (model bye-law)",
           bye_law="70", clause="70  [49-page edition: 72, 'maximum of 21 percent']", page="29",
           text="A Member shall be required to pay simple interest at twenty one percent per annum, or, at such lower "
                "rate as may be fixed by the General Body, on the outstanding dues to the Society, from the date the "
                "amount was due ... till full and final payment by the Member.",
           calc={"type": "reference_max_pct", "value": 21, "unit": "% p.a.", "interest": "simple",
                 "note": "Superseded for charges from 22-06-2026 by the 12% ceiling (MH-CHG-INTEREST-CAP v2)."}),
    _model("MH-MODEL-CHG-NONOCC", "reference.charges.non_occupancy", "charges",
           "Non-occupancy charges: by Government circular; not levied where the member's family occupies the flat",
           bye_law="43(2)(iii)(c)", clause="43(2)(iii)(c)  [49-page edition: 43(2)(c)]", page="16",
           text="Nonoccupancy charges shall be charged in accordance with the circular issued by the Government of "
                "Maharashtra and the Commissioner for Co-operation from time to time and shall not be levied if the flat "
                "is occupied by the 'Family' of the member as defined under these bye-laws.",
           calc={"type": "by_circular", "value": None,
                 "exempt": ["flat occupied by the member's Family", "flat purchaser intending to become a member, with "
                            "documentary evidence"]}),
    _model("MH-MODEL-EXP-COMMITTEE-LIMIT", "reference.expenditure.committee_limit", "expenditure",
           "Committee repair spending limit without General Body sanction (model bye-law; corrects the citation)",
           bye_law="156(a)", clause="156(a), 156(b)  [49-page edition: 158(a), 158(b)]", page="49",
           text="The Committee shall be competent to incur expenditure on the repairs and maintenance of the Society's "
                "property once in a financial year, the onetime expenditure does not exceed: Upto 25 Members Rs. 25,000/- "
                "26 to 50 Members Rs. 50,000/- 51 and above Upto Rs. 1,00,000/-. If one time expenditure ... exceeds the "
                "limit prior sanction of the meeting of the General Body shall be necessary.",
           calc={"type": "membership_slab_limit", "slabs": [[25, 25000], [50, 50000], [None, 100000]],
                 "scope": ["repairs", "maintenance"], "measure": "one_time, once in a financial year",
                 "note": "MH-EXP-BYELAW157 cites 'bye-law 157'; in both model editions read, the clause is 156(a) "
                         "(2014 edition) or 158(a) (49-page edition). 157 is the Secretary's duty to inspect."}),
    # ── 2026 draft bye-laws (DRAFT: never in force) ──────────────────────────────────────────────────────────────────
    _draft("MH-DRAFT26-FUND-SINKING", "draft2026.funds.sinking_fund.minimum", "funds",
           "Draft 2026: sinking fund minimum 0.25% a year of each flat's certified construction cost",
           bye_law="18(a); 19(b)", clause="18(a), 19(b) (as per Rule 106C-11)", page="17, 20",
           text="The Sinking Fund shall consist of contributions collected from its Members at a rate determined in the "
                "General Body Meeting, subject to a minimum of 0.25 per cent per annum of the construction cost of each "
                "flat, incurred during the building's construction and certified by the Architect.",
           calc={"type": "reference_min_pct", "value": 0.25, "unit": "% p.a.", "basis": "construction_cost_pct",
                 "difference_from_model": "the draft does not repeat the model's exclusion of the proportionate land cost",
                 "utilisation": "structural repairs, replacement of major components, reconstruction; prior General "
                                "Body approval; separately accounted"}),
    _draft("MH-DRAFT26-FUND-REPAIR", "draft2026.funds.repair_fund.minimum", "funds",
           "Draft 2026: repair and maintenance fund minimum 0.75% a year of each flat's certified construction cost",
           bye_law="18(b); 19(c)", clause="18(b), 19(c) (Section 154B-18 read with Rule 106C-13)", page="17, 20",
           text="The Repair and Maintenance Fund shall consist of contributions collected from its Members at a rate fixed "
                "in the General Body Meeting, subject to a minimum of 0.75 per cent per annum of the construction cost of "
                "each flat, incurred during the building's construction and certified by the Architect.",
           calc={"type": "reference_min_pct", "value": 0.75, "unit": "% p.a.", "basis": "construction_cost_pct",
                 "utilisation": "routine recurring repairs, day-to-day maintenance and upkeep of buildings and common "
                                "areas; the Managing Committee may spend from it in the ordinary course; separately "
                                "accounted"}),
    _draft("MH-DRAFT26-FUND-OTHERS", "draft2026.funds.other_contributions", "funds",
           "Draft 2026: major repair, education and training, election, welfare and other funds",
           bye_law="18(c)-(h); 63(a)(xii)", clause="18(c)-(h), 63(a)(xii)", page="18, 64",
           text="Major Repair Fund — on the basis of carpet area of each flat / unit; Education and Training Fund — as "
                "prescribed under the Act, Rules and these Bye-laws; Election Fund — equally by the Members; Welfare "
                "Fund — equally by the Members; Any Other Fund — equally by the Members.",
           calc={"type": "apportionment_reference", "bases": {
               "major_repair_fund": "carpet area of each flat/unit", "education_training_fund": "as prescribed (no "
               "figure in the draft)", "election_fund": "equally", "welfare_fund": "equally", "other_funds": "equally"}}),
    _draft("MH-DRAFT26-CHG-APPORTIONMENT", "draft2026.charges.apportionment", "charges",
           "Draft 2026: how each charge head is shared among the members (Rule 106C-12)",
           bye_law="61-63", clause="63(a)(i)-(xiv) (Rule 106C-12)", page="62-64",
           text="Service Charges: Equally divided by the number of flats / units. Property Taxes: As fixed by the Local "
                "Authority, and in respect of common areas, on the basis of carpet area of each flat / unit. Water "
                "Charges: On the basis of total number and size of inlets / taps provided in each flat / unit as per the "
                "sanctioned building plan. Lifts: Equally divided by the number of flats / units in the building in which "
                "lift is provided. Insurance Charges, Lease Rent, Non-agricultural Tax: On the basis of carpet area of "
                "each flat / unit. Amenities Charges: equally by the members. Playground, garden and similar common "
                "amenities: Equally divided by the number of flats / units.",
           calc={"type": "apportionment_reference", "bases": {
               "service_charges": "equally by number of flats/units", "property_tax": "as fixed by the local authority; "
               "common areas by carpet area", "water_charges": "inlets/taps per sanctioned plan",
               "lift_maintenance": "equally by the flats in the building with the lift", "parking": "rate fixed by the "
               "General Body", "insurance": "carpet area", "lease_rent": "carpet area", "non_agricultural_tax": "carpet "
               "area", "amenities_clubhouse_gym_pool": "equally by the members", "playground_garden": "equally by flats"}}),
    _draft("MH-DRAFT26-CHG-INTEREST", "draft2026.charges.interest_on_arrears", "charges",
           "Draft 2026: interest on defaulted charges, ceiling 12% simple, none during the payment period",
           bye_law="66; 64(iv)", clause="66, 64(iii)-(iv) (Rule 106C-12)", page="63, 66",
           text="The rate of such interest shall be fixed by the General Body, subject to the maximum 12% simple interest "
                "rate per annum. No interest shall be charged during the payment period. In case the General Body has not "
                "fixed the rate of interest, the Society shall charge simple interest at the rate of twelve per cent per "
                "annum on the outstanding dues.",
           calc={"type": "reference_max_pct", "value": 12, "unit": "% p.a.", "interest": "simple",
                 "default_if_unfixed": 12, "interest_free_during": "the payment period",
                 "payment_period_if_unfixed_days": 15}),
    _draft("MH-DRAFT26-CHG-NONOCC", "draft2026.charges.non_occupancy", "charges",
           "Draft 2026: non-occupancy charges at ten per cent of the service charges",
           bye_law="63(a)(viii)", clause="63(a)(viii) (Rule 106C-12)", page="63",
           text="Non-occupancy Charges: Ten per cent of the Service Charges.",
           calc={"type": "reference_pct", "value": 10, "of": "service charges"}),
    _draft("MH-DRAFT26-REC-DEFAULTER", "draft2026.recovery.defaulter", "recovery",
           "Draft 2026: a member is a defaulter after three months from service of the bill or the due date",
           bye_law="65(a)-(b)", clause="65(a), 65(b) (Rule 106C-12, Section 154B-29)", page="65",
           text="A Member who fails to pay such dues within three months from the date of service of the bill or notice or "
                "the due date of payment, whichever is later, shall be treated as a defaulter.",
           calc={"type": "checklist", "defaulter_after_months": 3, "counted_from": "later of service of bill and due date"}),
    _draft("MH-DRAFT26-EXP-REPAIR-LIMIT", "draft2026.expenditure.committee_limit", "expenditure",
           "Draft 2026: one-time repair spending the Managing Committee may incur without General Body approval",
           bye_law="147(e)-(f)", clause="147(e), 147(f)", page="117",
           text="The Managing Committee shall be competent to incur one-time expenditure on repairs and maintenance of the "
                "Society property in a financial year, without prior approval of the General Body Meeting, provided such "
                "expenditure does not exceed — up to 25 Members ₹1,00,000; 26 to 50 Members ₹2,00,000; 51 to 100 Members "
                "₹3,00,000; 101 to 1000 Members ₹4,00,000; 1001 and above Members ₹5,00,000. Where the estimated "
                "expenditure exceeds the above limit, prior approval of the General Body Meeting shall be mandatory "
                "except in cases of emergency repairs.",
           calc={"type": "membership_slab_limit", "slabs": [[25, 100000], [50, 200000], [100, 300000], [1000, 400000],
                                                           [None, 500000]],
                 "scope": ["repairs", "maintenance"], "measure": "one_time, in a financial year",
                 "boundary": "1,000 members falls in the 101-1000 band; 1,001 and above takes the top band",
                 "emergency_repairs": "exempt from prior approval"}),
]

RULE_PACK.extend(BYELAW_RULES)


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
    dict(dedupe_key="byelaws-2026-11:editions", review_type="RULE_VERIFICATION", blocking=False,
         title="Model and draft bye-law references were loaded: none is a society's registered bye-laws",
         description="Clauses were read from three uploaded PDFs: the 91-page 2014 model, a 49-page model edition and a "
                     "183-page 'Draft Bye-laws, 2026'. The model clauses are loaded as MODEL_REFERENCE and the draft "
                     "clauses as DRAFT (never applied). Neither is the society's own registered bye-law, and the bye-law "
                     "numbers differ between the editions. Upload the society's registered bye-laws, verify them, and "
                     "let them govern; the draft is not law until adopted.",
         rule_codes=[r["rule_code"] for r in BYELAW_RULES]),
    dict(dedupe_key="byelaws-2026-11:draft-vs-model", review_type="SOURCE_CONFLICT", blocking=False,
         title="The 2026 draft differs from the model bye-laws on several figures",
         description="Interest on arrears: 21% a year (or lower) in the model, 12% simple in the draft. Committee repair "
                     "spending without General Body approval: ₹25,000 / ₹50,000 / ₹1,00,000 in the model; ₹1 lakh to "
                     "₹5 lakh by five membership bands in the draft (1,000 members falls in the ₹4 lakh band). Sinking "
                     "fund: the model excludes the proportionate cost of land, the draft does not say so. Non-occupancy "
                     "charges: by Government circular in the model, ten per cent of service charges in the draft. "
                     "Education and training fund: ₹10 per flat per month in the model, 'as prescribed' in the draft. "
                     "The draft's 1,000-member boundary does not settle the open Rule 106C-13 review, which concerns the "
                     "Gazette's English and Marathi texts.",
         rule_codes=["MH-MODEL-CHG-INTEREST-70", "MH-DRAFT26-CHG-INTEREST", "MH-MODEL-EXP-COMMITTEE-LIMIT",
                     "MH-DRAFT26-EXP-REPAIR-LIMIT", "MH-MODEL-FUND-SINKING-RATE", "MH-DRAFT26-FUND-SINKING",
                     "MH-MODEL-CHG-NONOCC", "MH-DRAFT26-CHG-NONOCC", "MH-MODEL-FUND-EDU-TRAINING",
                     "MH-DRAFT26-FUND-OTHERS"]),
    dict(dedupe_key="byelaws-2026-11:citations", review_type="NUMBERING_DISCREPANCY", blocking=False,
         title="Check the bye-law numbers cited by MH-EXP-BYELAW157 and MH-FUND-REPAIR-RATE",
         description="MH-EXP-BYELAW157 cites 'bye-law 157'. In the model editions read, the committee's repair spending "
                     "limit is bye-law 156(a) (2014 edition, PDF page 49) or 158(a) (49-page edition, PDF page 42); "
                     "157 is the Secretary's duty to inspect. MH-FUND-REPAIR-RATE cites '67(a)(iii)'; the clause is "
                     "13(a) and 66(a)(iii) in the 2014 edition and 13(a) and 69(a)(iii) in the 49-page edition. The "
                     "figures match; only the citations need correcting, as a new version of each rule by a platform "
                     "administrator.",
         rule_codes=["MH-EXP-BYELAW157", "MH-FUND-REPAIR-RATE", "MH-MODEL-EXP-COMMITTEE-LIMIT",
                     "MH-MODEL-FUND-REPAIR-RATE"]),
]
