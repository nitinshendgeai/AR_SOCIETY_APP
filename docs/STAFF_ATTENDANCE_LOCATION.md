# Staff attendance: location check

Staff can be required to check in and out only from places the society sets (the gate, the office...). The phone's location is
read **at the moment of the check-in or check-out only**; it is never tracked in between.

## Set it up (Admin or committee, once)

1. Open the **web app on your phone's browser** (Admin and committee logins cannot use the staff app) and allow location when asked.
2. Go to **Staff → Attendance Approvals** and tap the **pin icon** (Attendance location).
3. Stand **outdoors at the gate** (or the office door), tap **Add spot here**, then **Use my location now**. Wait until it says
   "accurate to 10 m" or better, name the spot (for example *Main gate*) and save. The allowed distance starts at **10 m**.
   - No GPS? Type the latitude and longitude instead (on a map app, press and hold the spot and copy the numbers).
4. Add more spots (Tower B, the office...). The **nearest** spot decides.
5. Tap **How far am I from the spots?** at the gate and at the edge of the area to check the result before you rely on it.
6. Choose how strictly to apply it:
   - **Off**: no location check (how attendance worked before).
   - **Flag** (the default once a spot exists): everyone can check in; those outside, or without a usable location, are marked for the manager.
   - **Block**: a check-in or check-out outside the spots is refused.
   Start with **Flag** for a couple of weeks, look at the marks on the approval screen, and move to **Block** when it behaves.

## What staff do

On the Staff Portal attendance page, **Check In** / **Check Out** reads the phone's location (a few seconds) and sends it.
The phone needs **Location on** and the app allowed to use it **"while using the app"** with **Precise location** on.
They are told where they were ("At Main gate · 4 m") or, if outside, that the manager will see it.

## What the manager sees

On **Attendance Approvals**, each punch shows a chip: **At Main gate · 4 m** (green), **35 m from Main gate** (amber),
**Fake location detected** (red), **Location not accurate enough** or **No location** (grey). The manager still approves or
rejects as before: the check only adds information (or, in Block mode, refuses before the record is made).

## How a reading is judged (on the server)

1. The phone says the location is faked (Android's mock-location flag) → `mocked`.
2. Nothing usable was sent → `no_location`.
3. The reading is less accurate than the society's limit (default 20 m) → `low_accuracy`: the person is asked to wait for a better one.
4. Otherwise the distance to the nearest spot is compared with that spot's radius → `inside` / `outside`.

## Limits to know

- Phones are usually accurate to 3 to 10 m outdoors and 20 to 50 m indoors or in basements. A radius under about 10 m will turn honest
  staff away. If a gate is inside a covered area, add the spot a few metres out, or raise the radius.
- A fake-location app cannot be stopped completely; the app records Android's "mocked" flag and the server never treats it as inside.
- Supervisors checking in on behalf of staff use their own phone's location.
- Changing a spot or the rule affects check-ins from then on; past records keep what was recorded.

## Technical

Tables `attendance_geo_spots`, `attendance_geo_settings`, `attendance_geo_events` (migration `d5a7c9e1b3f5`, additive). With no spot,
attendance is unchanged. API under `/api/v1/staff/attendance-geo/...`; check-in and check-out accept an optional `location`
(`latitude`, `longitude`, `accuracy_m`, `mocked`); attendance records carry `geo_in` and `geo_out`.
