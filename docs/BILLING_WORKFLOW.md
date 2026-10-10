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
Built by `bill_pdf.generate_maintenance_bill_pdf`, in the layout Mumbai
housing societies commonly send (Maharashtra model bye-laws — charges under
bye-laws 65-67, arrears and interest on arrears shown on the bill). One A4
page:

1. **Letterhead** — grey band with the society name, Regn. No., address and
   GSTIN/PAN, over a red rule; then "Maintenance Bill" ("/ Tax Invoice" when
   GST was charged).
2. **Details box** — Name, Flat No., Area sq ft, Mobile No, Mail ID (the
   bill's resident, else the flat's primary owner; placeholder e-mails are
   left out) | Bill No., Bill Date, Due Date, Bill Period, and Virtual A/c
   No.(VAN) when the flat has one (`flats.virtual_account_number`, set on the
   flat's edit screen — the bank's per-flat account for NEFT payments).
3. **Heads** (No / Head / Amount) — always these nine, 0.00 when nothing is
   charged under one:
   Maintenance Charges, Sinking Fund, Repair & Maintenance Fund, Property
   Tax, Non Occupancy Charges, Parking Charges, Cheque Bounce Charges, In &
   Out Charges, Other Charges — then "GST @ X%" when charged.
   The society's **monthly running expenses are shown together under
   "Maintenance Charges"**: charge heads created from the service charges,
   water, common electricity, lift, security, housekeeping, insurance, lease
   rent / NA tax, education fund and amenities elements, and custom heads of
   the maintenance / water / amenities types. Property tax, the sinking and
   repair funds, non-occupancy and parking keep their own heads (bye-laws
   65-67 want them shown separately); cheque-bounce and in-&-out charges
   are matched by name; anything else is "Other Charges"
   (`bill_pdf.bill_head`).
4. **Totals** — Current Bill Amount; Arrears/Advances (`previous_dues`
   less the interest in it); Current Interest/ Late Fees (this bill's
   interest-on-arrears line and late fee); Previous Interest/ Late Fees
   (interest billed earlier and still unpaid); discount when given; Total
   Maintenance Payable Amount.
5. **Notes** — NEFT details (beneficiary, account no. and IFSC, bank, UPI
   from Rules → Payment details on bills; a flat with a VAN is told to pay to
   "Virtual Ac No Mentioned Above in Bill" instead of the society account), interest @ X% p.a. on late
   payment, queries within 7 days, dues subject to final audit, the
   society's own `bill_notes`, computer-generated bill.
6. **Receipts towards the previous bill** — "Receipts: Towards Bill No. X
   for <month>": receipt no., date, amount, transaction type, reference,
   cheque bank, narration. (Each payment's receipt is still its own
   document, below.)

`BillingService._bill_print_context` supplies each charge head's element,
the unpaid interest inside the arrears and the flat's previous bill.

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


## Billing from the possession date

Rules → **Billing start date** (optional). Set it to the day billing in the app starts (for example 1 Apr 2026).

For each flat, when a cycle's bills are generated:
- **First bill** (the flat has no live bill yet): from `max(start date, possession date)` — a flat with no possession
  date starts on the start date. Possession dates older than the start date therefore never produce back-bills before it.
- **Later bills**: from the day after the end of the flat's last live (not cancelled) bill.
- Every bill runs to the **end of the cycle** being billed. A skipped cycle is caught up in the next bill.
- Months = the whole months in the period, plus a part-month by its days (calendar days of that month). A bill that
  starts with the cycle is charged exactly as before (the cycle's own length).
- A flat whose period would start after the cycle ends (possession later) is skipped, with a note in the preview.
- GST's monthly threshold is judged on the monthly amount (total ÷ months), so a catch-up bill is not pushed over it.

The period is stored on the bill (`period_start`, `period_end`), printed on its PDF and shown in the cycle preview.
Empty start date = every cycle bills its own period only. All months in a period use the current charge rates.
