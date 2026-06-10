# Users and Roles — AR Society ERP

Last updated: 2026-06-10

---

## Role Hierarchy

```
Platform Admin
    │
    └── Society Admin  (full access within own society)
            │
            ├── Committee Chairman
            ├── Committee Secretary
            ├── Committee Treasurer
            └── Committee Member
                    │
                    └── Manager
                            │
                        ┌───┴───────────────────┐
                Security Supervisor    Housekeeping Supervisor
                        │                       │
                Security Staff          Housekeeping Staff
                                         Gym Trainer
                        Technical Staff (reports to Manager)
```

---

## Role Definitions

| Role | DB Name | Scope |
|------|---------|-------|
| Platform Admin | `Platform Admin` | Cross-society, internal use only |
| Society Admin | `Society Admin` | Full access within own society |
| Committee Chairman | `Committee Chairman` | Society governance |
| Committee Secretary | `Committee Secretary` | Records, notices |
| Committee Treasurer | `Committee Treasurer` | Finance, billing |
| Committee Member | `Committee Member` | General committee |
| Manager | `Manager` | Approves supervisors, assigns duties |
| Security Supervisor | `Security Supervisor` | Security dept head |
| Housekeeping Supervisor | `Housekeeping Supervisor` | Housekeeping + Gym dept head |
| Technical Supervisor | `Technical Supervisor` | Technical dept head |
| Security Staff | `Security Staff` | Gate operations |
| Housekeeping Staff | `Housekeeping Staff` | Cleaning operations |
| Technical Staff | `Technical Staff` | Maintenance work |
| Gym Trainer | `Gym Trainer` | Gym operations |
| Resident | `Resident` | Flat owner / permanent occupant |
| Tenant | `Tenant` | Rented flat occupant |

---

## Permission Matrix

`✅` = Full access · `👁` = View only · `🔒` = Own records only · `❌` = No access

### Core Modules

| Module | Platform Admin | Society Admin | Committee | Manager | Supervisor | Staff | Resident/Tenant |
|--------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Society Settings | ✅ | ✅ | 👁 | ❌ | ❌ | ❌ | ❌ |
| Society Structure (Wings/Floors/Flats) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Users & Roles | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Visitors (create entry) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Visitors (approve) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | 🔒 |
| Visitors (list all) | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | 🔒 |
| Complaints (create) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Complaints (assign/manage) | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Complaints (dept assignment) | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Notices (create) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Notices (view) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Billing (manage) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Billing (view own) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 🔒 |
| Parking (manage zones/slots) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Parking (log entry/exit) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Inventory (manage) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Inventory (view/issue) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Amenities (manage) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Amenities (book) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Vendors (manage) | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |

### Staff Module

| Action | Platform Admin | Society Admin | Committee | Manager | Supervisor | Staff |
|--------|:-:|:-:|:-:|:-:|:-:|:-:|
| Create/edit staff record | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| View staff list | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Punch in/out (own) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Approve punch-in | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Approve punch-out | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Assign duties | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| View own duties | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Shift handover | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Payroll management | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |

---

## Approval Chain

### Punch-In Approvals

| Staff Member | Approved By |
|---|---|
| Security Staff | Security Supervisor |
| Housekeeping Staff | Housekeeping Supervisor |
| Gym Trainer | Housekeeping Supervisor |
| Technical Staff | Manager |
| Security Supervisor | Manager |
| Housekeeping Supervisor | Manager |
| Technical Supervisor | Manager |
| Manager | Committee Member / Chairman |

### Punch-Out Approvals

Same routing as punch-in above.

---

## RBAC Implementation

### Backend Dependency Guards

Defined in `backend/app/core/dependencies.py`:

| Guard | Allowed Roles |
|-------|--------------|
| `require_admin` | Platform Admin, Society Admin |
| `require_admin_committee` | Platform Admin, Society Admin, all Committee roles |
| `require_manager_above` | + Manager |
| `require_supervisor_above` | + Security/Housekeeping/Technical Supervisor |
| `require_any_staff` | + Security/Housekeeping/Technical Staff, Gym Trainer |
| `require_any_member` | + Resident, Tenant |
| `require_security` | Platform Admin, Society Admin, Committee, Manager, Security Supervisor, Security Staff |

### Multi-Tenant Isolation

- Every endpoint enforces `society_id` scoping from the authenticated user's token.
- Society Admin A **cannot** access Society B data.
- All repository queries filter by `society_id`.

---

## Default Users Created on Society Registration

| User | Role | Email Pattern |
|------|------|--------------|
| Society Admin | `Society Admin` | admin@{society_code}.com |
| Committee Chairman | `Committee Chairman` | chairman@{society_code}.com |
| Committee Secretary | `Committee Secretary` | secretary@{society_code}.com |
| Committee Treasurer | `Committee Treasurer` | treasurer@{society_code}.com |

All default users have `must_change_password = true` and `terms_accepted = false` on first login.

---

## Role Routing (Flutter)

| Primary Role | Home Screen |
|---|---|
| Admin / Society Admin / Super Admin | `/admin` (AdminDashboardScreen) |
| Committee (any) | `/committee` (CommitteeDashboardScreen) |
| Manager | `/manager` (ManagerDashboardScreen) |
| Security Supervisor / Housekeeping Supervisor | `/supervisor` (SupervisorDashboardScreen) |
| Security Staff / Housekeeping Staff / Technical Staff | `/staff` (StaffHomeScreen) |
| Resident / Tenant | `/resident` (ResidentDashboardScreen) |
