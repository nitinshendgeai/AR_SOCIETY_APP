# Assets Module (asset register)

What the society owns — air conditioners, water pumps, lifts, the generator, CCTV — with where each is, its warranty,
when it is next due for service, and everything done to it. Code: `backend/app/modules/inventory/` (assets share the
module with the consumable stores), app: `mobile/lib/features/assets/`.

## Entities
| Entity | Table | Purpose |
|--------|-------|---------|
| Asset | `assets` | One physical asset (`AST-0001`, numbered per society) |
| AssetMaintenance | `asset_maintenance` | A service or repair: scheduled → completed / cancelled |
| AssetAMC | `asset_amc` | A service contract covering just this asset |
| AssetUsageLog | `asset_usage_logs` | Registered, handed over, status changed, service done |

The vendor module's `AMCContract` (annual contracts with sanction and visit schedule) and `WorkOrder` can point at an
asset (`asset_id`); the asset's page lists both.

## Asset fields
Name, category (AC, water pump, water tank, STP/WTP/RO plant, lift, generator, electrical, solar, CCTV, intercom,
biometric, fire safety, HVAC, gym and garden equipment, furniture, IT equipment, vehicle, other), location, status
(`active`, `under_maintenance`, `retired`, `disposed`, `lost`), purchase date / cost / vendor / invoice, warranty expiry,
expected life, make/model, serial no., notes.

**Service schedule**: `service_interval_months`, `last_serviced_on`, `next_service_due`.
- At registration the due date is the interval after the last service, else after the purchase date, unless a date is given.
- Changing the interval or the last-serviced date re-works the due date unless one is sent with it.
- Completing a service sets `last_serviced_on` to the service date and `next_service_due` to the date given, else the
  interval after it. A service older than the last one recorded does not pull the schedule back. An asset
  `under_maintenance` returns to `active`.

**Computed on every asset** (never stored): `service_status` — `none` / `ok` / `due_soon` (within 30 days) / `overdue`;
`days_to_service`; `warranty_status` — `none` / `active` / `expiring` (30 days) / `expired`. Retired, disposed and lost
assets need no service.

## API (`/api/v1/inventory`)
| Endpoint | Purpose |
|----------|---------|
| `POST /assets` | Register (admin, committee, manager). `society_id` is the caller's own; only a platform admin names one |
| `PATCH /assets/{id}` | Change fields; send `null` to clear an optional one; status changes are logged |
| `GET /assets/society/{sid}?q&category&status&due` | The register; `due=true` = service overdue or within 30 days, soonest first |
| `GET /assets/summary/{sid}` | Counts, value at cost, warranty and service tallies, AMC ending, by category |
| `GET /assets/{id}` · `GET /assets/{id}/history` | One asset; or with services, AMC, linked contracts and work orders, the log and total service cost |
| `POST /maintenance` · `…/{id}/complete` · `…/{id}/cancel` | Plan, finish (`completed_date` ≤ today, `cost`, `findings`, `next_due_date`) or cancel a service |
| `POST /amc` · `GET /amc/asset/{id}` · `GET /amc/expiring/{sid}` | Contract covering one asset |
| `GET /assets/society/{sid}/expiring-warranty` · `GET /maintenance/scheduled/{sid}` | Lists for the committee |

Reads are open to any staff role, writes to admin, committee and manager. A service or AMC always takes its society
from the asset (a `society_id` in the body is ignored).

## Society scoping
Every inventory and asset route now confines the caller to their own society: an id from another society reads as
*not found*, a society-wide list for another society is refused (403), and a new record is created in the caller's society
(naming another one is refused). Issuing an item or assigning an asset to a user or staff member of another society is
refused (422). Before this, an admin of one society could read or change another's items, stock and assets.

## Stores (consumables) fixes made with it
Item output now includes `current_stock`; a stock adjustment can't go below zero; an item returned **damaged or lost** is
closed off on its issue but not put back on the shelf.

## App
**Operations → Assets** (form `assets`: admin, committee, manager). Four tiles (assets in use, service due / overdue,
warranty ending, value at cost), search, filters (all, needs service, under repair, retired, kind) and the list with a
status pill. An asset's page: schedule, details, planned services (*Done* / cancel), service history with total spent,
contracts and work orders, activity. **Log a service** records what was done (type, date, who, cost, findings, next due)
and, when it cost money, offers **Record as expense** — the Add Expense form opens with the amount and a note filled in.

## Not covered yet
- Reminders: due services show on the register but nothing is sent.
- Photos and documents (the model has `image_url`, the app does not upload).
- Depreciation (the fields to support it, `expected_life_years` and cost, are kept).
- Screens for the consumable stores (items, stock in, issue, return); the API is ready.
