# Known Issues — AR Society ERP

Last updated: 2026-06-20 (dashboard integration audit — staff dashboard navigation defects fixed)

---

## Active Issues

### [FIXED 2026-06-20] Staff Dashboard "My Operations" cards do nothing when tapped

`StaffHomeScreen` resolved `currentStaffProvider` (async) but the returned `AsyncValue` was ignored. `staffIdProvider` starts `null` while the provider fetches; all three operation cards (Attendance, My Duties, Handover) received `onTap: null` silently. Cards appeared enabled but produced no navigation.

**Fix:** `_StaffProfileStatus` replaces `_StaffIdSetup`; cards use `disabled: !isReady` with `AnimatedOpacity`; `RefreshIndicator` added for pull-to-refresh retry.

---

### [FIXED 2026-06-19] Staff cannot apply for own leave / view own leave history — 2 RBAC bugs fixed

`POST /staff/leaves/{staff_id}` and `GET /staff/leaves/staff/{staff_id}` both used `supervisor_above`, blocking staff from self-service leave. Fixed: both now use `any_staff` with own-record enforcement at service layer. Supervisors/managers retain ability to apply/view on behalf of any staff member.

### [FIXED 2026-06-19] Technical Supervisor dashboard shows wrong department

`SupervisorDashboardScreen` only detected housekeeping vs security departments. Technical Supervisor was misclassified as security, loading wrong department approval counts. Fixed: `isTechnical` detection added, dashboard now resolves to correct department for all three supervisor types.

---

### [KNOWN GAP] Edit Duty — not implemented

There is no `PATCH /staff/duties/{id}` endpoint and no Edit Duty UI. Once assigned, a duty's name/description/location cannot be changed. The only lifecycle actions available are Mark Complete (staff) and Verify (supervisor). No broken button exists.

### [KNOWN GAP] Close Handover — not implemented

The handover lifecycle ends at `accepted` or `disputed`. There is no explicit "close" state or endpoint. Accepted handovers are considered complete. No broken button exists.

### [KNOWN GAP] Leave self-service UI not yet available

The leave apply/view API is now open to staff (`any_staff` guard + own-record check), but no Flutter screen exists for staff to apply or view their leave. Currently only accessible via direct API call.

---

### [FIXED 2026-06-18] Staff cannot punch in/out — 6 RBAC permission bugs fixed

Six critical permission mismatches in `backend/app/modules/staff/routes/staff.py` were identified and fixed:
1. `check_in` / `check_out`: was `supervisor_above` → now `any_staff`
2. `get_attendance`: was `admin_or_committee` → now `any_staff`
3. `list_staff`: was `admin_or_committee` → now `supervisor_above` + added optional `department` query param
4. `get_staff`: was `admin_or_committee` → now `supervisor_above`
5. `duties_by_date`: was `admin_or_committee` → now `supervisor_above`
6. `update_task status`: was `supervisor_above` → now `any_staff`

Staff attendance workflow now works end-to-end for all 7 staff roles. 79 backend tests pass.

---

### [FIXED 2026-06-17] Staff login management: last_login now tracked

`last_login` column added to `users` table (migration `f1g2h3i4j5k6`). `AuthService.login()` updates it on every successful login. `UserOut` exposes it. `StaffDetailScreen` Login Account card displays last login with human-readable relative format ("Today HH:MM", "Yesterday", "N days ago").

---

### [KNOWN GAP] Existing societies missing Manager/Gym Trainer roles and default designations

Societies registered before 2026-06-12 do not have 'Manager' or 'Gym Trainer' roles in their role table, and have no default designations or shifts. Admin must manually create them via the API or a one-time migration script. New registrations are fully seeded from this date onward.

---

### [KNOWN GAP] Admin/Committee/Security dashboards show partial static values

Manager and Supervisor dashboards use 100% live data for staff-related cards. Admin, Committee, and Security dashboards show live data for staff count but still show `--` for flats occupied, resident count, and visitor count — those modules need their own summary endpoints wired up. Hardcoded fake panel content has been removed (replaced with instructional guidance).

### [KNOWN GAP] SecurityDashboardScreen unreachable in current 11-role system

The `/security` route exists but no current role lands there. `Security Supervisor` routes to `/supervisor` (contains 'Supervisor'), `Security Staff` routes to `/staff` (contains 'Staff'). The screen remains as a fallback for legacy or custom roles with plain 'Security' designation.

### [KNOWN GAP] Dashboard drawer is not role-scoped

All dashboards share the same `_DashboardShell` drawer which includes links to "Users & Roles" and "Society Settings". These links are visible to all roles including Staff and Resident. The backend enforces permissions (403 on unauthorized access), so no data leaks occur, but low-privilege users see links that mostly fail. A future improvement should conditionally render drawer items based on role.

---

### [KNOWN GAP] Staff approval routing is role-convention, not enforced by FK

The supervisor-scoped attendance approval endpoint (`GET /staff/attendance/pending/supervisor/{society_id}?department=security`) relies on the calling user passing their own department — the backend does not re-derive the department from the authenticated token. A future improvement should extract department from the user's staff record and enforce it server-side.

### [KNOWN GAP] Complaint-to-department assignment does not auto-notify

When a manager assigns a complaint to a department via `POST /staff/complaints/assign-department`, the assigned supervisor receives no push notification. Notification infrastructure would be needed to close this gap.

### [KNOWN GAP] Manager/Supervisor dashboard approval counts are live-fetched per load

`approvalProvider` in `ManagerDashboardScreen` and `SupervisorDashboardScreen` makes individual API calls per session load. Consider WebSocket or SSE for real-time count updates in a future iteration.

## Recent Staff Workflow Update (2026-06-10)

Full staff hierarchy approval system implemented:
- Punch-in and punch-out approval with two-phase workflow
- Supervisor-scoped attendance filtering by department
- TECHNICAL and GYM departments added to enum
- Reporting Manager FK on staff records
- Complaint → department assignment by manager
- Manager Dashboard and Supervisor Dashboard screens in Flutter
- AttendanceApprovalScreen, DutyAssignScreen, StaffListScreen added

---

---

### [FIXED 2026-06-10] Society Admin receives 403 on all module APIs

**Symptom:** Staff Portal, Visitors, Complaints, and other modules showed blank screens or 403 errors when logged in as Society Admin.

**Root cause:** Every module route file (`staff.py`, `amenity.py`, `complaint.py`, etc.) defined local role aliases using abstract role names (`"Admin"`, `"Committee"`) that do not exist in the database. The actual roles stored are `"Society Admin"`, `"Committee Chairman"`, etc.

**Fix:**  
- Added canonical role sets and named guards to `backend/app/core/dependencies.py`:
  `require_admin_committee`, `require_manager_above`, `require_supervisor_above`, `require_any_staff`, `require_any_member`
- Updated all 10 module route files to import and use the canonical guards instead of local broken aliases.
- All guards explicitly include `"Society Admin"` and `"Platform Admin"`.

**Affected files:** `dependencies.py` + all module route files.

**Validation:** Society Admin can now access Staff, Attendance, Duty Assignment, Visitors, Complaints, Inventory, Parking, Billing, Vendor, Amenity, Notice, and Users & Roles without 403 errors.

---

## Resolved Issues

### [FIXED 2026-06-06] FloorForm crash — WingModel passed as Map

**Symptom:** `TypeError: Instance of 'WingModel' type 'WingModel' is not a subtype of type 'Map<String,dynamic>'` when tapping Add Floor on the Floors screen.

**Root cause:** `FloorListScreen` Add Floor button passed `extra: wing` (raw `WingModel`) to `AppRoutes.floorForm`. The GoRouter builder for that route casts `state.extra as Map<String, dynamic>`, causing a type mismatch at runtime.

**Fix:** Changed `floor_list_screen.dart` line 27:
```dart
// Before (wrong)
extra: wing,

// After (correct)
extra: {'wing': wing, 'floor': null},
```

**Affected file:** `mobile/lib/features/society_structure/presentation/screens/floor_list_screen.dart`

---

### [FIXED 2026-06-06] GET /api/v1/societies/ → 500 Internal Server Error

**Symptom:** Society Settings screen showed no data; browser console reported CORS error (misleading).

**Root cause:** `SocietyOut.trial_start_date: Optional[str]` but SQLAlchemy returns `datetime.date` objects. Pydantic v2 in strict mode raises `ValidationError` → FastAPI returns 500 before setting CORS headers.

**Fix:** Changed `backend/app/schemas/society.py` field types from `Optional[str]` to `Optional[date]`.

---

### [FIXED 2026-06-06] Flutter login fails after successful API response

**Symptom:** API returns 200 with tokens; Flutter logs `[LOGIN_ERROR] Unexpected: OperationError`.

**Root cause (1):** `flutter_secure_storage` throws `OperationError` on Chrome localhost via Web Crypto AES-GCM. Token save appeared to succeed but read-back failed.

**Root cause (2):** GoRouter was recreated on every `authProvider` state change (because `appRouterProvider` used `ref.watch(authProvider)`), resetting the nav stack to splash during login.

**Fix:** Platform-aware token storage (`SharedPreferences` on web via `kIsWeb`); single GoRouter instance with `refreshListenable: _RouterNotifier`.

---

### [FIXED 2026-06-06] Users & Roles screen showing users from ALL societies

**Symptom:** Admin of Society A could see users from Society B.

**Root cause:** `users` table had no `society_id` column. All user queries were unscoped.

**Fix:** Added `society_id` FK to `users` table (migration `b1c2d3e4f5a6`); all repository/service/route methods scoped by `society_id` extracted from the authenticated admin's token.
