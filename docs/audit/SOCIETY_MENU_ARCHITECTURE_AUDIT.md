# Society Menu Architecture Audit

| | |
|---|---|
| Status | **Phase 1 only (inspection). No application code has been changed. Awaiting approval before Phase 2+.** |
| Branch | `claude/compassionate-planck-6h3b5e`, at `origin/main` `371169b` (PR #126 merge). Working tree clean apart from this file. |
| Not done | Nothing pushed, merged, deployed. Railway, production data and `https://society.duxos.in` were not touched or contacted. |
| Toolchain | **`flutter` and `dart` are not installed in this container**, so `flutter analyze` / `flutter test` / web build have not been run and no baseline exists yet. Installing the SDK (proxy permitting) is the first step of Phase 2. |
| Screenshots | **No screenshots reached me in the message** (only the text). Everything below comes from code. The screen names you described (Accounts, long sidebar, Gateway of Accounts) were matched to code; please re-send the images if you want visual specifics (for example the negative bank balance) compared. |

Evidence rule: where a fact is not in the repository it is marked **NOT VERIFIED**; nothing is inferred.

---

## 1. How navigation works today

| Fact | Evidence |
|---|---|
| Menu is **static in code, visibility is server-driven**. One list, `appMenuCategories` (8 categories, 39 items), each item tagged with a *form code*. The person sees the items whose form code is in `GET /roles/forms/mine` (`myFormCodesProvider`). Admins edit grants in the Forms Matrix. | `mobile/lib/core/navigation/app_menu.dart`; `backend/app/core/rbac_seed.py` `FORM_DEFINITIONS`, `FORM_ROLE_GRANTS` |
| That one list feeds **three renderers**: desktop sidebar (`_Sidebar`, ≥1024 px), phone **More** sheet (`phone_bottom_bar.dart`), and a third, separate **drawer** on the phone dashboards (`_DashboardShell`, `role_dashboards.dart:118`, `ExpansionTile`, `context.push`). | `app_shell.dart`, `phone_bottom_bar.dart`, `role_dashboards.dart` |
| Phone bottom bar = Home + first 3 allowed of a per-role preference list + More. | `phoneTabsFor`, `_tabPreference` |
| Routes: `AppRoutes` constants + one `GoRouter`, all signed-in pages inside one `ShellRoute` → `AppShell`. | `app_router.dart` |
| **Two client guard layers + the backend.** (a) `route_access.dart` maps path prefix → form code (management screens only; member screens deliberately unguarded). (b) Per-route `redirect:` blocks in `app_router.dart` that test **role-name predicates** (`isAdmin`, `isAdminOrCommittee`, `isManager`, …), e.g. all `/accounts/*`, `/vendors/*`, `/assets*`, `/billing/defaulters`, `/billing/bank-reconciliation` need Admin/Committee/Manager; `/parking/management` and `/society-settings` Admin/Committee; `/permission-matrix`, `/forms-matrix` Admin only. (c) Backend decides: role-tier dependencies (`require_admin_committee`, `require_manager_above`, …, `dependencies.py`) and `require_permission`/`has_permission` in a few places. | `route_access.dart`, `app_router.dart:323-935`, `backend/app/api/routes`, `modules/*/routes` |
| Deep links/refresh: pending deep link restored after session check; unknown grants block nothing; expired token → global sign-out (Phase 3 audit). | `app_router.dart:264-440`, `PHASE_3_DASHBOARD_UX_AUDIT.md` §2 |
| Theme: `AppTheme` tokens (`primary`, `primarySoft`, `surface`, `cardBg`, `border`, `textPrimary/Secondary/Tertiary`, `radiusM`…). Sidebar tile: 40 px, 20 px icon, 13.5 px label. Reusable: `AppPage`, `ResponsiveBody`, `GatewayMenu`. | `core/theme/app_theme.dart`, `app_shell.dart`, `shared/widgets` |
| Labels are translated via `context.tr(label)` using `core/l10n/translations.dart`. **Any renamed label needs a translation entry** (e.g. "Gateway of Accounts" has none today). | `translations.dart`, `localization_test.dart` |

## 2. Current menu tree (what the code renders)

Sidebar = flat list under uppercase headings; no group collapses. Utility tile "Collapse" is at the bottom; account menu (society switch, language, help, signed-in devices, sign out) is in the top bar on desktop.

```
Dashboard (utility tile, role home)
PLATFORM        Platform Console
PEOPLE          Residents · Tenants
PROPERTY        Wings · Flats · Shops
COMMUNITY       Visitors · Notices · Amenities · Meetings · Polls · Documents ·
                Certificates & NOC · Parcels · Domestic help · Complaints ·
                Pending Resident Changes
OPERATIONS      Manager's Checklist · Staff · Checklist Templates · Parking Management ·
                Assets · Stores · Vendors & Work
FINANCE         Maintenance Billing · Maintenance Elements · Payments · Defaulters ·
                Bank Reconciliation · Vendor Bills · Accounts
ADMINISTRATION  Users & Roles · Permission Matrix · Forms Matrix · Society Settings ·
                Automatic tasks · Setup Wizard
MY ACCOUNT      My Bills · Edit My Info
Collapse (utility tile)
```
A Society Admin sees 36 entries (all but Platform Console, My Bills, Edit My Info); Platform Admin sees only Platform Console.

## 3. Every existing menu item

Roles are the **seeded defaults** (`FORM_ROLE_GRANTS`); an Admin can change them at runtime, so the live list may differ. Abbreviations: **A** Society Admin, **C** Committee (Chairman/Secretary/Treasurer/Member), **M** Manager, **Sup** Security/Housekeeping/Technical Supervisor, **Stf** Security/Housekeeping/Technical Staff + Gym Trainer, **R** Resident, **T** Tenant, **P** Platform Admin, **All** = every canonical role. "Client guard" = per-route `redirect:` in `app_router.dart`. "Backend" = router-level dependency family only (endpoint-level checks were **not** traced individually; see §9).

| # | Current label | Current parent | Route | Screen | Form code → seeded roles | Client guard | Backend family | Duplicated / linked from | Proposed parent › submenu | Change type |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Platform Console | Platform | `/platform` | PlatformConsoleScreen | platform_admin → P | P only | `require_platform_admin` | — | Platform (unchanged, P only) | config only |
| 2 | Residents | People | `/residents` | ResidentListScreen | residents → A, C | formcode | `require_admin_committee` | Admin dashboard | People & Residents › Residents | config only |
| 3 | Tenants | People | `/tenants` | TenantListScreen | tenants → A, C | formcode | `require_admin_committee` (+manager read) | Admin dashboard | People & Residents › Tenants | config only |
| 4 | Pending Resident Changes | **Community** | `/residents/edit-requests/pending` | PendingResidentChangesScreen | pending_resident_changes → A, C | formcode | `require_admin_committee` | Admin dashboard | People & Residents › Pending Resident Changes | config only |
| 5 | Staff | **Operations** | `/staff` (staff) or `/staff/list` (A, C, M) | StaffHomeScreen / StaffListScreen | staff → A, C, M, Sup, Stf | none (not guarded) | `assert_society_access`, supervisor/manager tiers | dashboards (many) | People & Residents › Staff | config only (route is role-resolved today) |
| 6 | Users & Roles | Administration | `/users` | UserListScreen | users_roles → A | formcode | `require_admin` | password-requests from Admin dashboard | People & Residents › Users & Roles (see D2) | config only |
| 7 | Wings | Property | `/wings` | WingListScreen | **setup_wizard** → A, C | formcode | `require_admin`(write)/`require_committee` | via Setup Wizard | Property & Parking › Wings | config only |
| 8 | Flats | Property | `/flats` | FlatListScreen | **setup_wizard** → A, C | formcode | `require_admin`/`require_committee` | via Setup Wizard | Property & Parking › Flats | config only |
| 9 | Shops | Property | `/shops` | ShopsScreen | shops → A, C | formcode | `require_admin_committee` | — | Property & Parking › Shops | config only |
| 10 | Parking Management | Operations | `/parking/management` | ParkingManagementScreen | parking_management → A, C | **A/C role check** | `require_admin_committee`, `require_security` | gate check (separate route) | Property & Parking › Parking Management | config only |
| 11 | Assets | Operations | `/assets` | AssetsScreen | assets → A, C, M | A/C/M role check | `require_manager_above` family | — | Property & Parking › Assets | config only |
| 12 | Visitors | Community | `/visitors/my` or `/visitors/society/:societyId` (role-resolved) | VisitorListScreen | visitors → All | none | `require_any_member`/`require_security` | every dashboard | Community & Services › Visitors | config only |
| 13 | Notices | Community | `/notices` | NoticesScreen | notices → All | none | `require_any_member` | emergency banner | Community & Services › Notices | config only |
| 14 | Amenities | Community | `/amenities` | AmenitiesScreen | amenities → All | none | `require_any_member` | Admin dashboard | Community & Services › Amenities | config only |
| 15 | Meetings | Community | `/meetings` | MeetingsScreen | meetings → All | none | governance, `require_any_member` | — | Community & Services › Meetings | config only |
| 16 | Polls | Community | `/polls` | PollsScreen | polls → All | none | governance | — | Community & Services › Polls | config only |
| 17 | Documents | Community | `/documents` | DocumentsScreen | documents → All | none | governance | — | Community & Services › Documents | config only |
| 18 | Certificates & NOC | Community | `/certificates` | CertificatesScreen | certificates → All | none | `require_any_member` | — | Community & Services › Certificates & NOC | config only |
| 19 | Parcels | Community | `/parcels` | ParcelsScreen | parcels → All | none | gate | — | Community & Services › Parcels | config only |
| 20 | Domestic help | Community | `/domestic-help` | DomesticHelpScreen | domestic_help → All | none | gate | — | Community & Services › Domestic Help | config only |
| 21 | Complaints | Community | `/complaints` or `/complaints/society/:societyId` (role-resolved) | ComplaintListScreen | complaints → All | none | `require_any_member`/`require_manager_above` | every dashboard | Community & Services › Complaints | config only |
| 22 | Manager's Checklist | Operations | `/manager-checklist` | ManagerChecklistScreen | manager_checklist → A, C, M | formcode | `require_manager_above` | — | Operations › Manager's Checklist | config only |
| 23 | Checklist Templates | Operations | `/staff/checklist-templates` | ChecklistTemplatesScreen | checklist_templates → A, C, M | A/C/M role check | manager/supervisor | under `/staff` prefix | Operations › Checklist Templates | config only |
| 24 | Stores | Operations | `/stores` | StoresScreen | inventory → A, C, M | formcode | `require_manager_above` | Admin dashboard | Operations › Stores | config only |
| 25 | Vendors & Work | Operations | `/vendors/work` | VendorsWorkScreen | vendors → A, C, M | A/C/M role check | `require_manager_above` | — | Operations › Vendors & Work | config only |
| 26 | Maintenance Billing | Finance | `/billing/maintenance` | MaintenanceBillingScreen | maintenance_billing → A, C, M | formcode | billing: `require_admin_committee`, `has_permission` | dashboards | Finance & Maintenance › Maintenance Billing | config only |
| 27 | Maintenance Elements | Finance | `/billing/maintenance-elements` | MaintenanceElementsScreen | maintenance_elements → A, C, M | formcode | billing | — | Finance & Maintenance › Maintenance Elements | config only |
| 28 | **Payments** | Finance | `/billing/online-payments` | OnlinePaymentsListScreen | online_payments → A, C, M | formcode | billing | Manager dashboard | Finance & Maintenance › Payments. **Rename suggestion "Online Payments"** (form code and screen purpose: resident payment screenshots for reconciliation; "Payment" is also an accounting voucher) | label only (+translation) |
| 29 | Defaulters | Finance | `/billing/defaulters` | DefaultersScreen | defaulters → A, C, M | A/C/M role check | billing | Admin dashboard | Finance & Maintenance › Defaulters | config only |
| 30 | Bank Reconciliation | Finance | `/billing/bank-reconciliation` | BankReconciliationScreen | bank_reconciliation → A, C, M | A/C/M role check | billing | — | Finance & Maintenance › Bank Reconciliation | config only |
| 31 | Vendor Bills | Finance | `/vendors/bills` | VendorBillsScreen | vendor_bills → A, C, M | A/C/M role check | vendors | **Also**: Gateway "Ledgers and masters", Accounts "Books" grid, Accounts "Payable to Vendors" card, Manager dashboard | Finance & Maintenance › Vendor Bills (canonical); Accounts keeps links to same route | config only |
| 32 | Accounts | Finance | `/accounts` | AccountsScreen | accounts → A, C, M | A/C/M role check | `/accounts` router: `require_manager_above` (+`require_admin_committee` on 7 endpoints) | Admin dashboard | **Accounts & Financial Reports** (top-level; landing = existing AccountsScreen, Gateway = existing AccountsGatewayScreen) | config only |
| 33 | Permission Matrix | Administration | `/permission-matrix` | PermissionMatrixScreen | permission_matrix → A | **A only** | `require_admin` (roles) | — | Administration & Settings | config only |
| 34 | Forms Matrix | Administration | `/forms-matrix` | FormsMatrixScreen | forms_matrix → A | **A only** | `require_admin` | — | Administration & Settings | config only |
| 35 | Society Settings | Administration | `/society-settings` | SocietySettingsScreen | society_settings → A, C | A/C role check | `require_admin`/`require_committee` | Manager dashboard link | Administration & Settings | config only |
| 36 | Automatic tasks | Administration | `/automation` | AutomationScreen | automation → A, C | formcode | `require_admin_committee` | — | Administration & Settings | config only |
| 37 | Setup Wizard | Administration | `/structure-wizard` | SetupWizardScreen | setup_wizard → A, C | formcode | `require_admin` (structure) | `/setup-wizard` is a *different* onboarding screen (same class) | Administration & Settings | config only |
| 38 | My Bills | My Account | `/billing/my-bills` | MyBillsScreen | my_bills → **R only** | none | `get_current_user` + own-flat scoping | Resident dashboard card + chip | Resident › Payments | config only |
| 39 | Edit My Info | My Account | `/residents/me/edit` | EditMyProfileScreen | edit_my_info → **R only** | none | resident self-service | Resident dashboard chip | Resident › Profile & Help | config only |

Not menu items but behave like them: **Dashboard** (role home), **Collapse** (utility), **Gateway of Accounts** (`/accounts/gateway`, Alt+G, button on Accounts), **New Voucher / Add Expense** (Accounts actions), **Signed-in devices** (`/devices`, desktop account menu only), **Language / Switch society / Help** (desktop account menu; phone More sheet), **Sign out** (desktop account menu; phone dashboard app bar only).

## 4. Findings

### 4.1 Duplicates and label problems
1. **Vendor Bills** is reachable from 5 places, all the same route and screen. This is acceptable ("reuse canonical route") but the menu, Gateway and Accounts grid each define it independently.
2. **Payments** (menu) vs **Payment** (voucher) vs "Payments" bills grid: different things share a name. The route is the resident-screenshot reconciliation list.
3. **Duplicate icons** make groups hard to scan: `inventory_2_rounded` = Parcels *and* Assets; `storefront_rounded` = Shops *and* Vendor Bills; `receipt_long_rounded` = Payments *and* My Bills; `apartment_rounded` = Property category *and* Society Settings.
4. **"Setup Wizard"** (`/structure-wizard`) and the first-run onboarding wizard (`/setup-wizard`, same screen class, different route and gating) are two destinations with one name.
5. **Wings and Flats** share the form code `setup_wizard` with the Setup Wizard: they cannot be granted separately today.
6. **Pending Resident Changes** sits under Community although it is a people-admin queue; **Staff** sits under Operations.
7. The phone dashboard **drawer** is a third menu implementation (always-expanded `ExpansionTile`s, uses `context.push` which stacks pages; the sidebar/More sheet use `context.go`).

### 4.2 Orphaned / reachable-only-from-elsewhere (not defects by themselves)
`/accounts/*` (19 routes, from Accounts/Gateway), `/staff/*` sub-routes (approvals, duties, attendance, paper sheet, import, add), `/users/password-requests` (Admin dashboard only), `/devices`, `/assets/import`, `/shops/import`, `/residents/import`, detail/form routes. No dead menu item found: every one of the 39 entries resolves to a registered route and screen. `appMenuCategories` item `route` is never null in the current list.

### 4.3 Gaps for the proposed resident menu
Verified implemented for residents: dashboard, My Bills, Edit My Info, Visitors (+pending approvals), Complaints, Notices, Amenities (+`/amenities/bookings/me/list`), Meetings, Polls, Documents, Certificates, Parcels, Domestic help, "My Flat" (dashboard card with flat switcher only, no screen).
**No resident-facing screen or route found for:** My Flat page, Household Members, My Vehicles (vehicles exist only inside Flat detail, an admin-guarded route), Occupancy Details, Society Directory (policy R12 still open), Payment History, Receipts, Statements as separate screens (**NOT VERIFIED** whether `MyBillsScreen` contains history/receipts; to be checked), Events, Notifications screen (a `/notifications` backend router exists; no app route), Help & Contact (Help opens an external doc via `openHelp`). Per your rule these are **not** put in the menu.

### 4.4 Role / permission risks
- **R1 – two authorization models for the same screen.** Menu visibility = form code; route guards = role-name predicates; backend = role tiers. If an Admin grants e.g. `accounts` to a role outside Admin/Committee/Manager, the menu shows it but the router bounces and the backend 403s. Today's defaults are consistent. Fixing it (permission-based guards) is outside navigation scope; **needs your decision** (D4).
- **R2 – Accounts → Vendor Bills / Defaulters cross-grant.** A user with `accounts` but not `vendor_bills`/`defaulters` can tap those links on the Accounts page and is redirected home with "no access". Gateway/Accounts links should be hidden per form code (client-side convenience only).
- **R3 – Tenant gap (existing).** Tenant has no `my_bills`, `edit_my_info`; their dashboard links to both. Not changed unless you approve.
- **R4 – member screens are unguarded client-side by design** (route_access.dart). Direct URLs to them open; backend is the control. Resident isolation tests must therefore be backend-level, not just menu-level.
- **R5 – role-resolved routes** (visitors, complaints, staff) are computed in `_resolveFor`; moving items must keep that logic or those items regress to the wrong list.
- **R6 – Platform Admin** sees only the Platform category by a hard-coded label comparison (`category.label == 'Platform'`). Renaming/reshaping categories must keep this.
- **R7 – Translations**: renamed or new labels/groups need `translations.dart` entries; `localization_test.dart` reads menu data.
- **R8 – Sign out is missing from the phone More sheet**; phone sign out exists only on role dashboards' app bar (and Signed-in devices has no phone entry). A user on a deep-linked page cannot sign out without going Home.
- **R9 – Existing tests that encode today's menu:** `phone_bottom_bar_test.dart`, `route_access_test.dart` ("every guarded menu entry maps to its own form code"), `localization_test.dart`, `accounts_gateway_test.dart`, `role_home_test.dart`. They must be updated deliberately, not weakened.

### 4.5 Accounts and Gateway today
- **Accounts landing** (`AccountsScreen`), in order: warning banners (ledger warnings → ledger/chart), pending-postings banner with the **Sync** action, approvals banner, recurring-due banner, KPI cards (Bank, Cash, Members' Dues, Payable to Vendors, Income FY, Expenditure FY), a flat **Books grid of 13 tiles** mixing registers, outstanding, setup and reports, Cash & Bank Books card, recent activity; header actions Gateway (Alt+G), New Voucher, Add Expense; FAB on phone.
- **Gateway** (`AccountsGatewayScreen` + `GatewayMenu`): sections **Vouchers** (Receipt R, Payment P, Contra C, Journal J, Expense E), **Books** (Day Book D, Cash & Bank B, Invoice Register I, Bills Register L, Approvals A, Monthly Expenses M), **Reports** (Trial Balance T, Income & Expenditure X, Balance Sheet S, Receipts & Payments Y, Funds F, Outstanding Receivable U, Outstanding Payable W, Spend by Element O, Financial Statements & Year-end Z), **Ledgers and masters** (Chart of Accounts H, Members' Ledger N, Vendor Bills V). 23 items, 23 unique letters (no duplicate shortcut). Keys: ↑/↓ wrap, Enter, letter, Esc; Ctrl/Alt/Cmd ignored; F4 Contra, F5 Payment, F6 Receipt, F7 Journal, Alt+G (voucher_hotkeys.dart). Tested in `accounts_gateway_test.dart`.
- Mapping to your groups A–E is straightforward and config-only: **Transactions** = Vouchers section; **Books & Registers** = Books minus Approvals; **Receivables & Payables** = Outstanding Receivable/Payable (now filed under Reports), Members' Ledger, Vendor Bills, Approvals; **Accounting Setup** = Chart of Accounts; **Financial Reports** = the report items. No "ledger/master configuration" screen other than Chart of Accounts was found. `/accounts/recurring` (Monthly Expenses) and `/accounts/ledger/:accountId` (any ledger) exist; ledgers have no list entry other than Chart of Accounts and the KPI cards.
- Defaulters and Maintenance Billing are not in the Gateway (they are Finance & Maintenance); keep it that way.
- The negative-bank-balance warning style, Sync, approvals and recurring banners are business surfaces: **preserved as is**.

## 5. Proposed master menu tree (for approval)

Adapted from your proposal where code evidence required. Same 39 items, same routes, same form codes; only grouping, order, labels and heading change.

```
Dashboard                      (utility tile, unchanged)
PEOPLE & RESIDENTS             Residents · Tenants · Pending Resident Changes · Staff · Users & Roles
PROPERTY & PARKING             Wings · Flats · Shops · Parking Management · Assets
COMMUNITY & SERVICES           Visitors · Parcels · Domestic Help · Complaints · Notices · Amenities ·
                               Meetings · Polls · Documents · Certificates & NOC
OPERATIONS                     Manager's Checklist · Checklist Templates · Stores · Vendors & Work
FINANCE & MAINTENANCE          Maintenance Billing · Maintenance Elements · Online Payments* · Defaulters ·
                               Vendor Bills · Bank Reconciliation
ACCOUNTS & FINANCIAL REPORTS   Accounts (landing) · Gateway of Accounts
ADMINISTRATION & SETTINGS      Permission Matrix · Forms Matrix · Society Settings · Automatic Tasks · Setup Wizard
PLATFORM (Platform Admin only) Platform Console
```
\* rename pending D3. Residents (R/T) never see the management groups because their form codes are not granted; they get the resident menu below.

**Adaptations from your proposal, with reasons**
- *Dashboard › Pending Actions / Alerts*: no separate screens exist (approvals/alerts are cards on dashboards); not added.
- *Users & Roles* is placed under People & Residents as you proposed, but it is Admin-only and a system-access screen; alternative is to keep it in Administration (**D2**).
- *Accounts*: kept as **one** menu entry that opens the existing landing page, plus **Gateway of Accounts** as a second entry to the existing Gateway. Sub-groups A–E live **inside** the Gateway and landing page (below), not as 20 sidebar entries (keeps depth ≤ 2, avoids a second copy of 20 destinations).
- *Vendor Bills* stays in Finance & Maintenance (canonical, as you asked) and remains linked from Accounts → Receivables & Payables to the same route.
- *Payments* proposed as Finance & Maintenance item under its existing code `online_payments`.
- *Users & Roles*, *Staff*, *Pending Resident Changes*, *Wings/Flats*: moves are config-only.
- Sidebar groups become **collapsible**, the group of the current route auto-expands (new behaviour, Phase 5).

## 6. Before / after mapping

| Item | Before (parent) | After (parent) | Route change | Note |
|---|---|---|---|---|
| Platform Console | Platform | Platform | none | |
| Residents, Tenants | People | People & Residents | none | |
| Pending Resident Changes | Community | People & Residents | none | |
| Staff | Operations | People & Residents | none | role-resolved route kept |
| Users & Roles | Administration | People & Residents (D2) | none | |
| Wings, Flats, Shops | Property | Property & Parking | none | |
| Parking Management, Assets | Operations | Property & Parking | none | |
| Visitors, Notices, Amenities, Meetings, Polls, Documents, Certificates, Parcels, Domestic help, Complaints | Community | Community & Services | none | reordered |
| Manager's Checklist, Checklist Templates, Stores, Vendors & Work | Operations | Operations | none | |
| Maintenance Billing, Maintenance Elements, Defaulters, Bank Reconciliation, Vendor Bills | Finance | Finance & Maintenance | none | |
| Payments | Finance | Finance & Maintenance (as "Online Payments", D3) | none | label + translation |
| Accounts | Finance | Accounts & Financial Reports | none | + Gateway entry (existing route) |
| Permission Matrix, Forms Matrix, Society Settings, Automatic tasks, Setup Wizard | Administration | Administration & Settings | none | |
| My Bills, Edit My Info | My Account | Resident menu (§7) | none | |

No route changes are proposed anywhere. Zero redirects needed.

## 7. Proposed resident menu (verified features only)

```
HOME                 Dashboard                       /resident (Resident and Tenant)
MY SOCIETY           — My Flat: dashboard card only (no screen) → not a menu item
                     — Household Members, My Vehicles, Occupancy, Directory: no resident screen / policy open → omitted
PAYMENTS             My Bills                        /billing/my-bills   (R only today; Tenant gap R3)
SERVICES & COMMUNITY Visitors  /visitors/my · Complaints /complaints · Notices · Amenities ·
                     Meetings · Polls · Documents · Certificates & NOC · Parcels · Domestic Help
PROFILE & HELP       Edit My Info  /residents/me/edit · Language · Help (external) · Sign out
```
Gating is the existing form codes, so a revoked grant removes an item. Residents cannot see management groups. Server-side authorization is untouched. The omitted items are listed in §4.3; adding any needs a real screen first (out of scope: "do not invent modules").

## 8. Accounts Gateway hierarchy (proposed, same 23 destinations and shortcuts)

| Group | Items (current letter) |
|---|---|
| **A. Transactions** | Receipt R · Payment P · Contra C · Journal J · Expense E (F4–F7 and Alt+G unchanged) |
| **B. Books & Registers** | Day Book D · Cash & Bank Book B · Invoice Register I · Bills Register L · Monthly Expenses M |
| **C. Receivables & Payables** | Outstanding Receivable U · Outstanding Payable W · Members' Ledger N · Vendor Bills V · Approvals A (badge kept) |
| **D. Accounting Setup** | Chart of Accounts H |
| **E. Financial Reports** | Trial Balance T · Income & Expenditure X · Balance Sheet S · Receipts & Payments Y · Schedule of Funds F · Spend by Maintenance Element O · Financial Statements & Year-end Closing Z |

Letters are kept so muscle memory and existing `gateway-<letter>` test keys survive; only section membership/order changes (`GatewayMenu` stays as is, plus a heading-level semantics improvement). Accounts landing order (warnings → summary cards → voucher actions → books → ledgers/reports) already matches your priority list except the 13-tile grid, which would be split into the same A–E headings using the same tile data.

## 9. Role-visibility matrix (seeded defaults)

| Menu group | P | A | C | M | Sup | Stf | R | T |
|---|---|---|---|---|---|---|---|---|
| Platform | ✔ | – | – | – | – | – | – | – |
| People & Residents | – | all 5 | Residents, Tenants, Pending, Staff | Staff | Staff | Staff | – | – |
| Property & Parking | – | all | Wings, Flats, Shops, Parking, Assets | Assets | – | – | – | – |
| Community & Services | – | all 10 | all 10 | all 10 | all 10 | all 10 | all 10 | all 10 |
| Operations | – | all | all | all | – | – | – | – |
| Finance & Maintenance | – | all | all | all | – | – | – | – |
| Accounts | – | ✔ | ✔ | ✔ | – | – | – | – |
| Administration | – | all 5 | Society Settings, Automatic tasks, Setup Wizard | – | – | – | – | – |
| Resident menu (My Bills, Edit My Info) | – | – | – | – | – | – | ✔ | – (R3) |

Per-item view/action permissions are the form code (view) and the backend endpoint dependency (action) from §3. **Action-level permissions (create/approve/post) were not individually traced**; Phase 4 will produce that table by reading each router, or you can limit scope to the form-code level. Behaviour on denial today: unknown grants → open (backend decides); known missing grant → redirect to own dashboard + "You do not have access to that screen."; backend → 403.

## 10. Prioritised implementation plan (after approval)

1. **P0 – set up**: install Flutter SDK, record baseline `flutter analyze` / `flutter test` / `flutter build web --release`, backend authorization tests. Branch stays local.
2. **P1 – menu data**: restructure `appMenuCategories` (groups, order, labels, `Accounts` + `Gateway` entries), add nesting-free group metadata, unique icons, translations. Tests: tree/order, route↔item, no duplicate form code+route, no orphan form codes, updated `route_access_test`/`phone_bottom_bar_test`/`localization_test`.
3. **P2 – one renderer set**: make the dashboard drawer use the same shared widget/data as the sidebar and More sheet (removes the third copy); sidebar groups collapsible, auto-expand current group, scroll with pinned header/footer, richer breadcrumb, `Semantics`/selected state, tooltips when collapsed.
4. **P3 – phone**: add Sign out and Signed-in devices to More, keep ≤ 4 tabs, safe-area and text-scale tests.
5. **P4 – Accounts**: regroup Gateway into A–E (letters unchanged), reorganise landing Books grid under the same headings, hide cross-links the user has no form code for.
6. **P5 – resident menu** from form codes (no new screens).
7. **P6 – docs/tests/final audit** per Phase 8.

Risk control: every step is config/presentation only; no route, schema, accounting, billing or payment code is touched.

## 11. Decisions I need from you

| # | Decision | My recommendation |
|---|---|---|
| D1 | Approve the proposed tree in §5 and the Gateway grouping in §8 | Approve |
| D2 | *Users & Roles* under People & Residents or Administration & Settings? | Administration & Settings (it is system access, Admin only; keeps people records separate from accounts, as your brief says) |
| D3 | Rename "Payments" → "Online Payments"? | Yes |
| D4 | Leave role-name route guards (R1) as they are for this work? | Yes; flag for a separate permission-based refactor |
| D5 | Tenant gap (R3): leave, or grant `my_bills`/`edit_my_info` to Tenant? | Leave (policy change) |
| D6 | Resident items with no screen (§4.3): leave out of the menu? | Leave out |
| D7 | Re-send the screenshots if any visual detail beyond the code should drive the design | — |

## 12. Not verified / not done in Phase 1
- No Flutter/Dart tooling, so nothing was run or compiled.
- Per-endpoint backend permissions, and whether `MyBillsScreen` shows history/receipts/statements, were not traced.
- Production (`society.duxos.in`) and the screenshots were not seen.
- Sections 13+ of the final audit (final tree, files changed, test and build results) are for Phase 8.
