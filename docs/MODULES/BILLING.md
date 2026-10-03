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
| PaymentAllocation | `payment_allocations` | How much of a recorded payment settled which bill |

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

## Expense-driven budgets (`services/budget_suggestions.py`)
Each expense ledger in the accounts can be linked to the maintenance element it pays for
(`accounts.maintenance_element_id`; Security Charges → Security, Lift Maintenance → Lift Maintenance …
see `DEFAULT_ELEMENT_LINKS` in `accounts/services/chart_of_accounts.py`; standard ledgers are linked when
created, existing ones by migration `fc2d3e4f5a6b`, and the committee can change or clear any link).
Everything posted to a linked ledger — vendor bills, payment vouchers, journals — is that element's actual cost.
- `GET /billing/charges/{society}/budget-suggestions?months=` — last N months of net spend per element,
  annualised (a partial year is scaled up, not taken as a year) and converted to each charge head's basis
  (annual budget / ₹ per flat per month / ₹ per sq ft per month). Read-only; also lists expense ledgers with spend
  that no element covers.
- A charge head can switch on **budget from expenses** (`auto_from_expenses`, `expense_months` 1–36; needs a head
  made from an element and a fixed / per-sq-ft / budget basis). The maintenance calculator then bills it at the
  spend-derived rate instead of the typed amount, in both the preview and bill generation. With nothing spent in
  the window the typed amount is used and the preview warns.
- Bills already generated are never recalculated.

## Fines and additional charges on a flat (`services/flat_charges.py`)
`flat_charges`: a **fine** or **extra** charge on one flat with a title, reason, amount, effective date, and
optionally recurring with an end date. Manager and above add/cancel them (`/billing/flat-charges`); a member can
read their own flat's (`GET /flat-charges/flat/{id}`) and is notified when one is added.
- The calculator adds each applicable charge to the flat's bill: fines as a non-GST PENALTY line
  (`Fine — {title}`, kept out of the principal that interest is charged on, posted to the *Fines & Penalties*
  ledger), extras as an OTHER line that carries GST only when marked.
- A one-off charge is marked `billed` (with its bill) when the bill is generated and goes back to `active` if that
  bill is cancelled; a recurring one stays active and goes on every bill from its effective date until its end date
  or cancellation. Only an `active` charge can be cancelled (reason required); a billed one is reversed by
  cancelling the bill.
- Not built yet: charges derived from resident-entered details (vehicles, family members) and automatic parking-fine
  feeding.

## Numbers per society
Maintenance bill numbers (`INV-2026-00001`), receipts (`RCP-` / `OPS-`) and inventory item / asset codes (`INV-00001`, `AST-0001`) run within each society and are unique on `(society_id, number)` (migration `fb1c2d3e4f5a`). They were unique platform-wide, so a second society's first bill, receipt, item or asset failed. The next number is one more than the society's highest.

## Payments set off against open bills (`services/allocations.py`)
- A payment recorded for a flat (Payments → Record Payment) **settles the flat's open bills oldest first** (by due date): each bill's paid amount, outstanding and status (partially paid / paid) and the flat's `DueTracker` update, and one `PaymentAllocation` per bill records the set-off. The form shows beforehand how the amount will be applied; **One bill** applies it to a single chosen bill instead.
- What is left over is the member's **advance** (`DueTracker.advance_balance`): it is set off against the next bill when that bill is **issued**. Bills cancelled meanwhile put their set-off back into credit, which settles the flat's other open bills.
- A payment **rejected** at reconciliation releases its set-offs — the bills are unpaid again — and is set off again if it is later cleared. Released allocations stay on record with the reason.
- The bill's payment list, the receipt (each bill with the amount applied to it, and any advance) and the bill's receipts section on the next bill read the allocations.
- Payments recorded "on account" before this existed stay held until **Set off now** on the Payments list (`POST /billing/online-payments/society/{id}/apply`; `GET …/unapplied` counts them).

## Members' dues & defaulters (`services/defaulters.py`)
- Each flat's dues = outstanding on its issued bills, less any money paid but not yet set off (an advance, or an old on-account payment — set off against the oldest bills first), aged from each bill's **due date**: not yet due, up to 3 months, 3–6, 6–12, over 1 year.
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
