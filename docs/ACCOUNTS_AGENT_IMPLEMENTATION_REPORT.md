# Accounts Agent — Implementation Report

Design and audit: [ACCOUNTS_AGENT_ARCHITECTURE.md](ACCOUNTS_AGENT_ARCHITECTURE.md).

## 1. What was built

An auditing agent inside the existing app. It never touches financial records on its own: it detects, explains,
proposes, and executes only after an authorised person explicitly approves.

| Capability | Where |
|---|---|
| Transactional outbox, written in the same transaction as every voucher change (create, edit, cancel, approve, reverse) | `services/outbox.py` (SQLAlchemy `after_flush` listener) |
| Separate, recoverable worker (leases, `SKIP LOCKED`, back-off, dead-letter, restart recovery, daily re-learning) | `worker.py` |
| Rolling **three-month** learning baseline, per society, with honest confidence (`none/limited/moderate/good`) | `services/learning.py` |
| Deterministic validators — balance, lines, ledger ownership/inactivity, voucher-type cash/bank rules, sub-ledgers, vendors, fiscal year, closed-year postings, source documents, reversals, duplicates, journal narration | `services/rules.py` |
| Statistical detectors — modified z-score (median/MAD) per ledger and vendor, recurring-expense deviation, frequency burst, vendor→ledger mapping drift, unseen debit/credit pair, nature mismatch, journal outliers | `services/anomaly.py`, `services/stats.py` |
| Structured findings, four claim classes (confirmed / strongly suspected / statistical / informational), severity, confidence, evidence with the calculation | `models/agent.py`, `services/engine.py` |
| Correction proposals with before/after and per-ledger debit/credit impact; approve/reject; stale protection; one-shot execution; post-correction verification | `services/proposals.py` |
| Notifications through the existing `NotificationService` (grouped, de-duplicated, society-scoped) | `services/notify.py` |
| Append-only agent audit trail | `services/audit.py` |
| Optional LLM interface (disabled, no provider shipped, no credentials read) | `services/llm.py` |
| REST API (`/api/v1/accounts-agent/...`) | `routes/accounts_agent.py` |
| Flutter dashboard, findings, finding detail, approval screen, learning & settings | `mobile/lib/features/accounts_agent/` |

### Key design decisions

* **One hook for all pathways.** `AccountsService.build_voucher` is the only `Voucher(...)` constructor, so a flush listener
  covers manual vouchers, bills, receipts, online payments, vendor invoices/payments, recurring expenses, amenity deposits,
  reversals and year-end closing — and any pathway added later. No existing posting code was modified.
* **The agent cannot block accounting.** The outbox insert runs in a SAVEPOINT with `ON CONFLICT DO NOTHING`, every exception is
  swallowed and logged. Verified on real PostgreSQL: a failing insert does not abort the posting.
* **Corrections go through the existing services** (`update_manual_voucher`, `cancel_manual_voucher`) as the approving user, so
  closed-year locks, voucher revisions, accounting audit log and the payment/journal approval workflow still apply (an edited
  payment returns to "pending approval", by design).
* **Auto-posted vouchers are never edited.** Their proposals are `source_review` (non-executable): approving only records that the
  source/mapping was reviewed.
* **Only derivable corrections are proposed:** duplicate → cancel the later voucher; vendor→ledger mapping drift → re-map the line.
  Other findings get an honest 422 ("no correction can be derived") and are closed by review.

### Maintenance-bill posting checks (`services/bill_checks.py`)

For live vouchers posted from a maintenance bill (on create/edit) the agent re-derives the posting from the bill, mirroring
`AccountPostings.post_bill`, and compares — it does **not** recompute rates or areas:

| Rule | Detects | Severity |
|---|---|---|
| `R-BILL-01` | the bill's own arithmetic is off (lines vs subtotal/GST, subtotal + GST + round-off vs total, line total) | Medium |
| `R-BILL-02` | Members' Dues debited ≠ the bill's total (+ penalty) | High |
| `R-BILL-03` | Members' Dues line names a different flat than the bill | High |
| `R-BILL-04` | a charge head credited with a different amount/ledger than the bill charged | High |
| `R-BILL-05` | a live posting for a bill that is not in an issued state | Medium |

### Flat-wise month-over-month bill check (`detect_bill_month_change`)

Compares a flat's new bill with **the same flat's bills in the last three months** (never one flat with another's amount, since
areas and parking differ), head by head:

| Rule | Detects | Severity / class |
|---|---|---|
| `S-BILLMOM-01` | a recurring head changed more than the tolerance (the society's "recurring tolerance", default 10 %) | Low <25 %, Medium ≥25 %, High ≥100 % (suspected anomaly, only with ≥2 earlier bills); always a statistical deviation otherwise |
| `S-BILLMOM-02` | a head the flat always had is missing while the other flats still have it | Medium (Low if too few peers) |
| `S-BILLMOM-03` | a head appeared on this flat that most flats don't have | Informational |

What keeps it from crying wolf: society-wide revisions are allowed for (the other flats' average movement of the same head,
excluding the flat itself); one-off / variable lines are never compared (penalties and interest, special assessments, "other"
additional charges, actual-expense shares); bills for a different length of period (quarterly cycle, a flat that joined part-way)
are skipped; a head whose own history isn't steady is skipped; no earlier bill in the window means no claim. Cost: a fixed handful
of queries per bill (one grouped aggregate per cohort), covered by a test.

Not covered: whether the billing rates/areas/charge configuration are right (the agent only compares a bill with its own history).

### Documented conflict with an existing rule

An "approved payment without approver" validator was drafted and **removed**: recurring-expense recording and bank
reconciliation create approved payment vouchers with no approver, so the rule would flag legitimate postings. Existing behaviour
is unchanged and not contradicted (`test_approved_payment_without_approver_is_not_flagged`).

## 2. Files

Created: `backend/app/modules/accounts_agent/**` (models, services, routes, schemas, worker), `backend/alembic/versions/a1d2e3f4b5c6_accounts_agent.py`,
`backend/tests/accounts_agent/**`, `mobile/lib/features/accounts_agent/**`, `mobile/test/accounts_agent_api_test.dart`, the two docs.

Modified (small, additive): `backend/app/models/__init__.py` (register models + install listener), `backend/app/api/__init__.py`
(router), `backend/Procfile` and `backend/Makefile` (worker entry), `mobile/lib/core/router/app_router.dart` (6 routes),
`mobile/lib/features/accounts/presentation/screens/accounts_screen.dart` (one menu entry).

## 3. Database migration

`a1d2e3f4b5c6` (down: `a7c9e1b3d5f2`) creates 7 tables: `accounts_agent_settings`, `_learning_runs`, `_patterns`, `_events`,
`_findings`, `_proposals`, `_audit_logs`. Nothing existing is altered; idempotent; downgrade drops only these tables.
Run against real PostgreSQL 16 with `scripts/ci/check_migrations.py full`: graph OK, empty→head, no model/schema drift, head
downgrade+upgrade, earlier-revision→head, `/health/ready` 200 / 503.

## 4. API (`/api/v1/accounts-agent`)

Read = manager and above · write/decide = admin/committee. Society always from the authenticated user; platform admin must pass
`society_id`; a different `society_id` from a scoped user is 403.

`GET status` · `GET dashboard` · `GET|PUT settings` · `POST monitoring {enabled}` · `GET learning/status` · `POST learning/run` ·
`GET learning/history` · `GET findings` (severity, category, status, finding_class, date_from/to, q, page, page_size) ·
`GET findings/{id}` · `POST findings/{id}/review` · `GET findings/{id}/history` · `POST findings/{id}/proposals` ·
`GET proposals` · `GET proposals/{id}` · `POST proposals/{id}/approve {confirm:true}` · `POST proposals/{id}/reject {reason}` ·
`GET audit-logs`.

## 5. Running it

```bash
cd backend
alembic upgrade head                           # (or RUN_MIGRATIONS=true on start)
python -m app.modules.accounts_agent.worker    # long-running worker (poll 5 s)
python -m app.modules.accounts_agent.worker --once   # drain once (cron / debugging)
```

Deploy the worker as a **second service/process** with the same `DATABASE_URL` and image (e.g. a second Railway service with start
command `cd backend && python -m app.modules.accounts_agent.worker`). Several workers may run together. Without a worker the
outbox simply accumulates (nothing is lost; the dashboard shows "Delayed — N waiting") and is processed once one starts.

Configuration: no new environment variables. Per-society settings in the app (monitoring on/off, outlier threshold 2.5–6 default 3.5,
recurring tolerance 10 %, duplicate window 7 days, notify-from severity). Worker constants in `worker.py`
(batch 50, lease 120 s, 6 attempts, back-off 30 s → 1 h, outbox retention 30 days).

## 6. Tests actually executed

Results (all actually executed in this environment):

| Run | Result |
|---|---|
| `tests/accounts_agent` (SQLite) + PostgreSQL integration (`AGENT_TEST_PG_URL`, PG 16) | **56 passed** (53 SQLite + 3 PostgreSQL) |
| Existing suites `accounts billing vendor security db ci notifications rbac assistant automation amenity test_error_responses` | **923 passed, 1 skipped, 0 failed** (16 min 47 s) |
| `scripts/ci/check_migrations.py full` on PostgreSQL 16 | **passed** (all 5 stages) |
| End-to-end smoke: Alembic-migrated PG → vouchers → `worker --once` | events `done`, findings + learning run stored |
| `flutter analyze` / `flutter test` | **not run — no Flutter SDK available** |


* `backend/tests/accounts_agent` on SQLite — detection (balanced/unbalanced/missing lines, duplicate voucher, duplicate payment,
  same source twice, incorrect ledger mapping, unusual expense, recurring deviation, invalid/foreign vendor, type-rule violation,
  valid and broken reversal, false-positive prevention), learning (3-month window, older data untouched, no invented history),
  monitoring reliability (event atomic with voucher, rollback → no event, duplicate event ignored, retry/back-off, dead-letter +
  notification, restart recovery, live lease respected, agent failure does not interrupt accounting, disabled → skipped), society
  isolation (findings, history, review, proposals, learning profiles, settings, forged cross-society event), approval security
  (unauthorised → 403, explicit confirmation, rejected cannot execute, stale cannot execute, double approval executes once,
  controlled service used + revision kept, audit trail, source-review proposals change nothing).
* `tests/accounts_agent/test_postgres_integration.py` on **real PostgreSQL 16** (opt-in via `AGENT_TEST_PG_URL`): atomic commit /
  rollback of voucher+event, a failing outbox statement cannot abort the posting, `FOR UPDATE SKIP LOCKED` gives two workers disjoint
  batches.
* Alembic checks on PostgreSQL (§3) and an end-to-end smoke: migrated DB → vouchers → `worker --once` → findings stored.
* Existing suites touching accounting (`accounts, billing, vendor, security, db, ci, notifications, rbac, assistant, automation, amenity`).

## 7. Known limitations / not verified

* **Flutter code was written but NOT compiled, analysed or run**: no Flutter/Dart SDK exists in this environment. The Dart test
  (`mobile/test/accounts_agent_api_test.dart`) has not been executed. Run `flutter analyze && flutter test` before release.
* The complete backend suite (~hours) was not run end-to-end here; the suites listed in §6 were. Run the full suite in CI.
* No push/notification-tap deep-link wiring beyond `action_url` paths (`/accounts-agent`, `/accounts-agent/proposals/{id}`), which match the new routes.
* Bill checks compare the books with the bill as issued; they cannot tell that the bill itself was calculated from a wrong rate.
* Statistical detectors need history: with fewer than 6 samples per ledger (4 per vendor, 3 recurring) they stay silent by design.
* Category names, rule codes and wording are English only (no l10n yet).
* An edited payment/journal re-enters approval: after approving a correction the voucher may still need its normal approval.
* `finding_class` "strongly suspected" can still be a false positive (e.g. a genuine ten-fold one-off); reviewers can mark "Not an issue".
* No LLM provider is implemented; `services/llm.py` is only the safe interface.

## 8. Production checklist

- [ ] Deploy backend, run `alembic upgrade head`.
- [ ] Start the worker process (second service); confirm dashboard state "Operational".
- [ ] Run "Learn again now" once per society (also happens automatically on the first event, then daily).
- [ ] Run `flutter analyze && flutter test`; build the app.
- [ ] Run the full backend suite and `scripts/ci/check_migrations.py full` in CI.
- [ ] Confirm admin/committee users receive notifications; tune "notify from" severity.
- [ ] Monitor worker logs for `[accounts-agent] ... failed` and the `failed_events` count on the dashboard.
- [ ] Back up the database before migrating production (migration is additive and reversible).


## Phase 2

Maharashtra legal & bye-law intelligence (rule registry, documents, resolutions, compliance engine): see
[ACCOUNTS_AGENT_LEGAL_REPORT.md](ACCOUNTS_AGENT_LEGAL_REPORT.md).
