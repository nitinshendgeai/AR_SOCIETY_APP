# Master Module

## Purpose
Core entity management: Society, Wing, Flat, Resident, Tenant, Vehicle. Foundation for all other modules.

## Core Entities

| Entity | Table | Key Fields |
|--------|-------|-----------|
| Society | `societies` | society_code, timezone, emergency_contact, settings |
| Wing | `wings` | society_id, name, code, total_floors, deleted_at |
| Floor | `floors` | wing_id, floor_number (0 = Ground, negative = basement), floor_name |
| Flat | `flats` | wing_id, flat_number, floor, flat_type, area_sqft, occupancy_status, maintenance_status, kyc_verified |
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
- Vehicle number auto-normalized (uppercase, no spaces/hyphens), 4–20 letters/digits, else 422

## Society structure rules (wings, floors, flats)
- Names and numbers are trimmed; blank ones are refused (422). Wing names are unique per society, wing codes too (upper-cased, case-insensitive); a flat number is unique within its wing; a floor number within its wing.
- Ranges: floor -10…200, wing total floors 1…200, flat area above 0; text lengths match the columns.
- Flat types: 1BHK, 2BHK, 3BHK, 4BHK, Studio, Duplex, Penthouse, Shop, Office, Other.
- A flat's floor is its floor number. **Renumbering a floor moves its flats with it.**
- **Delete is refused (409)** while something depends on the item: a floor with flats; a wing with flats (an empty wing takes its floors with it); a flat with residents or tenants, or with unpaid maintenance bills. The message says what is in the way.
- **Deactivating a wing** hides it from the pickers and stops new floors/flats being added to it; its flats, residents and bills carry on. `GET /wings/by-society/{id}?include_inactive=true` lists it so it can be activated again (a name or code taken meanwhile → 409). A **deleted** wing (`deleted_at`) can't be brought back.
- A flat stays in its wing: Edit Flat shows the wing but doesn't change it.

### Society profile and users (the other setup-wizard steps)
- Society profile: maintenance day 1–28, late fee 0–100 %, pincode 6 digits, PAN `ABCDE1234F`, GSTIN 15 characters (both upper-cased), email and phone checked; a society's name and code are unique (409 on rename).
- Create User (`POST /users/`): name not blank, phone checked, role must exist (unknown → 422), the platform role can't be granted by a society admin (403). The response carries `temporary_password` **once**; the app shows it in a copyable dialog.

## Residents, tenants and vehicles
- Names are trimmed (inner spaces collapsed) and never blank; email must be an address (stored lower-case); mobile is a 10-digit Indian number, the emergency phone any 7–15-digit number; blank optional fields are stored as nothing. Text lengths match the columns (422, not a database error). A date of birth can't be in the future; agreement, move-in and verification dates must be within 1900–2100; rent and deposit are ≥ 0 with at most 10 digits and 2 decimals.
- **PATCH clears**: a field sent as `null` is cleared (phone, email, ID proof, emergency contact, date of birth, remarks …); a field not sent is left alone. Name, type, primary, KYC and communication preference can't be cleared.
- `user_id` (the linked login) must belong to the same society (404 otherwise), on create and update. Resident self-service edit requests are validated the same way, so an approved request can't store a bad value.
- Move-out can't be dated before the move-in (422).
- Vehicles: year `YYYY` (1900 – next year), insurance expiry `YYYY-MM-DD`, lengths match the columns; clearing a field with `null` works. An **RFID tag** is unique — a second vehicle with it → 409 "already assigned"; deregistering a vehicle frees its tag and its number can be registered again.
- A plain resident or tenant sees and registers vehicles only for **their own flat** (403 / 404 otherwise); staff and committee see the whole society.
- The audit log stores dates, amounts, ids and enums as JSON (editing a date used to drop the audit entry).
- App: the resident, tenant, wing, floor and flat forms scroll in a plain scroll view, so **every field is validated** on Save (a lazy list skipped the ones scrolled out of view). Email, vehicle number, rent/deposit are checked as typed; a chosen date of birth or ID type can be cleared.

## Future Readiness
- `society_code` → multi-tenant email namespacing
- `kyc_verified` on Flat, Resident, Tenant → KYC workflow
- `rfid_tag` on Vehicle → gate/parking integration
- `police_verification_status` on Tenant → verification workflow
