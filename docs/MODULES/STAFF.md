# Staff Module

## Purpose
Complete workforce operations: staff onboarding, attendance, duties, tasks, leaves, rosters, payroll readiness, and shift handover.

## Core Entities

| Entity | Table | Purpose |
|--------|-------|---------|
| Staff | `staff` | Employee master (EMP-0001, payroll fields) |
| StaffDesignation | `staff_designations` | Configurable designations |
| StaffShift | `staff_shifts` | Shift definitions (morning/afternoon/night/general) |
| DutyAssignment | `duty_assignments` | Daily duty roster with verify workflow |
| StaffAttendance | `staff_attendance` | Check-in/out with hours + overtime |
| StaffTask | `staff_tasks` | Task FSM with worklog |
| StaffLeave | `staff_leaves` | Leave request + approval |
| StaffWorkLog | `staff_work_logs` | Append-only progress updates |
| StaffRoster | `staff_rosters` | Weekly roster (DRAFT → PUBLISHED) |
| StaffLeaveBalance | `staff_leave_balances` | Annual quotas per staff |
| StaffHandover | `staff_handovers` | Shift handover FSM |
| HandoverItem | `handover_items` | Keys, tasks, incidents in handover |

## Payroll Readiness (no calculations yet)
| Entity | Table | Purpose |
|--------|-------|---------|
| StaffSalaryStructure | `staff_salary_structures` | Versioned salary breakdown |
| AttendanceCorrection | `attendance_corrections` | Correction request workflow |
| MonthlyAttendanceSummary | `monthly_attendance_summaries` | Month-end aggregation + finalize lock |

## Key Workflows

### Attendance
```
POST /staff/attendance/{staff_id}/checkin  → creates attendance record (PRESENT)
POST /staff/attendance/{staff_id}/checkout → computes working_hours, overtime_hours
```
Validations: duplicate check-in (409), checkout without checkin (404), duplicate checkout (409).

### Task FSM
```
ASSIGNED → ACKNOWLEDGED → IN_PROGRESS → COMPLETED → VERIFIED
Any → CANCELLED
```

### Leave FSM
```
PENDING → APPROVED → (auto-deducts leave balance)
        → REJECTED
```
Validation: overlapping leave (409), to_date < from_date (422).

### Handover FSM
```
DRAFT → SUBMITTED → ACCEPTED → VERIFIED → CLOSED
                  → DISPUTED → ACCEPTED
```
Requires `incoming_staff_id` before submission.

## RBAC
| Action | Roles |
|--------|-------|
| Create staff, assign duty/task | Admin, Committee |
| Check-in/out | Admin, Committee, Staff |
| Apply leave | Admin, Committee, Staff |
| Approve leave/task | Admin, Committee |
| Create/submit handover | Admin, Committee, Staff, Security |
| Verify handover | Admin, Committee, Staff |
| Workload analytics | Admin, Committee |

## Key Validations
- Duplicate check-in same day → 409
- Duplicate check-out → 409
- Overlapping leave dates → 409
- Invalid task FSM transition → 409
- Handover submission without incoming staff → 422

## Rules (forms and API)
- **Staff**: name trimmed/never blank (≤255); mobile a 10-digit Indian number and **unique among the society's active staff** (409); email checked and, when given, creates the login — an email that already has a login → 409; salary ≥ 0; joining date 1900–2100; emergency phone, address, notes and bank account checked and limited. On edit a field sent as `null` is cleared (email, emergency contact, address, notes, bank, reporting manager …); name, mobile, department and status can't be cleared. Employee codes are platform-unique: one more than the highest, never repeated.
- **Designations, shifts, checklist templates**: names trimmed, never blank, unique within the society (a designation per department, a template per department); a shift that ends before it starts must be marked overnight.
- **Duties, tasks, leaves, rosters, handovers**: names/notes limited; a leave is ≤ a year and `to ≥ from`; a roster covers at most a week; manual attendance can't be future-dated and check-out must follow check-in; a handover needs a summary, a different incoming person and a dispute reason.
- **Society scoping**: every list by `society_id` is 403 for another society's users; every record by id (staff, duty, checklist, template, task, leave, roster, handover, complaint assignment) is 404 outside the caller's society; creating in another society, or naming another society's designation/shift/manager/staff, is refused.
- **Who acts**: a plain staff member completes only their *own* duties and checklist items, updates their own tasks, and sees only their own duties, attendance, leaves and handover queue; supervisors and above act for anyone in the society. In a handover only the outgoing person submits and only the incoming person accepts or disputes (supervisors can verify).
- Fixed: roster publish and leave balance crashed (500) for a missing record — they return 404.
- App: the add/edit staff, assign-duty and edit forms validate every field (they used a lazy list that skipped fields scrolled out of view); the handover form picks the incoming person from the society's active staff instead of asking for a UUID.

## Workload Analytics
```
GET /workload/society/{id}/summary   → present/absent, pending tasks, leave queue
GET /workload/staff/{id}/summary     → monthly attendance, overtime, active tasks
```
