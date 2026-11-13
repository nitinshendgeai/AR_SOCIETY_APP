# Mobile Implementation Plan

Branch per step, draft PR, CI green (flutter analyze + test + web build + backend tests) before the next. Nothing deploys without approval.
Defaults assumed (change any by saying so): phone navigation is built in the shared shell for every role and the Android field-edition gating is unchanged; Marathi and English are targets, Hindi stays; "Accountant" = a finance permission profile, no new role; `connectivity_plus` allowed in Step 6 only; shared-widget changes must be additive and checked at desktop width; CI is the test gate (Flutter is not installed locally).

| Step | Scope | Files (expected) | Risk | Exit criteria |
|---|---|---|---|---|
| 1 (this PR) | Design tokens, 4 widgets, design-system doc | `design_tokens.dart`, `app_status.dart`, test, docs | none (additive) | CI green |
| 2 | Navigation profiles and searchable More. Profiles: resident, admin/committee, manager, security, field staff. Tabs are hubs over existing routes, filtered by form codes, fallback to current logic | `app_menu.dart`, `phone_bottom_bar.dart`, new `phone_profiles.dart`; update `menu_architecture_test`, `phone_bottom_bar_test` | medium (tests encode current behaviour; change deliberately) | per-role tab tests incl. pruned-tab cases |
| 3 | Resident: Home hero (dues, next action), Payments hub (bills, receipts, history), Services hub (complaints, visitors, amenities, parcels), Profile | `role_dashboards.dart` (extract resident part), billing screens read-only UI | medium | no change to billing logic; resident tests green |
| 4 | Security: Gate home (new entry, check out, verify code, parcel in, inside now, search) | visitor, gate_extras, parking gate | medium | works with existing APIs only |
| 5 | Admin/manager/accountant hubs, phone card views for top tables (complaints, residents, defaulters, vendor bills) | per screen, additive card views | medium to high | desktop table untouched; totals unchanged |
| 6 | Reliability: GET retry with backoff (idempotent only, never POST), offline banner (`connectivity_plus`), stale-while-revalidate for dashboards, bounded paging | `api_client.dart`, `paged.dart` | medium | payments never auto-retried; tests with fake Dio |
| 7 | Localisation of resident and security screens (Marathi first), a11y fixes (`textTertiary` usage, tooltips), money widget | feature screens | low | text-scale and contrast tests |
| 8 | Android readiness: Android 12 splash, App Links (needs domain `assetlinks.json`, approval), R8 keep rules (device test), pin Flutter in build workflows, commit `pubspec.lock` | android, workflows | medium | signed AAB from approved secrets; checklist in `MOBILE_RELEASE_READINESS.md` |

Rules for every step: no backend, schema, calculation, payment or RBAC change; no mock data; new strings added to `kTranslations`; evidence recorded in `MOBILE_TEST_REPORT.md` with PASS / FAIL / CONDITIONAL PASS / NOT VERIFIED.

Deliverables still to create as steps land: `MOBILE_TEST_REPORT.md` (starts after Step 2), `MOBILE_RELEASE_READINESS.md` (Step 8).
