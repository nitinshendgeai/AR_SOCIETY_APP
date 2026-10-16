# Phase 2 — CI, Automated Testing and Regression Protection

| | |
|---|---|
| Branch | `claude/current-status-bqz2l6` (the session's designated branch), reset to `origin/main` `b2daa64` (Phase 0 + Phase 1 merged via PR #114) before this work |
| State of this work | **Uncommitted, unpushed, undeployed.** Nothing touched `main`, Railway, a production database, repository settings or branch protection. |
| Production | Not contacted. No production credential is used by any workflow or script added here. |
| Starting point | `main` had two workflows: **Secret Scan** (red on every recent run) and **Build Android APK** (green, main only). **No workflow ran a single test.** `main` is not protected and has no rulesets (read-only check, section 7). |
| Result | Backend **1,300 tests** (1,285 existing + 15 new CI self-tests), Python 3.12, hash-enforced install; migration checks on PostgreSQL 16; Flutter analysis clean of errors and warnings, **232 tests**, web release build. Details and exact output in section 6. |

Statuses: **PASS** verified here. **BLOCKED** cannot be done, exact reason given. **NOT VERIFIED** could not be proven in this environment (chiefly: the workflows have never run on GitHub's runners because nothing was pushed).

---

## 1. Summary for the decision-maker

1. **Test CI now exists.** Before this phase a pull request could break any test, the migrations or the app build and show only the (already red) secret-scan check.
2. **Three workflow files** run on every pull request and every push to `main`, with **no path filters** (so a check can be made "required" without ever being skipped): `backend-ci.yml` (2 jobs), `flutter-ci.yml` (2 jobs); `secret-scan.yml` and `build-apk.yml` were kept and hardened.
3. **A stale lock file was found and fixed.** `backend/requirements-dev.txt` was missing seven packages that the code imports (reportlab, fpdf2, pillow and others). A clean install from the repository could not run the test suite (`ModuleNotFoundError: reportlab`). It was regenerated from `requirements-dev.in`, constrained to the production lock: **no production version moved**.
4. **The migration chain is validated against a real PostgreSQL** (empty database to head, last migration reversible, earlier revision to head, no missing/extra table or column, `/health/ready` is 200 at head and 503 one revision behind). The five migrations you asked about are linear ancestors of the single head (section 4).
5. **Secret Scan cannot go green yet, and I did not hide that.** It reports the same two findings as on `main` (the Firebase web key in two files). Nothing was suppressed. Options are in section 5.
6. **Recommendation:** make four checks required once the first run on GitHub confirms they are green (section 7). Do not make Secret Scan required until the Firebase key is restricted and the finding handled.
7. **Not done, by instruction:** nothing was committed, pushed or merged; branch protection and repository settings were not changed; no deploy.

---

## 2. What existed before (audit, nothing rebuilt from scratch)

| Item | Finding |
|---|---|
| `.github/workflows/secret-scan.yml` | gitleaks v8.28.0 in Docker on the working tree. **Red on `main` at `b2daa64`, `7f5af9c` and `6507ca3`**, always for the same two findings. Preserved; only the checkout step was pinned and made credential-free. |
| `.github/workflows/build-apk.yml` | Builds a release APK on push to `main` (and to one old feature branch, `claude/beautiful-davinci-dLJtD`). Green. Had no `permissions:` block (GitHub default token rights), unpinned actions, and interpolated a repository variable directly into a shell command. Hardened (section 5). |
| Backend tests in CI | None. |
| Flutter analysis/tests in CI | None. |
| Migration checks in CI | None. |
| Python version | Production: `backend/runtime.txt` = `python-3.12.3`, nixpacks `python312`. The dependency locks were compiled on 3.11. Verified that the locks install and pass on 3.12 (below). |
| Dependency install | Railway installs `backend/requirements.txt` (hash-pinned). `requirements-dev.txt` (that lock plus test tools) was stale (point 3 above). |
| Linters/formatters (backend) | **None are configured** (no ruff/flake8/black/mypy config or dependency). None were added; CI runs a syntax check (`compileall`) and an import check only. |
| Dart formatting | 278 of 300 Dart files differ from `dart format`. A formatting gate would fail on day one and a mass reformat would bury real changes, so it is **not enforced** (BLOCKED, reason: pre-existing formatting debt; do it as its own reviewed change). |
| `flutter analyze` | 15 warnings and 437 infos at the start. 15 warnings cleaned (section 3); the infos are tolerated with `--no-fatal-infos`. |
| Branch protection / rulesets | `main`: "Branch not protected" (HTTP 404); rulesets: `[]`. |

---

## 3. What was added or changed

### 3.1 Backend CI — `.github/workflows/backend-ci.yml` (new)

Triggers: `pull_request`, `push` to `main`, `workflow_dispatch`. Permissions: `contents: read`. Concurrency: a newer push to the same PR cancels the older run; runs on `main` always finish.

**Job `Backend tests (Python 3.12)`**
1. Checkout (pinned SHA, `persist-credentials: false`), Python 3.12 with pip cache keyed on `requirements-dev.txt`.
2. `pip install --require-hashes -r requirements-dev.txt` then `pip check`: any drift from the lock is a hard failure.
3. `python -m compileall -q app tests scripts` and `from app.main import app` (syntax and import check; the only "lint" the project supports).
4. **Security regression tests first, on their own** (`tests/security`: authentication, tenant isolation, RBAC, readiness, from Phase 1), JUnit report, then the result checker (at least 50 tests).
5. **Full suite**, JUnit report, then the result checker: at least 1,200 tests, at most 5 skipped, and at least 50 of them from `tests.security`.
6. Upload the two JUnit reports as an artifact (14 days).

Test-only environment: `DATABASE_URL=sqlite:///./test_ar_society.db` (a throw-away file inside the runner), `SECRET_KEY` a 50-character dummy, `APP_ENV=test`, `SCHEDULER_ENABLED=false`. No repository secret is referenced anywhere in the file.

**Job `Migrations (PostgreSQL 16)`**
A `postgres:16` service container with throw-away credentials that exist only inside that job. Steps: graph check, then `check_migrations.py full` (below), then the CI-script self-tests including the schema-drift negative case against that Postgres.

### 3.2 `backend/scripts/ci/check_migrations.py` (new)

| Check | What fails it |
|---|---|
| `graph` (no database) | more than one head; a parent that does not exist; duplicate revision id; a revision unreachable from the head; Alembic unable to load the history |
| empty database to head | any migration erroring on a fresh PostgreSQL; takes ~6 s |
| structural drift | a table or column in the models but not in the migrated schema, or the reverse. (Alembic's own `alembic check` is **not usable**: it reports type/default noise on this project, so only table/column presence is compared.) |
| reversibility | `downgrade -1` then `upgrade head` on the head migration |
| earlier revision to head | upgrading from a database parked six revisions back |
| readiness | the real app answers `/health/ready` 200 at head and 503 when `alembic_version` is one revision behind |

It only ever touches databases it creates itself (`mig_fresh_<hex>`, `mig_upgrade_<hex>`) and always drops them. It never reads `DATABASE_URL` of an existing system and refuses to run without an explicit `--admin-url`.

### 3.3 `backend/scripts/ci/check_test_results.py` (new) — the false-green guard

pytest already exits non-zero on failure. This is a second line of defence that exits 1 if: the report is missing, empty or garbled; any failure/error is recorded; fewer than the minimum tests ran; more than the allowed number were skipped; or a required package (the security tests) has fewer tests than required. It writes a summary to the GitHub job summary page.

### 3.4 Tests of the CI tooling — `backend/tests/ci/test_ci_scripts.py` (new, 15 tests)

Two heads, missing parent, duplicate id, empty/missing history, CLI exit codes, a database with a missing and an extra column (PostgreSQL only; skipped locally unless `MIGRATION_TEST_ADMIN_URL` is set, and run with zero skips in the CI migrations job), and every false-green case of the result checker.

### 3.5 Flutter CI — `.github/workflows/flutter-ci.yml` (new)

| Job | Steps |
|---|---|
| `Flutter analyze and tests` | Flutter **3.47.5** (pinned: the version verified here), `cp .env.example .env` (public placeholders only), `flutter pub get --enforce-lockfile`, `flutter analyze --no-fatal-infos`, `flutter test` |
| `Flutter web release build` | the production web flags with a placeholder API address (`https://ci.invalid/api/v1`), then confirms `main.dart.js` and `index.html` exist. Output discarded. No production secret or URL. |

Dart cleanup needed to make the analyzer a gate: 12 files, +1/−19 lines, only unused imports/fields/one dead method and one pattern fix (`StaffListError(:final statusCode) when statusCode == 403`). No behaviour change; `flutter analyze` exit 0 and 232 tests pass after the change.

### 3.6 Other files

| File | Change |
|---|---|
| `backend/requirements-dev.txt` | Regenerated (point 3). `pip-compile --generate-hashes -c requirements.txt --no-header -o requirements-dev.txt requirements-dev.in`; production lock unchanged. |
| `backend/Makefile` | New targets `test-security`, `lint`, `check-migrations`, `check-migrations-db`. |
| `docs/TESTING_STRATEGY.md` | New "Continuous integration" section with the local equivalent of every CI step; corrected the stale "171 tests" and "SQLite in-memory" wording. |
| `.github/workflows/secret-scan.yml` | Checkout pinned to a full commit SHA, `persist-credentials: false`. Scan command, image, triggers and permissions are unchanged. |
| `.github/workflows/build-apk.yml` | `permissions: contents: read`; four actions pinned; `persist-credentials: false`; `API_BASE_URL` passed through a step `env` instead of interpolated into the script. Triggers unchanged (Phase 2 does not make it deploy anything). |

---

## 4. Migration history — the five revisions

The five revisions named in the Phase 0 report as "not yet confirmed as applied on production" were checked **against the actual history** (parsed through Alembic's own script loader). They were not run and not recreated.

| # in history | Revision | Parent | Purpose |
|---|---|---|---|
| 85 | `b7e3d1c9a4f2` | `e4c1324d5e6f` | Manager's daily checklist |
| 86 | `c8f2a6d4b1e9` | `b7e3d1c9a4f2` | Two-wheeler rate on a parking charge head |
| 87 | `d9a3b7c5e2f1` | `c8f2a6d4b1e9` | Interest waivers |
| 88 | `e1b4c8d6f3a2` | `d9a3b7c5e2f1` | Per-society service switches |
| 89 (head) | `f2c5d9e7a1b3` | `e1b4c8d6f3a2` | A mobile number or email may belong to one login per society |

89 revisions, one head (`f2c5d9e7a1b3`), no missing parent, no duplicate. The five are an unbroken line ending at the head, so a production database that is at `e4c1324d5e6f` upgrades through exactly these five and nothing else. The CI job proves the whole chain builds on PostgreSQL and the tail is reversible. **Whether production has already applied them is still NOT VERIFIED from here**; check `GET /health/ready` on production (it reports the database revision against the code's head) or `alembic current` there.

Local result of the full migration check (PostgreSQL 16, throw-away databases), total 37 s:
```
1. migration graph        ok: one head, no missing parent, no duplicate id, every revision reachable
2. empty database -> head upgraded 0 -> f2c5d9e7a1b3 in 5.7s; models and migrated schema agree on every table and column
3. head reversible        f2c5d9e7a1b3 -> e1b4c8d6f3a2 -> f2c5d9e7a1b3
4. earlier -> head        e4c1324d5e6f -> f2c5d9e7a1b3
5. /health/ready          at head -> HTTP 200; one revision behind -> HTTP 503
MIGRATION CHECKS PASSED
```

---

## 5. Workflow security and secret scanning

| Control | Status |
|---|---|
| Minimum `GITHUB_TOKEN` permissions | PASS — `permissions: contents: read` at the top of all four workflows; no job asks for more |
| Third-party actions pinned to full commit SHAs with a version comment | PASS — `actions/checkout` v6.0.3 (v4.4.0 in the APK workflow, kept at its existing major), `actions/setup-python` v5.6.0, `actions/upload-artifact` v4.6.2, `actions/setup-java` v4.9.1, `subosito/flutter-action` v2.23.0 (every SHA re-checked against its upstream tag with `git ls-remote`). The Docker image in Secret Scan is pinned by version tag `gitleaks:v8.28.0` (unchanged; a digest pin is optional hardening). |
| `pull_request_target` | none anywhere |
| Secrets referenced | none in any workflow. The only credentials are the throw-away Postgres user/password inside the migrations job and a dummy `SECRET_KEY`; both are labelled as test-only. |
| Expression injection | `API_BASE_URL` no longer interpolated into a shell line; CI uses no `${{ github.event.* }}` text in `run:` |
| Checkout credentials | `persist-credentials: false` everywhere (no later step needs to push) |
| Deploys | none; no workflow added or changed here deploys, touches Railway, or writes to the repository |
| `continue-on-error`, `|| true`, ignored exit codes | none. The result checkers run with `if: !cancelled()` so they report even after a test failure, and the job still fails because the test step already failed. |
| `actionlint` 1.7.12 | exit 0 on all four workflows |

### Secret Scan result (accurate, nothing suppressed)

Scanned a clean copy of every tracked and new file (build output excluded) with gitleaks v8.28.0, the same version CI uses, `--no-git --redact`:

```
gcp-api-key  mobile/lib/core/push/push_config.dart   line 14
gcp-api-key  mobile/web/firebase-config.js            line 6
2 findings
```

These are the same two findings that make Secret Scan red on `main`. The new workflow files (including the throw-away Postgres password and dummy `SECRET_KEY`) produce **no** finding. The values were not printed anywhere in this work.

What they are: a Firebase **web** API key. These identify the Firebase project to the browser SDK and are public by design (they ship in every web client), so this is not by itself a leaked server secret. What matters is whether the key is **restricted** in Google Cloud. I cannot check that from here.

- **Flag, for you to do (not done by me):** in Google Cloud Console, API & Services, Credentials, open that key: set HTTP-referrer restrictions to `society.duxos.in` (and any dev origins) and limit "API restrictions" to the Firebase APIs actually used. If its history ever included use as anything other than a web key, rotate it and update `push_config.dart` / `firebase-config.js`.
- **Options to turn Secret Scan green** (decision needed; I made none):
  1. **Restrict the key, then add a narrow allowlist** (a `.gitleaks.toml` limited to those two exact files/lines with a comment explaining why) and point the scan at it. Honest and durable; recommended. The finding is then documented, not hidden.
  2. Move the key out of source into the build (`--dart-define`) and a deploy-time generated `firebase-config.js`. Cleaner, larger change, touches runtime packaging; not for this phase.
  3. Leave it red and **do not require** it. Safe, but a red check that everyone ignores teaches people to ignore the next real finding.

---

## 6. Verification (exact results)

Environment: Python 3.12 virtualenv from a clean hash-enforced install of the new `requirements-dev.txt`; local PostgreSQL 16; Flutter 3.47.5; gitleaks v8.28.0; actionlint.

| Check | Result |
|---|---|
| Clean install on 3.12 with `--require-hashes`, `pip check` | PASS |
| **Baseline**, full suite, Python 3.12, before the new tests | **1,285 passed, 0 failed, 0 errors, 0 skipped** in 1,017 s (16:56). Same as the Phase 1 result, so the lock regeneration changed nothing. |
| Result checker on that run (`--min-tests 1200 --max-skipped 5 --require-package tests.security=50`) | passed, exit 0 |
| `tests/ci` without PostgreSQL | 14 passed, 1 skipped (the PostgreSQL-only drift test), 2.5 s |
| `tests/ci` with PostgreSQL | **15 passed, 0 skipped**, 13.8 s; checker `--min-tests 15 --max-skipped 0` exit 0 |
| Security step as CI runs it (`pytest tests/security` + checker `--min-tests 50`) | **62 passed**, 0 failed, 0 skipped in 120 s; checker exit 0 |
| Full suite as CI runs it (includes `tests/ci`) + checker (`--min-tests 1200 --max-skipped 5 --require-package tests.security=50`) | **1,299 passed, 1 skipped, 0 failed** (1,300 tests) in 1,010 s; the one skip is the PostgreSQL-only drift test, which runs in the migrations job. Checker exit 0. |
| `make lint` (compileall + import) | PASS — `app imports, 513 routes` |
| Migration graph on the real history | PASS — `migration graph ok` |
| Full migration check on PostgreSQL 16 | PASS (section 4) |
| `flutter pub get --enforce-lockfile` | PASS |
| `flutter analyze --no-fatal-infos` | exit 0 (was 452 issues = 15 warnings + 437 infos; now 437 issues, all infos, tolerated) |
| `flutter test` | **232 passed, 0 failed** |
| `flutter build web --release` with the CI flags | PASS, `main.dart.js` and `index.html` produced |
| `actionlint` on all four workflows | exit 0 |
| gitleaks on the clean tree | exactly the 2 known Firebase findings, no new ones |

**Negative cases — the gates really fail:**

| Case | Result |
|---|---|
| A deliberately failing test | pytest exit 1; checker `FAILED: 1 failed`, exit 1 |
| Report file never produced | checker exit 1: "test report … does not exist: the tests did not run" |
| Nothing collected (empty directory) | pytest exit 5; checker exit 1: "only 0 tests ran; at least 1200 are expected" |
| Security tests absent from a report | checker exit 1: "only 0 tests came from tests.security; at least 50 must run" |
| Two migration heads / missing parent / duplicate id / empty history | `tests/ci` asserts each is reported and the CLI exits 1 |
| Database missing a column the model has, and with an extra column | `tests/ci` (PostgreSQL) asserts both are reported |
| Garbled / empty / failed / too-skipped / too-few-tests reports | `tests/ci` asserts each fails |

**No runtime behaviour change:** no file under `backend/app` or `backend/alembic` was modified in this phase; the Flutter edits are unused-code removals only. Both suites pass unchanged.

### Findings from the negative testing (not fixed; runtime behaviour was out of scope)

- **Starting the app without `SECRET_KEY` does not fail.** `from app.main import app` with `SECRET_KEY` unset logs a CRITICAL "anyone can forge login tokens" line and starts anyway (this is the Phase 1 warning behaviour). CI is not affected, because the workflow sets a long key explicitly, but a production deploy with a missing key would still start. Recommend, for a later phase: refuse to start in production when the key is the default or shorter than 32 characters.

---

## 7. Required checks — recommendation (settings not changed)

Read-only inspection: `main` has **no branch protection and no rulesets**, so today nothing is required and anyone with write access can push straight to `main`. The Actions-settings endpoints are blocked for this session, so I could not read workflow-permission defaults or the allowed-actions policy. Please check those under Settings, Actions, General.

Recommended minimal set, to add **after** the first run on GitHub shows these green (the check names are the job names):

| Required check | Covers |
|---|---|
| `Backend tests (Python 3.12)` | full backend regression **and** the authentication / tenant-isolation / RBAC / readiness tests (they run first in this job and again inside the full suite) |
| `Migrations (PostgreSQL 16)` | migration chain, fresh database to head, upgrade from earlier, drift, readiness |
| `Flutter analyze and tests` | analysis (errors and warnings) and all 232 tests |
| `Scan working tree for secrets` (job `gitleaks` of workflow Secret Scan) | secret scanning, **only once it can go green** (section 5) |

Optional: `Flutter web release build`. Not recommended as required: `Build Android APK` (runs on pushes to `main` only, so as a required PR check it would never report and would block every PR).

Also recommended in the same branch-protection change: require a pull request, require the branches to be up to date before merging, and block force-pushes and deletion of `main`. Branch protection requires that the check has run at least once on the repository before GitHub offers it in the list.

---

## 8. Unresolved items and NOT VERIFIED

| Item | Status |
|---|---|
| Secret Scan red on the two Firebase findings | **OPEN**, needs your decision (section 5) and the Google Cloud key restriction check |
| Workflows have never run on GitHub's runners | **NOT VERIFIED.** Everything was run locally with the same commands, versions and a local PostgreSQL, and `actionlint` passes. Possible first-run surprises: runner image differences, the Postgres service container health timing, the pip cache. Expect one fix-up round. |
| Full backend suite takes ~17 minutes locally (timeout set to 45 min in CI) | If it is slow on the runners, splitting by `pytest-xdist` is possible but the suite shares one SQLite file today, so it needs its own change. |
| APK build | **NOT VERIFIED here** (no Android SDK). The workflow only gained pinning and permissions; it still runs only on push to `main`, so a break would show after merge, not on the PR. |
| Dart formatting gate | **BLOCKED**: 278 of 300 files would change. Needs a dedicated format-only PR. |
| Backend linter/formatter/type checker | **BLOCKED** by design: none is configured; adding one is a project decision. |
| Flutter integration tests (`integration_test/`) | **BLOCKED**: none exist in the repository. |
| Production image `mobile/Dockerfile` uses unpinned `cirruslabs/flutter:stable` | **OPEN**: production web can compile with a newer Flutter than the 3.47.5 CI verifies. |
| Production migrations applied? | **NOT VERIFIED** (section 4). |
| Production Python is 3.12.3 but locks were compiled on 3.11 | Verified working on 3.12; recompile the locks on 3.12 at the next dependency update. |

---

## 9. Recommended next actions (for your approval)

1. Review this branch; if approved, say **"push"** and I will push and open a draft PR so the workflows run on GitHub for the first time. I will fix any first-run issue on that PR.
2. Decide the Secret Scan option (section 5) and restrict/rotate the Firebase key in Google Cloud.
3. After the PR's checks are green, add the required checks and the `main` protection in section 7 (repository settings, by you).
4. Check `GET /health/ready` on production to confirm the five migrations are applied; rotate the exposed Railway database password and confirm `SECRET_KEY` and CORS (standing items from Phase 1).
5. Later phase: refuse startup in production with a weak `SECRET_KEY`; pin the production Flutter image; a format-only PR so the Dart format gate can be turned on.

---

## 10. Files changed

New: `.github/workflows/backend-ci.yml`, `.github/workflows/flutter-ci.yml`, `backend/scripts/ci/check_migrations.py`, `backend/scripts/ci/check_test_results.py`, `backend/tests/ci/__init__.py`, `backend/tests/ci/test_ci_scripts.py`, `docs/audit/PHASE_2_CI_AUDIT.md`.

Modified: `.gitignore` (ignore `backend/test-results/`), `.github/workflows/secret-scan.yml`, `.github/workflows/build-apk.yml`, `backend/Makefile`, `backend/requirements-dev.txt`, `docs/TESTING_STRATEGY.md`, and 12 Dart files (unused-code removals): `mobile/lib/core/router/app_router.dart`, `mobile/lib/features/accounts/presentation/screens/voucher_form_screen.dart`, `mobile/lib/features/automation/presentation/screens/automation_screen.dart`, `mobile/lib/features/onboarding/presentation/providers/onboarding_providers.dart`, `mobile/lib/features/onboarding/presentation/screens/register_society_screen.dart`, `mobile/lib/features/society_settings/presentation/providers/society_settings_providers.dart`, `mobile/lib/features/staff/presentation/screens/approval_screen.dart`, `…/attendance_screen.dart`, `…/staff_detail_screen.dart`, `…/staff_list_screen.dart`, `mobile/lib/features/vendor/presentation/screens/vendors_work_screen.dart`, `mobile/test/vendor_sync_test.dart`.
