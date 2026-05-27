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

## Integration Readiness
- `VisitorParking` in Parking module links visitors to temporary parking slots
- `rfid_tag` on `VisitorVehicle` → future RFID gate integration
