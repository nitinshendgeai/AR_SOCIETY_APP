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
| VendorInvoice | `vendor_invoices` | GST-ready vendor billing (`work_order_id` for bills against a work order) |
| ProcurementSettings | `procurement_settings` | Committee limit, tender limit, quotations needed (bye-law 157) |
| WorkOrder | `work_orders` | One-time work given to a vendor (WO-2026-0001), sanction to closure |
| Quotation | `vendor_quotations` | A vendor's quotation / tender for a work order or a contract |

## AMC Workflow
```
Create contract (DRAFT) → Activate (ACTIVE)
→ generate-schedule → AMCServiceSchedule records created per frequency
→ log-visit → schedule COMPLETED, visit logged
→ 60/30/7 day expiry alerts via alert_sent_* flags
→ EXPIRED / RENEWED / TERMINATED
```

## Work orders and sanctions (`services/work_orders.py`, migration `fd3e4f5a6b7c`)
Model bye-law 157: the committee may spend on repairs on its own only up to ₹25,000 / ₹50,000 / ₹1,00,000 (up to 25 /
26–50 / 51+ members) unless the general body fixes another limit; above the general body's tender limit, tenders are
opened in a committee meeting and the general body decides. A committee member with an interest in a society contract
is disqualified.
- **Limits** — `GET/PUT /vendors/procurement-settings/{society}`: blank = the slab for the number of active flats;
  another figure needs the general body resolution no. and date. Tender limit defaults to the committee limit;
  `min_quotations` 2–10 (3).
- **Work order** `DRAFT → SANCTIONED → ISSUED → COMPLETED → CLOSED`, `CANCELLED` from the first three while no bill is
  recorded. `POST /vendors/work-orders`, `PATCH` (draft; after the sanction only title, location, dates, estimate,
  expense head), `…/quotations` (+ `DELETE`), `…/sanction`, `…/revise-sanction`, `…/issue`, `…/complete`,
  `…/release-retention`, `…/close`, `…/cancel`, `…/pdf`; `GET …/society/{id}?status=`.
- **Sanction** (shared with contracts, `SanctionMixin` columns): one of the quotations; committee resolution no. + date
  always; above the tender limit at least `min_quotations` vendors, `tenders_opened_on`, no quotation dated after it;
  above either limit the general body resolution no. + date (not before the opening); a reason when not the lowest;
  quotation not expired or dated after the meeting; vendor active; `no_interest_declared`; the vendor's mobile/email
  must not be a committee member's (`committee_interest`). Sanctioned amount = the quotation's total; `sanction_level`
  committee / general_body.
- **Money**: bills only once issued, only from its vendor, total ≤ sanctioned (else revise the sanction; the general
  body's again when needed); a bill without an expense head takes the work order's. Payments: before completion up to
  `advance_amount`; after, bills less `retention_pct` until `retention_released_on` (allowed from completion +
  `defect_liability_months`). Close needs every bill paid.
- **Contracts**: `POST /vendors/contracts/{id}/quotations`, `…/sanction` (sets the vendor and `annual_value` from the
  quotation); **activation is refused until sanctioned**. Contract output now includes the sanction, quotations and
  requirements; lists are open to the Manager.
- **Vendor edit** `PATCH /vendors/{id}` (committee): duplicates refused; status active/inactive/under review (blacklist
  only via `/blacklist`, with a reason); leaving blacklisted clears the reason. `pincode` accepted on create.
- **PDF**: the work order on the letterhead with references, scope, value in words, terms, conditions and three
  signature lines (`work_order_pdf.py`).
- **App**: Operations → Vendors & Work (form `vendors`: Admin, committee, Manager) — Work Orders, Contracts, Vendors,
  Limits; work order and contract pages walk through each step. See `docs/GUIDES/VENDOR_MASTERS_COMPLETE_GUIDE.md`.
- Not built: TDS (s.194C) on contractor payments, two-signatory payment approval, contract expiry notifications.

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
| Manage vendors; sanction, issue, certify, release retention, close, cancel work; sanction/start contracts; set limits | Admin, Committee |
| Create work orders and contract drafts, enter quotations and bills, view limits | Admin, Committee, Manager |
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
