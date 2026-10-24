# Phase 1 — Production Safety, Authentication and Tenant Isolation

| | |
|---|---|
| Branch | `claude/current-status-bqz2l6` (the session's designated branch; equals `origin/main` `7f5af9c` plus the docs-only Phase 0 commit `0c3ec31`, PR #114) |
| Starting commit | `0c3ec31`. Working tree was clean at the start. |
| State of this work | **Uncommitted, unpushed, undeployed.** Nothing touched `main`, Railway, a production database or a secret. |
| Production | `https://society.duxos.in` was not contacted. Nothing here is validated against production. |
| Baseline (Phase 0) | Backend 1,223 passed / 0 failed on `7f5af9c`. |
| Result | Backend **1,285 passed / 0 failed** (1,223 + 62 new). |

Statuses: **PASS** = checked, no defect. **FIXED** = defect confirmed, fixed in this working tree, regression test added. **OPEN** = not fixed, reason given. **NOT VERIFIED** = could not be proven in this environment.

Evidence labels: **T** automated test, **L** live replay against the local PostgreSQL stack (two seeded societies), **P** throwaway probe on SQLite, **S** source reading only.

---

## 1. Summary for the decision-maker

1. **Critical, FIXED.** The public `POST /auth/register` creates a login with no society. The code reads "no society" as "platform administrator, no tenant filter", so any stranger could read other societies' data on at least 21 endpoints (society details, flats, vehicles, notices, governance documents, certificate requests, gate registers, parking, visitor gates). (P, then L)
2. **High, FIXED.** The whole payroll module had no society checks: an admin of one society could read and set salaries, file and approve attendance corrections and aggregate attendance for another society's staff. (P)
3. **High, FIXED.** `POST /vendors/payments/{id}/reverse` had no role guard: any signed-in member, including a Resident, could reverse a vendor payment of their society. (S, T)
4. **Medium, FIXED.** Every resident could read every other resident's ID-proof number, date of birth and emergency contacts, and every tenant's rent and deposit. Now redacted. (L)
5. **Medium, FIXED.** Cross-society reads in the workload summaries and `GET /staff/by-user`; penalty rules created in the society named in the request body; receipt PDF lookup by number alone (every society has `RCP-2026-00001`). (P, S, T)
6. **Medium, FIXED.** `/health` published the database user, host, port and name to anyone. There was no readiness signal, and a failed start-up migration was only logged at ERROR with the raw exception. (L)
7. **OPEN, needs your decision.** Roles are global, so a Society Admin editing the permission matrix changes access for every society (section 5.1).

---

## 2. Authentication findings

| # | Finding | Status | Evidence |
|---|---|---|---|
| A1 | Token validation: signature, expiry, `type`, `alg=none`, foreign signing key, missing/invalid subject, forged `roles` claim (authorisation reads the database, not the token) | PASS | T `tests/security/test_token_handling.py` (new) and `tests/auth/test_auth_hardening.py` |
| A2 | Deactivated, suspended or inactive users are refused at login and with an already-issued token | PASS | T existing |
| A3 | Logout revokes the device session at once; password change and admin reset sign other devices out; refresh refuses a revoked device | PASS | T `tests/auth/test_sessions.py` |
| A4 | Failed-login lock-out; a wrong password and an unknown account get the same reply | PASS | T existing + new |
| A5 | Password hashing is bcrypt via passlib; hashes and passwords never appear in login or `/auth/me` responses; no password or token is written to logs (grep of all `logger.*` calls) | PASS | S, T |
| A6 | **Self-registered login with no society treated as platform admin** | **FIXED** | P, L, T. `get_current_user` now refuses (403, "not linked to a society yet") any login that has no society, is not `is_superadmin`, and holds only `Resident`/`Tenant` roles; it may still use `/auth/me`, `/auth/logout`, `/auth/change-password`, `/auth/accept-terms`, `/auth/sessions*`. Platform admins (created by `create_platform_admin`, `is_superadmin=True`) are unaffected. |
| A7 | The same defect for a society-less login that holds an admin-level role (the shape ~440 existing test fixtures use as a stand-in for a platform admin) is **not** blocked | OPEN | Blocking it breaks hundreds of existing tests and needs a fixture migration. In production no flow creates such a login (users are created inside a society; platform admins carry `is_superadmin`). Recommended follow-up: make test fixtures use `is_superadmin`, then widen the rule to every non-platform login. |
| A8 | `SECRET_KEY` has a published default value; production's value cannot be seen from the repo | NOT VERIFIED / partly FIXED | The app now logs a CRITICAL warning (never the value) when the key is the default or shorter than 32 characters. **Manual check required:** confirm the Railway `SECRET_KEY` is long and random. |
| A9 | CORS allows every origin (`ALLOWED_ORIGINS=["*"]`) | OPEN (config) | Tokens are bearer headers, not cookies, so exposure is limited. A warning is logged in production. Set the app's origin on Railway. |
| A10 | Refresh tokens rotate but the previous one stays valid until its device session ends or 7 days pass | OPEN (design, low) | Single-use rotation would need a token-id store. |
| A11 | Web client keeps tokens in `SharedPreferences` (browser local storage) | OPEN (design, low) | Pre-existing; chosen because secure storage failed on web. An XSS bug would expose tokens. |
| A12 | `/docs`, `/redoc`, `/openapi.json` are public | OPEN (low) | Maps every endpoint for an attacker; disabling changes developer workflow. |
| A13 | Tokens issued before device sessions existed (no `sid`) work until they expire | OPEN (low) | Documented in `session_service.py`; at most 7 days. |
| A14 | Web and mobile use the same endpoints; the Flutter client refreshes once on 401 and clears tokens if refresh fails; no token is printed | PASS | S |
| A15 | Temporary passwords are returned once to the admin who creates/resets a user, by design | PASS | S |

## 3. Tenant-isolation findings

Method: (a) static call-graph scan of 334 id-keyed or write routes for any society-scope signal; (b) dynamic probes, 144 isolated cross-society calls on every route with `{society_id}`; (c) a read-only crawler on the local two-society PostgreSQL database that harvests real ids from society A and replays them as society B's admin (91 routes with ids; 29–198 valid combinations replayed each way).

| # | Finding | Status | Evidence |
|---|---|---|---|
| T1 | **Payroll: salary structures, corrections, monthly summaries** read and written across societies; any staff could file/read corrections for colleagues | **FIXED** | P (7 of 7 calls succeeded before), T `test_payroll_isolation.py` (14 tests). Every method now resolves the staff member / correction / summary inside the caller's society (404 otherwise), the body `society_id` is checked, and plain staff may act only on their own record. Platform admins keep access; they must name the society that owns the staff member. |
| T2 | `GET /workload/society/{id}/summary`, `GET /workload/staff/{id}/summary` | **FIXED** | P, L, T |
| T3 | `GET /staff/by-user/{user_id}` for privileged callers | **FIXED** | S, T |
| T4 | `POST /billing/penalty-rules` trusted `society_id` from the body | **FIXED** | S, T |
| T5 | Receipt PDF looked up by receipt number alone; numbers repeat per society, so a lookup could return another society's receipt (or a wrong 404) | **FIXED** | T (two societies, same `OPS-2026-00001`) |
| T6 | All other routes with `{society_id}` in the path refuse another society's admin (124 of 144 probes 403; 3 were the defects above) | PASS | P, T. The new whole-route-table test fails if any such GET returns 200 for another society, and a companion test checks the same routes do answer the owner. |
| T7 | 17 routes returned 422 (validation) before authorisation could be observed (governance/certificates/gate creates, `/staff/duties…`, `/accounts/vouchers/next-number`, bank-reconciliation import, `accounts/years/…/reopen`, `setup-progress`, `automation run`, …) | NOT VERIFIED dynamically | Source reading found `assert_society_access` or `resolve_create_society_id` in the services called by governance, certificates, gate, vendors; the rest have scope calls in the handler. Phase 2/3 should add valid-payload tests. |
| T8 | Id-keyed read crawl, both directions, after the fixes: remaining 200s are `GET /vehicles/flat/{flat_id}` returning `[]` | PASS | L. Proven scoped: a flat with 2 vehicles shows 2 to its own admin and 0 to the other society's. |
| T9 | 31 id-keyed GETs (complaints, certificates, vendor contracts/invoices/work orders, handovers, amenity day view…) could not be exercised dynamically (no data in the local seed) | NOT VERIFIED dynamically | Each was read: scope checks present in `_scoped`, `assert_society_access` or an `x.society_id != user.society_id` test (the vendor module uses `_scoped` and `resolve_create_society_id`). |
| T10 | Mutating routes keyed by id (PATCH/PUT/DELETE/POST on ids): reviewed statically; only the defects above lacked a scope signal | PASS (static) | S. Not every one has a negative test. |
| T11 | Platform admin: explicitly permitted via `is_superadmin`; preserved and tested. Its **cross-society reads are not audit-logged** (only the platform-console actions such as suspend and service switches are) | OPEN (medium) | The brief asks that such access be audited. Recommend an access-log for `is_superadmin` calls in Phase 2/3. |
| T12 | Report exports / downloads: bill, receipt, governance document, certificate, work-order PDFs | PASS (receipt, bill, billing PDFs by test; others static) | T, S |
| T13 | Background jobs (scheduler) | NOT VERIFIED | Iterates societies one at a time by design; not tested here. |
| T14 | Society-less administrative logins (see A7) | OPEN | Same as A7. |

## 4. RBAC findings

Method: 506 routes called with an empty body by a Resident, Security Staff, Manager, Committee Member (all in society A) and a self-registered login; a route "passes" the role guard if the reply is not 401/403. Before the fixes: Resident 81 routes, Security Staff 124, Manager 252, Committee Member 337, self-registered 102. A second scan found the 40 routes that need only a valid login and no role check.

| # | Finding | Status | Evidence |
|---|---|---|---|
| R1 | `POST /vendors/payments/{id}/reverse` had no role guard | **FIXED** | now `manager_above`, same as recording a payment. T |
| R2 | Resident and tenant registers readable by every member, including ID proofs, date of birth, emergency contacts, rent, deposit | **FIXED (redaction)** | `app/core/privacy.py`. Members still see names/flat/phone/email so the existing "members can read" tests hold; those fields are blank unless the caller is manager-and-above or it is their own record. T, L |
| R3 | Tenant agreements (`/tenants/{id}/agreements`) and flat occupancy history (`/occupancy/flat/{id}/history`) open to every member | **FIXED** | now `manager_above`. Only the admin resident/tenant screens call them. T |
| R4 | Payroll corrections: a plain staff member could file or read corrections for any colleague | **FIXED** | ownership check. T |
| R5 | Approve/reject of payroll corrections, leave, attendance: only manager-and-above (or the department supervisor for attendance) | PASS | T `test_only_manager_and_above_decide_corrections` (resident, security, supervisor refused; correction stays PENDING) |
| R6 | Residents cannot use administrative endpoints (users, accounts, billing cycles, penalty rules, role matrix, payroll) | PASS | T |
| R7 | Committee Member: read access to billing rules, no user administration | PASS | T |
| R8 | Security Staff reach no accounts, billing, vendor or salary routes. Extras beyond a Resident are gate, handovers, parking, staff duties, inventory reads and their own payroll correction | PASS | P. Inventory asset detail may show purchase cost: NOT VERIFIED whether that is "unrelated financial data". |
| R9 | Hidden buttons are not a control: every restriction above is enforced server-side and tested through the API | PASS | T |
| R10 | Permission-matrix edits (`PUT /roles/{id}/permissions`, `/forms`) left no trail | **FIXED** | audit-log entries (module `rbac`, old/new codes, who). T |
| R11 | **Roles are global** (`roles.name` unique, no society). A Society Admin has the `admin` permission, so editing the matrix changes the grants every society's residents/staff get, for example granting Residents `admin` everywhere | **OPEN** | Changing it alters the permission model, so it needs your approval. Options: (a) matrix edits platform-admin-only; (b) per-society role copies (needs a migration); (c) keep as is and rely on the new audit trail. |
| R12 | Whether every member should see the resident directory at all | **DECIDED 2026-10-24** | Members keep a neighbour directory of **name and flat**. Phone number and email now join the hidden fields (and members can no longer search by them); the office and each person's own record see everything. See `docs/CHANGELOG.md` 2026-10-24. |

## 5. Migration and start-up readiness

| # | Finding | Status | Evidence |
|---|---|---|---|
| M1 | Migration graph: 89 revisions, one head `f2c5d9e7a1b3`, two merge revisions, no missing parent | PASS | T `test_the_migration_history_is_one_unbroken_chain_with_one_head` |
| M2 | `/health` always returned 200 with `"status":"ok"` and exposed `postgresql://user:***@host:port/db` and raw error text | **FIXED** | now `database.status` only; migration check errors reduced to `{"status":"unknown"}`. Still always 200, so Railway's health check and the three existing `/health` tests are unaffected. L, T |
| M3 | No readiness signal | **FIXED** | new `GET /health/ready`: 200 only if the database answers, the schema equals the head and any start-up migration succeeded; otherwise 503. Verified live: schema one revision behind gives `/health` 200 and `/health/ready` 503 (scratch database, since dropped); an unreachable database gives 503. **Railway's `healthcheckPath` was not changed.** Pointing it at `/health/ready` is a deployment decision: it would stop a release from going live until migrations have been run, which matters if migrations are run by hand after deploy. |
| M4 | A failed start-up migration was logged at ERROR with the raw exception (which can contain a connection URL) and was otherwise forgotten | **FIXED** | logged at CRITICAL with credentials removed, remembered in `migrate.startup_result`, reported by `/health/ready`. T |
| M5 | `start.sh` aborts the deploy on a failed `alembic upgrade head` when `RUN_MIGRATIONS=true` (`set -e`) | PASS | S. If the flag is unset the app starts on whatever schema exists; `/health/ready` now says so. |
| M6 | Start-up does nothing destructive (no `create_all`/`drop_all`; scheduler only starts) | PASS | S |
| M7 | Whether the five recent migrations are applied on production | NOT VERIFIED | needs Railway access |

## 6. Files changed

Application (16 modified, 1 new, +221/−48):
`app/core/dependencies.py`, `app/core/society_gate.py`, `app/core/privacy.py` (new), `app/api/routes/{payroll_readiness,workload,resident,tenant,occupancy,role}.py`, `app/modules/staff/services/{payroll_service,staff_service}.py`, `app/modules/staff/routes/staff.py`, `app/modules/billing/{routes/billing.py,services/billing_service.py}`, `app/modules/vendor/routes/vendor.py`, `app/db/migrate.py`, `app/main.py`.
No migration, no schema change, no new dependency, no Flutter change.

Tests: new package `tests/security/` (62 tests: `test_payroll_isolation.py`, `test_tenant_isolation_and_rbac.py`, `test_token_handling.py`, `test_health_and_migrations.py`, shared `world.py`), plus a small helper `place_in` in `tests/conftest.py`.

**Existing tests edited (14 files, +64/−13), for review.** Assertions were not changed or removed. Each edit puts a Resident/Tenant fixture in the society it uses (`place_in(db, resident, society)`), because a resident with no society can no longer act (finding A6). Files: `amenity/test_amenity.py`, `billing/test_maintenance_billing.py`, `billing/test_online_payments.py`, `complaint/test_complaint.py`, `complaint/test_on_duty_assignment.py`, `complaint/test_own_flat_restriction.py`, `master/test_master.py`, `notifications/test_push.py`, `rbac/test_forms_matrix.py`, `rbac/test_rbac.py`, `rbac/test_rbac_hardening.py`, `test_seed_roles.py`, `visitor/test_visitor.py`, `conftest.py`. One test changed meaning: `master/test_master.py::test_get_society_not_found` now runs as a platform admin, because a society member asking for a missing society correctly gets 403 (no existence leak) instead of 404.

## 7. Verification

| Check | Command (from `backend/`) | Result |
|---|---|---|
| New tests against the **original** code (fixes stashed) | `git stash push -- backend/app` then `python -m pytest tests/security` | 18 failed (one per defect) + 14 errors (readiness module absent), proving the tests detect the defects. Fixes restored afterwards. |
| New tests with fixes | `python -m pytest tests/security` | pass |
| Full backend suite, final | `python -m pytest -q` | **1285 passed, 0 failed, 4 warnings, 18 min 49 s** |
| Lint / format | none documented (the Makefile declares a `lint` target but never defines it) | not run as a repo check. Extra, non-repo check: `ruff check --select F,E9` on all changed files compared with the base: no new finding after removing 3 unused imports from my new tests. All changed files byte-compile. |
| Live replay, local PostgreSQL | restart API on new code; self-register + read; Lotus admin vs Ganesh ids; resident listing; platform admin; id crawler both directions | stranger 403 on 5/5 society endpoints and 200 on `/auth/me`; platform admin 200 on both societies; Lotus admin 403/404 on every Ganesh payroll/workload/staff call; only `vehicles/flat` 200s (proven scoped) |
| Readiness, schema one revision behind | scratch DB via `pg_dump`, `alembic_version` set to `e1b4c8d6f3a2`, second API on :8001 | `/health` 200, `/health/ready` 503; database dropped afterwards |
| Flutter | not run | no Flutter file changed |

Baseline failures before the change: none (Phase 0 run on `7f5af9c`). An earlier attempt at a stricter rule produced hundreds of failures and was abandoned in favour of the narrow rule (A6/A7). That attempt was a run I stopped, not a result I am reporting as passing.

## 8. Not run / not verified

- Anything against production or Railway (`SECRET_KEY` strength, CORS, applied migrations, `RUN_MIGRATIONS`, health-check path).
- PostgreSQL-specific behaviour in the pytest suite (it runs on SQLite); the live replay above used PostgreSQL manually, not as automated tests.
- The 17 inconclusive routes (T7) and 31 unexercised id routes (T9) beyond source reading.
- Background-job isolation (T13); concurrency.
- Flutter analysis/tests.

## 9. Manual review required before merge

1. Read the 14 edited existing tests (section 6).
2. Decide R11 (global roles / who may edit the permission matrix) and R12 (resident directory visibility).
3. Decide whether Railway's health check should move to `/health/ready` (M3), and confirm `SECRET_KEY` and `ALLOWED_ORIGINS` on Railway (A8, A9).
4. UX follow-up (no code change made): the app's flat-detail "People" card reads residents and tenants by flat; for roles below manager it will now show as empty because the tenant lookups are redacted/blocked. Worth a friendlier message.
5. Approve the commit, then push and PR. **Not done: awaiting your approval.**

## 10. Recommended next phase

Phase 2 (CI and regression protection). It would make the new `tests/security` suite run on every PR, and would have caught the findings above and the `flutter analyze` exit code from Phase 0.
