# Amenities Module

## Purpose
Clubhouse, gym, pool, party hall, terrace… Residents see what the society offers, pick a day, see who has it when and
book a time. The booking is checked against the amenity's hours, capacity, rules, closed dates and everyone else's
bookings, and is confirmed at once or waits for the committee. Rules are stored per amenity, not hard-coded.

Screen: **Community → Amenities** (every role). Tabs: *Amenities*, *My bookings*, and for the committee and manager
*Requests* (waiting for a decision) and *All bookings*. An amenity's own page shows its day schedule and a Book button;
the committee also sets it up there (details, rules, rates, closed dates, close/reopen).

## Core Entities
| Entity | Table | Purpose |
|--------|-------|---------|
| Amenity | `amenities` | Name, kind, hours, capacity, whether booking / approval / a charge applies, open or closed |
| AmenityRule | `amenity_rules` | One rule of each kind per amenity (setting it again replaces it) |
| AmenityPricing | `amenity_pricing` | Rates: flat per booking, per hour, deposit; one is the default |
| AmenityBlackoutDate | `amenity_blackout_dates` | Dates the amenity is closed |
| AmenityBooking | `amenity_bookings` | A booking: date, times, guests, flat, status, charge and deposit |
| AmenityUsageLog | `amenity_usage_logs` | Written when a booking is marked as used (damage, extra charges) |
| AmenitySlot | `amenity_slots` | Older fixed-slot grid, kept; bookings don't need it |

## What a booking is checked against (in this order)
1. The amenity is open (not closed by the committee) and takes bookings.
2. It is inside the opening and closing times, and the number of people is within capacity.
3. The date isn't a closed date; the time hasn't already begun (the society's own clock, `Society.timezone`).
4. Nobody else has that time (pending and confirmed bookings both hold it; back-to-back is fine).
5. The rules below.
Anything wrong comes back as a plain sentence the app shows, e.g. "Clubhouse closes at 10:00 PM."

| Rule | Value | Effect |
|------|-------|--------|
| `max_duration_hours` | `3` | Longest booking |
| `max_guests` | `20` | Most people |
| `max_bookings_per_week` / `_month` | `2` | Per person; cancelled and rejected bookings don't count |
| `min_advance_hours` | `24` | Book at least this long before it starts |
| `max_advance_days` | `30` | Book at most this far ahead |
| `charge_per_hour` | `250` | Charge = rate × hours |
| `deposit_required` | `1000` | Refundable deposit |
| `owners_only` | — | Only registered residents may book |
| `approval_required` | — | The committee approves each booking |

A numeric rule must be a number above zero (whole for counts). The amenity's own "approval" switch has the same effect
as the approval rule.

## Prices
Charge and deposit come from the rate rules above, otherwise from the amenity's **default rate** (flat price, or price
per hour × hours, plus its deposit). A free amenity records none. They are shown on the booking and in the booking sheet.
**They are recorded, not billed**: nothing is added to a maintenance bill or posted to accounts; the committee collects
the money and records it as it does any other receipt.

## Booking FSM
```
PENDING ──► APPROVED ──► COMPLETED
        ──► REJECTED
PENDING / APPROVED ──► CANCELLED
```
* **Approve** re-checks that the time hasn't passed, the date hasn't since been closed and no other confirmed booking
  overlaps. **Reject** needs a reason, which the resident sees.
* **Cancel**: the person who booked it (until it starts) or the committee/manager (any time).
* **Complete** ("Mark as used"): once it has started; damage needs a note.

## RBAC
Form code `amenities` (all roles; migration `3d0e1f2a3b4c` grants it to existing roles).
| Action | Roles |
|--------|-------|
| See amenities, rules, rates, closed dates, a day's schedule; book; see/cancel own bookings | Any member |
| Create/edit/close amenities; rules, rates, closed dates | Admin, Committee |
| Approve, reject, mark as used; see all and pending bookings | Admin, Committee, Manager |

A resident's day view shows which times are taken (and which are theirs) but not who; the committee also sees the name
and flat. A booking is visible only to its booker and the committee.

## Society scoping
Every route is confined to the caller's society; another society's amenity or booking reads as *not found*, listing
another society's bookings is 403, and a society user can't create into another society by naming it.

## API
`POST /amenities/` · `PATCH /amenities/{id}` (incl. `is_active` to close/reopen) · `GET /amenities/society/{sid}`
(`include_closed` for the committee) · `GET /amenities/{id}` · `GET /amenities/{id}/day?for_date=` ·
`POST|GET /amenities/{id}/rules`, `DELETE /amenities/rules/{rid}` · `POST|GET /amenities/{id}/pricing`,
`DELETE /amenities/pricing/{pid}` · `POST|GET /amenities/{id}/blackouts`, `DELETE /amenities/blackouts/{bid}` ·
`POST /amenities/bookings` · `GET /amenities/bookings/me/list` · `GET /amenities/bookings/society/{sid}` (filters
`status`, `amenity_id`, `date_from`, `date_to`) · `GET …/society/{sid}/pending` · `GET /amenities/bookings/{id}` ·
`POST /amenities/bookings/{id}/approve|reject|cancel|complete`.
Bookings come back with `amenity_name`, `booked_by_name`, `flat`, `approved_by_name`.

## Not done
* No money handling: charges/deposits aren't billed or posted, and a deposit can't be marked paid/refunded in the app.
* No reminder before a booking, and no recurring bookings.
* `tenants_restricted` and `no_dues_required` rules exist but are not enforced yet.
