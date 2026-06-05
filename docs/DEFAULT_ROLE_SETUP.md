# Default Role Setup — AR Society ERP

## Roles Created on Society Registration

13 default roles are created (idempotent) on every new society registration.
Roles are **global** (shared across societies) — the same role table is reused.

| # | Role Name | Description | Level |
|---|-----------|-------------|-------|
| 1 | Platform Admin | AR Society internal staff — cross-society management | Platform |
| 2 | Society Admin | Full society-level administration | Admin |
| 3 | Committee Chairman | Head of society committee | Committee |
| 4 | Committee Secretary | Society secretary | Committee |
| 5 | Committee Treasurer | Society treasurer | Committee |
| 6 | Security Supervisor | Supervises security staff | Security |
| 7 | Housekeeping Supervisor | Supervises housekeeping | Staff |
| 8 | Technical Supervisor | Supervises maintenance team | Staff |
| 9 | Security Staff | Gate and patrol staff | Security |
| 10 | Housekeeping Staff | Cleaning and maintenance | Staff |
| 11 | Technical Staff | Electrical, plumbing, etc. | Staff |
| 12 | Resident | Flat owner / occupant | Resident |
| 13 | Tenant | Rented flat occupant | Resident |

## RBAC Mapping

Role names map to RBAC permission groups in `dependencies.py`:

| Role | RBAC Group |
|------|-----------|
| Society Admin | `require_roles("Admin")` |
| Committee Chairman/Secretary/Treasurer | `require_roles("Committee")` |
| Security Supervisor / Security Staff | `require_roles("Security")` |
| Housekeeping/Technical Supervisor/Staff | `require_roles("Staff")` |
| Resident / Tenant | `require_roles("Resident")` |
| Platform Admin | `require_platform_admin()` |

## Default Users Created

| User | Email Pattern | Role | must_change_password |
|------|--------------|------|---------------------|
| Society Admin | `admin@<code>.arsociety.com` | Society Admin | True |
| Chairman | `chairman@<code>.arsociety.com` | Committee Chairman | True |
| Secretary | `secretary@<code>.arsociety.com` | Committee Secretary | True |
| Treasurer | `treasurer@<code>.arsociety.com` | Committee Treasurer | True |

`<code>` = lowercase society_code, e.g., `sunap`

## Idempotent Behaviour

Running `initialize_society()` multiple times is safe:
- Roles already existing in DB are reused (no duplicate creation)
- Users with emails already in DB are skipped
- Returns only newly-created credentials (empty list if already initialized)

## First Login Enforcement

All default users have `must_change_password = True`.
On first login, Flutter forces:
1. Password change
2. Terms acceptance
3. Setup wizard (Admin only)

Until all three are complete, access to all modules is blocked.
