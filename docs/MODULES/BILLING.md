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

## Members' dues & defaulters (`services/defaulters.py`)
- Each flat's dues = outstanding on its issued bills, less money paid on account (set off against the oldest bills first), aged from each bill's **due date**: not yet due, up to 3 months, 3–6, 6–12, over 1 year.
- **Defaulter**: some dues outstanding longer than the limit after the due date — 3 months by default (the model bye-laws' three-month rule); 1, 6 or 12 months can be chosen.
- Per flat: member and phone, buckets, total, oldest due date, unpaid bills, last payment, last reminder.
- `GET /billing/defaulters/{society_id}?min_months=3&include_all=false&format=json|pdf` — the list; `include_all` lists every flat with dues; the PDF is "List of Defaulters as on <date>" on the letterhead, signed by the Hon. Secretary.
- `POST /billing/defaulters/{society_id}/remind` `{flat_ids?, min_months}` — app/push notification (module `billing_dues`, entity = flat) to members with a login; without `flat_ids`, every defaulter. The latest one is shown as "Reminded".
- Screen: Finance → Defaulters (form `defaulters`: Admin, committee, Manager), also linked from Accounts → Members' Ledger. CSV export in the app.

## RBAC
| Action | Roles |
|--------|-------|
| Generate bills, manage charges | Admin, Committee |
| Record payments | Admin, Committee |
| View own bills | Any authenticated |
| View outstanding/overdue reports | Admin, Committee |
