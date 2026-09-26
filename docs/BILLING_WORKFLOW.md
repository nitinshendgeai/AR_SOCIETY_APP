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
Built by `bill_pdf.generate_maintenance_bill_pdf` in the layout Mumbai
co-operative housing societies use for their monthly bill (Maharashtra model
bye-laws — charges under bye-laws 65-67, arrears and interest on arrears shown
on the bill). One A4 page for a typical bill:

1. **Header box** — society name, Regn. No., address, GSTIN/PAN (Society Settings).
2. **Bill details** — "Bill for the Month of Aug-2026" (or the period, for a
   bill covering several months), member name (the bill's resident, else the
   flat's primary owner) and flat on the left; bill no., bill date, due date
   and carpet area on the right. "TAX INVOICE" when GST was charged.
3. **Particulars** — every active charge head of the society in element
   order, with 0.00 for the heads this flat isn't charged, then any other
   lines (e.g. non-occupancy charges) and "GST @ X%" when charged.
4. **Summary** — left: Principal Amount Dues and Accumulated Interest (the
   arrears split into principal and interest billed earlier but still
   unpaid) and the grand total in words; right: Total (this month's
   charges), Arrears / Advance (`previous_dues`), Interest on Principal
   Arrears (the calculator's interest line), late fee / discount when set,
   and the Grand Total.
5. **Notes** — discrepancies within 7 days; flat and bill no. on the cheque
   and interest @ X% p.a. on unpaid bills; how to pay by NEFT (account name,
   bank, account no., IFSC, UPI from the Rules tab) or cheque in favour of
   the society; the society's own `bill_notes`, one per line; receipts
   subject to realisation of cheque.
6. **Sign-off** — "For <Society>", Hon. Secretary / Treasurer / Chairman.

`BillingService._bill_print_context` supplies the charge heads and the
unpaid interest inside the arrears. Payments are **not** printed on the bill —
each has its own receipt.

## Payment receipt (`GET /billing/receipts/{receipt_no}/pdf`)
Every amount received gets a receipt of its own (model bye-laws), built by
`receipt_pdf.generate_payment_receipt_pdf` — A5 landscape, same letterhead as
the bill:

- receipt no. and date; "RECEIPT — ON BILLING" or "ON ACCOUNT";
- received with thanks from <member>, flat;
- amount in words and figures;
- "Vide Cash/Chq." — cash, cheque no. and bank, or UPI/NEFT reference;
- **on billing**: "Towards Bill No. X Dated dd/mm/yyyy (Bill for the Month
  of …)"; **on account**: "On Account of <head> Charges, to be adjusted
  against the member's bills" (advance receipts say so);
- "Subject to Realisation of Cheque" for cheques;
- a reversed (returned cheque) or rejected payment prints "CANCELLED:
  <reason>";
- "For <Society>", Hon. Secretary / Treasurer / Chairman.

Works for both payment records (PaymentReceipt, OnlinePaymentSubmission).
Members can download the receipts of their own flats; managers and above,
any. In the app: the download / share buttons on each payment of a bill,
and "View / Share Receipt" on a recorded payment (also
`GET /billing/online-payments/{id}/receipt`).

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
