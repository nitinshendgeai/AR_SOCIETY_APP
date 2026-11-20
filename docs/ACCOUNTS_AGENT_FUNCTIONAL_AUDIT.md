# Accounts Agent — End-to-End Functional Audit

**Date:** 20 Nov 2026 · **Code audited:** `main` at `95cc7ab` · **Method:** I ran the real app and recorded what it did. Nothing in this report is taken on trust from the code alone.

No application code was changed during this audit. No production data was touched: every test ran against a separate PostgreSQL 16 database (`audit_e2e`). That database was built with the app's own Alembic migrations and filled only through the public HTTP API (registration, vouchers, approvals, billing). The real outbox worker processed the events, run as `python -m app.modules.accounts_agent.worker --once`. Every action went through the existing accounting services, RBAC, tenant scoping, maker–checker approval and audit log. Nothing was written to the database directly.

---

## 1. Executive assessment

**The agent really analyses the society's books. It does not show canned results.** Every finding seen in the test was computed from the data entered during the test, and each figure can be checked:

- The sinking fund overdraft was reported as ₹49,910. I worked it out separately from the ledger and got the same ₹49,910.
- The recurring-expense finding quoted the three earlier lift payments that were seeded: ₹4,500 ×3, median ₹4,500.
- The vendor-ledger finding quoted "3 of 3 earlier postings → Housekeeping & Cleaning".
- The learning summary shows exactly 50 vouchers learned from. That is the 52 seeded vouchers minus the one pending and the one cancelled voucher, which are correctly excluded.
- A second society with only 3 vouchers is clearly marked "limited history" and gets no statistical findings.

**The core controls are sound and were proved under test:**
- **Tenant isolation:** every cross-society call was refused.
- **Proposals:** they need explicit confirmation, are refused if the voucher has changed since (stale check), and run through `AccountsService`.
- **Outbox:** writes are atomic with the voucher; failed jobs retry with backoff, go to a dead-letter queue, and are de-duplicated.
- **Legal certainty:** no legal rule is treated as verified, and no legal finding was ever shown as a confirmed violation.

**It is not yet reliable enough to be trusted on its own.**
- **Precision:** a routine monthly housekeeping payment was flagged as a "possible duplicate" (false positive), and a society registered today is told its 2025-26 AGM is overdue.
- **Recall:** an exact duplicate payment disappears from the findings once its vendor tag is removed. A member receipt booked to the wrong flat was not detected at all (false negatives).
- **Legal wording:** one finding presents a model bye-law figure (₹25,000) as "the committee's limit", even though the governing rule's own figure is unverified and blocked.

**Overall:** good analytics engine, sound safety controls, with **2 Critical-for-trust (High) detection defects, 4 High, 9 Medium and 7 Low** (§9). None of them needs a rewrite. Each is a targeted fix in a named function.

| Area | Verdict |
|---|---|
| A. Accounting intelligence | **Partially working.** 7 of 9 accounting scenarios detected correctly; 1 false positive (S7) and 1 false negative (S4). The duplicate rule can be bypassed by removing the vendor tag. |
| B. Historical learning | **Working.** Correct 3-month window and correct exclusions. Confidence is reported honestly. |
| C. Real-time monitoring | **Working**, with one operational gap: `--once` processes only one batch, and the "Degraded" state can never be cleared. |
| D. Maharashtra legal compliance | **Safe but noisy.** Certainty classes are enforced. One figure is presented as binding when it is not. Calendar items for a new society are false alarms. |
| E. Findings & recommendations | **Working.** Evidence, legal source and proposals all work end to end. The proposer can approve their own proposal. |
| F. Flutter UX | **Working with real data**, no mock data. Finding history is not shown, and legal categories cannot be filtered. |

---

## 2. Implemented vs actually working

| Capability (code exists) | Executed? | Actually works? |
|---|---|---|
| Transactional outbox (`services/outbox.py`, `after_flush`) | Yes | **Yes.** All 52 seeded vouchers produced `voucher.created` events, plus 21 `approval_changed` and 1 `cancelled`. A rolled-back voucher produced no event. |
| Worker claim / retry / dead letter (`worker.py`) | Yes | **Yes.** Backoff 30 s, dead after 6 attempts, admins notified. **But** `--once` stops after 50 events (24 were left pending). |
| Learning (`services/learning.py`) | Yes | **Yes.** 50 vouchers, 33 patterns, 4 months, 75 days, confidence "moderate". Pending and cancelled vouchers excluded. |
| Engine A rules (`services/rules.py`, `anomaly.py`) | Yes | **Mostly.** R-DUP-02, S-MAP-01, S-REC-01, S-AMT-01 and S-PAIR-01 all fired correctly. R-DUP-04 false positive. R-DUP-02 bypassed by removing the vendor tag. |
| Engine B compliance scan (`legal/compliance.py`) | Yes (28 checks, 0 check failures) | **Mostly.** Fund misuse, fund overdraft and repair-without-approval detected. One wording defect, one false alarm on the calendar. |
| Legal registry classification (`legal/registry.py`) | Yes | **Yes.** 0 verified / 14 unverified. Unverified rules give at most POTENTIAL; the model bye-law gives ADVISORY. Rule versions resolve by date. |
| Proposals (`services/proposals.py`) | Yes | **Yes.** `edit_voucher` executed, re-verified, and the finding auto-resolved. `cancel_voucher` was refused as STALE after an edit. **But** there is no separation between the person who proposes and the person who approves. |
| Notifications (`services/notify.py`) | Yes | **Yes.** Only the admin and committee of the same society receive them. |
| Finding audit history (`GET /findings/{id}/history`) | Yes (API) | API works. **Not shown in Flutter.** |
| Member-ledger reconciliation | Scenario S4 | **Not implemented** for manual receipt vouchers. |
| Optional LLM explanation (`services/llm.py`) | Inspected | Off by default. No provider is registered and no key is read. All findings are deterministic. |
| Flutter screens (`features/accounts_agent`) | Yes, release web build in Chromium | **Yes.** Real API data appears on the dashboard, compliance hub, findings list and detail, learning and proposals screens. |

**Automated tests (executed):**
- Backend `tests/accounts_agent`: **171 passed, 5 skipped** (SQLite).
- The 5 skipped PostgreSQL integration tests: **5 passed** when run against a throwaway PG database.
- Flutter agent tests (4 files): **21 passed**.

None of these tests covers the defects listed in §9. The tests pass, but they do not exercise those paths.

---

## 3. Test scenarios and evidence

**Test data:**

| Item | Society A (`AUDITA`) | Society B (`AUDITB`) |
|---|---|---|
| Flats | 6 (650–1,200 sq ft) | — |
| Vendors | 4 | — |
| Payment history | 3 months: security ₹25,000, housekeeping ₹12,000, lift ₹4,500, electricity, office expenses | 3 vouchers |
| Billing | 3 billing cycles (₹2,020 per flat); flats 101–104 paid, 105–106 in arrears | — |
| Traps | One pending voucher (PV/0021, ₹99,000) and one cancelled voucher (PV/0022, ₹88,000) | — |

**How each scenario was run:** entered through the API → approved by a different committee member → real worker run → `POST /accounts-agent/compliance/scan`.

| # | Scenario | Input | Expected | Actual | Result |
|---|---|---|---|---|---|
| 1 | Duplicate vendor payment | PV/0023 then an identical PV/0024 (same reference `SG-NOV-26`); PV/0025 with no reference | Confirmed duplicate; a suspected one for the copy with no reference | R-DUP-02 **CONFIRMED HIGH** on 0024; R-DUP-04 ×2 + A-VEN-DOC-01 on 0025 | **PASS** |
| 2 | Incorrect ledger | CleanPro ₹12,000 debited to *Repairs — Plumbing* (PV/0026) | Mapping anomaly | S-MAP-01 MEDIUM ("3 of 3 earlier → Housekeeping"), S-PAIR-01 LOW | **PASS** |
| 3 | Unusual recurring amount | LiftCare ₹45,000 (PV/0027) against a ₹4,500 history | Recurring deviation | S-REC-01 HIGH, median ₹4,500, deviation 900% | **PASS** |
| 4 | Member receipt on the wrong flat | RV/0013 credits ₹2,020 to flat 101 (fully paid) for money from flat 105 | Over-collection on 101 / unexplained credit | **No finding** | **FAIL** (false negative) |
| 5 | Sinking fund misuse | ₹50,000 paid from the Sinking Fund (PV/0028), no resolution | Fund misuse + overdraft | L-FND-USE-01 POTENTIAL HIGH; A-FND-BAL-01 HIGH "overdrawn ₹49,910" (checked independently) | **PASS** |
| 6 | Expense without approval evidence | Building repair ₹1,50,000, no reference (PV/0029) | Potential non-compliance; missing document | L-EXP-REP-01 POTENTIAL HIGH + A-VEN-DOC-01 | **PASS** (detection). Wording defect D-03. |
| 7 | Normal recurring transaction | Housekeeping ₹12,000, ref `CP-NOV-OK` (PV/0030); electricity (PV/0031) | No finding | Electricity: none ✓. Housekeeping: **R-DUP-04 "Possible duplicate payment"** against PV/0026 even though the references differ | **FAIL** (false positive) |
| 8 | Insufficient history | Society B (3 vouchers) + a ₹45,000 office expense | Marked "limited"; no false statistics | `limited=true`, confidence "limited", no statistical findings | **PASS** (false-negative risk noted in §5) |
| 9 | Cross-society access | Society B's admin tries to reach Society A's data | Refused | Finding 404; list with `society_id=A` 403; propose 404; ledger map 403; dashboard 403; voucher 404. B sees only its own 5 findings | **PASS** |
| 10 | Stale proposal | Treasurer proposes cancelling PV/0024 → PV/0024 is edited → Chairman approves with `confirm:true` | Refused, nothing applied | Approving without `confirm` → 422. After the edit → **409 STALE**; voucher not cancelled | **PASS** (side defect D-02) |

**Additional executed checks:**

| Check | Result |
|---|---|
| **C1** Roll back a voucher | No voucher and no event left behind ✓ |
| **C2** Inject a failure into a job | `failed` → not retried before the 30 s backoff → succeeded after it ✓ |
| **C3** Six failures | `dead`, and the admin and committee notified ✓ |
| **C4** Reprocess the same event | No duplicate finding (unique `uq_agent_event_idem` + dedupe key) ✓ |
| **C5** First `--once` run | 50 events done, **24 left pending**; a second run drained them (D-08) |
| **D1** Interest cap by date | Ceiling resolves to 21% (v1, SUPERSEDED → ADVISORY) on 2026-05-01 and to 12% (v2 → POTENTIAL) on 2026-07-01 ✓ |
| **D2** Committee limit rule | `MH-EXP-106C13-LIMIT` has value `None` and is blocked by an open review; no CONFIRMED legal finding exists ✓ |
| **E1** Executable proposal | `edit_voucher` proposal on S-MAP-01 approved with `confirm:true` → executed through `AccountsService.update_manual_voucher`; the voucher went back to *pending approval*; the agent re-checked it and the finding became `RESOLVED / REVIEWED_RESOLVED`; history shows `finding_created → proposal_created → proposal_approved → proposal_verified` ✓. **The admin who created it was allowed to approve it** (D-09). |
| **F1** Flutter web release build, real API | Login → forced password change → setup wizard → agent dashboard. All 12 screenshots show live data. Legal findings display "Legal review required" and "Unverified" badges ✓ |

---

## 4. Failed or incomplete

1. **S4 — misposted member receipt not detected.** There is no check that compares the member sub-ledger in vouchers with the bills issued. `A-ADV-01` (`legal/residential_checks.py::chk_unadjusted_advances`) reads only billing-side allocations (`PaymentAllocator.society_unapplied`). A manual receipt voucher credited to a flat is never seen. `MemberARService.society_reconciliation` already exists but the agent does not use it.
2. **S7 — routine payment flagged as a duplicate.** See D-01.
3. **Exact duplicate disappears after the vendor tag is removed.** After PV/0024 was edited and its vendor tag dropped, the confirmed duplicate R-DUP-02 auto-resolved ("No longer detected"). The voucher still had the same date, amount, ledgers and reference as PV/0023. See D-02.
4. **`worker --once` does not drain the queue** as its docstring says. See D-08.
5. **"Degraded" can never be cleared.** One dead event leaves the dashboard showing "Degraded — 1 job(s) failed" for good. No API exists to requeue or acknowledge dead events. See D-10.
6. **Finding history is not shown in Flutter.** The API works; the UI never calls it. See D-11.

---

## 5. False-positive and false-negative risks

| Risk | Type | Cause | Effect |
|---|---|---|---|
| Monthly payments of the same amount to the same vendor within 3 days, with **different** references | FP | R-DUP-04 fires on `not same_ref`, which includes the case where both references are present and different | Alert fatigue on legitimate payments (rent, salaries, AMC instalments) |
| Statutory calendar items for years before the society existed | FP | `legal/calendar.py::ensure_items` always creates last year's items; `chk_calendar` flags them as overdue | A society registered today is told its 2025-26 AGM and audit are overdue (HIGH) |
| Interest finding that blames the rate rather than the period | FP-ish | `chk_bill_interest` limits by `bill_date`. The billing calculator charged interest up to the generation date (66 days rather than 16) | The finding is correct but its explanation points to the wrong cause |
| Duplicate with the vendor tag removed or changed | **FN** | `context.fingerprint` includes `vendor_id`; R-DUP-03 is skipped when the references are equal | An exact duplicate can be hidden by editing one field |
| Member receipt on the wrong flat | **FN** | No reconciliation between the sub-ledger and the bills | Misallocated dues go unnoticed |
| Large one-off expense in a young society | **FN** | Statistical rules are switched off while history is limited, and there is no deterministic absolute-size check | Society B's ₹45,000 office expense (normal is ~₹1,000) produced nothing |
| Stale partner finding | FP (minor) | When one voucher of a pair is edited, the other voucher's pair findings are not re-checked | R-DUP-04 (0025 vs 0024) stayed NEW after 0024 changed |
| Unapproved vouchers analysed | Neutral | Engine A runs on `voucher.created`, including pending vouchers | S-AMT-01 HIGH on PV/0021, which was never approved. Useful as an early warning, but not labelled "pending" in the title |

---

## 6. Security and isolation

**Verified by execution:**
- Every agent endpoint I called while logged in as Society B returned 404 or 403 for Society A's resources, including findings, proposals, the ledger map and the dashboard.
- The findings list is scoped by the token's society.
- Notifications went only to the admin, chairman, secretary and treasurer of the society concerned (A: 7 each, B: 2 each).
- Proposals cannot run without `confirm:true` (422).
- A stale voucher is refused (409) under a row lock.
- Corrections run as the approving user through `AccountsService`. The closed-year lock, voucher revisions and the accounting audit log all apply, and the edited voucher went back to *pending approval*.

**Gaps:**
- **D-09 — No separation of duties on proposals.** `services/proposals.py::approve_proposal` does not check `decided_by != created_by`. The admin who created the proposal approved it.
  - *Mitigation already present:* an `edit_voucher` correction sends the voucher back to normal approval.
  - *Not mitigated:* `cancel_voucher` takes effect immediately. It is no wider than what the same user can already do directly through `POST /accounts/vouchers/{id}/cancel`, but the proposal workflow promises a second person and does not enforce one.
- **D-15 — Misleading error message.** Reading with another society's `society_id` returns 403 "Cannot create resources for another society". The read endpoints reuse `tenant_scope.resolve_create_society_id`.
- **The optional LLM is safely boxed in** (`services/llm.py`). It gets no database session, no user and no society ID, and no provider is registered.

---

## 7. Legal-source reliability

- **Registry state (live API):** 0 verified rules, 14 unverified. The Act and Rules are `PENDING` or `LEGAL_REVIEW_REQUIRED`; the model bye-laws are `MODEL_REFERENCE`.
- **Classification works.** Only `ADVISORY_OBSERVATION`, `LEGAL_SOURCE_CONFLICT`, `MISSING_DOCUMENTATION` and `POTENTIAL_NON_COMPLIANCE` appeared. No legal finding was `CONFIRMED`.
- **Versioning works.** The interest ceiling changes from 21% to 12% by date, as expected.
- **Legal figures hard-coded outside the registry.** These are not governed by verification status:
  - `vendor/services/work_orders.py::bye_law_slab`: ₹25,000 / ₹50,000 / ₹1,00,000 by number of members (model bye-law 157). `procurement_limits` uses it as the committee limit. `legal/compliance.py::chk_repair_payments` and `chk_work_orders` both use it as the trigger threshold and quote it as *"The committee's limit is ₹25,000"*. Meanwhile the cited source `MH-EXP-106C13-LIMIT` has no value and is blocked (**D-03**).
  - Billing API caps in `MaintenanceSettingsUpdate`: interest ≤ 21%, non-occupancy ≤ 10%. These are validators, not registry rules.
  - Calendar due dates in `legal/calendar.py::_templates`: AGM by 30 September, already labelled "commonly cited … verify".
- **Assistant wording.** The assistant's `fund_use` answer states the approving authority in confident language. The `uncertainty` field is present, but the prose does not say "unverified" (D-13).
- **Member count.** `member_count` counts active flats as members. Co-owned or vacant flats would distort the slab.

---

## 8. Backend and Flutter integration gaps

| Gap | Where |
|---|---|
| Finding audit history is never displayed | `mobile/lib/features/accounts_agent/presentation/screens/agent_finding_detail_screen.dart` does not call `GET /accounts-agent/findings/{id}/history` (D-11) |
| The category filter lists Engine A categories only; legal categories (expenditure, funds, charges, statutory compliance…) cannot be filtered | `agent_findings_screen.dart` hard-codes `_categories` (D-16) |
| A resolved finding's detail page labels the voucher "**Original** voucher" but shows its **current** lines (Housekeeping), while the explanation describes the old posting (Plumbing) | finding detail screen and `queries.finding_dict` voucher block (D-17) |
| Evidence shows raw UUIDs ("Usual Ledger Id 6cbf1bb4-…") instead of ledger names | `services/anomaly.py` S-MAP-01 evidence and generic evidence rendering (D-18) |
| The financial-health card shows only dues, defaulters and pending approvals; no fund or bank balances, although the agent computes fund balances | compliance hub screen and `routes/legal.py` dashboard (D-12) |
| No UI or API to requeue or acknowledge dead events, so "Degraded" sticks | `services/queries.py::status`, worker (D-10) |

---

## 9. Prioritised defect list

Severity reflects the effect on the trustworthiness of the agent's output for a society. "Critical" is reserved for defects that corrupt books, leak data or bypass approvals; **none were found**.

### Critical
None found.

### High

| ID | Defect | Responsible component | Evidence |
|---|---|---|---|
| D-01 | **R-DUP-04 flags payments whose references differ.** Routine same-amount payments become "possible duplicates", and the explanation wrongly says "no matching reference to show they are different bills". | `backend/app/modules/accounts_agent/services/rules.py::check_duplicates`, R-DUP-04 branch (`… and not same_ref`). It should require at least one reference to be **missing**. | S7: PV/0030 (`CP-NOV-OK`) vs PV/0026 (`CP-NOV-26`) |
| D-02 | **An exact duplicate is hidden by removing or changing the vendor tag.** R-DUP-02 fails because `fingerprint` includes `vendor_id`; R-DUP-04 needs a vendor; R-DUP-03 is skipped when `same_ref`. So no rule fires. | `services/rules.py::check_duplicates` (R-DUP-03 `and not same_ref`); `services/context.py::fingerprint` | S10 side effect: R-DUP-02 auto-resolved after the edit, with the duplicate still in the books |
| D-03 | **A model bye-law figure is presented as the binding committee limit.** The ₹25,000 hard-coded slab triggers the finding and is quoted as "The committee's limit", while the cited rule is unverified and blocked. | `legal/compliance.py::chk_repair_payments`, `chk_work_orders`; `vendor/services/work_orders.py::bye_law_slab`, `procurement_limits` | S6 finding text and screenshot `07_finding_legal` |
| D-04 | **Member receipt on the wrong flat goes undetected.** There is no sub-ledger vs bills reconciliation. | Missing check: `legal/residential_checks.py` (A-ADV-01 reads billing allocations only); `MemberARService.society_reconciliation` is unused by the agent | S4 |

### Medium

| ID | Defect | Responsible component |
|---|---|---|
| D-05 | Overdue alarms for financial years before the society existed (AGM, audit report) | `legal/calendar.py::ensure_items` (always creates the previous year); `legal/compliance.py::chk_calendar` and the L-AUD-01 block (no check of registration or onboarding date) |
| D-06 | The interest finding blames the rate; the real cause is interest charged up to the generation date for back-dated cycles | Explanation text: `legal/compliance.py::chk_bill_interest`. Root cause, outside the agent: `billing/services/maintenance_calculator.py` interest period end (`interest_working` "to" = generation date) |
| D-07 | No absolute or deterministic large-amount check while history is limited, so a new society gets no outlier coverage | `services/anomaly.py` (S-AMT-01 gated on learned profile); `services/learning.py` limited mode |
| D-08 | `worker --once` processes one batch of 50, not "what is due", as its docstring and `--help` say | `backend/app/modules/accounts_agent/worker.py::main` / `run_once` (`BATCH_SIZE=50`) |
| D-09 | The proposer can approve their own proposal (no maker–checker on proposals) | `services/proposals.py::approve_proposal` (no `p.created_by != user.id` check) |
| D-10 | One dead event makes the agent "Degraded" for good; no requeue or acknowledge | `services/queries.py::status` (`dead > 0 → degraded`); no route in `routes/accounts_agent.py` |
| D-11 | Finding audit history is not shown in the app | `agent_finding_detail_screen.dart` + `data/accounts_agent_api.dart` (no history call) |
| D-12 | The financial-health card omits fund and bank balances | `compliance_hub_screen.dart`; legal dashboard payload in `routes/legal.py` |
| D-13 | The assistant's `fund_use` answer states authorities in confident wording although the rule is unverified | `legal/assistant.py` answer templates |

### Low

| ID | Defect | Responsible component |
|---|---|---|
| D-14 | When one voucher of a pair is edited, the other voucher's pair findings are not re-checked, so stale R-DUP-04 findings remain | `services/engine.py` event handling (only the edited voucher is re-analysed) |
| D-15 | Read endpoints return "Cannot create resources for another society" | `tenant_scope.resolve_create_society_id` reused by `routes/accounts_agent.py::_sid` / `routes/legal.py` for GETs |
| D-16 | Findings category filter misses legal categories | `mobile/lib/features/accounts_agent/presentation/screens/agent_findings_screen.dart` `_categories` |
| D-17 | A resolved finding shows the current voucher under the heading "Original voucher" | Flutter finding detail screen / `queries.finding_dict` |
| D-18 | Raw UUIDs in the evidence section | `services/anomaly.py` S-MAP-01 evidence keys; evidence renderer in the finding detail screen |
| D-19 | Pending (unapproved) vouchers are flagged with no "pending" marker in the title | `services/engine.py` / finding title builders |
| D-20 | `member_count` = active flats is used as the number of members for the bye-law slab | `vendor/services/work_orders.py::member_count` |

**Observation outside the agent:** for back-dated cycles the billing calculator accrues interest up to the generation date rather than the bill date (`billing/services/maintenance_calculator.py`). The agent correctly flagged the result (INV-2026-27-00011/12: ₹43.83 charged against a ₹10.63 bound).

---

## 10. Remediation plan

Each step is a targeted fix with a regression test that reproduces the audit scenario. No refactor is proposed.

**Phase 1 — detection correctness (High, about 2–3 days)**
1. **D-01:** In R-DUP-04, replace `not same_ref` with "at least one reference is empty". Test: same vendor and amount with different references → no finding; with one reference missing → R-DUP-04.
2. **D-02:** Make R-DUP-03 fire whenever the line signatures match, whatever the vendor tag. Add an R-DUP-02 variant keyed on date, amount, lines and reference *without* `vendor_id`, or drop `vendor_id` from `fingerprint` and compare it separately. Test: duplicate → remove vendor tag → finding persists.
3. **D-03:** In `chk_repair_payments` and `chk_work_orders`, keep the slab as the *trigger* but word it from the registry. When the governing rule has no verified value, say "the model bye-law suggests ₹25,000 (unverified; your registered bye-laws may differ)". Quote `committee_limit` as binding only when `committee_limit_set` is true.
4. **D-04:** Add a check (Engine B) that reconciles each flat's member-ledger balance from vouchers against outstanding bills, reusing `MemberARService.society_reconciliation`. Flag credits on flats that owe nothing. Test: S4.

**Phase 2 — noise and operations (Medium, about 3 days)**
5. **D-05:** In `ensure_items` and `chk_calendar`, skip financial years that ended before the society's onboarding date, or mark them `NOT_APPLICABLE` until the society confirms them.
6. **D-06:** Reword L-CHG-INT-02 to show the days charged against the days allowed. Raise the billing period issue with the billing module owners as a separate ticket.
7. **D-07:** Add a deterministic "large one-off vs society size" advisory that also runs in limited mode.
8. **D-08:** Make `--once` loop `run_once` until a pass claims nothing, or correct the docstring and help text.
9. **D-09:** Refuse approval when `user.id == p.created_by` for executable actions. If needed, make it configurable for single-admin societies.
10. **D-10:** Add `POST /accounts-agent/events/requeue-dead` (admin only, audited). Base "degraded" on recent dead events or on unacknowledged ones.
11. **D-11 / D-12 / D-13:** Show history on the finding detail screen, add fund and bank balances to the health card, and prefix assistant answers built on unverified rules with "Unverified:".

**Phase 3 — polish (Low)**
12. D-14 to D-20 as listed. Re-run scenarios 1–10 with the harness after each phase, and add S4, S7 and the vendor-tag case to `backend/tests/accounts_agent/test_detection.py`.

---

### Appendix — how to reproduce
- **Database:** an empty PostgreSQL database; `alembic upgrade head`. API run with `APP_ENV=test SCHEDULER_ENABLED=false uvicorn app.main:app`.
- **Seed:** register two societies via `POST /public/register`. Create committee users. Enter vendors, vouchers, billing elements and cycles via the API. Approve with a second committee member.
- **Analysis:** run `python -m app.modules.accounts_agent.worker --once` (twice; see D-08), then `POST /accounts-agent/compliance/scan`.
- **UI:** `flutter build web --release --no-web-resources-cdn --dart-define=API_BASE_URL=…`, driven with Playwright (Chromium).
- **Tests:** `pytest tests/accounts_agent` (171 passed, 5 skipped); `AGENT_TEST_PG_URL=… pytest tests/accounts_agent/test_postgres_integration.py` (5 passed); `flutter test` on the 4 agent test files (21 passed).
