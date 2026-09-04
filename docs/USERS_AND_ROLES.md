# Users and Roles — AR Society ERP

Last updated: 2026-09-04

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

### Dynamic Permission Matrix

Role → access-tier grants are no longer hardcoded. They live in the
`permissions` / `role_permissions` tables and can be edited by a Society
Admin at runtime via **Permission Matrix** (drawer menu, Admin only) or the
`GET/PUT /api/v1/roles/permission-matrix` and
`PUT /api/v1/roles/{role_id}/permissions` endpoints. A toggle takes effect
on the very next request — no deploy or app update needed.

The default seed (applied by the `permission_matrix` Alembic migration, and
auto-granted to any newly created Role via the `Role.after_insert` listener
in `backend/app/core/rbac_seed.py`) reproduces the table below exactly, so
this section still describes the out-of-the-box behavior.

### Backend Dependency Guards

Defined in `backend/app/core/dependencies.py`. Each guard is a thin wrapper
around `require_permission("<tier code>")`, which checks the current
user's roles against the `role_permissions` table:

| Guard | Permission code | Allowed Roles (default) |
|-------|-----------------|--------------------------|
| `require_admin` | `admin` | Platform Admin, Society Admin |
| `require_admin_committee` | `admin_committee` | Platform Admin, Society Admin, all Committee roles |
| `require_manager_above` | `manager_above` | + Manager |
| `require_supervisor_above` | `supervisor_above` | + Security/Housekeeping/Technical Supervisor |
| `require_any_staff` | `any_staff` | + Security/Housekeeping/Technical Staff, Gym Trainer |
| `require_any_member` | `any_member` | + Resident, Tenant |
| `require_security` | `security` | Platform Admin, Society Admin, Committee, Manager, Security Supervisor, Security Staff |

`require_platform_admin` is unaffected by the matrix — it checks the
`is_superadmin` boolean flag on the user record directly, not a role grant.

### Dynamic Forms Matrix (navigation)

A second, independent matrix controls which top-level mobile screens
(drawer items) each role can see — separate from the permission tiers
above, which gate backend API access. It lives in the `forms` /
`role_forms` tables, editable via **Forms Matrix** (drawer menu, Admin
only) or `GET/PUT /api/v1/roles/form-matrix` and
`PUT /api/v1/roles/{role_id}/forms`. On login the mobile app calls
`GET /api/v1/roles/forms/mine` and renders the drawer purely from the
returned form codes — no role-name checks are hardcoded client-side
anymore. As with the Permission Matrix, the default seed (the
`forms_matrix` Alembic migration, auto-granted to new roles via the same
`Role.after_insert` listener) reproduces the pre-existing drawer behavior
exactly:

| Form code | Screen | Default roles |
|-----------|--------|----------------|
| `residents` | Residents | Society Admin, all Committee roles |
| `tenants` | Tenants | Society Admin, all Committee roles |
| `users_roles` | Users & Roles | Society Admin |
| `permission_matrix` | Permission Matrix | Society Admin |
| `forms_matrix` | Forms Matrix | Society Admin |
| `society_settings` | Society Settings | Society Admin, all Committee roles |
| `visitors` | Visitors | Everyone |
| `complaints` | Complaints | Everyone |
| `edit_my_info` | Edit My Info | Resident |
| `pending_resident_changes` | Pending Resident Changes | Society Admin, all Committee roles |
| `staff` | Staff | Society Admin, Committee, Security/Housekeeping/Technical Supervisor, Security/Housekeeping/Technical Staff |
| `parking_management` | Parking Management | Society Admin, all Committee roles |
| `setup_wizard` | Setup Wizard | Society Admin, all Committee roles |

Note: this reproduces the *exact* pre-existing drawer logic, gaps
included — Platform Admin, Manager, Gym Trainer, and Tenant only ever saw
the two unconditional items (Visitors, Complaints) before this matrix
existed, since none of them matched the old Dart `isAdmin`/`isStaff`
string checks. An Admin can now close those gaps from the Forms Matrix
screen without a code change.

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
