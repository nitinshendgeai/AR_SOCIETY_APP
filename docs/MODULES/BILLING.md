# Billing Module

## Purpose
Maintenance billing lifecycle: charge config → billing cycle → per-flat invoices → payments → due tracking.

## Core Entities
| Entity | Table | Purpose |
|--------|-------|---------|
| FinancialPeriod | `financial_periods` | Accounting period with is_closed lock |
| MaintenanceChargeConfig | `maintenance_charge_configs` | Charge catalogue (9 types) |
| BillingCycle | `billing_cycles` | Named billing run |
| MaintenanceBill | `maintenance_bills` | Per-flat invoice (INV-2026-00001) |
| InvoiceLineItem | `invoice_line_items` | Per-charge breakdown with tax |
| PaymentReceipt | `payment_receipts` | Immutable payment record (RCP-2026-00001) |
| DueTracker | `due_trackers` | Rolling balance per flat (single source of truth) |
| PenaltyRule | `penalty_rules` | Configurable late-fee engine |

## Workflow
```
1. Create FinancialPeriod
2. Configure MaintenanceChargeConfigs
3. Create BillingCycle with due_date
4. POST /billing/cycles/{id}/generate-bills
   → One MaintenanceBill per active flat
   → DueTracker updated atomically
5. POST /billing/bills/{id}/issue → ISSUED, resident notified
6. POST /billing/payments → receipt created, bill + due updated
```

## Bill FSM
```
DRAFT → GENERATED → ISSUED → PARTIALLY_PAID → PAID
                           → OVERDUE
                   → CANCELLED (any non-PAID)
```

## Key Validations
- Over-payment prevention (amount > outstanding → 422)
- Duplicate bill generation per cycle → 409
- Cancellation of PAID bill → 409
- Period close lock (is_closed → no modifications)

## Finance Readiness
- `tax_percent` per line item (GST-ready)
- `is_reversed` on receipts (bounced cheque)
- `advance_balance` on DueTracker
- `PenaltyRule`: flat/percentage/compound_daily calculation types

## RBAC
| Action | Roles |
|--------|-------|
| Generate bills, manage charges | Admin, Committee |
| Record payments | Admin, Committee |
| View own bills | Any authenticated |
| View outstanding/overdue reports | Admin, Committee |
