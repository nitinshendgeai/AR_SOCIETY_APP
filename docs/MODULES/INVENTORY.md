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

## Stock Workflow
```
stock_in → current_quantity increases + transaction logged
issue_item → quantity validated (no negatives), deducted + issue created
return_item → quantity restored + return recorded (partial/full)
stock_adjust → direct override + ADJUSTMENT transaction
```

Low stock alert: when `current_quantity <= minimum_stock` → in-app notification.

## Asset Workflow
```
Register (AST-0001) → Assign → Schedule Maintenance → Complete → Log
AMC: add contract → expiry tracked (30-day window)
```

## Key Validations
- Negative stock prevention (issue > available → 409)
- Duplicate asset code → unique constraint
- Already-fully-returned issue → 409

## RBAC
| Action | Roles |
|--------|-------|
| Manage items/assets | Admin, Committee |
| Issue/return items | Admin, Committee, Staff |
| View stock/assets | Any authenticated |
| Low stock / expiry reports | Admin, Committee |
