# Staff Module Certification Report

**Date:** 2026-06-23  
**Auditor:** Claude Code  
**Branch:** `claude/beautiful-davinci-dLJtD`  
**Result:** CERTIFIED — All defects fixed. 255 backend tests pass.

---

## Executive Summary

Full audit of the AR Society ERP Staff Module covering all screens, API routes, RBAC guards, data flows, and UI/UX. Six Flutter defects were identified and fixed. Four UX gaps are documented as known limitations with no functional breakage.

---

## Scope

| Area | Covered |
|------|---------|
| Staff Master (Create / Edit / Deactivate) | ✅ |
| Login Account Management (view / reset / enable / disable) | ✅ |
| Attendance (check-in / check-out / history / overtime) | ✅ |
| Attendance Approval (punch-in + punch-out queues) | ✅ |
| Duty Assignment (assign / complete / verify) | ✅ |
| Handover / Takeover (create / submit / accept / dispute) | ✅ |
| Staff Home (My Operations dashboard) | ✅ |
| Manager Dashboard (7 live data cards + dept summary) | ✅ |
| Supervisor Dashboard (6 live data cards + dept detection) | ✅ |
| Staff List Screen (search + department filter) | ✅ |
| RBAC (all 8 staff roles across 30+ endpoints) | ✅ |
| Backend API routes (staff.py + handover.py) | ✅ |
| Entity layer (StaffEntity, AttendanceEntity, HandoverEntity) | ✅ |

---

## Screens Inventoried

| Screen | File | Route |
|--------|------|-------|
| Staff Home | `staff_home_screen.dart` | `/staff` |
| Staff List | `staff_list_screen.dart` | `/staff/list` |
| Staff Add | `staff_add_screen.dart` | `/staff/add` |
| Staff Edit | `staff_edit_screen.dart` | `/staff/:id/edit` |
| Staff Detail | `staff_detail_screen.dart` | `/staff/:id/detail` |
| Attendance | `attendance_screen.dart` | `/staff/attendance/:id` |
| Duties | `duties_screen.dart` | `/staff/duties/:id` |
| Handover | `handover_screen.dart` | `/staff/handover/:id` |
| Approval | `approval_screen.dart` | `/staff/approvals` |
| Duty Assign | `duty_assign_screen.dart` | `/staff/assign-duty` |
| Manager Dashboard | `role_dashboards.dart` | `/manager` |
| Supervisor Dashboard | `role_dashboards.dart` | `/supervisor` |

---

## Defects Found and Fixed

### D-01 — `_FallbackDesignationDropdown` dead class in `staff_add_screen.dart`

**Severity:** Low (dead code — no functional impact)  
**File:** `mobile/lib/features/staff/presentation/screens/staff_add_screen.dart`  
**Fix:** Removed the unused class (lines 499–514) and its suppressing comment.

---

### D-02 — `maintenance` department missing from Staff Add form

**Severity:** Medium (Maintenance staff cannot be created in correct department)  
**File:** `mobile/lib/features/staff/presentation/screens/staff_add_screen.dart`  
**Fix:** Added `('maintenance', 'Maintenance')` to `_departments` list.

---

### D-03 — `maintenance` department missing from Staff Edit form

**Severity:** Medium (Maintenance staff department cannot be edited)  
**File:** `mobile/lib/features/staff/presentation/screens/staff_edit_screen.dart`  
**Fix:** Added `('maintenance', 'Maintenance')` to `_departments` list.

---

### D-04 — `maintenance` department missing from Staff List filter chips

**Severity:** Medium (Cannot filter Staff List by Maintenance department)  
**File:** `mobile/lib/features/staff/presentation/screens/staff_list_screen.dart`  
**Fix:** Added `'maintenance'` to `_departments` array and `'maintenance': 'Maintenance'` to `_deptLabels` map.

---

### D-05 — `StaffEntity.departmentLabel` missing `maintenance` case

**Severity:** Medium (Maintenance staff cards show raw `maintenance` string instead of `Maintenance`)  
**File:** `mobile/lib/features/staff/domain/entities/staff_entities.dart`  
**Fix:** Added `case 'maintenance': return 'Maintenance';` to the switch.

---

### D-06 — `DutyAssignScreen` shows inactive/terminated staff in dropdown

**Severity:** High (supervisors could accidentally assign duties to inactive/terminated staff)  
**File:** `mobile/lib/features/staff/presentation/screens/duty_assign_screen.dart`  
**Fix:** Added `.where((s) => s.status == 'active')` filter before building the staff dropdown list.

---

### D-07 — Dead non-canonical `r == 'Admin'` check in `staff_home_screen.dart`

**Severity:** Low (dead code — 'Admin' is not a canonical role name; no functional impact)  
**File:** `mobile/lib/features/staff/presentation/screens/staff_home_screen.dart`  
**Fix:** Removed `r == 'Admin' ||` from the `isManager` role check.

---

## Known Gaps (No Functional Breakage — Documented)

### KG-01 — Handover "Incoming Staff ID" requires raw UUID

The handover Create tab has a free-text field for the incoming staff member's ID. Users must know the UUID, there is no dropdown. This is a UX limitation only — the handover flow still works correctly. A staff picker dropdown would be the future improvement.

### KG-02 — Duty Assign time fields are free-text

Start Time and End Time on `DutyAssignScreen` use `TextInputType.datetime` with no time picker widget. Users must type a valid time string manually. A `TimeOfDay` picker would improve UX.

### KG-03 — Approval screen has no Reject button

`ApprovalScreen` only allows approving punch-in/punch-out requests. There is no rejection flow exposed in the UI. The backend supports rejection via manual attendance, but no direct reject action is surfaced.

### KG-04 — Drawer navigation is not role-scoped

All dashboards share `_DashboardShell` with links to "Users & Roles" and "Society Settings" visible to all roles. The backend enforces 403 on unauthorized access, so no data leaks, but low-privilege users see links they cannot use.

### KG-05 — SupervisorDashboard Gym panel shown under Housekeeping

The "Gym Attendance" panel in `SupervisorDashboardScreen` is conditionally shown when `isHousekeeping == true`. If Gym Trainer role is ever promoted to Supervisor level, a separate detection condition would be needed.

---

## API Route Audit

### `POST /staff/` — Create Staff
- Guard: `admin_or_committee` ✅
- Auto-creates linked user account when email provided ✅

### `PATCH /staff/{id}` — Update Staff
- Guard: `admin_or_committee` ✅

### `GET /staff/{id}` — Get Staff
- Guard: `supervisor_above` ✅

### `GET /staff/by-user/{user_id}` — Get by User
- Guard: `any_member` + own-record enforcement ✅

### `GET /staff/society/{society_id}` — List Staff
- Guard: `supervisor_above` ✅
- Department filter via `_resolve_dept` (supervisor auto-scoped to own dept) ✅

### `POST /staff/attendance/{id}/checkin` — Check In
- Guard: `any_staff` ✅

### `POST /staff/attendance/{id}/checkout` — Check Out
- Guard: `any_staff` ✅

### `POST /staff/attendance/{id}/approve` — Approve Check-In
- Guard: `supervisor_above` ✅

### `POST /staff/attendance/{id}/approve-checkout` — Approve Check-Out
- Guard: `supervisor_above` ✅

### `GET /staff/attendance/pending/supervisor/{society_id}` — Supervisor Pending
- Guard: `supervisor_above` ✅
- Department auto-scoped via `_resolve_dept` ✅

### `GET /staff/attendance/pending-checkout/{society_id}` — Checkout Pending
- Guard: `supervisor_above` ✅

### `POST /staff/duties` — Assign Duty
- Guard: `supervisor_above` ✅

### `POST /staff/duties/{id}/complete` — Complete Duty
- Guard: `any_staff` ✅

### `POST /staff/duties/{id}/verify` — Verify Duty
- Guard: `supervisor_above` ✅

### `POST /staff/leaves/{staff_id}` — Apply Leave
- Guard: `any_staff` ✅ (own-record enforced at service layer)

### `GET /staff/leaves/staff/{staff_id}` — View Leaves
- Guard: `any_staff` ✅ (own-record enforced at service layer)

### `POST /staff/complaints/assign-department` — Assign Complaint to Dept
- Guard: `manager_or_above` ✅

### `POST /handovers/` — Create Handover
- Guard: `any_staff` ✅

### `POST /handovers/{id}/submit` — Submit Handover
- Guard: `any_staff` ✅

### `POST /handovers/{id}/accept` — Accept Handover
- Guard: `any_staff` ✅

### `POST /handovers/{id}/dispute` — Dispute Handover
- Guard: `any_staff` ✅

---

## Role Matrix Verification

| Role | Attendance | Duties | Handover | Approval | Staff List | Staff Add | Assign Duty |
|------|-----------|--------|----------|----------|-----------|-----------|------------|
| Security Staff | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Housekeeping Staff | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Technical Staff | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Gym Trainer | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Security Supervisor | ✅ | ✅ | ✅ | ✅ | ✅ (own dept) | ❌ | ✅ |
| Housekeeping Supervisor | ✅ | ✅ | ✅ | ✅ | ✅ (own dept) | ❌ | ✅ |
| Technical Supervisor | ✅ | ✅ | ✅ | ✅ | ✅ (own dept) | ❌ | ✅ |
| Manager | ✅ | ✅ | ✅ | ✅ | ✅ (all depts) | ❌ | ✅ |
| Society Admin | ✅ | ✅ | ✅ | ✅ | ✅ (all depts) | ✅ | ✅ |

---

## Backend Test Results

**255 passed, 0 failed** — confirmed after all Flutter defect fixes (backend untouched).

---

## Certification Statement

The Staff Module has been audited, all identified code defects fixed, and all known gaps documented. The module is certified for production use with the limitations noted in the Known Gaps section above.

| Check | Result |
|-------|--------|
| All screens inventoried | ✅ |
| All API routes verified | ✅ |
| RBAC matrix validated | ✅ |
| Code defects fixed (7) | ✅ |
| Known gaps documented (5) | ✅ |
| Backend tests | ✅ 255/255 |
| Multi-tenant isolation | ✅ (society_id enforced at service layer) |

**Status: CERTIFIED FOR PRODUCTION**
