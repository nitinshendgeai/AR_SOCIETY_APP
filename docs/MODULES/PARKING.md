# Parking Module

## Purpose
Parking zone/slot management, resident allocations, visitor parking, violations, and RFID-ready access logs.

## Core Entities
| Entity | Table | Purpose |
|--------|-------|---------|
| ParkingZone | `parking_zones` | Basement, Open, Covered zones |
| ParkingFloor | `parking_floors` | Levels within zones (B1, B2, Ground) |
| ParkingSlot | `parking_slots` | Individual slots with RFID/camera/barrier IDs |
| ParkingAllocation | `parking_allocations` | Permanent resident/tenant slot assignment |
| VisitorParking | `visitor_parking` | Temporary visitor slot with temp_access_code |
| ParkingViolation | `parking_violations` | Unauthorized/wrong parking reports |
| ParkingAccessLog | `parking_access_logs` | Immutable entry/exit log |

## Workflows

### Slot Allocation
```
Create slot (available) → Allocate to flat/vehicle → status = occupied
                        → Release → status = available
```

### Visitor Parking
```
Assign → temp_access_code generated, check_in_time set
       → Checkout → slot released, access exit logged
```

### RFID/Smart Access Readiness
Each slot has: `rfid_reader_id`, `camera_id`, `barrier_id`
Access log has: `access_method` (manual/rfid/anpr/app/biometric), `rfid_tag`

## RBAC
| Action | Roles |
|--------|-------|
| Manage zones/slots/allocations | Admin, Committee |
| Assign visitor parking | Admin, Committee, Security |
| Report/resolve violations | Admin, Committee, Security |
| View own allocation | Any authenticated |

## Key Validations
- Duplicate slot number per society → 409
- Allocating already-occupied slot → 409
- Duplicate active visitor parking for same vehicle → 409
