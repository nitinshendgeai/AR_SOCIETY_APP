# Mobile Module Coverage (Phase 1 baseline)

Basis: static reading of `mobile/lib/features`, `core/navigation/app_menu.dart`, `backend/app/modules`, `rbac_seed.py`.
Rating key: PASS, FAIL, CONDITIONAL PASS, NOT VERIFIED. **Nothing was run**, so test evidence is NOT VERIFIED across the board;
"Mobile UI" and "API" below mean *exists in code and is wired to a real endpoint*, not *verified working*.
Screens counts are `*_screen.dart` files; form code is the RBAC gate.

| Module | Form code(s) | Screens | In phone menu | In field APK | Existing functionality | Mobile UI / API | Permission handling | Test evidence | Remaining gaps |
|---|---|---|---|---|---|---|---|---|---|
| Auth, devices, biometric | - | 4 + devices | n/a | yes | login, forced pw change, terms, society switch, device list | Exists / real API | server session end handled | NOT VERIFIED (auth_page, device_session, multi_society tests exist) | no retry on slow net |
| Role dashboards | - | 7 role homes | Home tab | yes | Admin, Committee, Manager, Supervisor, Security, Staff, Resident | Exists, chip-style; data via `dashboard` module | per role routing, tested (`role_home_test`) | NOT VERIFIED | stale partial `--` values noted in KNOWN_ISSUES; no collection/outstanding hero cards for resident |
| Maintenance billing (admin) | maintenance_billing, maintenance_elements, defaulters | 10 | Finance | web only | cycles, elements, flat charges, interest, waiver | Desktop-style; phone usability NOT VERIFIED | form-code guarded | NOT VERIFIED (many billing tests) | table-heavy; **calculations must stay untouched** |
| My Bills / payments / receipts | my_bills, online_payments | billing 5 | Payments (resident) | yes | bills, online payment, screenshot upload, receipts | Exists / real API | Tenant lacks `my_bills` grant (known) | NOT VERIFIED (resident_bills/payments tests) | receipt UX, payment history cards need review |
| Accounts / finance | accounts, bank_reconciliation | 20 | Accounts | web only | vouchers, books, petty cash, BRS, TDS, reports | Desktop-first | guarded | NOT VERIFIED | not suited to field APK; admin-on-phone requires full edition decision |
| Vendors & work, vendor bills, vendor master | vendors, vendor_bills, vendor_master | 10 | Operations/Finance | web only | masters, bills, TDS, work orders, AMC | Exists | guarded | NOT VERIFIED | large forms |
| Visitors | visitors | 3 | Community | yes | entry, approval, society list, my visitors, guest pass, alerts | Exists, push alert wired | resident vs society-wide route resolution | NOT VERIFIED (visitor_alert, resident_visitors, guest_pass) | Security fast-gate flow not a dedicated tab set |
| Gate extras (parcels, domestic help) | parcels, domestic_help | 2 | Community | yes | delivery/parcels, domestic help | Exists | - | NOT VERIFIED (gate_extras_test) | "Delivery management" lives under Community menu |
| Parking | parking_management | 2 + gate check | Property | partial | zones, slots, gate check, violations, rates | Exists | guarded | NOT VERIFIED (4 tests) | - |
| Complaints | complaints | 3 | Community | yes | create, detail, assign, dept routing | Exists | resident vs society routes | NOT VERIFIED | "Service requests" overlap with vendors work - naming to confirm |
| Notices | notices | 2 | Community | yes | publish, view, acknowledge, emergency banner | Exists | create limited to admin/committee | NOT VERIFIED | - |
| Amenities | amenities | 2 | Community | yes | booking FSM, deposits | Exists | - | NOT VERIFIED | - |
| Governance (meetings, polls), documents, certificates | meetings, polls, documents, certificates | 3 + 1 | Community | yes | meetings, polls, documents, NOC | Exists | - | NOT VERIFIED | - |
| Staff, attendance, duties, handover | staff | 15 | People | yes (portal) | master, punch in/out, approvals, duties, leave API | Exists; manager/supervisor dashboards live | portal vs register by role | NOT VERIFIED | **leave self-service UI missing** (KNOWN_ISSUES); edit duty missing |
| Manager checklist, templates, lights check | manager_checklist, checklist_templates, lights_check | 3 | Operations | partial | daily/monthly checklists, lights check | Exists | guarded | NOT VERIFIED | - |
| Residents, tenants, pending changes, My Home | residents, tenants, pending_resident_changes, edit_my_info | 12 | People | partial (my info) | master, bulk import, edit requests, family/flat info | Exists | guarded; own-profile unguarded | NOT VERIFIED | bulk import is desktop-oriented |
| Society structure, settings, setup wizard | setup_wizard, society_settings | 9 + 1 + 3 | Admin | web only | wings/floors/flats, settings, wizard | Exists | guarded | NOT VERIFIED | - |
| Users and roles, matrices, automation | users_roles, permission_matrix, forms_matrix, automation | 8 + 1 | Admin | web only | RBAC admin | Exists | guarded | NOT VERIFIED | - |
| Assets, stores/inventory, shops | assets, inventory, shops | 3 + 2 + 2 | Property/Operations | web only | registers | Exists | guarded | NOT VERIFIED | - |
| Help assistant | - | 1 | More | yes | in-app assistant | Exists | - | NOT VERIFIED | - |
| Platform console | platform_admin | 2 | Platform | web only | cross-society | Exists | platform admin only | NOT VERIFIED | - |
| SOS | - | - | - | - | `sos_test` exists | NOT VERIFIED | - | NOT VERIFIED | locate feature |

## Brief's proposed experiences vs reality

| Brief expectation | Reality | Finding |
|---|---|---|
| Resident: Home/Payments/Services/Notices/Profile | Resident modules all exist (bills, receipts, complaints, visitor approval, amenities, My Home, notices) | Feasible without new APIs. Payments/Services are *groupings* of existing screens. |
| Admin: Home/Operations/Finance/People/More | All screens exist in full edition | Feasible, but finance/people tabs must adapt to granted form codes. Admin features are web-only in the shipped field APK. |
| Security: Gate/Visitors/Delivery/Logs/Profile | visitors, parcels, parking gate check, guest pass, entry/check-out/verify code exist | Feasible; "Gate" is a new composite screen over existing APIs. |
| Manager | Role exists; staff, complaints, checklists, vendor work exist | Feasible. |
| Accountant | **No such role**; Treasurer/Admin hold accounts form codes | Treat as a capability profile. |
| Reports and analytics | Accounts reports, defaulters, outstanding screens | Desktop-oriented; mobile report views not designed. |
| "Facility and amenity services" | amenities | PASS-shaped, verify. |


## Status after the transformation work (evidence: MOBILE_TEST_REPORT.md)

The baseline table above still describes the code *before* this work. What changed, with ratings:

| Area | Change | Rating |
|---|---|---|
| More sheet | Search by screen or group name, English or Marathi/Hindi, grant-aware | PASS (CI green, PR #237) |
| Resident Home | Outstanding-dues card first, with status chip and a 48 dp button; shown only with the `my_bills` grant | PASS (CI green, PR #238) |
| Resident bills / payments | Reviewed: the existing My Bills screen already has the mobile pattern (hero, Overdue / To Pay / History, claims). No change made | PASS (unchanged) |
| Security Staff home | Gate panel: inside now, let in today, visitors today, four large actions; unknown figures shown as `--`, never 0 | PASS (CI green, PR #239) |
| Visitor log (phone) | Search by name, mobile, flat, vehicle, purpose over the latest 50 visitors | CONDITIONAL PASS (PR #240): **FAIL for full-history search** until the backend gets a filter or paging |
| Admin / committee / manager navigation | Operations, Finance, People hub tabs from granted screens | CONDITIONAL PASS: tests green; not run on a device |
| Network failures | GET retry, offline banner | CONDITIONAL PASS |
| Accessibility | Text greys now meet 4.5:1 | PASS (computed and tested); other a11y items (tooltips, 200% text scale) NOT VERIFIED |
| Android | Flutter pinned for release builds, backup off; AAB, splash, App Links, R8 open | see MOBILE_RELEASE_READINESS.md |
| Marathi/English | All new phrases translated; most older screen bodies are still English | CONDITIONAL PASS |
| Accounts / finance reports, vendors, staff attendance, complaints, notices, amenities, governance | Not modified; existing tests green | PASS (unchanged), mobile table-to-card conversion NOT DONE |

### Not done, and why
- **Phone card views for the table-heavy admin screens** (defaulters, vendor bills, bank reconciliation, registers): each is a large screen with money logic; converting them without a device to look at them would be guesswork. Needs a device or emulator review first.
- **Full-history visitor search**: needs a backend parameter.
- **Android App Links, signed AAB, R8**: need your approval, secrets or a device.
- **Dark theme**: out of scope by the brief (light first); still blocked by static colour constants.
