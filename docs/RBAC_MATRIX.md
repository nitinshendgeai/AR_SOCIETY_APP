# AR Society ERP — RBAC Matrix

## Role Definitions

| Role      | Code        | Description                                              |
|-----------|-------------|----------------------------------------------------------|
| Admin     | `Admin`     | Super access — manages societies, users, system config   |
| Committee | `Committee` | Society management, approvals, announcements             |
| Resident  | `Resident`  | View own flat, raise complaints, book amenities          |
| Security  | `Security`  | Gate management, visitor entry/exit                      |
| Staff     | `Staff`     | Maintenance, housekeeping, payroll-visible               |

## Permission Matrix

`✓` = Allowed · `✗` = Denied · `own` = Own records only

### Core Module

| Action                    | Admin | Committee | Resident | Security | Staff |
|---------------------------|-------|-----------|----------|----------|-------|
| Create Society            | ✓     | ✗         | ✗        | ✗        | ✗     |
| View Society              | ✓     | ✓         | ✓        | ✓        | ✓     |
| Update Society            | ✓     | ✓         | ✗        | ✗        | ✗     |
| Delete Society            | ✓     | ✗         | ✗        | ✗        | ✗     |
| Create Wing / Flat        | ✓     | ✗         | ✗        | ✗        | ✗     |
| View Wing / Flat          | ✓     | ✓         | ✓        | ✓        | ✓     |
| Update Wing / Flat        | ✓     | ✓         | ✗        | ✗        | ✗     |
| Delete Wing / Flat        | ✓     | ✗         | ✗        | ✗        | ✗     |
| List All Users            | ✓     | ✗         | ✗        | ✗        | ✗     |
| Assign Roles              | ✓     | ✗         | ✗        | ✗        | ✗     |
| View Own Profile          | ✓     | ✓         | ✓        | ✓        | ✓     |

### Future Modules (Planned)

| Action                    | Admin | Committee | Resident | Security | Staff |
|---------------------------|-------|-----------|----------|----------|-------|
| Visitor Check-in/out      | ✓     | ✗         | ✗        | ✓        | ✗     |
| Approve Visitor           | ✓     | ✓         | own      | ✓        | ✗     |
| Raise Complaint           | ✓     | ✓         | ✓        | ✗        | ✗     |
| Resolve Complaint         | ✓     | ✓         | ✗        | ✗        | ✓     |
| Book Amenity              | ✓     | ✓         | ✓        | ✗        | ✗     |
| Approve Amenity Booking   | ✓     | ✓         | ✗        | ✗        | ✗     |
| View Payroll              | ✓     | ✓         | ✗        | ✗        | own   |
| Manage Inventory          | ✓     | ✓         | ✗        | ✗        | ✓     |
| Finance Reports           | ✓     | ✓         | ✗        | ✗        | ✗     |
| Generate Invoices         | ✓     | ✓         | ✗        | ✗        | ✗     |

## Implementation

Guards are FastAPI `Depends` factories in `app/core/dependencies.py`:

```python
# Require Admin
@router.post("/societies/", dependencies=[Depends(require_admin)])

# Require Admin OR Committee
@router.patch("/societies/{id}", dependencies=[Depends(require_committee)])

# Custom combination
admin_or_security = require_roles("Admin", "Security")
```

## Multi-Role Assignment

A single user can hold multiple roles simultaneously:

```
User(john@example.com)
  └── UserRole → Role(Committee)
  └── UserRole → Role(Resident)
```

This enables committee members who are also residents of the society.
