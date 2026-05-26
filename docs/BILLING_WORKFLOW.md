# Maintenance Billing & Finance — Workflow

## Bill Generation Flow
```
1. Create FinancialPeriod (e.g. "May 2026")
2. Configure MaintenanceChargeConfigs (maintenance/water/parking etc.)
3. Create BillingCycle with due_date
4. POST /billing/cycles/{id}/generate-bills
   → One MaintenanceBill per active flat
   → InvoiceLineItems per charge config
   → DueTracker updated per flat
5. POST /billing/bills/{id}/issue → status=ISSUED, resident notified
6. POST /billing/payments → PaymentReceipt created, bill/due updated
```

## Bill Status FSM
```
DRAFT → GENERATED → ISSUED → PARTIALLY_PAID → PAID
                           → OVERDUE
                   → CANCELLED (any non-PAID state)
```

## Payment Modes
cash · upi · bank_transfer · cheque · online_gateway · neft · rtgs

## DueTracker
Single rolling balance per flat — source of truth for outstanding.
Updated atomically on every bill generation and payment.

## Penalty Rules
Configurable: flat_amount / percentage / compound_daily
Grace period configurable per rule.
Max penalty cap configurable.
Applied to specific charge types or all.

## Finance ERP Readiness
- FinancialPeriod.is_closed → accounting period lock
- PaymentReceipt.is_reversed → bounced cheque handling
- InvoiceLineItem with tax_percent → GST integration ready
- DueTracker.advance_balance → advance payment ready
