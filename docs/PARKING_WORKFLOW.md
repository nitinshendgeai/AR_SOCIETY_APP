# Parking Management — Workflow

## Hierarchy
```
Society → ParkingZone → ParkingFloor → ParkingSlot
```

> Full guide (registering, allotting, the gate check, who can do what): `GUIDES/PARKING_AND_GATE_GUIDE.md`.

## Slot Allocation
```
Create Slot (available) → Allocate to flat/vehicle → slot.status=occupied
                        → Release allocation → slot.status=available
```

## Visitor Parking
```
Security assigns VisitorParking → check_in_time set, temp_access_code generated
→ Visitor parks → slot.status=occupied
→ Checkout → check_out_time set, slot.status=available
```

## RFID/ANPR Readiness
Each ParkingSlot has: `rfid_reader_id`, `camera_id`, `barrier_id`
ParkingAccessLog records: `access_method` (manual/rfid/anpr/app), `rfid_tag`

## Violation Types
unauthorized · expired_permit · wrong_slot · double_parking · blocked_access · restricted_zone

## Gate check
`GET /parking/gate/validate/{society}/{plate}` → `status`: `allowed` · `no_parking` · `unregistered`.
Allowed = resident/tenant vehicle with parking in force today, active visitor parking, or a resident-approved visitor's
vehicle. Parking ends on move-out, deregistration or the allocation's end date.

## Access Log
Every entry/exit → ParkingAccessLog with method, time, authorization status
