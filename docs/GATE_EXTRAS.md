# Gate extras — parcels and domestic help

Screens under **Community**: `/parcels`, `/domestic-help` (forms `parcels`, `domestic_help`, all roles).

## Parcels
- Security (or the office) logs: flat, courier, name on the parcel, description → status `at_gate`; every resident and
  tenant of the flat gets a notification.
- `collect`: security hands over (optionally recording who collected) — or the flat's own resident marks it. `return`:
  security only (with a reason). Once collected/returned a parcel cannot change (409).
- A resident sees only their flat's parcels; security and the office see the society's.

## Domestic help
- Register (`POST /gate/help/society/{id}`): a resident/tenant registers for their own flat; the office can name flats.
  Registered by a member → `pending` (the office is notified); registered by the office → `active` with a pass.
- The same mobile number in a society is one person: a second flat is simply linked to the existing record.
- Office approves → pass number `DH-nnnn` (per society), valid 365 days (or a date given); can suspend, end, activate
  again or renew. A resident can remove the person from their own flat.
- Gate (`POST /gate/help/{id}/scan`): toggles in / out. Entry needs an active, in-date pass linked to a flat; exit is
  always allowed. Flats are notified (in-app only). `GET /help/society/{id}/inside` lists who is inside now.
- Pass PDF (`GET /gate/help/{id}/pass`): A5 card with the QR of the pass number; only for active passes.
- History: `GET /gate/help/{id}/entries?days=30`.

## Not yet
Camera scanning of the QR at the gate (security searches by name/mobile/pass no. for now), and reminders for
parcels left uncollected.
