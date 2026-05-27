# Amenities Module

## Purpose
Rule-driven amenity booking governance. Rules are DB-stored, not hardcoded.

## Core Entities
| Entity | Table | Purpose |
|--------|-------|---------|
| Amenity | `amenities` | Clubhouse, gym, pool etc. |
| AmenityRule | `amenity_rules` | DB-driven policy engine (12 rule types) |
| AmenitySlot | `amenity_slots` | Time-slot grid with capacity |
| AmenityPricing | `amenity_pricing` | Hourly/flat/deposit rates |
| AmenityBlackoutDate | `amenity_blackout_dates` | Admin-managed unavailable dates |
| AmenityBooking | `amenity_bookings` | Booking with FSM + financial fields |
| AmenityUsageLog | `amenity_usage_logs` | Post-booking usage record |

## Rule Engine
Rules stored in `amenity_rules` — add a rule row to instantly change behavior.

| Rule Type | Example Value | Effect |
|-----------|--------------|--------|
| `max_duration_hours` | `4` | Max 4h booking |
| `max_bookings_per_week` | `2` | 2 per resident/week |
| `approval_required` | `true` | Goes to PENDING |
| `charge_per_hour` | `500.00` | ₹500/h auto-calculated |
| `deposit_required` | `2000.00` | ₹2000 deposit |

## Booking FSM
```
PENDING → APPROVED → COMPLETED
        → REJECTED
PENDING/APPROVED → CANCELLED
```

## RBAC
| Action | Roles |
|--------|-------|
| Create/configure amenity | Admin, Committee |
| Manage rules, blackouts | Admin, Committee |
| Create booking | Any authenticated |
| Approve/reject booking | Admin, Committee |
| View availability | Any authenticated |
