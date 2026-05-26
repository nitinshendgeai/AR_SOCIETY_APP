# Inventory & Asset Management — Workflow

## Stock Workflow
```
Stock In (stock_in) → inventory_stock.current_quantity increases
Item Issued (issue_item) → stock decreases + issue record created
Item Returned (return_item) → stock increases + return record, issue status updated
Adjustment → direct quantity override with notes
```

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
