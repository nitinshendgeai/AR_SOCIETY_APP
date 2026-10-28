# Help AI Bot — Phase 1 Verification Report

Audit only. No application code, migrations, dependencies, CI, env files or deployments were changed. Nothing was committed or pushed.

## 1. Repository state

| Item | Value |
|---|---|
| Branch | `claude/happy-dirac-2h9n2q` |
| HEAD | `83e1e98f4cd678f7dfe97abb3ac522dd942ca2f4` — **matches** the expected baseline |
| Working tree | Clean before and after the audit (this report is the only new file). Test artefacts (`test_ar_society.db`, `__pycache__`) are gitignored. |

## 2. Verified facts vs unverified assumptions

**Verified (read in code or executed)**
- No Help AI Bot exists anywhere: no route, service, provider adapter, Flutter chat UI, test, dependency or config name (searched `git grep` for assistant / chatbot / openai / anthropic / gemini / llm / rag across backend, mobile, docs, config).
- Auth, role and society scope come from server-side state: the JWT carries only `sub` / `sid` / `peers`; the `User` row is loaded from the DB (`backend/app/core/dependencies.py:33-90`).
- Roles are DB-driven permission codes (`require_permission`, `dependencies.py:99-145`).
- Provider configuration is absent from `Settings` (`backend/app/core/config.py`) and from `backend/.env.example`.
- Six focused test files pass (section 8).

**Unverified / assumptions**
- Exact role→permission seed values (`rbac_seed.py`) were not enumerated; role-case assessments below are from guard code, not exercised per role.
- Whether platform admins satisfy `manager_above` on accounts routes was not traced.
- Production data, Railway settings and the deployed environment were not touched; behaviour there is unverified.
- Flutter was not built or tested (no Flutter SDK run).

## 3. Existing implementation inventory

- **Help Bot:** none.
- **Current help launcher:** `mobile/lib/core/help/help_launcher.dart`. It is **web-only** (`helpAvailable => kIsWeb`; `help_open_io.dart` is a no-op), opens the static page `/help/DUX_OS_Help_Guide.html?role=<role>`, and is wired in `app_shell.dart:536,565` and `phone_bottom_bar.dart:183`. The role in the URL is a UI hint only.
- **App registration:** `backend/app/main.py` includes `api_router` at `/api/v1`. `/docs` and `/openapi.json` are enabled in all environments.
- **Flutter networking:** a single Dio client with a Bearer interceptor and 401 refresh (`mobile/lib/core/api/api_client.dart`). Base URL comes from `API_BASE_URL`. A chat feature would reuse this client.
- **HTTP client dep:** `httpx` is already in `backend/requirements.in`. No LLM SDK.

## 4. Documentation coverage

| Module | Sources | Assessment |
|---|---|---|
| Maintenance billing | `GUIDES/MAINTENANCE_BILLING_COMPLETE_GUIDE.md` (309 lines), `GUIDES/MAINTENANCE_ELEMENT_WISE_MANUAL.md` (310), `MODULES/BILLING.md`, `BILLING_WORKFLOW.md` | Strong; step-by-step and written against code. The element-wise manual itself says to verify rules against the bye-laws. |
| Vendors | `GUIDES/VENDOR_MASTERS_COMPLETE_GUIDE.md` (185), `MODULES/VENDOR_AMC.md`, `VENDOR_WORKFLOW.md` | Good; cross-check TDS (`TDS_RATES.md`) before answering tax questions. |
| Accounts | `MODULES/ACCOUNTS.md` (134), `ACCOUNTING_PROCEDURE.md` (120) | Usable; developer-oriented (API tables). Needs an SOP-style user view. |
| Parking/gate, staff, login/devices | `GUIDES/*` | Good. |
| All roles overview | `user-guide/DUX_OS_Help_Guide.html` (958 lines) | Best retrieval source: sections carry `data-roles` / `data-title` attributes, so role filtering is possible at ingest time. Duplicate copy in `mobile/web/help/`. |
| Others (complaints, amenities, visitors, notices, inventory…) | `MODULES/*`, `*_WORKFLOW.md` | Present; not deep-checked. |

**Conflicts / gaps**
- `docs/RBAC_MATRIX.md` lists only Admin / Committee / Resident / Security / Staff; the code and help guide also use Manager / Supervisor / Tenant. It is stale and **must not** be a retrieval source for permission answers. `USERS_AND_ROLES.md` and `DEFAULT_ROLE_SETUP.md` were not reconciled against code.
- `docs/KNOWN_ISSUES.md` notes older societies lack some roles — answers must not assume the default role set.
- `AI_DEVELOPMENT_RULES.md` and `ARCHITECTURE.md` are developer docs: exclude from end-user retrieval.
- Business rules not documented for any "why is my config wrong" diagnosis were not invented; diagnostics rules need an approved checklist.
- PDFs duplicate HTML/MD; ingest only the source text.

**Suitable for retrieval:** the help guide (role-tagged), the two billing guides, the vendor guide, parking/staff/login guides, and `MODULES/ACCOUNTS.md` after review.

## 5. Authentication / RBAC / tenant isolation

- `get_current_user` validates an access token, loads the active user from the DB, checks the device session, then applies three gates: no-society (`no_society_block_reason`), suspended society, and platform-switched-off services (`society_gate.py`, `services_catalog.py`). `service_for_path` maps by URL prefix, so a new `/assistant` prefix would be **ungated by service switches** unless registered.
- Tenant scope: `user.society_id` is DB state. `None` means platform admin / no tenant filter (`tenant_scope.py`). `assert_society_access` is the shared check. Society-less non-admin logins are blocked from society data by `no_society_block_reason` (residents/tenants only).
- Client-supplied role, user ID and society ID cannot grant access **if** the assistant derives them from `get_current_user` and ignores request-body values. Existing routes put `society_id` in the path and compare it with `user.society_id`. The assistant should not take a society_id from the client at all, except for platform admins.
- Platform admins have `society_id=None`, so an assistant must require an explicit target society and audit it.
- Resident-specific scoping exists for bills (`_ensure_can_view_flat`, 404 on mismatch). Accounts routes require `manager_above` at router level (`accounts.py:40`). Vendor routes are guarded per endpoint (not fully enumerated).
- Data-exposure risk: help answers built from per-society data (dues, vendor bills, ledgers) would reach residents unless the assistant re-applies the same guards. Phase 1 should answer from docs plus non-sensitive config booleans only.
- Existing regression tests: `tests/security/*` (21+ tests in the isolation file), `tests/rbac/*`, CI requires ≥50 security tests.

## 6. Unsafe read paths (still present at HEAD)

All GETs below mutate (seed rows and `db.commit()`):

| Endpoint | Evidence | Mutation |
|---|---|---|
| `GET /accounts/chart/{society_id}` | `accounts.py:248-261` (`db.commit()` "the standard chart, if this was the first visit") | `AccountsService.chart → ensure_chart → seed_chart_of_accounts` |
| `GET /accounts/ledgers/{society_id}` | `accounts.py:264-269` | `list_accounts → ensure_chart` |
| `GET /accounts/registers/cash-bank/{id}`, `/members/{id}`, `/summary/{id}`, `/expenses-by-element/{id}`, `/bank-reconciliation/{id}`, `/years/{id}` | `accounts.py:339,400,625,651,702,796` | same chart seeding + commit |
| `GET /billing/elements/{society_id}` | `billing.py:308` → `billing_service.py:310-319` | seeds standard elements, commits (covered by test `test_first_read_seeds_standard_bye_law_elements_once`) |
| `GET /vendors/tds/rules/{society_id}` | `vendor.py:617-624` | `ensure_default_rules` + commit |

Reads that looked suspicious but did not mutate in the code read: `GET /billing/maintenance-settings/{id}` (returns in-memory defaults), `GET /billing/cycles/{id}/preview` and `cycle_readiness` (no writes found in `period_expenses.py`). PDF GETs under billing were not traced.

The two risks named in the brief (`/chart`, `/ledgers`) **still exist**, and the pattern is wider than those two.

**Recommendation:** the assistant must not call these routes or services. Add dedicated read-only service functions that `SELECT` only and report "not initialised" instead of seeding (for example `chart_exists`, `elements_count`, `tds_rules_count`, last-closed FY, readiness via `cycle_readiness`), run through a read-only DB session or a session that is rolled back, never committed.

## 7. Provider readiness

- Provider adapter: **none**. SDK dependency: **none**.
- Configuration names referenced in code for AI: **none**. Existing optional-secret pattern (blank = feature off, graceful no-op): `FIREBASE_SERVICE_ACCOUNT_JSON`, `SMTP_*`. A provider key should follow that pattern (optional, blank = assistant disabled with a clear message).
- Startup: nothing mandatory for a provider. `SECRET_KEY` default is logged critical, not fatal (`main.py`), and `ALLOWED_ORIGINS` defaults to `["*"]` (warned in production).
- Secret leakage: the unhandled-error path returns a generic message (`utils/exceptions.py`); `/health` hides the DB location; `Settings` has no `repr` guard but is not returned by any route found. Flutter `.env` files contain only `API_BASE_URL`, `APP_NAME`, `APP_ENV` — no provider key would ever be needed client-side. Risk: `logger.exception(f"...{exc}")` could log provider error text, and `DEBUG` is a setting; provider errors must be sanitised before logging.
- Values were never read or printed.

## 8. Test commands and outcomes

Environment: isolated venv at `<scratchpad>/venv` created with `pip install --require-hashes -r backend/requirements-dev.txt` (the CI method; repo dependency files untouched). **Python 3.13.17**, whereas CI/production use 3.12 — a deviation. Env vars as in CI: `DATABASE_URL=sqlite:///./test_ar_society.db`, throw-away `SECRET_KEY`, `APP_ENV=test`, `SCHEDULER_ENABLED=false`. Working directory: `backend/`. Command per file: `python -m pytest <file> -q -o log_cli=false -p no:cacheprovider`.

| File | Exit | Result |
|---|---|---|
| `tests/security/test_tenant_isolation_and_rbac.py` | 0 | 23 passed, 0 failed, 0 skipped (82s) |
| `tests/billing/test_month_end_readiness.py` | 0 | 16 passed (22s) |
| `tests/billing/test_manager_billing_access.py` | 0 | 3 passed (7s) |
| `tests/billing/test_maintenance_elements.py` | 0 | 10 passed (9s) |
| `tests/accounts/test_accounts.py` | 0 | 15 passed (21s) |
| `tests/vendor/test_vendor_hardening.py` | 0 | 10 passed (13s) |

77 passed, 0 failed, 0 skipped. Only SQLite throw-away DB; no production DB or migrations touched. The full suite, Flutter tests and Postgres-specific behaviour were **not** run.

## 9. Prioritised gaps

1. **High — GET endpoints mutate state** (section 6). `backend/app/modules/accounts/routes/accounts.py:248,264,339,400,625,651,702,796`; `backend/app/modules/billing/services/billing_service.py:310`; `backend/app/modules/vendor/routes/vendor.py:617`. Build separate read-only diagnostics.
2. **High — No provider, no AI settings, no assistant code.** All of it is new: settings (optional key, model, timeout, limits), adapter with timeouts and graceful degradation, rate limiting per user.
3. **High — Service gating by URL prefix.** A new route prefix needs a decision (core vs service) in `services_catalog.py`, or suspended/disabled societies are inconsistent.
4. **Medium — Stale/conflicting docs.** `docs/RBAC_MATRIX.md` omits Manager/Supervisor/Tenant. Needs reconciling or exclusion; permission answers should come from live server-side permissions, not docs.
5. **Medium — No retrieval corpus or ingestion rule.** Role-tag mapping (`data-roles`) exists in the help guide only; markdown guides need role metadata and an approved-document allowlist.
6. **Medium — Platform admin / no-society handling** must be explicit for the assistant (`society_id=None` is "no filter").
7. **Medium — Hygiene:** `test_venv/` and `test_build/` (5,045 tracked files, last touched in the PR #116 merge) are committed virtualenvs containing site-packages; they bloat the repo and any code scan (including prompt-ingestion or secret scans). Not changed here.
8. **Low — `/docs` and `/openapi.json` are public in all environments;** `ALLOWED_ORIGINS` defaults to `*`.
9. **Low — Help is web-only** (`helpAvailable => kIsWeb`); the mobile chat UI is a net-new entry point.
10. **Low — Python 3.13 vs 3.12:** tests passed on 3.13 but CI parity not confirmed.

## 10. Recommendation: **CONDITIONAL GO**

Proceed to implementation of a docs-grounded, authenticated chat, subject to:
- Phase 1 diagnostics use only newly written, non-committing read-only functions; the mutating GETs above are never called.
- Role, user and society are taken solely from `get_current_user`; no client-supplied identity fields; platform admin requires an explicit, audited target.
- Retrieval allowlist excludes `RBAC_MATRIX.md` and developer docs; role-tagged chunks filtered by server-side permissions.
- Provider key optional, disabled gracefully, timeouts/limits/sanitised logging; new route prefix registered in the service gate.
- Required tests: cross-tenant, unauthorised data request, provider failure/timeout, retrieval grounding/no-answer, prompt-injection, and a mutation-prevention test (row counts unchanged after assistant calls).

Separately, the GET-mutation pattern is a latent issue worth fixing independently of the bot.
