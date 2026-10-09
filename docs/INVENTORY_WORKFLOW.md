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
