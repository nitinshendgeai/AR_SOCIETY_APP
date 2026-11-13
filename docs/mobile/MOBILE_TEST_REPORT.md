# Mobile Test Report

Rating: PASS, FAIL, CONDITIONAL PASS, NOT VERIFIED. Evidence is a command that was run, or a CI job, never an inference.
Environment for local runs: Flutter 3.47.5 (the version CI pins), `flutter analyze --no-fatal-infos`, `flutter test`.

## Baseline (main before this work, CI run on PR #235)
| Check | Result |
|---|---|
| Flutter analyze (errors and warnings) | PASS |
| Flutter tests | PASS |
| Flutter web release build | PASS |
| Backend tests, migrations, secret scan | PASS |

## Step log

| Step | PR | Change | Local analyze | Local tests | CI | Notes |
|---|---|---|---|---|---|---|
| 1 | #236 | Design tokens, status widgets | not run locally (SDK not yet installed) | not run locally | PASS after one fix (unused import warning) | CI caught it |
| 2 | #237 | Searchable More sheet | PASS (0 errors/warnings, 483 infos) | PASS 668/668 | PASS after one fix (sheet height hid the list at 70%) | Existing test caught a real layout regression |
| 3a | #238 | Resident dues card on Home | PASS (0 errors/warnings, 483 infos = baseline) | PASS 678/678 | PASS (all 5 checks) | 10 new tests: statuses, rupee format, singular/plural, all-paid, button target size and navigation, loading, failure + retry, Marathi |
| 4a | #239 | Gate panel on the Security Staff home | PASS (0 errors/warnings, 483 infos = baseline) | PASS 692/692 | PASS (all 5 checks) | 14 new tests: counts, real zero vs unavailable (`--`, never 0), loading, retry, navigation to the 4 existing screens, 48 dp targets, grants and service switches, Marathi, plus Security-only presence on the Staff Portal |
| 4b | #240 | Visitor log search (phone) | PASS (0 errors/warnings, 483 infos = baseline) | PASS 706/706 | Flutter jobs PASS; backend job pending at time of writing | 14 new tests: matching rules (name, mobile, flat forms, plate forms, multi-word, pass code excluded), narrow and clear, no-match, Inside tab, cap note, resident list unaffected |
| 5-8 | this PR | Retry + offline banner; Operations/Finance/People hubs; text-contrast token; Android pins and backup off | PASS (0 errors/warnings, 483 infos = baseline) | PASS 735/735 | pending | +29 tests: network resilience 15 (retry rules, writes never retried, reachability flag, banner), hubs 11, contrast 1, tab/bar tests updated for the new admin tabs (4 existing assertions changed on purpose: admin tabs are now Operations / Finance / People, not Visitors / Complaints / Billing) |

## Module status after Step 4b (what has actual evidence)

| Module | Evidence | Rating | Remaining |
|---|---|---|---|
| Security gate (Security Staff home) | 14 tests, CI green | PASS for the panel (not run on a device) | dedicated tab set |
| Visitor history search (phone) | 14 tests, local only until CI | CONDITIONAL PASS: searches the latest 50 visitors only (server has no search); FAIL for "searchable full history" until the backend adds a filter or paging | backend `q` parameter, or load more pages |
| Phone navigation: More search | 6 tests, CI green | PASS | tab hubs not started |
| Resident Home: dues card | 10 tests incl. widget_test regression, local | CONDITIONAL PASS (CI pending, not run on a device/emulator) | Payments and Services hubs |
| Authentication, RBAC, permission boundaries | existing suite (route_access, menu_architecture, role_home) green; not extended | PASS for existing behaviour, NOT VERIFIED for new screens beyond grants | add per-role navigation tests in the hub step |
| Billing, payments, receipts | existing suite green; logic untouched | PASS (unchanged) | receipt UX not reviewed |
| Visitors, staff, finance, vendors, complaints, notices | existing suite green; untouched | PASS (unchanged), mobile UI NOT VERIFIED | later steps |
| Slow network, offline, retry | 15 tests with a scripted fake network (retry only for GET on network failure / 502-504, never for writes, flag, banner) | CONDITIONAL PASS: logic verified; not exercised on a real flaky network or device | cache for stale-while-revalidate not built |
| Manager navigation (Operations / Finance / People) | 11 hub tests + updated bar tests | CONDITIONAL PASS: reaches admin, committee and manager on the web app on a phone; the Android field build still excludes those roles | decision on an Android edition for them |
| Small screens (360 x 640), text scale 130%/200% | not yet tested | NOT VERIFIED | add golden/size tests |
| Real device or emulator | none | NOT VERIFIED | needs an emulator or device |
| Android release build / AAB | not built (no Android SDK here, no signing secrets) | NOT VERIFIED | see MOBILE_RELEASE_READINESS.md |
