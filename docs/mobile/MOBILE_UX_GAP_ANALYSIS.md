# Mobile UX Gap Analysis (Phase 1)

Evidence is from code reading only; nothing was run on a device (NOT VERIFIED visually). Severity: H/M/L.

| # | Gap | Evidence | Sev | Proposed direction | Needs approval / risk |
|---|---|---|---|---|---|
| 1 | Navigation is generic: Home + 3 dynamic tabs + More, not role-designed | `_tabPreference`, `phone_bottom_bar.dart` | H | Role-profile tab sets built from form codes, with fallback to today's logic | Edits menu tests; low backend risk |
| 2 | More sheet has no search; long category/pill lists | `_showMore` | H | Searchable "All screens" sheet, recents, favourites | none |
| 3 | Admin and finance functions are absent from the shipped Android edition | `AppEdition.fieldFormCodes`; web-only roles blocked at sign-in | H | **Decision needed**: ship a full-edition phone build for admins, or keep admin on web. Affects Play listing and security review | **Product decision** |
| 4 | Dashboards are chip grids, heavy on `--` placeholders in places | KNOWN_ISSUES; `role_dashboards.dart` | H | Role hero cards (dues, collections, pending approvals), pulled from existing dashboard endpoints | Only if endpoints already return data; otherwise client aggregation of existing calls |
| 5 | Table-first screens (23 files use data tables) | grep | H | Card/list views at phone width with search, filter chips, expandable detail; keep tables at desktop width | Per-screen, shared widget risk to web |
| 6 | No offline/slow-network handling: 15 s timeout, no retry, no connectivity banner, no cache | `api_client.dart`, 0 connectivity uses | H | Idempotent-GET retry with backoff, offline banner, retry widget, stale-while-revalidate for dashboard | Library only if justified (`connectivity_plus`); never retry non-idempotent POSTs (payments) |
| 7 | Eager `getAllPages` loads everything | `paged.dart` | M | Server-paged infinite lists for long registers; keep full fetch only where totals demand | Totals/aggregates must stay correct |
| 8 | Localisation mostly menu-level; screen bodies English | 7 feature files use `context.tr` | M | Move to ARB/`gen_l10n` or extend map; phase per module, Marathi first for resident/security | Needs native-reader review (already noted in code) |
| 9 | Dark theme blocked by static colour constants | `app_theme.dart` header | M | Introduce ThemeExtension tokens and migrate gradually; not now | Large; light-only in scope per brief |
| 10 | Design tokens incomplete: spacing scale, elevation levels, motion durations, state components not named | `AppTheme` | M | Add `AppSpacing`, state widgets (loading/empty/error/success) consolidated in `shared/widgets` | Additive, safe |
| 11 | Accessibility: 22 Semantics uses; touch target and contrast not audited; text-scale untested | grep | M | Audit with a11y checklist, min 48 dp targets, contrast pass on `textTertiary` (#AEAEB2 on white fails AA) | none |
| 12 | Splash is the legacy window background; no Android 12+ splash config | `launch_background.xml` | L | `core-splashscreen` style/theme values | none |
| 13 | No Android App Links; push tap routing unverified | manifest | M | assetlinks + intent filter for `society.duxos.in`; verify FCM payload route handling | Needs domain control; **web infra change, approval** |
| 14 | R8 disabled, no keep rules; release size/security | `build.gradle` | M | Author keep rules and test on device before enabling | Needs real device |
| 15 | Reproducibility: `pubspec.lock` not committed; unpinned Flutter in APK/AAB workflows vs pinned CI | workflows | M | Commit lock; pin Flutter in build workflows | CI change; do not weaken checks |
| 16 | Stale docs (`FLUTTER_ARCHITECTURE`, `RBAC_MATRIX`) | docs | L | Refresh when design system lands | none |
| 17 | Unused dependency `cached_network_image`; avatars/images use plain loading | grep | L | Use it for profile/notice images or remove | tiny |
| 18 | `withOpacity` x276 deprecated | grep | L | Replace with `withValues` mechanically later | analyzer-infos only |
| 19 | Missing functionality noted by the team: staff leave self-service UI, edit duty, no reject button on approvals | KNOWN_ISSUES | M | Add leave screen (API exists) in staff phase | API ready |
| 20 | Security gate: fast flow is a dashboard chip set | `SecurityDashboardScreen` | H | Dedicated Gate home: big actions (new entry, check-out, verify code, parcel in), inside-now list, search by name/flat/vehicle | Uses existing visitor/parking APIs |

## What is already good (keep)

Server-driven menu and route guards; secure token storage and refresh; multi-society reset; biometric; push for visitors; Hindi/Marathi
plumbing and bundled fonts; consistent `AppTheme` usage; cleartext disabled; strong existing test culture around navigation.

## Recommended architecture (for approval before any code)

1. **Keep** Riverpod + go_router + Dio. Add nothing structural.
2. **Design system**: keep `AppTheme` as the single token source; add spacing/elevation/state components in `shared/widgets`, documented in `MOBILE_DESIGN_SYSTEM.md`. Premium direction: deepen the neutral palette, reduce saturated iOS accents for finance, tabular numerals for INR, 8-pt spacing grid.
3. **Navigation**: introduce `PhoneProfile` (resident, admin/committee, manager, security, staff, field-tech) that maps to tab definitions; each tab is a *hub screen* listing the existing screens for that group, filtered by form codes; a tab with no granted screens disappears; five slots max. Proposed:
   - Resident: Home | Payments (bills, receipts, history) | Services (complaints, amenities, visitors, parcels) | Notices | Profile (My Home, family, help)
   - Admin/Committee: Home | Operations (complaints, visitors, parking, vendors work, checklists) | Finance (billing, defaulters, receipts, vendor bills, BRS, reports - if granted) | People (residents, staff, attendance, users) | More
   - Security: Gate | Visitors | Delivery | Logs | Profile
   - Manager / Accountant: same Admin skeleton, tabs auto-pruned by form codes.
4. **Searchable All-screens** in More; recents.
5. **Reliability layer**: GET retry + offline banner + standard error/empty/retry widgets.
6. **Rollout order** (each its own branch and PR, tests green before next): (a) design tokens and state widgets; (b) nav profiles + searchable More; (c) Resident home + Payments + Services; (d) Security Gate; (e) Admin hubs; (f) reliability; (g) localisation of resident/security screens; (h) Android readiness (splash, links, R8, pinning).

## Decisions needed from you before Phase 2

1. Should admin/committee/manager/accountant users get a **phone build** (full edition on Android), or stay on the web app as today? This changes scope of tabs 2-4 above.
2. Is Marathi/English the target (Hindi already exists)?
3. Confirm "Accountant" = users holding finance form codes (no new role will be created).
4. May I add `connectivity_plus` (and nothing else) for the offline banner?
5. Is touching shared widgets acceptable if verified at desktop width, or must changes be phone-only?
6. Flutter is not installed here; should I install it to run analyze/tests, or will CI be the gate?
