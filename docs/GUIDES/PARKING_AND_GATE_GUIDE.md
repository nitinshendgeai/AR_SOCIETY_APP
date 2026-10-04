# Parking and the Gate Check — Complete Guide

How a vehicle a resident or tenant registers ends up in Parking Management, how the committee gives it parking, and how
the guard at the gate finds out in one step whether a vehicle is allowed in. Written against the code
(`backend/app/modules/parking/`, `backend/app/api/routes/vehicle.py`).

---

## 1. The flow

```
Resident / tenant adds a vehicle (My Vehicles)
        │
        ▼
Parking Management → Vehicles tab ──▶ "No parking (3)" list ──▶ Allot parking (pick a free slot, optional monthly charge)
                                                                           │
Gate: guard types or scans the plate ──▶ Vehicle Gate Check ◀──────────────┘
        │
        ├─ green  Allowed — has parking          (resident / tenant vehicle with parking today, or an approved visitor)
        ├─ amber  Registered — no parking        (known vehicle, no slot: send it elsewhere)
        └─ red    Not registered                 (verify by hand)
```

---

## 2. Registering a vehicle

A resident or tenant adds their vehicle for **their own flat** (Vehicles). The number is stored without spaces or
dashes and in capitals (`MH 12 ab-1234` → `MH12AB1234`); the same plate can't be registered twice in a society. A
vehicle shows up in Parking Management straight away — nothing else to do.

## 3. Parking Management (committee, admin)

**Operations → Parking Management** has three tabs.

| Tab | What it is for |
|---|---|
| **Slots** | Zones (Basement, Open …) and their slots. Add a zone, then slots. |
| **Allocations** | Who holds which slot. *Release* gives it back. |
| **Vehicles** | **Every registered vehicle** and whether it has parking. Opens on **No parking** — the vehicles still waiting. Search by plate, owner or flat. **Allot parking** next to a vehicle: pick a free slot, add a monthly charge for rented parking (blank = allotted free), done. **Release** on one that has parking. |

Rules the app keeps for you:

- A vehicle holds **one** slot at a time (release it before giving another), and a slot goes to one vehicle at a time.
- The vehicle and slot must belong to your society, and the vehicle to the flat chosen.
- An allocation can have an **end date** (rented for a year, say). When it passes the parking **stops counting at once**
  and the slot becomes free again — nobody has to remember. An end date already in the past is refused.
- An allotment can start in the future; the vehicle isn't allowed in on it until the day comes.
- The slot number appears on the resident's own vehicle once it is allotted, and goes again when released.

**When a vehicle's parking ends by itself**

- A resident or tenant **moves out** → their vehicles are unassigned **and their parking is released**, the slots freed.
- A vehicle is **deregistered** → its parking is released.

(A vehicle that still has a slot *typed into its own record* — the older, simple way — counts as having parking too,
until that field is cleared.)

## 4. The gate check (security guard)

**Dashboard → Vehicle Gate** (or `/parking/gate-check`). Type the plate — in any case, with or without spaces and
dashes — or scan it with a handheld/USB scanner, which types it for you — and press Enter. The screen is ready for the
next plate after *Check Another Vehicle*.

| Answer | When | What the guard sees |
|---|---|---|
| **Allowed — has parking** (green) | A resident/tenant vehicle with parking in force **today** | Owner, flat, slot |
| **Allowed — approved visitor** (green) | The visitor has active visitor parking, **or** the guard logged them in Visitors with this vehicle and the resident **approved** (or they are already inside) | Visitor, flat visited, purpose |
| **Registered — no parking allotted** (amber) | Known resident/tenant vehicle with no slot (a second car, a lapsed rental, an owner who has moved out) | Owner, flat — send it elsewhere |
| **Not registered** (red) | Not known | "Verify manually before allowing entry" |

A visitor still **waiting for the resident's approval**, one the resident **rejected**, or one who has **checked out**
shows red.

**Log Entry / Log Exit** records the movement (date, time, who, and whether it was authorised — worked out by the
server, never taken from the app). The lookup itself writes nothing.

> The gate screen reads a typed or scanner-entered number. Reading a plate from a camera photo (ANPR) is not built;
> the access log already has a field for it (`access_method = anpr`).

## 5. Who can do what

| | Security | Resident / tenant | Admin / committee |
|---|---|---|---|
| Gate check, log entry/exit | ✔ | – | ✔ (security permission) |
| Register a vehicle | – | their own flat | ✔ |
| Parking Management, allot / release | – | – | ✔ |
| Vehicle list with parking status | – | – | ✔ |

Everyone works **inside their own society only**: another society's slots, allocations, violations or gate history can't be
read or changed, and one society's records are reported as *not found* to another.

## 6. Not covered yet

- Camera / ANPR plate reading.
- A parking charge added to the maintenance bill automatically (the monthly charge is recorded, not billed).
- Vehicles of a person who moved out **before** this version keep any slot typed on their record until a committee member
  clears it or deregisters the vehicle.
