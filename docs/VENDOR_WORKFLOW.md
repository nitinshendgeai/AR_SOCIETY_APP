# Vendor & AMC Management — Workflow

## Vendor Lifecycle
```
Create Vendor (VND-0001) → Add Services catalogue
→ Active | Inactive | Blacklisted
```

## AMC Contract Lifecycle
```
Create Contract (AMC-2026-0001) → status=DRAFT
→ Activate → status=ACTIVE
→ Generate Schedule → AMCServiceSchedule records created per frequency
→ Log Visit → schedule marked COMPLETED
→ Expiry alerts: 60/30/7 days before end_date
→ Renewed/Expired/Terminated
```

## Service Request FSM
```
OPEN → ASSIGNED → SCHEDULED → IN_PROGRESS → COMPLETED → VERIFIED → CLOSED
                                                        ↘ IN_PROGRESS (rework)
Any → CANCELLED
```

## Auto-numbers
- Vendors: VND-0001
- AMC Contracts: AMC-2026-0001
- Service Requests: SRQ-00001

## One Vendor Master
Every place that says who was paid takes a vendor from the Vendor Master, and a vendor can be added on the spot
in the Vendor Master form itself (the same one as Vendors & Work, GSTIN, PAN and bank details included). A vendor added in
the **Add Expense**, **monthly expense**, **payment voucher** or **vendor bill** form is in the master immediately,
and a vendor edited in the master shows in all of them.

- A payment voucher and a monthly expense carry `vendor_id` (`vouchers.vendor_id`, `recurring_expenses.vendor_id`);
  only a payment can name a vendor. Day Book: `GET /accounts/vouchers/society/{id}?vendor_id=`.
- The vendor's page lists what was paid to them from expenses (approved payments only).
- A monthly expense's old typed payee is linked to the vendor of the same name when there is one (migration
  `6a3b4c5d6e7f`); the rest stay as text and are flagged in the form so someone can pick the vendor.

## Auto-numbers on the forms
The app numbers its own documents and shows the number before saving — a voucher form says "Voucher no.
PV/2026-27/0004, given automatically" (`GET /accounts/vouchers/next-number/{society_id}?voucher_type=`). Codes left
blank are made for you: a ledger's code (next number in its group), a wing's code ("A Wing" → "A") and a parking
zone's ("Basement" → "BAS"). Numbers that come from *outside* — the supplier's bill or invoice no., a cheque no., a UTR
— stay as optional fields, labelled as the supplier's or the bank's.

## Finance Readiness
- VendorInvoice: GST-ready (gst_amount), mark_paid with payment_ref
- annual_value on AMC contracts for budget tracking
- actual_cost on service requests vs estimated_cost
