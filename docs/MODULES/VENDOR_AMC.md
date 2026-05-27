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

## Finance Readiness
- `annual_value` on contracts
- `actual_cost` vs `estimated_cost` on service requests
- `VendorInvoice` with `gst_amount`, `is_paid`, `payment_ref`
