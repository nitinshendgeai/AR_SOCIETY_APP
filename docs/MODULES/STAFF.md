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

## Workload Analytics
```
GET /workload/society/{id}/summary   → present/absent, pending tasks, leave queue
GET /workload/staff/{id}/summary     → monthly attendance, overtime, active tasks
```
