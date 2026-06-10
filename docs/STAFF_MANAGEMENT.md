# Staff Management — Workflow and Approval Matrix

Last updated: 2026-06-10

---

## Hierarchy

```
Committee Members (Chairman / Secretary / Treasurer)
        │ approve
        ▼
      Manager
        │ approves
        ├──────────────────────────────────────┐
        ▼                                      ▼
Security Supervisor              Housekeeping Supervisor
        │ approves                      │ approves
        ▼                               ├──────────────┐
  Security Staff               Housekeeping Staff   Gym Trainer
                                                (also approved by Housekeeping Supervisor)

Technical Staff → reports directly to Manager
```

---

## Staff Master Fields

| Field | Type |
|-------|------|
| Employee Code | Auto-generated (EMP-0001) |
| Full Name | String |
| Mobile | String |
| Email | String (optional) |
| Department | Enum |
| Designation | FK → staff_designations |
| Reporting Manager | FK → users (reporting_manager_id) |
| Joining Date | Date |
| Employment Status | active / probation / on_leave / inactive / terminated |
| Shift | FK → staff_shifts |
| Society | FK → societies (multi-tenant isolation) |

### Departments

| Code | Label |
|------|-------|
| security | Security |
| housekeeping | Housekeeping |
| technical | Technical |
| gym | Gym |
| admin | Administration |
| maintenance | Maintenance |

### Designations

- Manager
- Security Supervisor
- Security Guard
- Housekeeping Supervisor
- Housekeeping Staff
- Technical Staff
- Gym Trainer

---

## Attendance Workflow

### Punch-In Flow

```
Staff Login
    │
    ▼
Punch In → status: present, is_approved: false
    │
    ▼
Pending Approval
    │
    ├── Security Staff        → Security Supervisor approves
    ├── Housekeeping Staff    → Housekeeping Supervisor approves
    ├── Gym Trainer           → Housekeeping Supervisor approves
    ├── Technical Staff       → Manager approves
    ├── Security Supervisor   → Manager approves
    ├── Housekeeping Supervisor → Manager approves
    └── Manager               → Committee Member approves
    │
    ▼
is_approved: true, approved_by: user.id, approved_at: timestamp
```

### Punch-Out Flow

```
Staff Punch Out → check_out_time set, working_hours computed
    │
    ▼
Pending Checkout Approval
    │
    └── (Same department routing as punch-in)
    │
    ▼
is_checkout_approved: true
```

---

## Backend API Reference

### Staff CRUD
| Method | Path | Permission |
|--------|------|------------|
| POST | /staff/ | Admin, Committee |
| PATCH | /staff/{id} | Admin, Committee |
| GET | /staff/{id} | Admin, Committee |
| GET | /staff/by-user/{user_id} | Any auth |
| GET | /staff/society/{society_id} | Admin, Committee |
| GET | /staff/society/{society_id}/department/{dept} | Admin, Committee |

### Attendance
| Method | Path | Permission |
|--------|------|------------|
| POST | /staff/attendance/{id}/checkin | Staff+ |
| POST | /staff/attendance/{id}/checkout | Staff+ |
| GET | /staff/attendance/{id} | Admin, Committee |
| GET | /staff/attendance/daily/{society_id} | Admin, Committee |
| GET | /staff/attendance/pending/{society_id} | Admin, Committee |
| GET | /staff/attendance/pending/supervisor/{society_id} | Staff+ |
| GET | /staff/attendance/pending-checkout/{society_id} | Staff+ |
| POST | /staff/attendance/{id}/approve | Admin, Committee |
| POST | /staff/attendance/{id}/approve-checkout | Admin, Committee |
| GET | /staff/society/{society_id}/summary | Staff+ |

### Duties
| Method | Path | Permission |
|--------|------|------------|
| POST | /staff/duties | Admin, Committee |
| POST | /staff/duties/{id}/complete | Staff+ |
| POST | /staff/duties/{id}/verify | Admin, Committee |
| GET | /staff/duties/society/{society_id} | Admin, Committee |
| GET | /staff/duties/me/{staff_id} | Staff+ |

### Complaint Assignment (Manager → Department)
| Method | Path | Permission |
|--------|------|------------|
| POST | /staff/complaints/assign-department | Admin, Committee |
| GET | /staff/complaints/department/{society_id} | Staff+ |

### Tasks, Leaves, Handovers, Roster
See inline API documentation in `/backend/app/modules/staff/routes/staff.py`.

---

## Duty Assignment Rules

### Security Department
- Main Gate
- Visitor Gate
- Parking Gate
- Night Patrol

### Housekeeping Department
- Wing A
- Wing B
- Club House
- Garden
- Parking Area

### Technical Department
- Electrical
- Plumbing
- Lift Maintenance
- Generator Room

---

## Complaint Assignment

Manager assigns complaints to a staff department:
- `POST /staff/complaints/assign-department { complaint_id, department, notes }`
- Department values: `security`, `housekeeping`, `technical`
- Assignment is recorded on the complaint as `assigned_department`
- Supervisor can query: `GET /staff/complaints/department/{society_id}?department=security`

Statuses (complaint module): `open → assigned → in_progress → resolved → closed`

---

## Flutter Screens

| Screen | Route | Role |
|--------|-------|------|
| StaffHomeScreen | /staff | Staff, Manager, Supervisor |
| AttendanceScreen | /staff/attendance/:id | Staff |
| DutiesScreen | /staff/duties/:id | Staff |
| HandoverScreen | /staff/handover/:id | Staff |
| AttendanceApprovalScreen | /staff/approvals | Supervisor, Manager |
| DutyAssignScreen | /staff/assign-duty | Supervisor, Manager |
| StaffListScreen | /staff/list | Supervisor, Manager |
| ManagerDashboardScreen | /manager | Manager |
| SupervisorDashboardScreen | /supervisor | Security Supervisor, Housekeeping Supervisor |

---

## Manager Dashboard

Shows:
- Pending Check-in Approval count
- Pending Check-out Approval count
- Total Staff count
- Open Complaints count
- Department-wise status panel
- Quick actions: Approvals, Staff, Assign Duty, Complaints

## Supervisor Dashboard

Shows:
- Staff Present / Absent
- Pending Check-in count (dept-scoped)
- Pending Check-out count (dept-scoped)
- Quick actions: Approvals, My Team, Assign Duty, Handover
- Housekeeping Supervisor: additionally shows Gym Trainer attendance panel

---

## Multi-Tenant Security

Every staff, attendance, duty, and task record includes `society_id`.
All repository queries filter by `society_id`. No cross-society visibility is possible.

Supervisor-scoped endpoints accept an optional `department` query param. When not provided, all departments in the society are returned (manager use-case). When provided, only that department's records are returned (supervisor use-case).

---

## Database Migration

Migration: `d1e2f3a4b5c6_staff_hierarchy_checkout_approval.py`

Adds:
- `staff.reporting_manager_id` → FK to users
- `staff_department` enum values: `technical`, `gym`
- `staff_attendance.is_checkout_approved` (bool, default false)
- `staff_attendance.checkout_approved_by` (UUID FK)
- `staff_attendance.checkout_approved_at` (datetime)
- `staff_attendance.checkout_approval_notes` (text)
- `complaints.assigned_department` (string)

---

## Implementation Completeness

| Feature | Status |
|---------|--------|
| Staff CRUD | ✅ Complete |
| Employee Code auto-generation | ✅ Complete |
| Department/Designation management | ✅ Complete |
| TECHNICAL + GYM departments | ✅ Complete (migration d1e2f3a4b5c6) |
| Reporting Manager FK | ✅ Complete (migration d1e2f3a4b5c6) |
| Punch-In with pending approval | ✅ Complete |
| Punch-In approval endpoint | ✅ Complete |
| Supervisor-scoped approval endpoint | ✅ Complete |
| Punch-Out recording | ✅ Complete |
| Punch-Out approval fields | ✅ Complete (migration d1e2f3a4b5c6) |
| Punch-Out approval endpoint | ✅ Complete |
| Attendance summary endpoint | ✅ Complete |
| Duty assignment by supervisor | ✅ Complete |
| Duty completion + verification | ✅ Complete |
| Shift Handover workflow | ✅ Complete |
| Leave management | ✅ Complete |
| Task FSM | ✅ Complete |
| Roster management | ✅ Complete |
| Complaint→Department assignment | ✅ Complete |
| Flutter: Staff attendance screen | ✅ Complete |
| Flutter: Duty screen | ✅ Complete |
| Flutter: Handover screen | ✅ Complete |
| Flutter: Attendance Approval screen | ✅ Complete |
| Flutter: Duty Assign screen | ✅ Complete |
| Flutter: Staff List screen | ✅ Complete |
| Flutter: StaffHome (supervisor actions) | ✅ Complete |
| Flutter: Manager Dashboard | ✅ Complete |
| Flutter: Supervisor Dashboard | ✅ Complete |
| Multi-tenant isolation | ✅ Complete |
