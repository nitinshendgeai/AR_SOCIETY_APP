# Amenity Management — Workflow

See `docs/MODULES/AMENITIES.md` for the rules, prices, checks and permissions. This is the flow.

## Setting up (Admin / Committee) — Amenities → an amenity
1. **Add an amenity**: name, kind, where, opening and closing times, most people at a time, whether residents book a
   time, whether the committee approves, whether there is a charge. A name can't repeat; it must close after it opens.
2. **Rules** (optional): longest booking, most people, bookings a week/month, how far ahead, deposit, charge per hour.
3. **Rates** (if chargeable): flat price and/or per hour, deposit; the default rate is used for bookings.
4. **Closed dates**: a day the amenity can't be booked (painting, a society event).
5. **Close / reopen** an amenity that is out of use. A closed one disappears for residents.

## Booking (any member)
1. Open the amenity, pick a day (arrows or the calendar): the page shows the opening hours, whether it's closed that day
   and the times already taken.
2. **Book**: date, from/to, how many people, what for. The sheet shows the charge and deposit if there are any.
3. Confirmed at once, or "waiting for approval" when the committee approves bookings. Rejected bookings show the reason.
4. **My bookings** lists everything; a booking can be cancelled until it starts.

## Deciding (Admin / Committee / Manager) — Requests tab
Approve, or reject with a reason; both notify the resident. **All bookings** filters by status and lets the committee
cancel any booking or mark one as used afterwards (noting any damage).

## Booking FSM
```
PENDING ──► APPROVED ──► COMPLETED
        ──► REJECTED
PENDING / APPROVED ──► CANCELLED
```
