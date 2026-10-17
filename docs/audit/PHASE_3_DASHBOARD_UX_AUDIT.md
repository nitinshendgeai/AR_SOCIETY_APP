# Phase 3 — Dashboard Accuracy, Role-Aware Navigation and Operational UX

| | |
|---|---|
| Branch | `claude/current-status-bqz2l6` (the session's designated branch), reset to `origin/main` `a12a967c1878802f5e8c5bb33ce5d272c68fb312` (the verified Phase 2 merge; it is an ancestor of this work) |
| State of this work | **Committed locally in 7 commits, not pushed, not merged, not deployed.** Nothing touched `main`, Railway, a production database, repository settings or a secret. |
| Production | `https://society.duxos.in` was not contacted. Nothing here is validated against production or on a real device/browser. |
| Plan | Presented as Step A/B and approved before any code changed (the six decisions are in section 10). |
| Baseline (before) | Flutter analyze exit 0 (437 infos), 232 tests passed. Backend dashboard tests 5 passed; full backend 1,300 (Phase 2). |
| Result | Flutter analyze exit 0 (**437 infos, unchanged; 0 errors, 0 warnings**), **358 tests passed**. Backend **1,310 tests: 1,309 passed, 1 skipped, 0 failed** on the second full run; the first full run had one setup error that is a random-UUID artefact of the SQLite test database, unrelated to this work (section 8 and item 13). Details in section 8. |

Statuses: **PASS** checked, no defect. **FIXED** defect confirmed, fixed here, regression test added. **OPEN** not fixed, reason given. **NOT VERIFIED** could not be proven here.

---

## 1. Summary

1. **A failed request is no longer drawn as a real number or an empty state.** The dashboard service swallowed a failing block and returned `None`/`[]`, which the app drew as "No billing cycle yet" or "All clear. Nothing is waiting on the office". Complaint counts, attendance, duties, approvals, visitors-waiting and the platform console figures fell back to `0`. They now show "…" while loading and "--" with "Could not load. Tap to retry" on failure; a real `0` is still shown as `0`. (FIXED)
2. **The Security dashboard was placeholders and could not be reached.** Hard-coded `--` and a permanent "Duty Status: Active"; and no seeded security role could land on it. Now a Security Supervisor lands there, and it shows real figures from a new read-only endpoint. (FIXED)
3. **The Committee dashboard** made four separate calls, summed billing cycles in the app, showed static text, and was titled "Chairman Dashboard" for every committee role. It now shows the server's overview and is titled for the role held. (FIXED)
4. **Typed addresses are checked against the same grants as the menu.** A Resident typing `/accounts` or `/users`, or anyone typing another role's dashboard, is now sent to their own dashboard (management screens also show a one-line notice). The backend was and remains authoritative. (FIXED, deliberately limited — section 4.2)
5. **Dashboard cards and quick actions are accessible by label, size and contrast** (automated checks only). (FIXED)
6. **Not done / still open:** the Manager's "Maintenance Dues" is still summed in the app (needs an authorization decision); the Tenant role's Forms Matrix gap; the resident-directory policy; and the web-administration and mobile-workflow audits of 3C/3D were not performed beyond what the plan covered (section 10).

---

## 2. Dashboard inventory and data sources

| Dashboard | Route | Who lands there | Data | Canonical backend source? | Before | Now |
|---|---|---|---|---|---|---|
| Admin overview | `/admin` | roles containing "Admin" | `GET /dashboard/society/{id}` (admin and committee; own society) | **Yes** (collection, accounts summary, occupancy, attention) | live; a failed block drawn as empty | live; failed block reported with retry — **FIXED** |
| Committee | `/committee` | any `Committee*` | was 4 separate calls + app-side sum | was partly (sum in the app) | derived/static | same overview as Admin — **FIXED** |
| Security | `/security` | Security Supervisor (now); a custom role named like "Security" | none | none | **static/placeholder** | `GET /dashboard/security/{id}` (new) — **FIXED** |
| Resident (and Tenant) | `/resident` | Resident, Tenant | complaints, visitor approvals (15 s poll, existing), `myBills`, flat | bills: yes | live; failures drawn as 0 | failures shown as unavailable — **FIXED** |
| Manager | `/manager` | role `Manager` | staff list, approvals, attendance summary, duties, complaints, billing cycles | attendance/duties yes; "Maintenance Dues" is summed in the app | failures drawn as 0 | failures shown; **dues sum OPEN** |
| Supervisor | `/supervisor` | Housekeeping and Technical Supervisor | attendance summary, duties, approvals | yes | failures drawn as 0 | failures shown — **FIXED** |
| Staff Portal | `/staff` | any "Staff" role, Gym Trainer | staff profile | n/a | navigation hub; "Tasks — Coming soon" tile | Security Staff get Visitor Log / Vehicle Gate tiles — **FIXED** (Tasks tile is labelled, left) |
| Platform console | `/platform` | Platform Admin | `/platform/stats`, societies, activity | yes | stats failure drawn as 0 | shown as unavailable — **FIXED** |

Authorization of the data: every endpoint above is society-scoped and role-guarded by the backend (`assert_society_access` plus a permission dependency). The new endpoint follows the same pattern and is tested (section 7). **PASS** for tenant isolation of the changed endpoints.

### Loading / empty / error / denied behaviour
- **Admin and Committee overview:** loading skeleton, empty ("No billing cycle yet" only when the server says there is none), per-section failure with retry, whole-request failure with retry. 401 (expired) is handled globally: a failed token refresh ends the session and returns to sign-in. **PASS**.
- **Count cards (Resident, Manager, Supervisor, Security, Platform):** loading "…", failure "--" + retry on tap, genuine zero "0". **FIXED**.
- **Permission denied (403) on a dashboard request:** shows the same failure state; no figure is invented. **PASS**.

---

## 3. Static / mock / placeholder metrics found

| Item | Disposition |
|---|---|
| Security "Visitors Today" `--` | now the server's `visitors_today` — **FIXED** |
| Security "Check-ins" `--` | now "Let In Today" (`checked_in_today`) — **FIXED** |
| Security "Parking Entries" `--` | **removed**: there is no source for it; not faked |
| Security "Duty Status: Active" | **removed**: constant text with no source |
| Committee "Open actions": "Staff module operational", "See Staff → Approvals" | **removed** (static text) |
| Committee "Maintenance Dues" (sum of all cycles in the app) | replaced by the server's overview |
| Manager "Maintenance Dues" / "Collected" (sums of billing cycles in the app) | **OPEN** — see section 10, decision 4 |
| Occupancy/resident/visitor figures on Admin | already live (`_occupancy`, `_today`) — **PASS** (the earlier audit's "static" finding is out of date for Admin) |

Three different "dues" definitions still exist side by side: the accounts ledger ("Members owe"), the latest cycle's outstanding (Admin/Committee), and the sum over all cycles (Manager). They are separately labelled; unifying them is a business-definition decision (OPEN).

---

## 4. Role-aware navigation

### 4.1 Role → landing page → menu (from the real seeded grants)

Landing page = `userRoleHome`; "Menu" = non-member form codes granted by default (`FORM_ROLE_GRANTS`). Every role also gets the ten member screens: Meetings, Polls, Documents, Certificates & NOC, Parcels, Domestic help, Visitors, Complaints, Notices, Amenities.

| Role | Lands on | Management menu entries |
|---|---|---|
| Platform Admin | Platform console | Platform Console |
| Society Admin | Admin overview | Residents, Tenants, Shops, Automatic tasks, Manager's Checklist, Users & Roles, Permission Matrix, Forms Matrix, Society Settings, Pending Resident Changes, Staff, Parking Management, Setup Wizard, Checklist Templates, Online Payments, Bank Reconciliation, Vendor Bills, Vendors & Work, Maintenance Billing, Maintenance Elements, Accounts, Defaulters, Assets, Stores |
| Committee Chairman / Secretary / Treasurer / Member | Committee overview (same as Admin's) | as Admin **without** Users & Roles, Permission Matrix, Forms Matrix |
| Manager | Manager dashboard | Manager's Checklist, Staff, Checklist Templates, Online Payments, Bank Reconciliation, Vendor Bills, Vendors & Work, Maintenance Billing, Maintenance Elements, Accounts, Defaulters, Assets, Stores |
| Security Supervisor | **Security dashboard (changed)** | Staff |
| Housekeeping / Technical Supervisor | Supervisor dashboard | Staff |
| Security Staff | Staff Portal (+ gate tiles, new) | Staff |
| Housekeeping / Technical Staff | Staff Portal | Staff |
| Gym Trainer | Staff Portal | none (no "Staff" grant by default — existing gap) |
| Resident | Resident dashboard | Edit My Info, My Bills |
| Tenant | Resident dashboard | none (the dashboard links to My Bills and Edit My Info but the Tenant role is not granted them — existing gap) |

### 4.2 The route guard (what it does and does not do)
- Management screens (residents, tenants, shops, automation, users and matrices, society settings, wings/flats/setup, parking management, checklist templates and manager checklist, billing screens, vendors, accounts, assets, stores) require the same form code the menu uses. Without it: redirect to the person's own dashboard with "You do not have access to that screen."
- A role dashboard that is not the person's own redirects to their own, quietly.
- **Not blocked, on purpose:** the member screens (visitors, complaints, notices, amenities, meetings, polls, documents, certificates, parcels, domestic help, my bills, edit my info) and the whole Staff area. The Forms Matrix has known gaps for some roles (above), and dashboards link to those screens; bouncing would remove things people use today. The backend still decides.
- Never blocks while the grants are unknown (not loaded, load failed, or belong to a previous sign-in); never touches the Platform Admin; never redirects to a place that would redirect back.
- Verified: pure-function tests for every seeded role's open/shut screens; the real router with typed addresses; the screen is re-checked when the grants arrive; a different person signing in does not inherit the previous person's grants (mutation-checked — the test fails if that protection is removed).
- **Session and role changes:** grants reload on sign-in, sign-out and account switch (**PASS**). A role or Forms-Matrix change made by an administrator takes effect at that person's next sign-in or when the matrix screen invalidates the cache (**OPEN**, existing behaviour).

### 4.3 The reported security-dashboard reachability issue
**FIXED.** Every seeded security role contains "Supervisor" or "Staff", which `userRoleHome` tested first, so `SecurityDashboardScreen` was reachable only by a custom role named like "Security". A Security Supervisor now lands on it (with My Team shortcuts); Security Staff stay on the Staff Portal, which gained Visitor Log and Vehicle Gate tiles.

---

## 5. Mobile vs web responsibilities (as the code stands)

| Mobile (monitor and act) | Web (configure, administer, analyse) |
|---|---|
| Resident: bills, visitor approvals, complaints | Users & Roles, Permission Matrix, Forms Matrix |
| Security: visitor log, check in/out, vehicle gate, today's gate figures | Setup Wizard, wings/flats structure, imports |
| Supervisor/Manager: approvals, duty queue, attendance, complaints | Accounts, statements, bank reconciliation, billing set-up |
| Staff: attendance, duties, handover | Society Settings, Automatic tasks, vendors and contracts |

No deep administrative workflow was moved to mobile and none was removed; the split is by role and menu grant, not by platform. A real mobile-vs-web workflow audit (3C/3D) was **not** performed beyond the dashboards (section 10).

---

## 6. Screens and workflows changed

Admin overview (failed sections, retry); Committee dashboard (rewritten onto the overview, role-specific title); Security dashboard (real figures, team shortcuts for supervisors); Resident, Manager, Supervisor (count cards); Staff Portal (gate tiles for Security Staff); Platform console (stats); shared `KpiCard` (semantics, darker note), quick-action chips (semantics, unavailable state, 56 dp), info tiles (wrap), tile height (follows text size); router (central guard, "no access" notice); `userRoleHome`.

## 7. API and backend changes

| Change | Detail |
|---|---|
| `GET /dashboard/society/{id}` | **Additive** `errors: [block names]` in the response (empty when all blocks loaded). No change to who may call it. Older apps ignore it; this app treats a missing list as "nothing failed". |
| `GET /dashboard/security/{society_id}` (new) | Guard: `require_security` (same as the visitor log: Platform/Society Admin, Committee, Manager, Security Supervisor and Staff) **plus** `assert_society_access`. Returns `{as_of, today:{visitors_today, checked_in_today, visitors_inside}, errors}` — counts only, no visitor details. `today` is `null` when the Visitors service is switched off for the society or the block failed (then named in `errors`). Query cost: three `COUNT` queries on `visitors` filtered by society (indexed `society_id`, `status`). |
| Schema | **None.** No migration, no new dependency, no polling added. |

Tests for the new endpoint: counts correct (including yesterday excluded), quiet gate is `0` not missing, allowed roles (5) and refused roles (Resident, Tenant, Housekeeping Staff, Technical Supervisor), anonymous refused, another society's gate refused and its visitors never counted, Visitors switch off, failing block reported.

---

## 8. Tests added and exact commands

Backend (`backend/`, Python 3.12 venv from the hash-locked dev lock; SQLite test database; test-only secret):
```
python -m pytest tests/dashboard -q -o log_cli=false -p no:cacheprovider
python -m pytest tests/security -ra -q -o log_cli=false -p no:cacheprovider --junitxml=test-results/security.xml
python scripts/ci/check_test_results.py test-results/security.xml --min-tests 50 --title "Security regression tests"
python -m pytest -ra -q -o log_cli=false -p no:cacheprovider --junitxml=test-results/backend.xml
python scripts/ci/check_test_results.py test-results/backend.xml --min-tests 1200 --max-skipped 5 --require-package tests.security=50 --title "Backend test suite"
```
Flutter (`mobile/`, Flutter 3.47.5):
```
flutter pub get && flutter analyze --no-fatal-infos && flutter test
flutter build web --release --dart-define=API_BASE_URL=https://ci.invalid/api/v1 --dart-define=APP_ENV=ci --no-tree-shake-icons
```

| Check | Result |
|---|---|
| `tests/dashboard` | 15 passed (5 before; +10 new) |
| Security regression suite (CI sequence) | **62 passed**, 0 failed, 0 skipped in 134 s; result checker exit 0 |
| Full backend suite, run 1 (CI sequence) | 1,308 passed, 1 skipped, **1 error** in 1,073 s: `tests/notice/test_notice_board.py::test_a_notice_without_a_society_goes_to_the_callers`, **at fixture setup** (`make_user`, `db.refresh`): SQLite returned a freshly generated user id as the number `4.64e+31`, so `UUID()` rejected it. Result checker exit 1 (correctly: it counts an error). |
| Same notice module re-run alone | 28 passed |
| Full backend suite, run 2 (CI sequence) | **1,309 passed, 1 skipped, 0 failed, 0 errors** in 1,077 s (1,310 tests); result checker exit 0 |
| `flutter analyze --no-fatal-infos` | exit 0; 437 infos, the same as before; 0 errors, 0 warnings |
| `flutter test` | **358 passed, 0 failed** (232 before; +126) |
| `flutter build web --release` (CI flags) | built; `main.dart.js` and `index.html` present |

New Flutter tests by file: `admin_overview_test` +4, `dashboard_states_test` 19, `role_home_test` 24 (every seeded role's landing page), `route_access_test` 65, `dashboard_accessibility_test` 14. One existing test (`widget_test`, Security dashboard) was given a taller screen because the summary tiles grew; no assertion was weakened or removed. Mutation checks done: removing the stale-grants protection fails the router test; a fixed tile height fails the large-text tests; pale note colour fails the direct contrast test; un-merged chip semantics fails the semantics test.

Existing failures: none found. **Not run:** the migrations job and CI scripts' PostgreSQL tests (no migration or CI change in this phase); the GitHub workflows (nothing pushed).

---

## 9. Accessibility and responsive-usability findings

| Finding | Status |
|---|---|
| Summary cards had no combined label (each word read separately) | **FIXED** — one label, button when tappable |
| Quick actions with no destination looked like working buttons | **FIXED** — dimmed and announced as unavailable |
| Quick-action text 11 px | **FIXED** — 12 px, min height 56 dp |
| Retry note colour 2.2:1 on white | **FIXED** — 5.2:1; direct test (the automated guideline cannot see it because the card is one semantics node) |
| Fixed 148 px tiles clipped large text | **FIXED** — height follows the text scale; no overflow at 1.3x and 2.0x |
| Info tile text ran off the tile | **FIXED** |
| Loading indicator has a label and live region | **PASS** (existing `AppLoader`) |
| Flutter tap-target (Android 48 dp, iOS 44 dp), labelled-target and text-contrast guidelines on Resident, Resident-with-failure and Security dashboards | **PASS** (automated) |
| Other screens (forms, lists, the admin overview's own chart and rows), keyboard navigation, focus order, screen-reader use, colour-only meaning (severity colours), `textTertiary` grey used app-wide | **NOT VERIFIED** / **OPEN** |
| Only about 3 uses of `Semantics` across the whole app | **OPEN** — a wider pass is needed |

These are automated checks plus reasoning; **no claim of accessibility compliance is made**.

---

## 10. Remaining defects, decisions and unverified behaviour

Decisions you gave (approved plan): (1) central route guard — approved, implemented last; (2) new read-only security endpoint — approved; (3) committee shows the admin overview — approved; (4) Manager dues left as is, labelled, flagged; (5) resident directory unchanged; (6) no schema change, no new dependency, no polling.

| # | Item | Status |
|---|---|---|
| 1 | Manager "Maintenance Dues" / "Collected" are summed in the app from billing cycles. The canonical endpoint refuses managers; fixing it means widening an authorization rule (or adding a manager-safe summary). Needs your decision. | **OPEN** |
| 2 | Three definitions of "dues" across dashboards (ledger, latest cycle, all cycles). | **OPEN** (business decision) |
| 3 | **Resident directory:** `residents` is granted only to Admin and Committee by default, so members have no directory access; Phase 1 also redacts personal fields. Not changed. If members should see a directory, that is a policy decision. | **OPEN** (policy) |
| 4 | Tenant role is not granted My Bills / Edit My Info although the dashboard links to them; Gym Trainer has no "Staff" grant although it lands on the Staff Portal. These are Forms-Matrix data; shared role configuration was not altered. | **OPEN** (policy) |
| 5 | An attention row the person cannot open (for example "password reset requests" shown to a committee member: that screen needs Users & Roles, which committee are not granted by default) now shows the "no access" notice when tapped instead of a screen full of 403s. Better: stop counting admin-only items for committee. | **OPEN** |
| 6 | The route guard does not cover member screens or the Staff area (reasons in 4.2). The backend decides. | **OPEN** (by design) |
| 7 | A role or Forms-Matrix change takes effect at next sign-in. | **OPEN** (existing) |
| 8 | Phase 3C (mobile workflow audit: approvals, complaints follow-up, payment status) and 3D (web admin UX: active-route highlighting, filters, deep-link refresh in a browser) were **not** audited beyond dashboards, navigation and the guard. | **NOT VERIFIED** |
| 9 | Nothing was run in a real browser or on a device; layout was verified with widget tests at 420 px wide and 1.3x/2.0x text. | **NOT VERIFIED** |
| 10 | Deep link / browser refresh: the router re-checks the screen when grants arrive (tested), but a very brief view of a restricted screen before the grants load is possible. | **NOT VERIFIED** in a browser |
| 11 | The gate "Visitors Today" counts rows created today in the society's timezone; it was not compared against production data. | **NOT VERIFIED** |
| 13 | **Random-UUID artefact in the SQLite test database (pre-existing; found by this phase's first full run).** A random UUID4 whose 32-character hex is only digits, or digits with one `e`, is read back by SQLite as a number and `UUID()` fails. Chance about 1.2 in a million per generated id, so roughly 1–2 % of full runs. It is a test-environment problem (production uses PostgreSQL's UUID type) and it can turn a pull-request check red at random. Not fixed here (test infrastructure, outside this phase). Proposed fix: have the test database store UUIDs with a text type that cannot be read as a number (for example the hyphenated string form), in `backend/tests/conftest.py`. Until then a red run whose only failure is this error should be re-run once. | **OPEN** |
| 12 | Pre-existing: Secret Scan red (two Firebase web-key findings); `mobile/pubspec.lock` not committed; formatting not enforced. Unchanged. | **OPEN** (Phase 2 items) |

---

## 11. Changed files and risks

Backend: `backend/app/modules/dashboard/routes/dashboard.py`, `backend/app/modules/dashboard/services/dashboard_service.py`, `backend/tests/dashboard/test_dashboard.py`.

Flutter: `mobile/lib/core/navigation/route_access.dart` (new), `mobile/lib/core/router/app_router.dart`, `mobile/lib/features/dashboard/{admin_overview,gate_summary (new),role_dashboards}.dart`, `mobile/lib/features/complaint/presentation/providers/complaint_providers.dart`, `mobile/lib/features/staff/presentation/providers/staff_providers.dart`, `mobile/lib/features/staff/presentation/screens/staff_home_screen.dart`, `mobile/lib/features/visitor/presentation/providers/visitor_providers.dart`, `mobile/lib/features/platform/presentation/screens/platform_console_screen.dart`, `mobile/lib/shared/widgets/app_widgets.dart`; tests `admin_overview_test`, `dashboard_states_test`, `role_home_test`, `route_access_test`, `dashboard_accessibility_test` (new), `widget_test` (one test given a taller screen); this report.

Risks and how they were limited:
- **Route guard** (largest change). A wrong mapping could lock someone out of a screen. Limited to management screens; fails open when grants are unknown; consistency test ties every guarded menu entry to the menu's own form code; the backend is unchanged and authoritative.
- **Providers now throw on failure** (complaints, attendance summary, duties, first visitor poll). Every consumer was reviewed; those that used `valueOrNull` keep working; the visitor approvals screen already had an error branch. Behaviour change: a failure that used to show 0 now shows "--".
- **Larger summary tiles** push content down slightly on phones.
- **Backend additions** are read-only and additive; no schema change.
- Not exercised against production data or on real devices.

## 12. Recommended next phase

1. Review this branch and decide items 1–5 in section 10, then say "push" so the Phase 2 workflows run on it.
2. Phase 4 candidates: (a) the mobile operational workflows audit (approvals, complaints follow-up, payment status) and web admin UX audit that Phase 3 did not cover; (b) a manager-safe dashboard summary so no financial figure is summed in the app; (c) a wider accessibility pass (labels, focus order, keyboard) on forms and lists; (d) stop counting admin-only attention items for committee; (e) resolve the Tenant/Gym Trainer Forms-Matrix gaps once the policy is decided.
