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

## Finance Readiness
- VendorInvoice: GST-ready (gst_amount), mark_paid with payment_ref
- annual_value on AMC contracts for budget tracking
- actual_cost on service requests vs estimated_cost
