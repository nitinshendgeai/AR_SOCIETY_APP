# Baseline Audit — AR Society ERP (Phase 0)

| | |
|---|---|
| Audited commit | `7f5af9c` (`origin/main`, branch `claude/current-status-bqz2l6`, working tree clean at start) |
| Date | 2026-10-15 |
| Scope | Read-only. No application code, migration, test or configuration was changed. The only file added is this report. |
| Production | `https://society.duxos.in`. **Not contacted.** Nothing in this report was verified against production. |

## 1. How to read the evidence

Every statement carries one of these evidence classes. Nothing is called "working" on code inspection alone.

| Class | Meaning |
|---|---|
| **T** | Verified by an automated test run in this audit (results in section 3). |
| **P** | Verified by a throwaway probe test run in this audit against the SQLite test database. The probes were deleted after use; Phase 1 turns them into regression tests. |
| **S** | Source inspection only. Behaviour not executed. |
| **D** | A claim made in the docs. Compared against the code where noted. |
| **U** | Cannot be verified without a running environment (production, Railway, SMTP, push, real Postgres load). |

## 2. Executive summary

1. **Baseline is green.** Backend 1,223 passed / 0 failed. Flutter 232 passed / 0 failed. Alembic has one head and no broken parents. (T)
2. **Confirmed cross-tenant defect (P0): the payroll module has no society scoping.** A Society Admin of society A can read and set salary structures, aggregate monthly attendance and create attendance corrections for society B's staff, and list society B's corrections. Two further read endpoints (`workload` summary, correction list) leak the same way. (P) See section 5.
3. **Elsewhere tenant isolation held.** Of 144 isolated cross-society probes on routes taking `{society_id}`, 124 were refused with 403, 17 returned 422 before authorisation could be observed (inconclusive, not proven safe), and 3 are the payroll/workload defects above. All 501 non-public routes reject anonymous callers (401/403). Only 7 of 508 routes are intentionally public. (P)
4. **Migration failure is not visible to the platform.** `/health` always returns HTTP 200 with `"status": "ok"`, even when the database is unreachable or behind the code. Railway's health check cannot detect it. `app/main.py` also swallows migration errors. (S)
5. **No CI for tests.** Only two workflows exist: a gitleaks scan (documented as red on `main`: "leaks found: 2") and an APK build. Nothing runs backend tests, Flutter analyze/tests or a migration check. `flutter analyze` exits 1 (0 errors, 15 warnings, 437 infos). (S, T)
6. **5,045 generated files are tracked** in `test_venv/` and `test_build/` (about 75 MB on disk), added in one commit and never ignored. (S)
7. **Several documents are stale** and understate or misstate the product. `docs/KNOWN_ISSUES.md` and `docs/PROJECT_STATUS.md` still list gaps that are already fixed and omit gaps that exist (section 6). (S)

## 3. Baseline test results (exact)

| Check | Command (from repo root) | Result | Evidence |
|---|---|---|---|
| Backend tests | `cd backend && python -m pytest -q` (venv with `requirements.txt`) | **1223 passed, 0 failed, 4 warnings, 16 min 48 s** on `7f5af9c` | T |
| Flutter tests | `cd mobile && touch .env && flutter test` | **232 passed, 0 failed** | T |
| Flutter analyze | `cd mobile && flutter analyze` | **452 issues, exit 1: 0 errors, 15 warnings, 437 infos** (303 `deprecated_member_use`, 90 `prefer_const_constructors`, 11 `unused_import`) | T |
| Alembic graph | static parse of `backend/alembic/versions` | 89 revisions, **1 head `f2c5d9e7a1b3`**, 0 dangling parents, 2 merge revisions (`4e1f2a3b4c5d`, `b3c4d5e6f7a9`) | S |
| Route inventory | import `app.main`, walk `app.routes` | 508 routes; 501 under `/api/v1` probed | P |

Notes and caveats:
- Pre-existing failures: **none** in this run. A previous session saw two tests (`accounts/test_reports.py::test_trial_balance_tallies`, `staff/test_payroll_readiness.py::test_double_approve_rejected`) fail once in one full run and pass in every other run, including this one. The cause was never found. Treat them as a possible order- or time-dependent flake until proven otherwise.
- All backend tests use SQLite with `JSONB` patched to `JSON` (`tests/conftest.py`). PostgreSQL-specific behaviour (partial unique indexes, `ON CONFLICT`, enum types, locking, concurrency) is therefore **not exercised** by the suite.
- The Alembic graph was checked statically. An upgrade/downgrade run on PostgreSQL was not repeated in this phase.
- `flutter pub get` rewrites `mobile/analysis_options.yaml` and `mobile/android/local.properties`. Those side effects were reverted, as was the temporary `mobile/.env`.

## 4. Architecture snapshot

- **Backend:** FastAPI, SQLAlchemy, Alembic; 90 files under `alembic/versions`; 19 domain modules under `app/modules/` plus core routes under `app/api/routes` and `app/services`; 100 backend test files. Routers are registered through `app/api` into `/api/v1`.
- **Flutter:** `mobile/lib` has 260 Dart files across 26 feature folders; 40 test files. Web and mobile share one code base.
- **Deploy (S, D):** `railway.json` uses NIXPACKS, `startCommand: bash /app/start.sh`, `healthcheckPath: /health`, restart on failure (3 retries). `start.sh` runs `alembic upgrade head` only when `RUN_MIGRATIONS=true`, under `set -e` (a failed migration aborts boot). `docs/DEPLOYMENT.md` and `docs/PROJECT_STATUS.md` say Railway auto-deploys on push to `main`. **The actual production branch cannot be confirmed from the repository (U).**
- **Dependencies:** `backend/requirements.txt` is a hash-pinned `pip-compile` output (generated with Python 3.11; nixpacks installs `python312`). A separate root `requirements.txt` (14 unhashed lines) differs from it. (S)

## 5. Confirmed defects and risks (not fixed in this phase)

### 5.1 P0 — Payroll module has no tenant isolation (evidence: P)

Reproduced in the test database with two societies, an admin of A, and a staff member plus salary structure in B. Every call below was made with A's admin token:

| Call | Result |
|---|---|
| `GET /payroll/salary-structure/{B staff}` | 200, returns B's salary record |
| `POST /payroll/salary-structure` for B's staff | 201, writes B's salary |
| `POST /payroll/monthly-summary/{B}/{B staff}/2026/10` | 200, creates B's summary |
| `GET /payroll/monthly-summary/{B staff}/2026/10` | 200 |
| `POST /payroll/attendance-correction` (society B) | 201, creates correction in B |
| `GET /payroll/attendance-correction/society/{B}` | 200 |
| `GET /payroll/attendance-correction/staff/{B staff}` | 200 |

Root cause (S): `PayrollService` (`modules/staff/services/payroll_service.py`) filters by IDs it is given and never compares them to the caller's `society_id`; routes in `api/routes/payroll_readiness.py` pass path/body IDs straight through. `POST /monthly-summary/{summary_id}/finalize` and the approve/reject correction routes take only a record ID and were not exercised, but share the same service and no scoping code. Existing tests (`tests/staff/test_payroll_readiness.py`) have no cross-society case.

### 5.2 P1 — Workload summary reads any society (evidence: P)

`GET /workload/society/{society_id}/summary` (`api/routes/workload.py`) is guarded by role only; the query uses the path `society_id` directly. Returned 200 with society B's counts for society A's admin.

### 5.3 P1 — Health and migration readiness (evidence: S)

- `/health` returns HTTP 200 and `"status": "ok"` unconditionally; database and migration state are reported in the body (`database.status`, `migrations.up_to_date`) but never change the status code. A Railway health check therefore passes with a dead database or an un-migrated schema.
- `app/main.py` calls `run_migrations()` at import and ignores its `False` return. `start.sh` already aborts on a failed `alembic upgrade head` when `RUN_MIGRATIONS=true`, so the real gap is deployments where that flag is unset: the application then starts against whatever schema exists with only a log line.
- Five migrations from the last work packages (`b7e3d1c9a4f2`, `c8f2a6d4b1e9`, `d9a3b7c5e2f1`, `e1b4c8d6f3a2`, `f2c5d9e7a1b3`) are recorded in earlier session notes as **not yet confirmed as applied on production** (U).

### 5.4 P2 — Inconclusive authorisation probes (17 routes)

These returned 422 (payload validation) before authorisation could be observed. They need a valid payload to prove isolation. The service functions read for governance, certificates and gate parcels/help contain `assert_society_access`; the rest were not read.
`POST /automation/{id}/run`, governance meetings/polls/documents (POST), manager-checklist items (POST), certificates (POST), gate parcels and help (POST), `GET /staff/society/{id}/department/{department}`, `GET /staff/duties/society/{id}`, `GET /staff/duties/sheet/society/{id}`, `GET /staff/complaints/department/{id}`, `POST /billing/bank-reconciliation/society/{id}/import`, `GET /vendors/society/{id}/category/{category}`, `GET /accounts/vouchers/next-number/{id}`, `POST /accounts/years/{id}/{fy}/reopen`, `PATCH /societies/{id}/setup-progress`.

### 5.5 Not covered by the probes

- IDs other than `society_id` (staff, flat, resident, vendor, bill, voucher, asset IDs in paths and bodies). The payroll finding shows these are the likeliest place for further defects. A per-endpoint review is the first task of Phase 1.
- Foreign keys supplied in request bodies that point into another society (for example a `flat_id` or `vendor_id` from society B on a create in society A). Existing tests cover wings, flats, vehicles, residents, parking and tenants; most other modules are untested for this.
- Platform-admin versus society-admin separation was exercised only by existing tests (`tests/rbac`, `tests/platform_admin`), not re-proved here.

### 5.6 Other observations

- `POST /auth/register` is public and creates an active login with the Resident role and no society (S). Its reachable surface (what such a login can do before being linked to a society) was not tested.
- The staff leave "used" balances (`casual_used`, `sick_used`, `earned_used`) are exposed by `GET /staff/leave-balance` but **no code updates them** when a leave is approved (S: grep shows the fields only in the response schema). Balances will always read zero used.
- Billing duplicate-generation prevention is a service-level check ("Bills already generated for this cycle") with no database unique constraint on a bill per flat per cycle. A concurrent double-click is not covered by any test, and SQLite tests could not show it anyway. (S)
- Rate limiting, request size limits and CORS policy were not assessed.

## 6. Documentation accuracy

`docs/KNOWN_ISSUES.md` (last updated 2026-06-23) and `docs/PROJECT_STATUS.md` (2026-06-23) are out of date.

| Claim in docs | What the code shows |
|---|---|
| Handover UUID field (KG-01) | **Fixed.** `handover_screen.dart` uses an "Incoming Staff" dropdown. (S) |
| No Reject button in approval (KG-03) | **Fixed.** `approval_screen.dart` has Approve/Reject; provider has `rejectCheckin`/`rejectCheckout`. (S) |
| Drawer not role-scoped (KG-04) | Superseded: menu is built from `/forms/mine` permissions plus service switches. (S, D) |
| Supervisor department is not enforced server-side | **Largely fixed.** `_resolve_dept`, `_check_dept_access` and `supervised_departments` are applied to attendance list, approve and reject routes. Leave approval is manager-only, so it does not need it. (S) |
| Printed sheets are Latin-only | **Fixed** for duty sheets and certificates (Noto Sans Devanagari bundled). Not verified for every PDF. (S) |
| Admin/Committee/Security dashboards show `--` for occupancy and counts | **Partly fixed.** The Admin dashboard uses a single summary endpoint with live occupancy and counts. Committee uses several separate calls. The Security dashboard still hard-codes `--` and "Duty Status: Active". (S) |
| Edit Duty not implemented | **Still true.** No duty PATCH route exists. (S) |
| Leave self-service UI not available | **Still true.** The API exists; no Flutter code references the leave endpoints. Leave approval has no UI either. (S) |
| Close Handover not implemented | **Still true** and documented as intentional. (S) |
| Complaint assignment does not notify | **Still true.** `assign_complaint_to_department` sends no notification. (S) |
| "255 backend tests pass" | Now 1,223. (T) |

## 7. Module matrix

Priority: P0 = fix before anything else; P1 = next; P2 = planned; P3 = polish. "Evidence" cites the class from section 1.

| Module | Existing functionality | Confirmed gap | Evidence | Priority | Dependencies | Acceptance criteria |
|---|---|---|---|---|---|---|
| Auth and sessions | Login with multi-society choice, refresh rotation, per-device sessions, password change, forgot-password, platform admin, society and user gating | `/auth/register` reachable surface untested; token expiry and password-change enforcement not re-verified here | S, T (`tests/auth`) | P2 | none | Registered login without a society cannot reach any society data; tests prove token expiry and post-password-change invalidation |
| Tenant isolation (cross-cutting) | `assert_society_access`, `_scoped`, parking/master/vehicle isolation tests | Payroll fully unscoped; workload unscoped; 17 routes inconclusive; non-`society_id` IDs and body FKs not audited | P | **P0** | none | Negative tests for A→B on read/create/update/delete for every module; 0 cross-society 200s |
| Payroll readiness | Salary structure, attendance corrections (request/approve/reject), monthly summaries | No society scoping on any route | P | **P0** | Tenant isolation | Society A caller gets 403/404 for all seven calls in section 5.1; same-society flow unchanged |
| Platform admin | Suspend/activate, trial extension, limits (stored only), per-society service switches, audit events | Limits (users, flats, storage) are not enforced | T (`tests/platform_admin`), D | P3 | owner decision | Documented, not a defect; enforce only if the owner asks |
| Society structure / residents / tenants | Wings, floors, flats, residents, tenants, vehicles, agreements, occupancy, imports | None found; isolation tested for these | T | none | none | Keep tests green |
| Visitors / gate | Visitor lifecycle, pre-approval, gate extras (parcels, domestic help, passes) | Gate create routes' scoping confirmed only in the service (S), not by probe | S | P2 | Tenant isolation | Probe with valid payload returns 403 |
| Complaints | Create, assign, status changes, dept assignment | Department assignment sends no notification | S | P2 | Notification service | Assigned supervisor receives a notification; failure to notify does not roll back the assignment |
| Staff — attendance, duties, tasks, handover | Punch in/out with two-phase approval, duty plans, paper sheet entry, handover (no close state by design), department scoping | Edit duty missing; duty time is free text; leave-balance "used" never updated; no leave UI | S | P1 | none | Leave applied/approved from the UI; balances decrement and reconcile; editable duty rules documented |
| Staff — leave | Apply/approve/reject API; staff may apply for themselves | No self-service or approval UI; balances not decremented | S | P1 | Staff module | Staff apply and view leave in the app; manager approves/rejects in the app; balance updates and has tests |
| Dashboards and navigation | Role routing, admin dashboard with live summary, menu from permissions, phone bottom bar, service switches | Security dashboard has placeholder values; committee dashboard issues several separate calls and shows `--` with no retry; `SecurityDashboardScreen` reachable only by legacy roles | S | P1 | summary endpoints | Every card shows real data or an explicit empty/error state with retry; one summary call per dashboard |
| Maintenance billing | Elements, charge heads, cycles, bill lines, interest and waivers, parking (incl. two-wheeler), fines/extra charges, payments with allocation, cancellation releasing allocations | No database-level guard against duplicate generation; behaviour under concurrency untested; rented-flat surcharge and closed-period behaviour for billing not reconfirmed | S, T | P1 | Postgres test environment | Repeated or concurrent generation yields one bill per flat per cycle; line items reconcile to totals |
| Accounts | Chart of accounts, member and vendor subledgers, vouchers with maker-checker, reversals, year close/reopen, statements, PDFs, recurring expenses | Reconciliation of statements to vouchers and idempotency of auto-posting not independently re-verified here | T (11 test files), S | P1 | Billing | Deterministic scenario: source document → ledger → Trial Balance / I&E / Balance Sheet agree |
| Vendors and work orders | Vendor master with PAN, work orders with sanction levels, quotations, AMC contracts, vendor bills | No AMC/contract expiry notification job; TDS lives in accounts postings, vendor-side statutory setup not confirmed | S | P2 | Automation | Contract expiry produces a notification; TDS applied and reported per rules |
| Assets (inventory) | Register, categories, service history, warranty fields, weekly service/warranty digest to the office | No photo upload (single `document_url` text field); reminders go to the office only, once a week | S | P2 | Storage decision | Documents/photos attach and are access-controlled |
| Amenities | Slots, booking state machine, rules (owner-only, tenant restrictions, advance limits, deposit, charge) | `NO_DUES_REQUIRED` rule exists in the enum but nothing enforces it; deposit/charge not posted to accounts; refund tracking not found | S | P2 | Billing dues query, accounting design approval | Booking by a member with dues is refused when the rule is on; tests |
| Notices | Drafts, audience targeting (all/owners/tenants/wings/flats/staff/security/committee), acknowledgements, emergency alerts, communication log | Delivery status of push/email/SMS cannot be confirmed from the code | S, U | P2 | SMTP/push config | Delivery results recorded honestly; no claim of delivery without provider confirmation |
| Governance / certificates / shops / automation / checklist | Meetings and polls, documents, NOC/certificates with Devanagari PDF, shop master, scheduler (5 jobs), manager checklist | Service-level scope checks exist (S); automation and checklist routes were not probed with valid payloads | S | P2 | Tenant isolation | Included in Phase 1 negative tests |
| Notifications | In-app notification service, push and email services | Push and email delivery unverified (SMTP not configured per earlier notes) | U | P2 | environment | Out of scope until configured |
| CI and repository hygiene | Secret-scan and APK workflows | No test/analyze/migration CI; `flutter analyze` exits 1; 5,045 generated files tracked; secret scan red on `main`; root and backend `requirements.txt` diverge | S, T | P1 | none | See Phase 2 acceptance criteria |
| Deployment and readiness | Nixpacks, `start.sh`, `/health` | `/health` cannot signal failure; production branch unverifiable from the repo | S, U | P1 | Railway access | Readiness returns non-200 when the DB is unreachable or behind; migration failure stops the release |

## 8. Claims that cannot be verified here (U)

- Which branch Railway deploys, and whether auto-deploy is on.
- Whether the five recent migrations have been applied on production, and the current production Alembic revision.
- Production data volumes, existing duplicate emails/phones across societies (the multi-society migration splits such links), and any rows that violate new constraints.
- SMTP, push and SMS delivery.
- The gitleaks "leaks found: 2" findings and whether the exposed Railway database password has been rotated.
- Behaviour on PostgreSQL under concurrent requests (billing generation, voucher numbering, payment allocation).
- Hindi and Marathi wording quality.

## 9. Recommended order

1. **Phase 1 first**, scoped to: payroll and workload isolation; per-endpoint review of every route that takes a non-`society_id` identifier; the 17 inconclusive routes with valid payloads; regression tests for each; `/health` readiness and migration-failure handling. Do not touch the authentication system.
2. Then Phase 2 (CI), because it would have made 5.1 and the analyzer exit code visible, and because removing the tracked `test_venv/` and `test_build/` needs its own reviewed commit.
3. Then Phase 3 onwards in the order given, with leave self-service and leave-balance handling taken together in Phase 4.

Nothing here has been pushed. The report is committed locally only, pending approval.
