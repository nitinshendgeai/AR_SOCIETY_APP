# Changelog — AR Society ERP

Format: `[YYYY-MM-DD] type: description`

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
