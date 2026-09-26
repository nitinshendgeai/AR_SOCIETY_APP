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

## Bill PDF (`GET /billing/bills/{id}/pdf`)
Built by `bill_pdf.generate_maintenance_bill_pdf`, laid out like a
co-operative housing society's maintenance bill (Maharashtra model bye-laws —
charges under bye-laws 65-67, interest on arrears shown on the bill):

1. **Society** — name, Regn. No., address, GSTIN/PAN, contact (Society Settings).
2. **Title** — "MAINTENANCE BILL", "/ TAX INVOICE" when GST was charged.
3. **Member & bill** — member (the bill's resident, else the flat's primary
   owner), flat, area, bill no., bill date, billing period, due date.
4. **Charges** — numbered heads (Amount / GST / Total when GST applies),
   including "Interest on arrears @ X% p.a." when the calculator added it.
5. **Totals** — current bill charges, arrears as on the bill date
   (`previous_dues`), total amount payable, and the amount in words
   (Indian lakh/crore wording).
6. **Payments received** — receipts and on-bill payments (not
   reversed/rejected), paid so far and the balance of this bill.
7. **Payment details** — account name, bank, account no., IFSC, UPI ID from
   the Rules tab (`maintenance_settings.bank_*`, `upi_id`); omitted if blank.
8. **Notes** — pay by the due date; simple interest at the society's rate
   (and grace days) on late payment per the bye-laws; pay in favour of the
   society quoting flat and bill no.; report discrepancies to the committee;
   the society's own `bill_notes`; E. & O. E.
9. **Sign-off** — "For <Society>", Hon. Secretary / Treasurer, computer-generated note.

Amounts print as "Rs." (the built-in PDF fonts have no rupee glyph) with
Indian digit grouping (12,34,567.00).

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
