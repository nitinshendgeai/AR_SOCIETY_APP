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

## Tower parking billing (element-wise)
Who pays: only the flats that hold an active slot in the tower zone. Mark them by allotting the slot to the flat
(Parking → Slots → Allot); nothing else to tick.

1. **Fixed car-parking charge** - set the zone's monthly rate (Parking → Slots → zone). A normal *Parking Charges*
   head then bills each holder that rate per slot.
2. **Shared tower costs** - Maintenance Billing → Rules → add a charge head from each element: *Tower Parking AMC*,
   *Tower Parking Electricity* (parking meter), *Tower Parking Wallet*, *Tower Parking Fire AMC*. On each, choose
   **Only for parking zone → Tower** and switch on *Budget from expenses → Actual expenses of each billing cycle*,
   after linking the matching expense ledger to the element.
3. At billing, each head's approved spend for the cycle is shared **equally per tower slot** among the holders (a
   flat with two slots carries two shares) and appears as its own line on their bill. Other flats get no line.
   A head with a typed amount instead of actual expenses is charged per slot (fixed) or as a yearly budget over the
   zone's slots (equal budget).
