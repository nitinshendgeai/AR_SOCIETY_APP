# Accounts Agent — Maharashtra Legal & Bye-law Intelligence: Implementation Report

Extends the existing Accounts Agent (see [ACCOUNTS_AGENT_IMPLEMENTATION_REPORT.md](ACCOUNTS_AGENT_IMPLEMENTATION_REPORT.md)).
Nothing in the accounting module was rebuilt; Engine A (per-voucher validation, three-month learning, approval-gated
corrections) is unchanged and still runs on every posting.

## 0. Legal verification status — read first

**No legal rule is verified.** The original Gazette (MCS (Amendment) Rules 2026, Part IV-B, 22-06-2026), the
Co-operation Department portal, the Commissioner's model bye-law PDF and the third-party research copy were all
**unreachable from the build environment** (the network proxy refused every one of those hosts; a separate web-fetch
attempt failed the same way). No clause text was read.

So the shipped rule pack (`backend/app/modules/accounts_agent/legal/seed.py`):

* takes its figures only from values the app already used in its billing and procurement configuration (12 % interest
  cap, 10 % non-occupancy cap, 0.25 % sinking fund, 0.75 % repair fund, bye-law 157 slabs, ₹7,500 GST threshold) or
  leaves them **empty** where nothing was known (106C-7 education fund, 106C-13 slab amounts);
* marks every rule `PENDING_VERIFICATION` or `LEGAL_REVIEW_REQUIRED`, with a note saying why;
* opens two **blocking** legal reviews for the Gazette discrepancies named in the brief (106C-12 share-of-charges
  numbering, English vs Marathi; 106C-13 slab boundary around 1,000 members) and one non-blocking review to verify the
  whole pack against the original Gazette.

Effect enforced in code (`registry.classify`): with unverified law the engine reports at most
**POTENTIAL_NON_COMPLIANCE**; a model bye-law figure gives only an **ADVISORY_OBSERVATION**; a rule named by a blocking
review can never produce a confirmed violation. **CONFIRMED_STATUTORY_VALIDATION_FAILURE** needs a rule that a platform
administrator has verified against an uploaded primary-source document, page recorded, `BINDING`, no open blocking
review, and a deterministic calculation. A test exercises that whole path.

| Rule code | Topic | Ref (to verify) | Value | Status |
|---|---|---|---|---|
| MH-CHG-INTEREST-CAP v1 | interest on arrears ceiling | older model bye-law | 21 % p.a., until 21-06-2026 | SUPERSEDED / model reference |
| MH-CHG-INTEREST-CAP v2 | interest on arrears ceiling | 106C-12 | 12 % p.a. simple, from 22-06-2026 | UNVERIFIED, blocked by 106C-12 review |
| MH-CHG-NONOCC-CAP | non-occupancy ceiling | 106C-12 | 10 % of service charges | UNVERIFIED, blocked |
| MH-CHG-APPORTIONMENT | basis per charge head | 106C-12 | allowed bases per head | LEGAL_REVIEW_REQUIRED, blocked |
| MH-FUND-SINKING-RATE | sinking fund minimum | 106C-11 / bye-law 13(c) | ≥ 0.25 % p.a. of construction cost | UNVERIFIED |
| MH-FUND-REPAIR-RATE | repair fund reference | model bye-law 67 | 0.75 % p.a. | MODEL_REFERENCE |
| MH-FUND-UTILISATION | fund purpose & approval authority | 106C-11 | per fund (assumption) | UNVERIFIED |
| MH-FUND-EDUCATION-106C7 | education & training | 106C-7 | **not loaded** | LEGAL_REVIEW_REQUIRED |
| MH-EXP-106C13-LIMIT | committee expenditure slabs | 106C-13 | **slabs not loaded** | LEGAL_REVIEW_REQUIRED, blocked |
| MH-EXP-BYELAW157 | committee limit by size | model bye-law 157 | 25k / 50k / 1L | MODEL_REFERENCE |
| MH-BORROW-106C10 | borrowing needs GB resolution | 106C-10 | — | UNVERIFIED |
| MH-REC-154B29 | recovery certificate readiness | s.154B-29 / 106C-14 | defaulter after 3 months + evidence list | UNVERIFIED |
| MH-TRF-PREMIUM-CAP | transfer premium ceiling | Government order (unidentified) | ₹25,000 | LEGAL_REVIEW_REQUIRED |
| MH-ADM-ENTRANCE-FEE | entrance fee | model bye-law | ₹100 | MODEL_REFERENCE |
| IN-GST-MEMBER-THRESHOLD | GST on contributions | CGST notifications | ₹7,500 / 18 % | UNVERIFIED, professional verification |

**Verified rules: 0. Unverified rules: 15 (14 codes, one with two versions).**

## 1. What was built

| Phase | Delivered | Where (`backend/app/modules/accounts_agent/…`) |
|---|---|---|
| A. Legal foundation | Society legal profile; legal document registry (original file + SHA-256, page-by-page text, language detection incl. Marathi, draft-marker detection, duplicate and missing-page detection, clause extraction with page refs); verification workflow (upload never makes a document operative; type↔status rules; draft guard; registered bye-laws supersede earlier ones); structured resolution register with import from governance meetings | `legal/models.py`, `legal/documents.py`, `legal/resolutions.py` |
| B. Rule engine | Versioned rule registry (new version closes the old, never overwrites); rule applicable **on the transaction date**; hierarchy A–H with scope (stricter bye-law honoured, looser bye-law = override attempt → conflict review); society rules govern only when verified against an operative document; conflict detection; legal reviews that block confirmation; classification policy | `legal/registry.py`, `legal/seed.py` |
| C. Residential accounting | Bill integrity (outstanding = total + interest − paid), duplicate bills, equal-share heads billed at different rates, interest on bills with no arrears, duplicate receipts, duplicate vendor invoices, vendor payments without a bill, vendor concentration, fund overdrawn, fund moved to income, budget vs actual | `legal/compliance.py` |
| D. Compliance | 106C-11 fund rates & utilisation authority, 106C-12 interest / non-occupancy (settings and per-bill) and apportionment basis, 106C-13 / bye-law 157 work orders and repair payments above the committee limit, payments beyond resolution / work-order sanction (taking later approvals into account), 106C-10 borrowing, transfer premium, statutory calendar, missing audit report, 154B-29 / 106C-14 recovery readiness checklist (report only) | `legal/compliance.py`, `legal/calendar.py`, `legal/recovery.py` |
| E. Integrated agent | Same findings table (new columns `engine`, `compliance_category`, `legal_rule_code`, `legal_source`, `flat_id`, `vendor_id`); unified 8-class classification (Engine A's classes mapped); auto-resolve / re-open on re-scan; notifications via existing service; non-executable **remediation proposals** showing the 10 required items; deterministic question assistant (no AI API) that cites source, clause, effective date, verification and uncertainty | `legal/compliance.py`, `services/proposals.py`, `legal/assistant.py` |
| Worker | Daily per-society compliance scan inside the existing worker loop (`scan_due`, one society per transaction); `python -m app.modules.accounts_agent.worker --scan` | `worker.py` |
| F. Flutter | Compliance hub with the 12 sections, legal document library (documents / rules / reviews, upload, verify), resolutions, statutory calendar, member dues & recovery readiness, ask screen; findings list by section; finding detail shows "Which rule or bye-law applies" with verification state | `mobile/lib/features/accounts_agent/**` |

### Safety properties

* The scan and the assistant only read. A remediation proposal is `executable: false`; approving it records the decision
  (`ACKNOWLEDGED`) and changes no books — tested. Executable corrections remain the existing Engine A paths through
  `AccountsService` with maker-checker, fingerprints and audit.
* Recovery: the agent never issues notices or starts proceedings; every recovery response says so.
* Statutory taxes: applicability is `APPLICABLE` only when the society's own records show it (GST number / GST billing,
  TDS actually deducted); otherwise **"Professional verification required"**. Due dates are filled only for the AGM
  (30 September, marked to verify); others are left for the committee to set.
* Budget overrun is an `INTERNAL_POLICY_DEVIATION` and the text says it is not by itself an absence of authority.

## 2. Models and migration

Migration `c8f1e2d3a4b9` (down: `a1d2e3f4b5c6`): 8 new tables — `accounts_agent_legal_documents`, `_legal_profiles`,
`_legal_clauses`, `_legal_rules`, `_legal_reviews`, `_resolutions`, `_budget_lines`, `_compliance_items` — and 6 columns
added to `accounts_agent_findings`. No accounting table altered. Idempotent and reversible. The rule pack is seeded at
runtime, never by the migration.

## 3. API (prefix `/api/v1/accounts-agent`)

Read = manager and above; write/decide = admin/committee; jurisdiction-wide law = platform administrator only.
`GET|PUT legal/profile` · `GET legal/documents` · `POST legal/documents` (multipart) · `POST legal/jurisdiction-documents` (platform) ·
`GET legal/documents/{id}` · `GET …/file` · `GET …/clauses` · `POST …/verify` · `GET legal/hierarchy` · `GET legal/rules` ·
`GET legal/rules/{id}` · `POST legal/rules` (society rule) · `POST legal/rules/{id}/versions` · `POST legal/rules/{id}/verify` ·
`GET legal/applicable?topic&on_date` · `GET legal/reviews` · `POST legal/reviews/{id}/decide` · `GET|POST resolutions` ·
`PUT resolutions/{id}` · `POST resolutions/{id}/verify` · `POST resolutions/import-governance` · `GET|PUT budgets` ·
`POST compliance/scan` · `GET compliance/overview` · `GET compliance/calendar` · `PUT compliance/calendar/{id}` ·
`GET recovery/arrears` · `GET recovery/checklist/{flat_id}` · `POST assistant/ask`.
Existing `GET findings` gains `engine`, `classification`, `compliance_category`, `flat_id`, `vendor_id`, `section` filters.

Society isolation: society always from the authenticated user (a different `society_id` → 403); every row lookup
filters by society; jurisdiction rows are read-only to societies; a society rule can cite only its own document; the
worker scans one society per transaction.

## 4. Tests actually executed (this environment)

| Run | Result |
|---|---|
| `tests/accounts_agent` (SQLite): existing 53 + new legal registry 16, compliance 21, API/security 10 | **100 passed, 4 skipped** (PG-only tests) |
| `tests/accounts_agent/test_postgres_integration.py` on real **PostgreSQL 16** (incl. new end-to-end compliance scan) | **4 passed** |
| `scripts/ci/check_migrations.py full` on PostgreSQL 16 | **passed** (graph, empty→head, no drift, head down/up, earlier→head, /health/ready 200/503) |
| Whole remaining backend suite (all other `tests/*` dirs, 4 shards) | see §4.1 |
| `flutter analyze --no-fatal-infos` with Flutter **3.47.9** (CI's version) | **exit 0**; no warning/error in changed files |
| `flutter test` (whole mobile suite, incl. new `accounts_agent_legal_api_test.dart`) | see §4.1 |

### 4.1 Regression results

| Run | Result |
|---|---|
| Every other backend test directory (`auth`, `accounts`, `billing`, `vendor`, `security`, `governance`, `rbac`, `db`, `ci`, … 31 dirs + 2 root files), 4 parallel shards on SQLite | **1,996 passed, 1 skipped, 0 failed** |
| `flutter test` (Flutter 3.47.9), whole mobile suite | **854 passed, 0 failed** |

The backend shards ran before the last, agent-only change (the `section` filter on `GET findings`); that change is
covered by the re-run of `tests/accounts_agent` (100 passed). The full suite was not re-run after it.

## 5. Remaining limitations

* **Legal content is unverified** (§0). Upload the original Gazette as a primary source (platform admin), resolve the two
  discrepancy reviews against the Marathi text, then verify each rule with its page.
* 106C-7 and 106C-13 slab figures are not loaded; 106C-13 checks fall back to the society's procurement limits / model
  bye-law 157 and are labelled accordingly.
* Scanned PDF pages and photos (PNG/JPG) are read by OCR (Tesseract, Marathi + English) and legacy `.doc` files by
  antiword, when those tools are installed (`nixpacks.toml` installs them; without them the file is stored and flagged
  for manual transcription). OCR text is always marked for verification, with a confidence per page.
* Clause extraction is pattern-based; every clause is marked for human verification.
* Interest checking is an upper-bound test (exact recomputation of the billing calculator was not duplicated).
* Parking rate checking (A-PRK-06) covers full-period bills of flats holding their slots for the whole cycle with one
  parking head not priced from expenses; other cases are not judged. The parking module records no deposits or
  refunds, so there is nothing to reconcile for those.
* The assistant is keyword-matched; questions outside its intents get a list of what it can answer.
* Society rules are added, revised (new version, with history) and verified from Legal Library → Legal rules.
* Flutter screens were analysed and unit/widget-tested, not run on a device.

## 6. CI change

Backend CI caps the full suite at 5 skipped tests. The Accounts Agent's PostgreSQL-only tests were only ever skipped
there. They now run in the **Migrations (PostgreSQL 16)** job against its PostgreSQL service (`--max-skipped 0`), and
the SQLite full-suite step no longer collects that file. The PDF extraction test checks the "no `pdftotext`" fallback
(stored, flagged OCR_REQUIRED, no clauses) instead of skipping when the tool is missing.

## 7. Residential checks added later (`legal/residential_checks.py`)

| Rule | What it flags | Class |
|---|---|---|
| A-VEN-BANK-01 | A vendor's bank account / IFSC changed (any route: vendor screen, import, direct edit) within 180 days; HIGH when money was paid after the change or it changed twice in 90 days. Who/when from the vendor audit trail; first scan rebuilds recent changes from it. Account numbers are stored and shown masked (last 4 digits), with a SHA-256 fingerprint of account + IFSC (the bank's name is free text and ignored). | Suspected anomaly |
| A-HND-01 | After a change of owner, bills due before the transfer still unpaid on the flat | Missing documentation |
| A-HND-02 | The previous owner's unadjusted advance still on the flat | Suspected anomaly |
| A-HND-03 | No transfer premium / fee credited for the flat within four months of the transfer | Advisory |
| A-HND-04 | A new owner moved in while the earlier owner has no move-out date | Advisory |
| A-PRK-01 / 02 | Latest cycle: a held, chargeable slot not billed / parking billed with no slot held (two-wheeler rate and released slots respected) | Suspected anomaly |
| A-PRK-03 | One slot allotted to two flats for overlapping periods | Suspected anomaly |
| A-PRK-04 | An allotment pointing at another society's slot | Confirmed error |
| A-PRK-05 | Slots allotted but no parking charge head | Advisory |
| A-ADV-01 | A member's advance not set off while the flat has unpaid bills (with the amount that could be set off) | Suspected anomaly |
| A-ADV-02 | An advance unused for more than 180 days with nothing due | Advisory |

Migration `d4e6f8a0b2c4` adds `accounts_agent_vendor_bank_records` (the agent's own history). Nothing else is written;
no bill, receipt, vendor or voucher is changed. Tests: `tests/accounts_agent/test_residential_checks.py` (13).

## 8. Element → ledger against the society's own rules (`legal/ledger_mapping.py`)

Bills are posted with one standard table (`bill_line_ledger_key` / `ELEMENT_LEDGER`), the same for every society. The
agent now checks that table against each society's rules and reports where it does not fit:

| Rule | What it flags | Class |
|---|---|---|
| A-LED-01 | Recent bill lines credited to a ledger other than the society's **verified** element → ledger rule (topic `ledger.element.<code>`, from registered bye-laws, a General Body resolution or the accounting policy). The rule in force on each bill's date is used. | Potential non-compliance (bye-law) / internal policy deviation (policy) |
| A-LED-02 | Lines posted to a default ledger because the charge head has no element, or a custom element not in the standard table; MEDIUM when it lands in the catch-all "Other Charges Recovered" | Suspected anomaly / advisory |
| A-LED-03 | Bill lines whose description matches no charge head (e.g. head renamed after billing) | Suspected anomaly |
| A-LED-04 | Active charge heads with no element at all | Advisory |

`GET /accounts-agent/ledger-mapping` lists every active charge head with its element, the ledger it posts to and why,
the society's rule (verified or pending), what was posted in the last 100 days, and any bill lines matching no head.
`POST /accounts-agent/ledger-mapping/sign-off` (admin / committee) records a committee or auditor sign-off of the map
with its fingerprint; a later change shows the map as "changed since sign-off", and signing a map that changed since it
was shown is refused (409). Flutter: Compliance hub → "Element → ledger map" (rows, "Set society rule", sign-off).

The posting table itself is unchanged: a society rule changes what the agent checks against, not how bills post. A
difference is corrected by a person (re-linking the charge head's element in Billing and a journal), never by the agent.

## 9. Follow-ups

* **Rule revisions in the app**: Legal rules → "Revise" shows every version and saves a new one (new figure / ledger,
  clause, page, text, effective date, reason). The earlier version is kept and closed the day before.
* **OCR and .doc** (`legal/documents.py`): pages with no text layer are rendered (poppler) and read by Tesseract
  (`mar+eng`), with a mean word confidence per page; photos of documents are read the same way; `.doc` via antiword.
  Quality `OCR_TEXT` (or `POOR` below 60 % confidence); verifying such a document needs a note on how it was checked.
  Backend CI installs the same tools, so the OCR tests run against the real engine.
* **Parking rate check** (A-PRK-06): the bill's parking amount against the slots held, priced the way the billing
  calculator prices them (slot charge → zone rate for cars → head rate / two-wheeler rate, × months in the cycle).
* **Ownership transfer**: `POST /occupancy/ownership-transfer` (admin / committee) and "Transfer ownership" on a
  resident: the previous owner(s) move out on the date (vehicles unassigned as on any move-out), the new owner becomes
  primary, and an `OWNERSHIP_TRANSFER` entry (with share-certificate / deed references) is written. The agent's
  handover checks use the recorded event, falling back to move-in / move-out dates when none was recorded.
