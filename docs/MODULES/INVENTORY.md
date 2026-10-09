# Inventory & Asset Module

## Purpose
Stock management with immutable ledger, asset lifecycle, AMC contracts, and maintenance history.

## Core Entities
| Entity | Table | Purpose |
|--------|-------|---------|
| InventoryCategory | `inventory_categories` | Custom item categories |
| InventoryItem | `inventory_items` | Item master (INV-00001) |
| InventoryStock | `inventory_stock` | Live stock level (1 per item) |
| InventoryTransaction | `inventory_transactions` | Immutable stock ledger |
| InventoryIssue | `inventory_issues` | Issue tracking with partial return |
| InventoryReturn | `inventory_returns` | Return records (condition tracking) |
| Asset | `assets` | Equipment master (AST-0001) |
| AssetMaintenance | `asset_maintenance` | Service records |
| AssetAMC | `asset_amc` | Asset-level AMC contracts |
| AssetUsageLog | `asset_usage_logs` | Lifecycle log |

## Stores (consumables)
Screen: **Operations → Stores** (admin, committee, manager). *Items* tab: what is in stock, what is running low, search
and filter by kind; an item's page has Stock in, Issue, Correct the count, who has some of it now, and every movement.
*Issued* tab: what is out with staff (still out / overdue / all), with a Take back button.

```
stock_in        → quantity up + a ledger row (cost and bill number kept)
issue (to staff) → quantity checked (409 if short), deducted; status "issued" and expected back
issue (used up)  → "consumed": deducted as consumption, nothing is expected back, can't be returned
return           → up to what is outstanding; good items go back on the shelf, damaged or lost ones don't
count correction → sets the quantity, needs a reason, written to the ledger and the audit log
```
Rules: an item needs a name; the minimum and costs can't be negative; an item name isn't repeated in a society; an issue
must name who it is for (a staff member of the same society) and any linked complaint must be in the society; a return
date can't be in the past; a returned quantity must be above zero and no more than is outstanding. An item can be
retired only when none is in stock and none is out. An item is **low** when stock is at or below its minimum.

The **summary** (`GET /inventory/summary/{society}`) gives items, running low, out of stock, stock value (stock × the
cost entered), what is out with people and what is overdue. Overdue is measured on the society's own calendar.

Low stock: when a count correction or an issue leaves stock at or below the minimum the person acting gets an in-app
notification. Nobody else is notified, and there is no reminder for overdue returns.

## Asset Workflow
```
Register (AST-0001) → Assign → Schedule Maintenance → Complete → Log
AMC: add contract → expiry tracked (30-day window)
```

## RBAC
| Action | Roles |
|--------|-------|
| Add/edit/retire items, stock in, correct the count, summary, assets | Admin, Committee, Manager |
| Issue and take back items | Supervisors and above (API); the screen is shown to Admin, Committee, Manager |
| View items, stock, issues, history | Any staff role (API) |

Every route is confined to the caller's society: another society's item or issue reads as not found.
