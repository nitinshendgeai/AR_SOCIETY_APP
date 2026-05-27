# Master Module

## Purpose
Core entity management: Society, Wing, Flat, Resident, Tenant, Vehicle. Foundation for all other modules.

## Core Entities

| Entity | Table | Key Fields |
|--------|-------|-----------|
| Society | `societies` | society_code, timezone, emergency_contact, settings |
| Wing | `wings` | society_id, name, code, total_floors |
| Flat | `flats` | wing_id, flat_number, occupancy_status, maintenance_status, kyc_verified |
| Resident | `residents` | flat_id, user_id, resident_type, kyc_verified, comm_preference |
| Tenant | `tenants` | flat_id, agreement_start/end, police_verification_status |
| Vehicle | `vehicles` | society_id, vehicle_number (normalized), rfid_tag, parking_slot |

## Workflows

### Society Onboarding
```
POST /societies/register-and-initialize
→ Creates Society + 6 default roles + 3 default users (temp passwords)
→ All audit logged, transactional
```

### Occupancy Lifecycle (OccupancyService)
```
resident_move_in  → flat.occupancy_status = OWNER_OCCUPIED
tenant_move_in    → flat.occupancy_status = TENANT_OCCUPIED + AgreementTracker created
tenant_move_out   → flat.occupancy_status = VACANT + agreement TERMINATED
```
Every event logs to `occupancy_logs` (immutable history).

### Agreement Tracking
`AgreementTracker`: alert_sent_30 / alert_sent_7 flags for expiry notifications.
`GET /occupancy/agreements/expiring/{society_id}?days=30`

## RBAC
| Action | Roles |
|--------|-------|
| Create/update society, wing, flat | Admin, Committee |
| View society, wing, flat | All authenticated |
| Register vehicle | Any member |
| Move-in / move-out | Admin, Committee |

## Key Validations
- Duplicate society name → 400
- Duplicate vehicle number per society → 409
- Double tenancy (two active tenants in same flat) → 409
- Agreement date overlap → 409
- Vehicle number auto-normalized (uppercase, no spaces/hyphens)

## Future Readiness
- `society_code` → multi-tenant email namespacing
- `kyc_verified` on Flat, Resident, Tenant → KYC workflow
- `rfid_tag` on Vehicle → gate/parking integration
- `police_verification_status` on Tenant → verification workflow
