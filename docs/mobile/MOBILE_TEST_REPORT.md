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


## Visual review (rendered screens, not just tests)

Method: the real screens were rendered at 390 x 844 (2x) with the bundled Inter and Devanagari fonts, the Material icon font and fake data, then looked at. The throwaway harness is not in the repo (it needs fake data per screen). This is a *rendering* review: it shows layout, spacing, fonts and colour. It is **not** a device test (no touch, scrolling feel, real data, keyboard, or other phone sizes).

Found by looking, and fixed in the "UI polish" PR (all of these passed the automated tests before):

| Finding | Cause | Fix | Lock-in test |
|---|---|---|---|
| Gate tiles and manager-hub tiles drawn grey | shadow painted above a coloured Material (the pitfall `KpiCard`'s comment warns about) | colour and outline on the outer box, ink on a transparent Material | visual only |
| Guard's four action buttons used the platform font | `styleFrom(textStyle:)` replaced the theme's font and the Marathi fallback | size set on the `Text`, which keeps the button font | `gate_panel_test`: label font is Inter (fails if the bug returns) |
| Resident Home showed the same amount four times | dues card, Bills Due card, My Bills chip, Pay bills chip, Recent updates row | one dues card; other copies removed | `widget_test`: dues card once; duplicates absent |
| White text on bright orange (2.2:1) on Check Out, the guard's main button | `AppTheme.warning` as a fill | `kWarningFill` (5.0:1) | `design_tokens_test` |
| Status words in bright green / red / orange / sky (2.2 to 3.6:1) | status colour used as text | tone colours for words (visitor status, bill status, due notes) | `design_tokens_test` covers bill statuses |
| Dead "Tasks - Coming soon" card on the guard's home | placeholder | removed | n/a |
| Grey band under the dues card | shadow where neighbours use an outline | outline | visual only |

Still not verified: real devices, other screen sizes (360 x 640, large phones), 130% / 200% text scale, Marathi layouts (Devanagari is taller), slow-network behaviour, the keyboard over forms, accessibility with TalkBack.


## Marathi review (rendered screens)

Rendered in Marathi at 390 x 844, like the visual review above. **Finding:** before this change the resident Home, the guard's Staff Portal and the visitor log were mostly English even in Marathi mode (only the new phrases were translated), so a Marathi-speaking resident saw a mixed screen.

Fixed by translating inside the shared dashboard helpers (section labels, chips, service tiles, summary cards, greeting, panels), the staff-portal cards and banners, and the visitor log (tabs, button, statuses, types, time lines), with ~75 new Hindi and Marathi strings and a `context.trf` helper for texts with values (`'Across {n} open bills'`). Because the helpers are shared, every role's dashboard benefits.

| Check | Result |
|---|---|
| Rendered Marathi resident Home, guard Home, visitor log: no clipped or overlapping text, Devanagari glyphs correct | PASS (rendering only) |
| Marathi tests: translated words present, listed English words absent, no unfilled `{slot}` on screen; English unchanged | PASS (6 tests) |
| Wording quality, tone and spelling of the new Hindi and Marathi | NOT VERIFIED: **needs a native reader**; all strings are in `core/l10n/translations.dart` |
| Existing "Check out" translation is past tense ("went out") and is used on the domestic-help button | Flagged for the native reader; left unchanged |
| Dates and times still show English month names and "AM/PM" | Not done |
| My Bills, bill detail, receipts, notices, complaints, amenities, forms and the login screen in Marathi | Not reviewed or translated yet |


## Lights check: floor and area detail (reported from a phone screenshot)

Request: on the Report tab, tapping a wing / floor card should open its details.

| Item | Result |
|---|---|
| Floor and common-area cards open a detail sheet: the floor's tube lights, each flat's spot lights, the camera; each light with its state, who checked it and when, and "not working since" | PASS (11 tests; rendered in English and Marathi) |
| A flat with a broken light is listed first and opens on its lights; the others stay folded | PASS (test checks the order against the server's order) |
| Each section shows its count ("4/4 checked"); only the kinds the floor has are requested | PASS |
| Uses existing endpoints only (`/report`, `/sheet`, `/area/{id}/sheet`); the report already sent `wing_id`, the app now reads it | no backend change |
| **Limit, shown on screen:** the sheet shows each light as it was **last found**, not as it stood in a past month (the backend sheet has no month parameter). On an earlier month the sheet says so | CONDITIONAL PASS: a month-accurate floor detail needs a backend parameter |
| Found while testing: the flat cards wrapped a tappable tile in a coloured box (invisible tap highlight) | fixed |
| Report tab polish found by rendering: "Partly" chip and the red/green/orange words and numbers were 2.1 to 3.6:1; the "Not working" tile was taller than its neighbours | fixed (tone colours, equal-height tiles) |
| Rest of the Lights check screen (Check, To replace) in Marathi | still English; only the new sheet and the cards' accessibility label are translated |
| Real device | NOT VERIFIED |


## Ported from the earlier draft PRs #233 and #234 (reviewed, not merged as they were)

| Piece | Where it came from | Result |
|---|---|---|
| `/health` test no longer fails when the Unix timestamp in the response happens to contain "5432" (about 0.07% of runs; it hit once on 12 Nov) | #233 | Fix applied. Proved on a sample timestamp; **the backend test itself was not run here (no pytest); the backend CI job runs it** |
| Release workflows pinned to Flutter 3.47.9 (and an explanation) | #233 | Applied; both files checked for duplicate keys (merging #233 as it was would have left two `flutter-version` lines, which is invalid) |
| Compact greeting card on every dashboard (greeting and date on one line, one society pill, ellipsis for long names) | #234 | Ported onto current `main`, keeping the Marathi/Hindi texts; rendered in English and Marathi |
| Removed the duplicate phone drawer (the bottom bar's More menu holds the same menu) | #234 | Ported. The 7 tests that opened the drawer (the reason #234's CI was red) are **moved, not deleted**, to `role_menu_visibility_test.dart`: the same assertions on the More menu for admin, committee, security and resident, plus a "nothing beyond the grants" check |
| Not taken: moving "Society services" below "Summary", the 280 to 190 grid change, attendance and staff-home spacing | #234 | Left out on purpose (the first contradicts the cleanup made after rendering; the grid change broke a test and was not rendered) |
| Not taken: Accounts and Stores for admins on Android | #233 | Left out: the app is lightweight, full accounts stay on the web app |
