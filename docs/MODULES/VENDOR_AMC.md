# Vendor & AMC Module

## Purpose
Vendor lifecycle, service contracts (vendor-centric AMC), service requests, visit logging, and vendor invoicing.

> Note: `AssetAMC` in the Inventory module is asset-specific. This module's `AMCContract` is vendor-centric and can cover multiple assets/services.

## Core Entities
| Entity | Table | Purpose |
|--------|-------|---------|
| Vendor | `vendors` | Vendor master (VND-0001) |
| VendorService | `vendor_services` | Capability catalogue |
| AMCContract | `amc_contracts` | Vendor-centric contract (AMC-2026-0001) |
| AMCServiceSchedule | `amc_service_schedules` | Auto-generated visit schedule |
| ServiceRequest | `service_requests` | Issue → vendor workflow (SRQ-00001) |
| ServiceVisitLog | `service_visit_logs` | Append-only visit records |
| VendorInvoice | `vendor_invoices` | GST-ready vendor billing |

## AMC Workflow
```
Create contract (DRAFT) → Activate (ACTIVE)
→ generate-schedule → AMCServiceSchedule records created per frequency
→ log-visit → schedule COMPLETED, visit logged
→ 60/30/7 day expiry alerts via alert_sent_* flags
→ EXPIRED / RENEWED / TERMINATED
```

## Service Request FSM
```
OPEN → ASSIGNED → SCHEDULED → IN_PROGRESS → COMPLETED → VERIFIED → CLOSED
Any → CANCELLED
```

## Key Validations
- Overlapping AMC for same vendor+asset → 409
- Service frequency ON_CALL cannot auto-generate schedules → 422
- Blacklisted vendor cannot be assigned → (service-layer check)

## RBAC
| Action | Roles |
|--------|-------|
| Manage vendors, contracts | Admin, Committee |
| Create service requests | Admin, Committee, Staff |
| Assign vendor to SR | Admin, Committee |
| Update SR status, log visits | Admin, Committee, Staff |
| Manage invoices | Admin, Committee |

## Rules (forms and API)
- **Vendors**: company name trimmed, never blank, unique within the society (409); mobile 7–15 digits; email checked; GSTIN (15 characters), PAN, IFSC and bank account are checked and upper-cased, and a GSTIN already on another vendor of the society → 409; blacklisting needs a reason; a blacklisted vendor can't be assigned work (422).
- **Numbers run per society** — `VND-0001`, `AMC-2026-0001`, `SRQ-00001` — and are unique on `(society_id, number)` (migration `fa0b1c2d3e4f`). They used to be unique platform-wide, so a second society's first vendor, contract or request failed.
- **Contracts**: must end after they start; annual value ≥ 0; SLA 0–8760 h; renewal notice 0–365 days; the document is an `http(s)` link; the vendor and asset must be the society's own.
- **Service requests / visits**: title and notes limited; the vendor, complaint, asset, contract and request named must belong to the society; a visit's check-out follows its check-in.
- **Vendor bills**: amount > 0 and total **= amount + GST** (2 decimals — the app sends paisa-exact strings); due date not before the invoice date; the same invoice number can't be entered twice for a vendor (409). **Payments**: amount > 0, not more than the outstanding, not future-dated and not before the invoice.
- **Society scoping**: lists by society are 403 for another society's users; vendors, contracts, requests and bills by id are 404 outside the caller's society; creating in another society is refused. Lists are paged (`limit` ≤ 500).
- App: the Add Bill sheet validates every field (a lazy list skipped some, which could crash on a blank amount), limits money to 10 digits + 2 decimals, and checks the due date; the Add Vendor dialog checks the phone number.

## Finance Readiness
- `annual_value` on contracts
- `actual_cost` vs `estimated_cost` on service requests
- `VendorInvoice` with `gst_amount`, `is_paid`, `payment_ref`
