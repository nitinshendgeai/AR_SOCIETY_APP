# Vendor Masters & Work Order Management Guide
## Complete Workflow for Vendor Contracts and Service Requests

---

## Table of Contents
1. [Overview](#overview)
2. [Vendor Master Setup](#vendor-setup)
3. [Contracts (AMC) Lifecycle](#contracts)
4. [Service Requests (Work Orders)](#service-requests)
5. [Service Visit Tracking](#visits)
6. [Vendor Invoicing & Integration](#invoicing)
7. [Step-by-Step Workflows](#workflows)
8. [Best Practices](#best-practices)

---

## Overview {#overview}

### What is the Vendor Masters Module?

The **Vendor Masters** module manages all relationships between your society and external service providers (vendors). It handles:

1. **Vendor Registration**: Company details, contact, ratings
2. **AMC Contracts**: Annual contracts with vendors (e.g., lift maintenance, security)
3. **Service Requests**: Ad-hoc work orders (e.g., emergency plumbing, repairs)
4. **Service Visits**: Log vendor visits, work completion
5. **Invoicing**: Generate bills from contracts/services, track payments

### Key Concepts

| Term | Meaning | Example |
|------|---------|---------|
| **Vendor** | A service provider (company) | ABC Security Services Pvt Ltd |
| **Service** | A capability a vendor offers | CCTV Maintenance, Lift Service |
| **AMC Contract** | Annual maintenance contract | Lift Maintenance Jan-Dec 2026, ₹60,000/yr |
| **Work Order** (Service Request) | Ad-hoc work order | Fix broken water pipe in wing A |
| **Vendor Invoice** | Bill from vendor to society | Invoice #INV-2026-0042 for ₹5,000 |

### Why Vendor Masters Matter

✅ **Centralized vendor data**: One source of truth for all vendors  
✅ **Contract lifecycle**: Track expiry dates, renewals, SLAs  
✅ **Work order tracking**: Know what's scheduled, in-progress, completed  
✅ **Financial accuracy**: Invoices auto-post to correct expense ledgers  
✅ **Performance metrics**: Track vendor rating, on-time completions  
✅ **Audit trail**: Every visit logged, every payment recorded  

---

## Vendor Master Setup {#vendor-setup}

### Creating a Vendor

**Where**: Admin Panel → Vendors → "Add Vendor"

**Required Information**:

```
Company Details:
├─ Vendor Code: UNQ-001 (auto-generated per society)
├─ Company Name: ABC Security Services
├─ Contact Person: Mr. Rajesh Kumar
├─ Mobile: 9876543210
├─ Email: rajesh@abcsecurity.com
└─ Category: Security [required for matching work orders]

Address:
├─ Street Address: 123 Business Park
├─ City: Mumbai
├─ Pincode: 400001
└─ (Optional but recommended for address on invoices)

Finance (GST-ready):
├─ GST Number: 27AAACR5055K1Z5 (required for billing)
├─ PAN: AAACR5055K (backup identifier)
├─ Bank Account: 10234567890123
├─ Bank Name: HDFC Bank
└─ Bank IFSC: HDFC0001234

Performance:
├─ Rating: (auto-calculated from visits, 1-5 stars)
├─ Insurance Expiry: Date (track when insurance needs renewal)
└─ Notes: "Preferred vendor for lift maintenance"
```

### Vendor Status Transitions

```
ACTIVE (default)
  ├─ INACTIVE: Temporarily unavailable (e.g., on holiday)
  └─ BLACKLISTED: Permanently banned (with reason)

UNDER_REVIEW
  └─ (After inspection/probation, move to ACTIVE or BLACKLISTED)
```

**Blacklisting**: If vendor fails to deliver or breaches contract:
- Go to Vendor detail
- Click "Blacklist" button
- Enter reason: "Missed service for 3 months", "Damaged equipment"
- Reason is logged; cannot hire this vendor until status is changed

### Vendor Services (Capabilities)

Once vendor is created, register their services:

**Where**: Vendor detail → "Add Service"

**Example**:
```
Service 1: CCTV Maintenance
├─ Category: CCTV
├─ Rate per visit: ₹500
└─ Rate per hour: ₹250

Service 2: Lift AMC
├─ Category: Lift
├─ Rate per visit: ₹1,500
└─ Rate per hour: (not applicable)
```

These services are used when:
- Creating AMC contracts (what the vendor will do)
- Assigning work orders (matching vendor capabilities to request)

---

## Contracts (AMC) Lifecycle {#contracts}

### What is an AMC?

**AMC = Annual Maintenance Contract**: A standing agreement with a vendor for regular, scheduled services.

### Creating an AMC Contract

**Where**: Admin Panel → Contracts → "Add Contract"

```
Basic Info:
├─ Contract Number: CTR-2026-001 (auto-generated per society)
├─ Contract Name: "Lift Maintenance Jan-Dec 2026"
├─ Vendor: [Select from dropdown]
├─ Category: Lift Maintenance
└─ Status: Draft (changes to Active when activated)

Duration & Renewal:
├─ Start Date: 01 Jan 2026
├─ End Date: 31 Dec 2026
├─ Auto-Renew: Yes/No [auto-renew before expiry?]
└─ Renewal Notice Days: 30 [send alert 30 days before expiry]

Service Details:
├─ Frequency: Monthly (Weekly/Fortnightly/Monthly/Quarterly/Half-yearly/Yearly/On-call)
├─ SLA Response Hours: 24 [if emergency, vendor must respond within 24 hrs]
├─ Scope of Work: "Monthly lift inspection and maintenance"
├─ Inclusions: "Oil top-up, inspection, minor adjustments"
└─ Exclusions: "Motor replacement, major repairs (billed separately)"

Finance:
├─ Annual Value: ₹60,000
├─ Payment Terms: "Net 15" [pay within 15 days of invoice]
└─ Document URL: [Attach signed contract PDF]
```

### Contract Status Flow

```
1. DRAFT (Created but not yet active)
   ↓ [Click "Activate"]
2. ACTIVE (Services are scheduled and happening)
   ↓ [At end date, either:]
   ├─→ EXPIRED (No renewal)
   ├─→ RENEWED (Continuation contract created, old marked RENEWED)
   └─→ TERMINATED (Cancelled early due to breach or vendor failure)
```

### Auto-Schedule Services

Once activated, AMCs can auto-generate visit schedules:

**Where**: Contracts list → [Select contract] → "Generate Schedule"

```
Result:
├─ If Monthly: Creates 12 visits (Jan-Dec)
├─ If Quarterly: Creates 4 visits (Q1, Q2, Q3, Q4)
└─ If Yearly: Creates 1 visit

Each visit gets:
├─ Scheduled Date: 1st of month (configurable)
├─ Status: SCHEDULED (ready to notify vendor)
└─ Linked to contract for tracking
```

### Contract Alerts

The system auto-sends alerts:

| Days Before Expiry | Alert | Action |
|---|---|---|
| 60 days | Email to procurement | Consider renewal documents |
| 30 days | SMS + In-app | Urgent: decide renewal or replacement |
| 7 days | Escalated alert | Last chance to activate renewal |
| 0 days | Marked EXPIRED | Contract ends, services stop being scheduled |

---

## Service Requests (Work Orders) {#service-requests}

### What is a Service Request?

**Service Request** = Work order for ad-hoc, non-contracted services.

**Examples**:
- Emergency plumbing (pipe burst)
- Broken CCTV camera replacement
- Painting common areas
- Pest control (one-off, not on contract)

### Creating a Service Request

**Where**: Admin Panel → Service Requests → "Create Request"

```
Request Details:
├─ Title: "Fix broken water pipe in Wing A"
├─ Description: "Main supply line leaking in basement, needs urgent welding"
├─ Category: Plumbing [auto-filters vendors with plumbing capability]
├─ Priority: Critical/High/Medium/Low
├─ Location: "Wing A, Basement, Near pump house"
└─ Preferred Date: ASAP / [pick date]

Linking:
├─ Linked Complaint: [Optional - if from a resident complaint]
├─ Linked Asset: [Optional - if asset maintenance]
└─ (Auto-fills some fields from link)

Financials (Initial estimate):
├─ Estimated Cost: ₹3,000
└─ (Actual cost determined when vendor completes)

Status: OPEN (ready for assignment)
```

### Service Request Lifecycle

```
1. OPEN (Created, waiting for vendor assignment)
   ↓ [Assign vendor]
2. ASSIGNED (Vendor accepted, scheduling in progress)
   ↓ [Vendor confirms date]
3. SCHEDULED (Date fixed, vendor arrives on scheduled_date)
   ↓ [Vendor arrives]
4. IN_PROGRESS (Vendor is working)
   ↓ [Vendor completes]
5. COMPLETED (Work done, awaiting verification)
   ↓ [Inspector verifies]
6. VERIFIED (Approved, waiting closure)
   ↓ [Admin closes]
7. CLOSED (Final status, invoice generated)
   ↓ [Optional: reversal if reopened]

Alternative paths:
├─ CANCELLED (Any status → stopped)
└─ [Can move back for rework]
```

### Assigning Vendor to Work Order

**Where**: Service Request detail → "Assign Vendor"

```
System shows:
├─ Category matched: Plumbing
├─ Vendors with capability: [List with ratings]
│  ├─ ABC Plumbing (4.5 stars, on-time: 95%)
│  ├─ XYZ Pipe Works (3.8 stars, on-time: 80%)
│  └─ Quick Plumbing (4.0 stars, on-time: 100%)
│
├─ Click "Assign" to vendor
├─ System sends: SMS + In-app notification + WhatsApp
└─ Vendor confirms acceptance

Behind the scenes:
├─ SLA due date calculated (start_date + 24 hours for emergency)
├─ Over-SLA flag triggers if not completed by due date
└─ On-time completion %age updates for vendor rating
```

---

## Service Visit Tracking {#visits}

### Logging a Vendor Visit

After vendor completes work, log the visit:

**Where**: Service Request detail → "Add Visit Log"

```
Visit Details:
├─ Visit Date: [Date work was done]
├─ Check-in Time: [When vendor arrived]
├─ Check-out Time: [When vendor left]
├─ Work Done: "Welded main pipe, tested pressure, all OK"
├─ Materials Used: "Welding rods (5 pcs), epoxy sealant (1 tube)"
├─ Next Visit Date: [If follow-up needed, e.g., 1 week]
├─ Photo: [Upload before/after photos]
└─ Is Satisfactory: Yes/No [quality check]
```

### Vendor Rating Calculation

After each visit, vendor rating updates:

```
Rating = (Services On-Time / Total Services) × 5

Example:
├─ Vendor has completed 10 services
├─ 9 completed on-time (before SLA)
├─ 1 delayed (after SLA)
└─ Rating = (9/10) × 5 = 4.5 stars
```

Use ratings when:
- Assigning future work orders (prioritize high-rated vendors)
- Renewing contracts (don't renew low-rated vendors)
- Blacklisting (if rating falls below 2 stars, consider action)

---

## Vendor Invoicing & Integration {#invoicing}

### How Invoices Connect to Accounting

When vendor invoice is recorded:

```
1. Committee receives paper invoice from vendor
2. Finance admin enters in app: Vendor Bills → Record Invoice
3. System creates VendorInvoice record with:
   ├─ Invoice number & date
   ├─ Amount & GST
   ├─ Vendor & linked contract/request
   ├─ Expense ledger (from ledger-element linking)
   └─ Payment status tracking

4. Journal entry posts automatically:
   ├─ Debit: Expense ledger (e.g., Plumbing Repairs)
   ├─ Credit: Accounts Payable
   └─ Audit logged with timestamp & approver

5. Payment recorded: Finance → Payments → Vendor Payment
   ├─ System shows: Amount due, partial payment tracking
   ├─ Records: Payment date, mode, reference
   └─ Marks invoice as PAID when paid_amount = total_amount
```

### Linking Invoices to Ledgers

By default, vendor invoice amount posts to the ledger matching vendor **category**:

| Vendor Category | Default Ledger |
|---|---|
| Lift | Lift Maintenance Expenses |
| Plumbing | Plumbing Repair Expenses |
| Electrical | Electrical Repair Expenses |
| Security | Security Charges |
| Housekeeping | Housekeeping Expenses |
| etc. | [Per chart of accounts] |

**Can override**: When entering invoice, select different ledger if needed (e.g., emergency repair → Budget Reserve Fund instead).

### Invoices as Budget Expense Source

Vendor invoices feed into **"Budget from Expenses"** calculations:

```
Example workflow:
1. Record all plumbing vendor invoices (Jan-Dec): ₹25,000
2. System links to "Plumbing Repairs" ledger
3. When setting up maintenance charges:
   └─ Committee clicks "Suggest from Expenses"
   └─ System shows: "Plumbing spending: ₹25,000"
   └─ Suggests amount per flat for next cycle
4. Charges can auto-bill from this ledger amount
```

---

## Step-by-Step Workflows {#workflows}

### Workflow 1: Setting Up Annual Lift Maintenance Contract

```
Month: September (contract renewal season)

Step 1: Register/Update Vendor
├─ Admin → Vendors → Find "Lift Masters Inc"
├─ Verify GST, bank details (for invoices)
├─ Rate as ACTIVE status
└─ Confirm they offer "Lift Maintenance" service

Step 2: Create AMC Contract
├─ Admin → Contracts → "Add Contract"
├─ Name: "Lift Maintenance Jan-Dec 2026"
├─ Select Vendor: Lift Masters Inc
├─ Dates: 01-Jan-2026 to 31-Dec-2026
├─ Frequency: Monthly
├─ Annual Value: ₹60,000 (₹5,000/month)
├─ Payment Terms: Net 15
├─ Upload signed contract PDF
├─ Auto-Renew: Yes
└─ Status: Save as DRAFT

Step 3: Activate Contract
├─ Contracts list → Select contract
├─ Click "Activate"
└─ Status changes to ACTIVE

Step 4: Generate Schedule
├─ Same contract detail
├─ Click "Generate Schedule"
├─ System creates 12 monthly visits (Jan 1, Feb 1, ... Dec 1)
├─ Each scheduled_date is configurable
└─ Vendor notified of schedule

Step 5: Monthly Invoice Cycle
├─ Vendor submits invoice (usually on scheduled date):
│  └─ Invoice #LM-2026-0042 for ₹5,000 + GST
│
├─ Admin records: Finance → Vendor Bills
│  ├─ Select Vendor: Lift Masters Inc
│  ├─ Enter invoice details
│  └─ Expense Ledger: Auto-filled "Lift Maintenance"
│
├─ Approval: Committee approves invoice
│  └─ Posting: Debit Lift Maintenance, Credit A/P
│
├─ Payment: Finance → Payments
│  ├─ Record payment on Net 15 date
│  └─ Mark invoice PAID

Step 6: Annual Review (Nov/Dec)
├─ Contracts → "Expiring Contracts"
├─ See: Lift Maintenance expires Dec 31
├─ Alerts sent 60d, 30d, 7d before
├─ Decision:
│  ├─ RENEW: Create new contract, mark old as RENEWED
│  ├─ RENEGOTIATE: Change terms, create new contract
│  └─ TERMINATE: Find new vendor, mark TERMINATED
└─ Next cycle repeats
```

### Workflow 2: Emergency Pipe Burst Service Request

```
Scenario: Wing A basement pipe bursts, water flooding

Step 1: Raise Service Request
├─ Supervisor discovers leak
├─ Admin Panel → Service Requests → "Create Request"
├─ Title: "Urgent: Water pipe burst Wing A basement"
├─ Category: Plumbing
├─ Priority: CRITICAL
├─ Preferred Date: TODAY
└─ Save as OPEN

Step 2: Assign Vendor
├─ Admin notified (in-app alert)
├─ System shows Plumbing vendors sorted by:
│  ├─ Rating (highest first: 4.5+ stars)
│  └─ On-time completion %
├─ Admin selects: "Quick Fix Plumbing" (highest rated)
├─ System sends: Instant SMS + WhatsApp to vendor
└─ Vendor confirms: "Arriving in 30 min"
└─ Request moves to ASSIGNED

Step 3: Vendor Arrives & Works
├─ Vendor arrives ~30 min later
├─ Work begins: diagnose, repair, test
├─ Estimated cost ₹3,000 (vs ₹3,000 estimate = OK)
└─ Work completes: 2 hours later

Step 4: Log Visit & Complete
├─ Vendor or supervisor logs visit:
│  ├─ Visit Date: Today
│  ├─ Check-in: 14:00, Check-out: 16:00
│  ├─ Work Done: "Main line welding, pressure tested OK"
│  ├─ Materials: "Welding materials, sealant"
│  └─ Satisfactory: YES
│
├─ Request moves to COMPLETED
└─ Vendor rating updated: +1 on-time service

Step 5: Invoice & Payment
├─ Next day, vendor submits invoice ₹3,000 + GST
├─ Admin records invoice:
│  ├─ Expense Ledger: "Plumbing Repair"
│  └─ Linked to Service Request for audit
│
├─ Approval: Committee approves
│  └─ Posting: Debit Plumbing Repair, Credit A/P
│
├─ Finance records payment (UPI transfer)
└─ Invoice marked PAID

Step 6: Expense Tracking
├─ Monthly: Finance summary shows
│  ├─ Total plumbing repairs: ₹3,500 (this one + others)
│  └─ Annualized: ₹42,000/year
│
├─ Next maintenance cycle:
│  └─ Committee can allocate for preventive maintenance budget
└─ Audit trail complete: Request → Visit → Invoice → Payment
```

---

## Best Practices {#best-practices}

### 1. Vendor Selection
✅ **Prefer rated vendors**: Use high-rated vendors (4+ stars) for critical services  
✅ **Diversify**: Don't depend on single vendor for critical services  
✅ **Check credentials**: Verify GST, insurance, qualifications before hiring  
✅ **Reference checks**: Contact previous societies the vendor worked for  

### 2. Contract Management
✅ **Always use contracts for recurring services**: No verbal agreements  
✅ **Include SLA clauses**: Define response time, quality standards, penalties  
✅ **Annual review**: Evaluate vendor performance before renewal  
✅ **Document everything**: Attach signed PDFs, payment terms, scope  
✅ **Set auto-renew reminders**: Don't let contracts lapse unexpectedly  

### 3. Service Request Tracking
✅ **Close request only after verification**: Not after just completion  
✅ **Log all visits**: Even if vendor says "nothing to do", log it for proof  
✅ **Use priority levels**: Don't mark everything as CRITICAL  
✅ **Track response time**: Use SLA to identify delayed vendors  

### 4. Financial Accuracy
✅ **Record all invoices**: Even partial payments or credits  
✅ **Link to service requests**: Audit trail from work → invoice → payment  
✅ **Use correct ledgers**: Ensure expenses go to right budget categories  
✅ **GST compliance**: Collect GST certificate & number from all vendors  

### 5. Performance Management
✅ **Monitor vendor ratings**: Review quarterly  
✅ **Track on-time completion**: Use for contract renewal decisions  
✅ **Use ratings for assignment**: Let data drive vendor selection  
✅ **Blacklist systematically**: Document reason, give notice before blacklisting  

### 6. Legal Compliance
✅ **Contracts signed by both parties**: Keep originals with society  
✅ **Insurance verification**: Check annual; many contracts require vendor insurance  
✅ **Tax compliance**: Collect GST numbers; match with Tax Authority database  
✅ **Work safety**: Require vendor to follow safety protocols (logged in visit notes)  

---

## Financial Impact Summary

### Expense Control Through Vendor Masters

```
Without proper vendor management:
├─ Duplicate payments: ₹X lost
├─ Untracked work: How much did we really spend on maintenance?
├─ Poor vendor performance: Same vendor repeats mistakes
├─ Audit failures: "We can't prove this work was done"
└─ Cost: ₹HighCost

With Vendor Masters:
├─ Single source of truth: All vendor data centralized
├─ Expense tracking: Every rupee linked to work order
├─ Performance metrics: Data-driven vendor selection
├─ Audit ready: Complete trail from request → visit → payment
├─ Contract management: Never pay more than agreed
└─ Result: 15-20% savings on maintenance costs
```

### Integration Points

```
Vendor Masters integrates with:

1. Chart of Accounts
   └─ Vendor invoices post to expense ledgers
   └─ Ledger-element links feed "Budget from Expenses"

2. Maintenance Billing
   └─ Vendor expense data becomes basis for maintenance charges
   └─ Committee reviews actual spending to adjust future bills

3. Inventory Module
   └─ Vendor services link to asset maintenance
   └─ AMC schedules track asset health

4. Complaints & Issues
   └─ Service Requests linked to resident complaints
   └─ Tracks: Complaint → Work Order → Resolution
```

---

## Next Steps

1. **Add your first vendor**: Admin → Vendors → Create Vendor
2. **Set up annual contracts**: For each recurring service (lift, security, etc.)
3. **Create AMC schedules**: Auto-generate monthly visits
4. **Log first service request**: Test workflow with ad-hoc repair
5. **Record vendor invoice**: Complete the accounting cycle
6. **Review vendor ratings**: After 10+ services, data-driven metrics emerge

Your Vendor Masters is now the nerve center of all external service management.
