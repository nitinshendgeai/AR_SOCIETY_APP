# Accounts Agent — Remediation Report

**Date:** 20 Nov 2026
**Fixes the audit in:** `docs/ACCOUNTS_AGENT_FUNCTIONAL_AUDIT.md`
**Pull requests:**

| PR | Covers |
|---|---|
| nitinshendgeai/ar_society_app#282 | The audit report itself (merged) |
| nitinshendgeai/ar_society_app#283 | Phases 1–2 of the fixes |
| Follow-up PR | Phases 3–4 of the fixes |

The architecture is unchanged:
- The accounting engine, the legal registry, the outbox and worker, and the proposal workflow are all still in place.
- Every correction still runs through `AccountsService`.
- No financial record is changed automatically.
- Tenant scoping, RBAC and audit logging apply to everything new.

Every fix has a regression test. Every result below was produced by actually running the test or scenario.

---

## 1. Defects fixed

| ID | Before (audited behaviour) | After | Main change |
|---|---|---|---|
| D-01 | R-DUP-04 flagged two monthly payments whose references differed (CP-NOV-26 vs CP-NOV-OK) | Two different non-empty references count as two different bills. A pair is flagged only when at least one reference is missing, and the explanation names which one | `services/rules.py::check_duplicates` |
| D-02 | Removing the vendor tag from an exact duplicate made R-DUP-02 auto-resolve | Duplicates are compared on date, amount, ledger lines (ignoring vendor tags) and reference. The vendor tag only adjusts confidence. Conflicting tags downgrade the pair to R-DUP-03; they never clear it. A re-classification is recorded as such. The partner voucher is re-checked when one side changes | `rules.py::check_duplicates`, `content_key`, `vendor_of`; `services/engine.py::reanalyse_related`, `resolve_cleared`, `_closing_note` |
| D-03 | A model bye-law ₹25,000 figure was quoted as "the committee's limit" | Thresholds resolve through the registry, in this order: a statute with a loaded figure, then the society's own verified rule, then its explicit procurement setting, then the model bye-law. The figure is labelled with its source. Classification follows the figure's source: model → advisory; setting → internal-policy deviation; unverified statute → potential issue at most | `legal/compliance.py::committee_threshold`, `threshold_draft`, `chk_repair_payments`, `chk_work_orders` |
| D-04 | A manual receipt posted to the wrong flat raised no finding | New check **A-MAR-01** reuses `MemberARService.society_reconciliation`. It flags a credit on a flat's ledger that its bills don't explain, and lists the manual receipts and the flats that could be the real payer. **A-MAR-02** is an advisory for other ledger/billing differences. Cancelled and reversed receipts are ignored. A society whose bills were never posted to the ledger is not flagged flat by flat. Wording is "may be", never "is" | `legal/residential_checks.py::chk_member_ledger_reconciliation` |
| D-05 | A society registered today was told its 2025-26 AGM and audit were overdue | Years that ended before the **registration date** are NOT_APPLICABLE. Years before the **onboarding date** (registration not recorded) become "confirm whether it applies" (advisory, LOW). Overdue items say "overdue". A person's own edits are never overwritten | `legal/calendar.py::obligation_start`, `_before_start`, `ensure_items`, `_untouched`; `compliance.py::chk_calendar` |
| D-06 | The interest finding blamed the rate when the period was wrong | The finding reads the bill's interest working and names the cause: RATE, PERIOD (with the number of days past the bill date), both, or UNKNOWN. Billing is unchanged; see §7 | `compliance.py::interest_cause`, `chk_bill_interest` |
| D-07 | A new society got no large-expense check at all | **R-AMT-LIM-01** runs only while learning is "none" or "limited". It compares the expense with the largest earlier posting to the same ledger (≥10×, above ₹10,000), or with an absolute ₹1,00,000 where there is no earlier posting. It is informational and claims no statistical confidence | `services/rules.py::check_large_expense_limited_history` |
| D-08 | `worker --once` processed only one batch of 50 | `--once` drains every due batch. It is capped at 1,000 passes; a failing event backs off, so the loop always stops | `worker.py::drain`, `main` |
| D-09 | The proposer could approve their own correction | For executable actions (cancel or edit), the proposer's approval is refused with 403 and audited. The approval audit records who proposed, who approved, the action, the time and the voucher. A society with no second authorised person gets a clear message. There is no bypass. Withdrawing (rejecting) one's own proposal is still allowed | `services/proposals.py::assert_maker_checker`, `other_approvers`, `approve_proposal` |
| D-10 | One dead event left the agent "Degraded" for good | `GET /accounts-agent/events/dead`, `POST /events/{id}/requeue` (at most 3 per event) and `POST /events/{id}/acknowledge` (note required). All are admin/committee only, society-scoped and audited. Acknowledged failures no longer degrade monitoring. Status reports recent and acknowledged counts separately | `services/event_recovery.py`, `routes/accounts_agent.py`, `services/queries.py::status`, `worker.py` (`dead_at`) |
| D-11 | Finding history was available in the API but not in the app | A History section on the finding screen | `agent_finding_detail_screen.dart::_History`, `accounts_agent_api.dart::findingHistory` |
| D-12 | The health card showed only dues | Bank, cash and fund balances, read from `AccountsService.balances` (approved vouchers and opening balances). Overdrawn funds are marked | `routes/legal.py::_fund_and_bank_balances`, `compliance_hub_screen.dart` |
| D-13 | The assistant stated authorities in confident language | An answer based on any unverified source starts with "UNVERIFIED — …" and carries `answer_unverified` | `legal/assistant.py::ask` |
| D-14 | A stale pair finding stayed open when its partner voucher changed | Covered by `reanalyse_related` (D-02) | `services/engine.py` |
| D-15 | Reads from another society returned "Cannot create resources for another society" | Now: "You can only view or act on your own society's Accounts Agent data." The shared helper is untouched | `routes/accounts_agent.py::_sid`, `routes/legal.py::_sid` |
| D-16 | The category filter could not select legal categories | All legal and residential categories added | `agent_findings_screen.dart::_categories` |
| D-17 | "Original voucher" showed the current lines | Each finding keeps a snapshot of the voucher as it was when raised. The app shows "when the finding was raised" and "now" side by side when they differ | `services/context.py::voucher_snapshot`; `engine.store_findings`; `compliance.store`; `routes/accounts_agent.py::finding_detail`; detail screen |
| D-18 | Evidence showed raw IDs | `evidence_display` resolves ledger, vendor, voucher and flat IDs to names, within the society only, and drops duplicate rows | `services/queries.py::evidence_display` |
| D-19 | A finding on an unapproved voucher looked the same as any other | Lists and details carry the voucher's approval status, and the app shows "Voucher not yet approved" | `queries.list_findings`; findings and detail screens |
| D-20 | Committee slab members counted as active flats | Members come from the membership recorded in the legal profile; otherwise from flats with an active owner or co-owner; otherwise from active flats. The basis is always stated | `vendor/services/work_orders.py::member_count_with_basis` |

---

## 2. Files changed

**Backend, Accounts Agent:**
- `services/rules.py`, `services/engine.py`, `services/context.py`, `services/proposals.py`, `services/queries.py`
- `services/event_recovery.py` (new)
- `worker.py`, `models/agent.py`
- `routes/accounts_agent.py`, `routes/legal.py`
- `legal/compliance.py`, `legal/calendar.py`, `legal/residential_checks.py`, `legal/assistant.py`

**Backend, other:**
- `backend/app/modules/vendor/services/work_orders.py`: member count only. The procurement module's own rules are unchanged.

**Flutter:**
- `features/accounts_agent/data/accounts_agent_api.dart`
- `presentation/providers/accounts_agent_providers.dart`
- `presentation/screens/`: `agent_finding_detail_screen.dart`, `agent_findings_screen.dart`, `compliance_hub_screen.dart`, `agent_proposal_screen.dart`, `agent_learning_screen.dart`, `accounts_agent_dashboard_screen.dart`

**Tests:**
- Backend: `tests/accounts_agent/test_remediation_detection.py`, `test_remediation_legal_approval.py`, `test_remediation_monitoring.py`, `test_remediation_presentation.py`, and additions to `test_postgres_integration.py`
- Flutter: `mobile/test/accounts_agent_remediation_test.dart`

**Existing tests updated, not weakened:**
- 7 proposal tests in `test_api_security.py` now approve as a second committee member (`Rig.chair`).
- 2 tests in `test_legal_compliance.py` asserted the audited model-figure behaviour and now assert the corrected classification.
- 2 calendar tests now record a past registration date, which their scenario assumes.

## 3. Database migrations

`backend/alembic/versions/e5f7a9b1c3d5_agent_dead_event_recovery.py` (revises `d4e6f8a0b2c4`).
- Adds nullable or defaulted columns to `accounts_agent_events`: `dead_at`, `requeue_count`, `acknowledged_at`, `acknowledged_by`, `acknowledge_note`.
- It is idempotent, and no existing data changes.
- Executed on PostgreSQL 16: `upgrade head` → columns present → `downgrade -1` → columns gone → `upgrade head` again. All succeeded.

No other migrations. The voucher snapshot is stored inside the finding's existing `evidence` JSON.

## 4. Tests executed (actual results)

| Suite | Result |
|---|---|
| Backend `tests/accounts_agent` (SQLite) | **215 passed, 9 skipped**. The 9 skipped are the PostgreSQL tests, run below |
| `tests/accounts_agent/test_postgres_integration.py` on PostgreSQL 16 | **9 passed**. 5 existing; 4 new: vendor-tag edit through the outbox and worker, wrong-flat receipt with a rolled-back receipt, maker–checker, and drain plus dead-event requeue with no duplicate findings |
| Other backend tests touching procurement and members (`tests/vendor`, `tests/master/test_resident.py`, `tests/inventory/test_assets.py`, `tests/test_error_responses.py`) | **174 passed** |
| Flutter Accounts Agent tests (5 files, including the new one) | **27 passed** |
| `flutter analyze` | No errors or warnings. No issue in `lib/features/accounts_agent` or the new test |
| Migration up/down/up on PostgreSQL 16 | Passed |

New regression tests by phase:

| Phase | Defects | Tests |
|---|---|---|
| 1 | D-01, D-02, D-04 | 12 + 2 on PostgreSQL |
| 2 | D-03, D-09 | 8 + 1 on PostgreSQL |
| 3 | D-05–D-08, D-10 | 17 + 1 on PostgreSQL |
| 4 | D-12, D-13, D-15, D-17–D-20 | 7 backend + 6 Flutter |

### Live functional scenarios

All 10 original scenarios were re-run on a fresh PostgreSQL database through the real API and the real worker process. They were run after each phase, and the results below are from the final run.

| # | Scenario | Audit result | Now |
|---|---|---|---|
| 1 | Duplicate vendor payment | Pass | R-DUP-02 CONFIRMED on PV/0024; R-DUP-04 on the no-reference copy — unchanged ✓ |
| 2 | Wrong ledger | Pass | S-MAP-01 ✓ |
| 3 | Unusual recurring amount | Pass | S-REC-01 ✓ |
| 4 | Receipt on the wrong flat | **FAIL** | **A-MAR-01** on flat 101 (₹2,020 credit the bills don't explain). Evidence: RV/0013; possible payers A-105 and A-106 ✓ |
| 5 | Sinking fund misuse | Pass | L-FND-USE-01; fund shown overdrawn on the health card ✓ |
| 6 | Expense without approval | Pass, wording defect | L-EXP-REP-01 is now ADVISORY. Text: "above ₹25,000 — the model bye-law 157 reference figure for 6 members (flats with an active owner…) — a MODEL figure … not verified … The statutory limit (MH-EXP-106C13-LIMIT) is not loaded and is under legal review." ✓ |
| 7 | Normal recurring payment | **FAIL** (false positive) | **No finding** for housekeeping or electricity ✓ |
| 8 | Insufficient history | Pass, with false-negative risk | Still "limited"; the ₹45,000 expense now raises an informational R-AMT-LIM-01 ✓ |
| 9 | Cross-society access | Pass | Still refused; message now "You can only view or act on your own society's Accounts Agent data." Society B shows 1 finding, not 5: the calendar false alarms are gone ✓ |
| 10 | Stale proposal | Pass | Still 409 STALE, nothing applied. After the vendor tag was removed, PV/0024's R-DUP-02 **stays open**; the partner R-DUP-04 is re-classified to R-DUP-03, with the reason recorded ✓ |

**Additional live checks:**
- **Maker–checker:** the admin approving their own proposal got 403. The chairman approved it, and it was executed through `AccountsService`; the voucher went back to pending approval and the agent re-verified it.
- **Calendar:** for the new society, L-CAL-01 and L-AUD-01 now read "confirm whether it applies" (LOW).
- **Interest:** the L-CHG-INT-02 title is "runs past the bill date", with cause PERIOD ("50 day(s) after the bill date").

**Flutter web (release build, Chromium) against the live API:**
- The finding screen shows "Voucher when the finding was raised" (Plumbing) and "Voucher now" (Housekeeping), with a "changed" notice.
- Evidence shows ledger and vendor names.
- History lists: raised → proposed → self-approval refused → approved and applied → re-checked.
- The health card shows bank, cash and fund balances, with Sinking Fund marked overdrawn.
- On the proposer's own proposal there is no Approve button, and the maker–checker note is shown.

**Controls re-verified:**
- **Tenant isolation:** S9, plus new D-10 and D-15 tests.
- **Approval controls:** D-09 tests on SQLite and PostgreSQL.
- **Rolled-back events leave no finding:** the existing outbox test, plus a new PostgreSQL rolled-back receipt test.
- **No financial record changes without explicit authorised approval:** voucher lines are asserted unchanged after detection and after refused approvals.

## 5. Before and after

See the table in §1 and the scenario table in §4. In short:
- One false negative (S4) and one false positive (S7) are fixed.
- A duplicate-hiding path (D-02) is closed.
- The figure presented as legally binding (D-03) is corrected.
- Approval integrity (D-09) is enforced.
- Monitoring can recover from dead events (D-10).
- The app now shows history, original evidence, readable names, balances and pending status.

## 6. Remaining limitations

1. **D-01 trade-off.** Two payments with *different* references are never treated as duplicates. A bill entered twice with a typo in the reference will not be caught by the duplicate rules. A-VEN-DOC and the vendor-invoice checks may still catch it.
2. **A-MAR-01 relies on the member sub-ledger.** It needs receipts posted to the member AR sub-ledger (a flat on the line). A receipt credited straight to an income ledger is not seen. Its "possible payers" are candidates, not conclusions.
3. **R-AMT-LIM-01 is deliberately coarse.** Its thresholds are 10× the largest earlier posting, above ₹10,000, or ₹1,00,000 with no history. They are fixed constants, not settings.
4. **Findings raised before Phase 4 have no snapshot.** The app says "Shown as it is today: no copy was kept".
5. **Requeue limit.** After 3 requeues, an event can only be acknowledged.
6. **Member count with a partial owner register.** If the resident register lists owners for only some flats, the member count is understated. Recording the membership in the legal profile overrides it.
7. **Auto-resolved findings that recur.** An auto-resolved Engine A finding is not reopened if the same condition comes back later; the dedupe key already exists. This is unchanged from before.

## 7. Items needing separate billing or legal review

- **Billing — interest period on back-dated bills.** See `docs/BILLING_INTEREST_PERIOD_REVIEW.md`. Interest is counted to the generation date, not the bill date. This is documented in `billing_service.py`, but it needs a decision from the billing module owners and the committee. Nothing in billing was changed.
- **Legal — committee spending limit (Rule 106C-13).** The registry still has no verified slab figures, and the English/Marathi review is open. Until it is verified, findings fall back to the society's own rule or setting, or the labelled model figure.
- **Legal — procurement module defaults.** `vendor/services/work_orders.py::bye_law_slab` still provides the model bye-law slab as the procurement workflow's *default* committee limit, which governs work-order sanction requirements. The agent no longer presents this figure as law, but whether the procurement workflow should default to it is for the committee and legal review to decide.
- **Legal — the remaining hard-coded figures noted in the audit** (billing API caps; the AGM date of 30 September) are unchanged and remain on the legal-verification list.
