# Changelog — AR Society ERP

Format: `[YYYY-MM-DD] type: description`

---

## 2026-06-12

### feat: finalize staff management module

**Routing (critical fix)**
- `_userRoleHome` now routes based on actual role strings rather than
  the simplified `primaryRole` computed property.
  - Manager → `/manager` (was landing on Resident dashboard)
  - Security/Housekeeping/Technical Supervisor → `/supervisor` (was going to Security or Staff)
  - Security Staff → `/staff` (was going to Security dashboard)
  - Gym Trainer → `/staff` (was landing on Resident dashboard)

**Flutter**
- Removed all `print('[STARTUP]...')` and `print('[THEME]...')` debug calls
- `StaffListScreen`: "Add Staff" FAB hidden for non-admin/committee users (prevents 403)
- `StaffAddScreen`: replaced broken fallback designation dropdown (no-op `onChanged`)
  with a clear "No designations configured" message; also auto-loads staff list on
  init so the Reporting Manager dropdown is populated without first visiting StaffList
- `AttendanceApprovalScreen`: shows staff full name instead of truncated UUID

**Backend**
- `StaffAttendance` model: added `staff_name` computed property (reads from relationship)
- `AttendanceOut` schema: added `staff_name: Optional[str]` field
- Onboarding: added `Manager` and `Gym Trainer` to `EXTENDED_DEFAULT_ROLES` (were missing)
- Onboarding: new societies automatically get 7 default designations + 3 default shifts
  (Morning 06:00–14:00, Afternoon 14:00–22:00, Night 22:00–06:00)

---

## 2026-06-06

### fix: resolve WingModel floor creation serialization issue

- **File:** `mobile/lib/features/society_structure/presentation/screens/floor_list_screen.dart`
- **Change:** Add Floor button now passes `extra: {'wing': wing, 'floor': null}` instead of `extra: wing` to match the GoRouter `floorForm` builder contract (`Map<String, dynamic>`).
- **Impact:** Eliminates `TypeError: Instance of 'WingModel' is not a subtype of type 'Map<String,dynamic>'` crash on the Floors screen.

### fix: resolve Flutter web registration connectivity issue

- Token storage is now platform-aware: `SharedPreferences` (localStorage) on web, `FlutterSecureStorage` on native, via `kIsWeb` guard in `token_storage.dart`.
- Fixes `OperationError` from Web Crypto AES-GCM on Chrome localhost.

### fix: resolve Flutter startup asset and env configuration issues

- GoRouter now created once via `_RouterNotifier + refreshListenable`; no longer recreated on auth state changes.
- `AuthLoading` state no longer redirects to splash (allows login to complete without nav stack reset).

### fix: resolve onboarding user authentication issue

- `RegistrationResult` and `TrialSuccessScreen` updated to show all 9 onboarding credentials, Society Code badge, Copy All, Sign in as Admin button.

### fix: parse roles from flat API list instead of nested user_roles

- `UserOut.from_orm_with_roles()` reads roles from `user.user_roles` relationship.
- `GET /users/` now returns only users belonging to the authenticated admin's society.

### security: enforce multi-tenant user isolation

- Added `society_id` FK to `users` table via Alembic migration `b1c2d3e4f5a6`.
- All user repository/service/route methods now filter by `society_id`.
- Backfill migration assigns `society_id` to existing users via email domain pattern matching.

### fix: GET /api/v1/societies/ 500 Internal Server Error

- Changed `SocietyOut.trial_start_date` and `trial_end_date` from `Optional[str]` to `Optional[date]` in `backend/app/schemas/society.py`.
- Root cause: Pydantic v2 does not coerce `datetime.date` → `str` in lax mode; FastAPI 500 before CORS headers made it appear as a CORS error.

---

## 2026-06-10 (Railway Frontend Deployment Prep)

### docs: prepare railway frontend deployment

**Flutter web build verified** — `flutter build web --release` and `flutter build web --release --dart-define=API_BASE_URL=... --dart-define=APP_ENV=production` both pass cleanly (Flutter 3.41.7).

**New files**
- `mobile/Dockerfile` — Multi-stage build: Flutter builder (ghcr.io/cirruslabs/flutter:stable) → Nginx 1.27 Alpine runtime
- `mobile/nginx.conf` — SPA routing with gzip, asset caching, index.html fallback for GoRouter
- `mobile/railway.json` — Railway service config for frontend (Docker builder, health check `/`)

**Updated files**
- `mobile/lib/core/config/env.dart` — Added `--dart-define` priority: compile-time constants checked first, `.env` fallback second, hard-coded fallback third
- `mobile/lib/main.dart` — `.env` load wrapped in `catchError` — silent no-op if file missing (production builds bake URL via `--dart-define`)
- `docs/DEPLOYMENT.md` — Full two-service Railway architecture, step-by-step deploy guide, local dev override instructions, troubleshooting

**Architecture**
```
Service 1 — Backend: root / → Nixpacks → FastAPI
Service 2 — Frontend: root /mobile → Docker → Flutter Web + Nginx
```

**Not yet deployed** — Railway service setup is manual (create new service, set root dir `/mobile`).

---

## 2026-06-10 (RBAC Fix)

### fix: implement role hierarchy and society admin permissions

**Root Cause**
Every module route file defined local role aliases using abstract names (`"Admin"`, `"Committee"`, `"Staff"`) that do not exist in the database. The actual DB roles are `"Society Admin"`, `"Committee Chairman"`, etc. This caused 403 Forbidden for Society Admin on all module endpoints.

**Backend — `backend/app/core/dependencies.py`**
- Added canonical role sets matching `EXTENDED_DEFAULT_ROLES` in onboarding:
  `_ROLES_PLATFORM`, `_ROLES_SOCIETY`, `_ROLES_COMMITTEE`, `_ROLES_MANAGER`, `_ROLES_SUPERVISORS`, `_ROLES_STAFF`, `_ROLES_RESIDENTS`
- Added hierarchy guards: `require_admin_committee`, `require_manager_above`, `require_supervisor_above`, `require_any_staff`, `require_security`, `require_any_member`
- Kept backwards-compatible aliases: `require_committee`, `require_resident`, `require_staff`

**Backend — All Module Routes (10 files updated)**
Replaced broken local role aliases with imports from `dependencies.py`:
- `staff/routes/staff.py` — `admin_or_committee`, `supervisor_above`, `any_auth`, `manager_or_above`
- `staff/routes/handover.py` — `admin_committee`, `supervisor_above`, `any_staff`
- `amenity/routes/amenity.py` — `committee_or_admin`, `any_member`
- `notice/routes/notice.py` — `admin_committee`, `any_member`
- `complaint/routes/complaint.py` — `staff_or_above`, `committee_or_admin`, `any_member`
- `visitor/routes/visitor.py` — `security_or_admin`, `resident_or_above`, inline `require_roles()` calls
- `inventory/routes/inventory.py` — `admin_or_committee`, `staff_above`, `any_auth`
- `parking/routes/parking.py` — `admin_committee`, `security_above`, `any_member`
- `billing/routes/billing.py` — `admin_committee`, `any_member`
- `vendor/routes/vendor.py` — `admin_committee`, `staff_above`, `any_member`
- `onboarding/routes/onboarding.py` — `admin_or_committee`
- `api/routes/vehicle.py`, `occupancy.py`, `payroll_readiness.py`, `workload.py`

**Flutter — Improved State Handling**
- `StaffListError` now carries `statusCode` field
- `StaffListScreen`: 403 → shows `_AccessDeniedWidget` (lock icon, "Access Denied" message, Retry button); `_ initial` → shows spinner instead of blank
- `AttendanceApprovalScreen`: `ApprovalInitial` and `ApprovalError` now show visible UI; Retry button added

**Validation**
- Society Admin: no more 403 on Staff, Attendance, Duty, Visitors, Complaints, Inventory, Parking, Billing, Vendor, Amenity, Notice
- Multi-tenant isolation unchanged — all queries still filter by `society_id`

---

## 2026-06-10 (Staff Master)

### feat: implement staff master and reporting hierarchy

**Backend**
- Added `designation_name` and `reporting_manager_name` as `@property` on `Staff` ORM model (reads from loaded relationships)
- Added `designation_name: Optional[str] = None` and `reporting_manager_name: Optional[str] = None` to `StaffOut` schema — these are now returned in every staff API response

**Flutter — New Screens**
- `StaffAddScreen` (`/staff/add`) — full form: full name, mobile, email, department (dropdown), designation (filtered by dept), shift, joining date picker, reporting manager dropdown; calls `POST /staff/`
- `StaffDetailScreen` (`/staff/:staffId/detail`) — read-only record view with employment, reporting, and contact sections; Edit button navigates to edit screen
- `StaffEditScreen` (`/staff/:staffId/edit`) — pre-filled edit form for all fields including status and deactivate shortcut; calls `PATCH /staff/{id}`

**Flutter — Updated**
- `StaffListScreen` — added FAB (Add Staff → `/staff/add`); cards are now tappable → detail screen; cards show `designationName` and `reportingManagerName` inline
- `StaffEntity` — added `designationId`, `designationName`, `reportingManagerName`
- `StaffModel.fromJson` — parses `designation_id`, `designation_name`, `reporting_manager_name` from API
- Added `DesignationEntity`, `ShiftEntity`, `DesignationModel`, `ShiftModel`
- `StaffRemoteDataSource` — added `createStaff`, `updateStaff`, `listDesignations`, `listShifts`; removed duplicate `getStaff`/`getStaffByUser` stubs
- `StaffRepository` — added `createStaff`, `updateStaff`, `listDesignations`, `listShifts`
- `staff_providers.dart` — added `designationsProvider`, `shiftsProvider`, `StaffFormNotifier`, `staffFormProvider`
- `app_router.dart` — added routes `/staff/add`, `/staff/:staffId/detail`, `/staff/:staffId/edit`; added route constants `staffAdd`, `staffDetail`, `staffEdit`

---

## 2026-06-10

### feat: complete staff management workflow and approval hierarchy

**Backend — Migration `d1e2f3a4b5c6_staff_hierarchy_checkout_approval`**
- Added `staff.reporting_manager_id` (UUID FK → users) to model, schema, and migration
- Added `TECHNICAL` and `GYM` to `staffdepartment` PostgreSQL enum via `ALTER TYPE ... ADD VALUE IF NOT EXISTS`
- Added punch-out approval columns to `staff_attendance`: `is_checkout_approved`, `checkout_approved_by`, `checkout_approved_at`, `checkout_approval_notes`
- Added `complaints.assigned_department` (String) and `complaints.assigned_by` (UUID FK → users)

**Backend — New API Endpoints**
- `POST /staff/attendance/{id}/approve-checkout` — approves punch-out; restricted to Admin/Committee/Manager
- `GET /staff/attendance/pending/supervisor/{society_id}?department=` — supervisor-scoped pending punch-in list
- `GET /staff/attendance/pending-checkout/{society_id}?department=` — supervisor-scoped pending punch-out list
- `GET /staff/society/{society_id}/summary?att_date=` — daily attendance summary (total/present/absent/pending + dept breakdown)
- `POST /staff/complaints/assign-department` — manager assigns open complaint to security/housekeeping/technical
- `GET /staff/complaints/department/{society_id}?department=` — supervisor views complaints assigned to their department

**Backend — Model Changes**
- `Staff.user` relationship now declares `foreign_keys=[user_id]` to avoid SQLAlchemy ambiguity after adding `reporting_manager` relationship
- `Staff.reporting_manager` relationship added with `foreign_keys=[reporting_manager_id]`
- `StaffAttendance.approver` and `StaffAttendance.checkout_approver` relationships added

**Flutter — New Screens**
- `AttendanceApprovalScreen` (`/staff/approvals`) — tabbed punch-in / punch-out approval list for supervisors and managers
- `DutyAssignScreen` (`/staff/assign-duty`) — duty assignment form with predefined location options per department
- `StaffListScreen` (`/staff/list`) — searchable, filterable staff roster with quick duty-assign shortcut

**Flutter — New Providers**
- `staffListProvider` (`StaffListNotifier`) — loads and caches staff list per society with optional department filter
- `approvalProvider` (`ApprovalNotifier`) — loads pending check-in and check-out lists; exposes `approveCheckin`, `approveCheckout`, `clearStatus` actions
- `dutyAssignProvider` (`DutyAssignNotifier`) — wraps duty assignment with `assign` and `reset` actions

**Flutter — Updated Screens**
- `StaffHomeScreen` — added Management section (Approvals, My Staff, Assign Duty, Complaints) visible to supervisors and managers
- `ManagerDashboardScreen` — live approval counts, quick actions, department-status panel
- `SupervisorDashboardScreen` — dept-scoped approval counts, gym trainer panel for housekeeping supervisors

**Flutter — Router**
- New routes: `/staff/approvals`, `/staff/assign-duty`, `/staff/list`, `/manager`, `/supervisor`
- `_roleHome` updated: Manager → `/manager`, Security/Housekeeping Supervisor → `/supervisor`

**Impact:** Staff management module reaches 100% feature coverage against the specified hierarchy, approval matrix, attendance workflow, and duty assignment rules.

---

## 2026-06-08

### feat: implement staff attendance approval workflow

- **Files:** `backend/app/modules/staff/routes/staff.py`, `backend/app/modules/staff/services/staff_service.py`, `backend/app/modules/staff/models/staff.py`, `backend/tests/staff/test_attendance.py`
- **Change:** Added pending attendance approval listing plus supervisor/committee approval support for staff attendance records.
- **Impact:** Completes the first operational approval step in the staff management workflow and adds regression coverage for the new path.

### feat: redesign dashboard with operational summary cards

- **File:** `mobile/lib/features/dashboard/role_dashboards.dart`
- **Change:** Reworked the dashboard from large module tiles into a compact operational layout with:
  - welcome card showing society name, user name, role, and current date
  - responsive summary cards for occupancy, residents, staff, visitors, complaints, approvals, and notices
  - operational panels for complaints, visitors, and staff duty
  - compact quick actions for frequent tasks
  - drawer-based navigation instead of menu-style landing tiles
- **Impact:** Better mobile and web responsiveness, cleaner operational dashboard, and role-aware overview screens for admins, committee, security, and residents.

## Earlier (pre-2026-06-06)

See git log: `git log --oneline` for full history of module builds (amenity, billing, complaint, inventory, notice, parking, staff, vendor, visitor, society structure, onboarding, auth).
