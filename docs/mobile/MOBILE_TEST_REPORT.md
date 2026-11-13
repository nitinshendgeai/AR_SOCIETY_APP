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
| 3 | this PR | Resident dues card on Home | PASS (0 errors/warnings, 483 infos = baseline) | PASS 678/678 | pending | 10 new tests: statuses, rupee format, singular/plural, all-paid, button target size and navigation, loading, failure + retry, Marathi |

## Module status after Step 3 (what has actual evidence)

| Module | Evidence | Rating | Remaining |
|---|---|---|---|
| Phone navigation: More search | 6 tests, CI green | PASS | tab hubs not started |
| Resident Home: dues card | 10 tests incl. widget_test regression, local | CONDITIONAL PASS (CI pending, not run on a device/emulator) | Payments and Services hubs |
| Authentication, RBAC, permission boundaries | existing suite (route_access, menu_architecture, role_home) green; not extended | PASS for existing behaviour, NOT VERIFIED for new screens beyond grants | add per-role navigation tests in the hub step |
| Billing, payments, receipts | existing suite green; logic untouched | PASS (unchanged) | receipt UX not reviewed |
| Visitors, staff, finance, vendors, complaints, notices | existing suite green; untouched | PASS (unchanged), mobile UI NOT VERIFIED | later steps |
| Slow network, offline, retry | no tests | NOT VERIFIED | Step 6 |
| Small screens (360 x 640), text scale 130%/200% | not yet tested | NOT VERIFIED | add golden/size tests |
| Real device or emulator | none | NOT VERIFIED | needs an emulator or device |
| Android release build / AAB | not built | NOT VERIFIED | Step 8, needs approved secrets |
