# Inventory & Asset Management — Workflow

## Stock Workflow (Operations → Stores)
```
Stock in  → quantity up (cost and bill number recorded)
Issue     → to a staff member; either expected back by a date, or "used up" (consumed)
Take back → some or all of what is outstanding; damaged / lost is closed off and not restocked
Count correction → the real count, with a reason
```
Overdue returns show on the Stores tiles and under *Issued → Overdue*.

## Ledger
Every stock change creates an immutable `InventoryTransaction` record with `quantity_before` and `quantity_after` — full audit trail.

## Low Stock Alert
When `current_quantity <= minimum_stock` → in-app notification sent automatically.

## Asset Workflow
```
Asset Registered → AST-0001 code assigned + usage log
Asset Assigned → assigned_at + usage log
Maintenance Scheduled → AssetMaintenance (SCHEDULED)
Maintenance Completed → status=COMPLETED, next_due_date set, usage log
AMC Added → AssetAMC with start/end dates
```

## Expiry Alerts
- `GET /inventory/assets/society/{id}/expiring-warranty` → warranties expiring in 30 days
- `GET /inventory/amc/expiring/{society_id}` → AMC contracts expiring in 30 days

## Auto-codes
- Inventory items: `INV-00001`, `INV-00002`
- Assets: `AST-0001`, `AST-0002`

## Importing the asset register (Excel / CSV)

`POST /inventory/assets/import/{society_id}` takes an `.xlsx` or `.csv` upload (max 5 MB, 5000 rows). `dry_run=true` (the
default) checks every row and saves nothing; `dry_run=false` adds the good rows. Parsing lives in
`modules/inventory/services/asset_import.py`: headings are matched to fields by name (`FIELDS`), a column can be
overridden with `mapping` (`{heading: field|null}`), dates are read day first, categories and statuses are matched by
keyword (unknown category becomes Other with a note). A blank asset code is numbered `AST-nnnn` skipping codes in use or
in the file; a code or serial number already registered is skipped as a duplicate. `GET /inventory/assets/import-template`
returns a CSV with every column. Each created asset gets a REGISTERED usage log ("Imported from <file>") and one audit entry.
