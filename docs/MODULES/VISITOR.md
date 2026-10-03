# Visitor Module

## Purpose
Gate management, visitor entry/exit, pre-approval workflow, visitor vehicle tracking.

## Core Entities
| Entity | Table | Purpose |
|--------|-------|---------|
| Gate | `gates` | Entry points with gate type |
| Visitor | `visitors` | Visitor master with host flat linkage |
| VisitorVehicle | `visitor_vehicles` | Vehicle brought by visitor |
| VisitorLog | `visitor_logs` | Entry/exit timestamps |

## Workflow
```
Visitor arrives → Security creates entry → Resident approves (if required)
               → Check-in logged → Visit complete → Check-out logged
```

## RBAC
| Action | Roles |
|--------|-------|
| Create visitor entry | Security, Admin, Committee |
| Approve/deny visitor | Resident, Admin, Committee |
| View visitor list | Admin, Committee, Security |
| View own approvals | Resident |

## Key Validations
- Duplicate active visit for same vehicle → 409
- Check-out without check-in → 404
- Expired/inactive gate → 422

## Rules (forms and API)
- Name trimmed and never blank (≤255); mobile 7–15 digits — an Indian mobile typed `+91 98765-43210` / `09876…` is stored as its 10 digits, so the same person typed two ways is one active entry (409); purpose ≤500; vehicle number 4–20 letters/digits (upper-cased, no spaces/hyphens), an empty vehicle is dropped. A reject reason is required (≤1000).
- **Scoping**: everything is confined to the caller's society (another society's visitor/gate → 404, its list → 403); logging at or for another society, a flat outside the society, a gate or named resident from elsewhere → 403/422. A gate name is unique per society (409).
- **Who decides**: approve/reject only by the people of the flat visited (the named resident, or a resident/tenant of that flat) or a manager/committee/admin. Guards log and check in/out but don't decide. A resident sees only visitors for their own flat; the society log and "inside now" are for security and above.
- Lists are paged (`limit` 1–200; the society log up to 1000).

## Integration Readiness
- `VisitorParking` in Parking module links visitors to temporary parking slots
- `rfid_tag` on `VisitorVehicle` → future RFID gate integration
