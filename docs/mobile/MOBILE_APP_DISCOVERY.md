# Mobile App Discovery (Phase 1)

Status: discovery only. No application code was changed. Date: 2026-11-12. Branch: `ccr-be1ab1af-sdjnmf`.

**Verification limits.** The Flutter SDK is not installed in this environment, so `flutter analyze` and `flutter test`
were **not run** (NOT VERIFIED). Everything below comes from reading source, docs, workflows and git history.
The production site (society.duxos.in) was not exercised.

## 1. Headline finding

There is no prototype to replace. `mobile/` is one mature Flutter codebase (~93k lines, 416 Dart files, 129 screens,
93 test files, 466 Dio calls against ~600 backend routes). It already serves **web, desktop-width and phone** from the
same code. A phone-specific shell, role dashboards, push, biometrics, Hindi/Marathi and a Play-Store release pipeline
exist. The brief's "transformation" is therefore **polish and re-architecture of the phone experience on top of the
existing app**, not a build. **No second mobile architecture is needed or proposed.**

## 2. Architecture

| Area | Current implementation |
|---|---|
| Stack | Flutter (CI pins 3.47.5), Riverpod 2, go_router 14, Dio 5, flutter_secure_storage, local_auth, firebase_messaging, shared_preferences, intl |
| Layout | `lib/core` (api, auth, config, layout, navigation, router, theme, l10n, push, motion), `lib/features/<module>/{data,domain,presentation}` (clean-architecture in older modules; flatter `data` + `presentation` in newer ones), `lib/shared/widgets` |
| Layout switch | `AppShell`: width >= 1024 -> desktop sidebar/top bar; below -> `_PhoneFrame` + `PhoneBottomBar` |
| Editions | `APP_EDITION=field` (Android APK) keeps only field screens and field roles; web-only roles are told to use the web app at sign-in. Default = full (web). |
| Backend | FastAPI, 21 modules, RBAC by "form codes" seeded in `backend/app/core/rbac_seed.py` |

Largest files (refactor risk): `maintenance_billing_screen.dart` 1690, `role_dashboards.dart` 1609,
`maintenance_billing_api.dart` 1413, `bank_reconciliation_statement_screen.dart` 1212, `app_router.dart` 1187.

## 3. Authentication and session

- Login -> `/auth/login`, tokens in `flutter_secure_storage` (EncryptedSharedPreferences on Android; Keychain on iOS). Web uses SharedPreferences (documented rationale).
- Dio `QueuedInterceptor` injects Bearer, on 401 refreshes through a separate interceptor-free client and retries; on failure clears tokens and fires `ApiClient.onSessionEnded` -> sign-in. A past deadlock here was fixed.
- Biometric lock screen, signed-in-devices screen, forced password change, terms acceptance, multi-society switcher (`ResettableScope` rebuilds all providers on switch, so no cross-tenant state).
- Pending deep link is captured pre-login and restored after (`_pendingDeepLink`).
- Gaps: timeouts fixed at 15 s connect/receive with **no retry/backoff**; no connectivity awareness (0 uses of a connectivity package); a "server may be starting up" message exists but there is no automatic retry.

## 4. Role and permission model (important for the proposed navigation)

Two layers, both real:

1. **Role names** (16 seeded): Platform Admin, Society Admin, Committee Chairman/Secretary/Treasurer/Member, Manager, Security Supervisor, Housekeeping Supervisor, Technical Supervisor, Security Staff, Housekeeping Staff, Technical Staff, Gym Trainer, Resident, Tenant. `UserEntity` derives booleans by substring (`isSecurity` = any role containing "Security", `isStaff` = contains "Staff"/"Supervisor"). **There is no "Accountant" role**; accounting is Committee Treasurer / Society Admin.
2. **Form codes** (39) granted per role at runtime via `GET /roles/forms/mine` (`myFormCodesProvider`); an admin can regrant per role without an app release. The menu (`appMenuCategories`), phone tabs (`phoneTabsFor`) and client route guards (`route_access.dart`) are all driven by form codes. The backend independently returns 403.

Consequences for the brief:
- Navigation must be **form-code-aware**, not role-name-aware. A fixed "Admin: Home|Operations|Finance|People|More" must hide/replace tabs the person has no form codes for (e.g. a Treasurer may have Finance but not People).
- "Accountant" and "Manager" experiences are *capability bundles* (form-code sets), not roles. The one Manager role exists.
- Known mismatch recorded in code: a Tenant is not granted `my_bills`, so those screens are deliberately unguarded client-side.
- Docs `RBAC_MATRIX.md` and `FLUTTER_ARCHITECTURE.md` describe an older 5-role model (Admin/Committee/Resident/Security/Staff, "HomePlaceholderScreen"); they are **stale**. `USERS_AND_ROLES.md` and `rbac_seed.py` are authoritative.

## 5. Navigation today

- Phone: `NavigationBar` = Home + up to 3 role-preferred, permission-filtered tabs + More. Preference order: admin/committee/manager `visitors, complaints, maintenance_billing, notices`; security `visitors, notices, complaints`; resident `my_bills, visitors, notices, complaints`.
- More = bottom sheet with society header, category pills, items, language, switch society, help, devices, sign out. There is **no search** in More.
- Bar only shows on tab/menu pages; detail pages use a back arrow.
- Deep linking: in-app capture/restore only. **No Android App Link/intent filter** for https URLs; push taps routing not verified.
- Role dashboards in `role_dashboards.dart`: Admin, Committee, Security, Resident, Manager, Supervisor, Staff; chip-style quick actions.

## 6. Design system today

`AppTheme` (iOS-inspired): primary #0066FF, iOS semantic colours, radii 10/14/18/24, Inter + bundled NotoSansDevanagari, card shadow, light theme only. 2,510 `AppTheme.x` static references across features; only ~12 raw `Color(0x...)` outside the theme (good consistency). **Dark mode is architecturally blocked**: colours are static constants, not `Theme.of(context)`. 276 `withOpacity` calls (deprecated in recent Flutter; CI tolerates ~437 analyzer infos). Shared widgets: `app_widgets.dart` (684), `app_form.dart` (875), `app_data_table.dart`; 23 files use a data table. 22 `Semantics` uses in total. Motion helpers in `core/motion`.

## 7. Localisation

English/Hindi/Marathi via a custom `kTranslations` map and `context.tr`, covering menu and shared strings. Only ~7 feature files call `context.tr`, so **screen bodies are mostly English**. Devanagari font bundled. INR/date formatting: 93 `NumberFormat`/`₹` uses, consistency not audited.

## 8. Reliability and performance

- Pagination: `getAllPages` fetches *every* page eagerly (page 200, up to 50 pages) for several lists - correct totals, but heavy on slow networks. Infinite scroll exists in places (`paged_test`).
- `cached_network_image` is a dependency but **unused** (0 references).
- No offline cache, no request retry, no connectivity banner.
- Startup: dotenv load, Firebase/push init before `runApp`; not profiled.

## 9. Android

| Item | State |
|---|---|
| Application ID / namespace | `in.duxos.society` (PASS) |
| Label / icon | "DUX OS"; adaptive-icon xml present; launch_logo splash via `launch_background.xml` (legacy splash, no Android 12 SplashScreen API check) |
| Permissions | INTERNET, ACCESS_NETWORK_STATE, USE_BIOMETRIC, CAMERA, POST_NOTIFICATIONS. Camera permission declared for image_picker. |
| Network security | cleartext off, system trust anchors (PASS) |
| Signing | key.properties or `ANDROID_KEYSTORE_*` env; **falls back to debug key** when absent (Play-rejected; guarded by workflow secret check) |
| Versioning | `version: 1.0.0+1`; AAB workflow overrides build number with run number |
| Shrinking | R8/minify **disabled** (documented crash history); no proguard rules |
| Workflows | `build-aab.yml` (manual, signed), `build-apk.yml` (field APK), `flutter-ci.yml` (analyze `--no-fatal-infos`, test, web build) |
| Firebase | `androidAppId` in `push_config.dart` must match registered app (per ANDROID_RELEASE.md) - NOT VERIFIED |
| Other | no iOS project in repo; portrait locked; `pubspec.lock` not committed (non-reproducible builds); build-apk.yml and build-aab.yml use unpinned `channel: stable` while CI pins 3.47.5 |
| Privacy | account/data deletion page added (#232) |

## 10. Tests and CI

- Flutter: 93 test files (widget/unit) covering accounts, billing, visitors, role home, route access, menu architecture, phone bottom bar, localization, motion, etc. Not executed here.
- Backend: pytest suites across 21 module dirs plus rbac/security/ci. Not executed here (docs claim 255 tests at last UAT, likely now higher).
- CI: backend-ci, flutter-ci, secret-scan, build-apk, build-aab. Analyzer infos tolerated.
- No integration/golden/device-size tests; no accessibility or text-scale tests beyond `dashboard_accessibility_test`.

## 11. Risks to honour during the transformation

1. Production web shares this code. Every shared-widget or theme change affects web/desktop; changes must be phone-scoped or verified against desktop width.
2. `role_dashboards.dart` and billing screens are very large; edit by extraction, not rewrite.
3. Do not touch `maintenance_billing_api.dart`, accounts calculations or payment flows without approval (rule 6).
4. Menu/route logic has dedicated tests (`menu_architecture_test`, `route_access_test`, `phone_bottom_bar_test`) that encode current behaviour; update intentionally, never weaken.
