# Accounts Agent — Architecture (Phase 0 audit + design)

Scope: add an auditing "Accounts Agent" to the existing AR Society app. It extends the
existing accounting module; nothing in `backend/app/modules/accounts` is rebuilt.

## 1. Existing architecture findings

| Area | What exists | Reuse |
|---|---|---|
| Stack | FastAPI + SQLAlchemy 2 + Alembic (124 revisions, single head), Flutter app in `mobile/` | all |
| Ledger models | `AccountGroup`, `Account`, `Voucher`, `VoucherEntry`, `VoucherRevision`, `FinancialYearClosing`, `RecurringExpense(+Run)` in `accounts/models/accounts.py`; sub-ledgers in `entities.py` | read-only |
| Voucher creation | **One choke point**: `AccountsService.build_voucher()` (validates balance, society ownership, open year; `flush`, never commits). The caller commits. | hook point |
| Manual vouchers | `create_manual_voucher` / `update_manual_voucher` / `cancel_manual_voucher` / `approve_manual_voucher` / `reject_manual_voucher` (maker-checker, revisions, audit log, closed-year lock) | executor for approved corrections |
| Automatic postings | `AccountPostings` (`postings.py`): maintenance bill, payment receipt, online payment, advance allocation, vendor invoice, vendor payment, amenity deposit/refund, plus `reverse()`/`void()`; each hook runs in a SAVEPOINT (`run`) | monitored through the same choke point |
| Recurring expenses | `recurring_expenses.py` records a confirmed month by calling the voucher service | monitored through choke point |
| Auth / RBAC | `get_current_user`, DB-driven `require_permission(code)` (`admin_committee`, `manager_above` …), `User.society_id` (None = platform admin) | reuse |
| Tenant isolation | `core/tenant_scope.py`: `assert_society_access`, `resolve_create_society_id` | reuse for every endpoint |
| Notifications | `NotificationService.send(...)` (in-app + optional push), `notifications` table | reuse, no new notification table |
| Audit | `AuditService.log` → `audit_logs` (used by accounts service) | reused indirectly; agent keeps its own audit table for agent-specific actions |
| Background work | `automation/scheduler.py`: a 10-minute daemon thread inside the API process | **not** used for the agent (see §5) |
| Assistant | `modules/assistant`: docs-grounded help bot with a `Provider` protocol, disabled by default | pattern copied for the optional LLM interface; the assistant itself is untouched |
| Tests | pytest on SQLite (`tests/conftest.py`, UUID→CHAR(32), JSONB→JSON), `db` fixture = rolled-back outer transaction | same conventions |
| Migrations | hand-written, idempotent Alembic files, CI graph check (`scripts/ci/check_migrations.py`) | same conventions |
| Flutter | feature folders (`mobile/lib/features/<x>/{data,presentation}`), Riverpod-style providers, shared widgets | same conventions |

## 2. Transaction lifecycle map

```
manual voucher API ─┐
bill issue / cancel ┤                                  ┌─ Voucher + VoucherEntry rows
payment receipt ────┤                                  │
online payment ─────┼─► AccountPostings ─► AccountsService.build_voucher ──flush──► DB (uncommitted)
vendor invoice/pay ─┤        (SAVEPOINT)                         │
recurring expense ──┤                                            ▼
amenity deposit ────┘                              SQLAlchemy after_flush listener
year-end closing, reversals                         └─ INSERT accounts_agent_events (same tx)
                                                                 │ COMMIT (or ROLLBACK → event gone too)
```

Mutations that also emit events (same listener, `Session.dirty`): cancel (`is_cancelled`), approval
transitions (`approval_status`), edits (`edited_at`), reversal (`reversed_at`).

### Posting pathways monitored

| Pathway | Voucher type / source_type | Covered by |
|---|---|---|
| Manual receipt/payment/journal/contra | `receipt…contra`, no source | choke point |
| Maintenance bill | `bill` / `maintenance_bill` | choke point |
| Payment receipt, online payment, advance allocation | `receipt` / `payment_receipt`, `online_payment`, `advance_allocation` | choke point |
| Vendor invoice / vendor payment | `purchase`, `payment` / `vendor_invoice`, `vendor_payment` | choke point |
| Recurring expense | manual voucher created by the recurring service | choke point |
| Amenity deposit & refund | `receipt`/`payment` | choke point |
| Reversal of closed-year voucher | `journal` + `reversal_of_id` | choke point |
| Year-end closing | `closing` | choke point (analysed but exempt from statistics) |
| Cancel / approve / reject / edit | state change on `Voucher` | `Session.dirty` check in the same listener |

Hooking the ORM flush (rather than each endpoint) is deliberate: no pathway can be forgotten, and
future pathways are covered automatically. `grep "Voucher("` confirms `build_voucher` is the only constructor.

## 3. Proposed database design (all society-scoped)

* `accounts_agent_settings` — 1 row/society: `monitoring_enabled`, `notify_min_severity`,
  `z_threshold`, `recurring_tolerance_pct`, `duplicate_window_days`, `last_monitored_at`, `last_error`.
* `accounts_agent_learning_runs` — one row per learning run: window start/end, status, voucher/line counts,
  months covered, confidence score + label, summary JSON, error.
* `accounts_agent_patterns` — the current learning profile: `(society_id, pattern_type, key)` unique;
  `stats` JSON (robust statistics + a capped sample list so the detector can do leave-one-out).
* `accounts_agent_events` — **transactional outbox**: `idempotency_key` unique, status
  (`pending|processing|done|failed|dead|skipped`), attempts, `next_attempt_at`, `locked_until`, last error.
* `accounts_agent_findings` — structured findings; unique `(society_id, dedupe_key)`.
* `accounts_agent_proposals` — correction proposals with `voucher_fingerprint`, before/after JSON, status.
* `accounts_agent_audit_logs` — append-only trail of every agent/user action.

No accounting table is altered. No notification table is added.

## 4. Event processing architecture

1. `build_voucher` flushes → listener inserts an outbox row with `ON CONFLICT DO NOTHING` inside a SAVEPOINT
   (an agent-side failure can never abort the financial transaction).
2. Commit makes voucher + event durable together; rollback (including a rolled-back posting SAVEPOINT) removes both.
3. `python -m app.modules.accounts_agent.worker` is a separate process. It claims rows with
   `FOR UPDATE SKIP LOCKED` (PostgreSQL), sets `locked_until`, processes each event in its own session/transaction.
4. Success: findings stored + event `done` in one commit; notifications afterwards (best effort, grouped).
5. Failure: exponential back-off (`next_attempt_at`), after `MAX_ATTEMPTS` the event is `dead` and admins are notified.
6. Crash recovery: `processing` rows whose `locked_until` passed are re-claimed. Findings use a `dedupe_key`, so
   re-processing is idempotent.
7. The worker also refreshes each society's learning profile at most once per 24 h (rolling window).

## 5. Why not the 10-minute scheduler

It is a daemon thread inside the web process, runs every 10 minutes and has no retry bookkeeping. The agent worker is
separate (`Procfile` entry), near-real-time (poll interval 5 s) and recoverable. The API never starts agent threads.

## 6. Intelligence engine (no paid AI)

* Learning window: the most recent three calendar months of live (not cancelled / reversed, approved, non-closing)
  vouchers. Older data is never touched; it simply isn't in the baseline.
* Deterministic validators (`confirmed` class): balance, line validity, society ownership, inactive ledgers,
  voucher-type ↔ cash/bank rules (mirroring `_manual_lines`), sub-ledger tagging, fiscal-year consistency, approval
  consistency, source-document consistency, reversal mirroring, confirmed duplicates.
* Statistical detectors (`statistical_deviation` / `suspected_anomaly` classes): modified z-score (median/MAD,
  Iglewicz–Hoaglin 3.5 cut-off) per ledger and per vendor with a minimum sample size, recurring-expense deviation vs
  learned median, unseen debit/credit pair, vendor→ledger mapping drift, frequency burst.
* Severity ≠ certainty: every finding carries `finding_class`, `severity` and `confidence`. Statistical findings are
  never labelled as confirmed errors and are capped at MEDIUM unless corroborated by a deterministic rule.
* Insufficient history ⇒ statistical detectors stay silent, the profile is labelled "limited", nothing is invented.

## 7. Security model

* Every endpoint resolves the society through `resolve_create_society_id(user, society_id)`; a scoped user can
  never name another society; platform admin must name one.
* Every query filters `society_id`; the worker loads the voucher by id **and** checks `voucher.society_id ==
  event.society_id`; pattern lookups are by society.
* View: `manager_above`. Review/propose/approve/reject/settings/learning-run: `admin_committee`.
* Approving executes only through `AccountsService` (`update_manual_voucher`, `cancel_manual_voucher`) as the approving
  user, so closed-year locks, maker/checker and the voucher-revision history apply. Auto-posted vouchers get
  `source_review` proposals that execute nothing.
* Stale protection: SHA-256 fingerprint of the voucher state stored on the proposal and re-checked under a row lock.
* Logs carry ids and counts only, never amounts or narrations.

## 8. API (prefix `/api/v1/accounts-agent`)

`GET status` · `GET/PUT settings` · `POST monitoring` · `GET learning/status` · `POST learning/run` ·
`GET learning/history` · `GET dashboard` · `GET findings` · `GET findings/{id}` · `POST findings/{id}/review` ·
`GET findings/{id}/history` · `POST findings/{id}/proposals` · `GET proposals` · `GET proposals/{id}` ·
`POST proposals/{id}/approve` · `POST proposals/{id}/reject` · `GET audit-logs`.

## 9. Flutter structure

`mobile/lib/features/accounts_agent/{data/accounts_agent_api.dart, presentation/screens/*}`: Dashboard, Findings list,
Finding detail, Proposal approval, Learning & settings; one navigation entry from the Accounts area.

## 10. Testing strategy

pytest on SQLite like the rest of the suite (detection fixtures with three months of synthetic vouchers, isolation,
approval security, outbox reliability, migration graph). **Limits of this environment:** no PostgreSQL server and no
Flutter SDK are installed here, so `FOR UPDATE SKIP LOCKED`, the real-Postgres migration run and `flutter test`
cannot be executed locally; they are called out in the implementation report as CI-only checks.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Listener slows or breaks postings | one cheap `INSERT … ON CONFLICT DO NOTHING` in a SAVEPOINT; all exceptions swallowed + logged |
| Outbox growth | processed rows are compacted by the worker after 30 days (`done`/`skipped` only) |
| False positives | statistical detectors need minimum samples, are capped in severity, labelled as deviations |
| Executing a stale correction | fingerprint + row lock + one-shot status transition |
| Voucher edit re-enters approval | intentional: reuse existing workflow, executor result reported honestly |
| SQLite vs PostgreSQL differences | portable constructs only; Postgres-only locking guarded by dialect check |
