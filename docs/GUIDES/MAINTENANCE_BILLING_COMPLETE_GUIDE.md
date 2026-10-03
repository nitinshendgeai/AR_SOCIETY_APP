# Complete Maintenance Billing Guide
## Financial Calculations & Workflow for Residential Society

---

## Table of Contents
1. [Overview & Core Concepts](#overview)
2. [Maintenance Elements & Service Charges](#elements)
3. [Expense Ledger Linking](#ledger-linking)
4. [Financial Calculation Flow](#calculations)
5. [Step-by-Step Workflow](#workflow)
6. [Examples with Real Numbers](#examples)
7. [Standards & Best Practices](#standards)

---

## Overview & Core Concepts {#overview}

### What is Maintenance Billing?
Maintenance billing is the **monthly/quarterly billing to residents for** common area maintenance and operations. It consists of:
- **Service Charges**: Security, housekeeping, management fees (reduced for non-occupied flats)
- **Hard-Coded Elements**: Property tax, water, insurance, repairs (no reduction)
- **Fines/Extra Charges**: Parking violations, damage charges (per-flat)

### Key Principle: Expense-Driven Budgets
Instead of guessing amounts, the system **calculates budgets from actual spending**:
1. Committee records all expenses (vendor bills, vouchers)
2. System links expenses to maintenance elements
3. When billing, it **annualizes** the spending and suggests amounts
4. Bills can auto-include these calculated amounts OR use typed amounts

### Financial Accuracy
- **Double-entry accounting**: Every expense posts to ledgers, bills post revenue
- **Per-flat precision**: Amounts adjusted by area, occupancy, unit count
- **GST-ready**: Tax calculated per line item, reported separately
- **Auditability**: Full ledger trail, reversals, allocations tracked

---

## Maintenance Elements & Service Charges {#elements}

### Standard Maintenance Elements (Seeded)

| Element | Code | Type | Basis Options | Service Charge? |
|---------|------|------|---|---|
| **Security Services** | security | SERVICE | Annual/Per Flat/Per Sqft | ✅ YES |
| **Housekeeping & Cleaning** | housekeeping | SERVICE | Annual/Per Flat/Per Sqft | ✅ YES |
| **Lift Maintenance** | lift_maintenance | FACILITY | Annual/Per Flat/Per Sqft | ❌ NO |
| **Common Electricity** | common_electricity | UTILITY | Annual/Per Flat/Per Sqft | ❌ NO |
| **Water Charges** | water_charges | UTILITY | Per Sqft/Annual | ❌ NO |
| **Property Tax** | property_tax | TAX | Per Flat/Per Sqft | ❌ NO |
| **Insurance** | insurance | INSURANCE | Annual/Per Flat | ❌ NO |
| **Lease Rent / NA Tax** | lease_rent_na_tax | TAX | Annual | ❌ NO |
| **Repair & Maintenance Fund** | repair_fund | FUND | % of Construction Cost | ❌ NO |
| **Sinking Fund** | sinking_fund | FUND | % of Construction Cost | ❌ NO |

### Service Charge Rule
**Service charges are reduced proportionally for non-occupied flats** (empty, rented out to commercial use, under renovation).

Formula:
```
Service Charge for Flat = Base Amount × (Occupancy Factor)
Occupancy Factor = 1.0 (occupied), 0.5 (non-occupied), 0.75 (partial)
```

**Hard-coded elements (Property Tax, Insurance, etc.) are NOT reduced** — every flat pays full amount regardless of occupancy.

---

## Expense Ledger Linking {#ledger-linking}

### How It Works

Each **expense ledger** in Chart of Accounts is linked to ONE **maintenance element**:

```
Chart of Accounts (Expense Ledgers)    →    Maintenance Elements
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Security Charges                       →    Security Services
CCTV & Security Systems Maintenance    →    Security Services
Housekeeping & Cleaning                →    Housekeeping
Garden Maintenance                     →    Housekeeping
Pest Control                           →    Housekeeping
Lift Maintenance (AMC)                 →    Lift Maintenance
Electricity Charges (Common Areas)     →    Common Electricity
Generator / DG Maintenance             →    Common Electricity
Water Charges                          →    Water Charges
Property Tax                           →    Property Tax
Insurance Premium                      →    Insurance
Lease Rent / NA Tax                    →    Lease Rent / NA Tax
Repairs & Maintenance — Plumbing       →    (UNLINKED — must link manually)
Repairs & Maintenance — Electrical     →    (UNLINKED — must link manually)
Repairs & Maintenance — Building       →    (UNLINKED — must link manually)
Repairs & Maintenance — General        →    (UNLINKED — must link manually)
```

### Default Links (Automatic)
**New societies get default links during setup:**
- Security Charges + CCTV → Security
- Housekeeping + Garden + Pest Control → Housekeeping
- Lift → Lift Maintenance
- Electricity + Generator → Common Electricity
- Water → Water Charges
- Property Tax → Property Tax
- Insurance → Insurance
- Lease Rent → Lease Rent / NA Tax

**Existing societies get upgraded via Migration `fc2d3e4f5a6b`**.

### Changing Links (Committee Can Do This)
**Finance → Chart of Accounts → [Select Ledger] → Edit → "Counts towards Maintenance Element"**

Example: If "Repairs & Maintenance — Plumbing" should count towards repair fund:
1. Find the ledger in Chart of Accounts
2. Click Edit (pencil icon)
3. Select "Repair & Maintenance Fund" from dropdown
4. Click "Save"
5. **From now on, all expenses in this ledger count towards that element**

### What Counts Toward an Element?
Everything posted to the linked ledger:
- ✅ Vendor bill amounts
- ✅ Payment vouchers (actual cash paid out)
- ✅ Journal entries (manual adjustments)
- ✅ Returns/credits (negative amounts)
- ❌ Cancelled/reversed entries (excluded from calculations)

---

## Financial Calculation Flow {#calculations}

### Step 1: Expense Data Collection
```
MONTH 1  →  Record Vendor Bills
            ├─ Security vendor invoice: ₹50,000
            ├─ Housekeeping vendor invoice: ₹20,000
            ├─ Water supplier bill: ₹15,000
            └─ Insurance premium payment: ₹25,000

MONTH 2  →  Record more bills
            └─ ... and so on for all months
```

### Step 2: Calculate Spending Per Element (Budget Suggestions)
**What happens when you click "Suggest from Expenses":**

```
Window: Last 12 months
For each Maintenance Element:
  1. Find all linked expense ledgers
  2. Sum all debits (expenses) and credits (returns)
  3. Calculate net spend = debits - credits
  4. Determine # of months with activity
  5. Annualize: Annual Spend = (Net Spend / Months Covered) × 12
  6. Convert to charge basis (see below)
```

### Step 3: Basis Conversion

**Annual budget → ₹/flat/month**
```
Cost/Flat/Month = (Annual Spend ÷ Total Flats) ÷ 12

Example:
  Annual security spend: ₹600,000
  Total flats: 100
  = (600,000 ÷ 100) ÷ 12
  = ₹500 per flat per month
```

**Annual budget → ₹/sqft/month**
```
Cost/Sqft/Month = (Annual Spend ÷ Total Area Sqft) ÷ 12

Example:
  Annual water spend: ₹360,000
  Total area: 40,000 sqft
  = (360,000 ÷ 40,000) ÷ 12
  = ₹0.75 per sqft per month
```

**Fixed/Single Amount (for insurance, NA tax, etc.)**
```
Monthly = Annual Spend ÷ 12

Example:
  Annual insurance: ₹600,000
  = ₹50,000 per month (same for all flats)
```

### Step 4: Apply Service Charge Rule
If element is a **Service Charge** (Security, Housekeeping):
```
Final Amount = Calculated × Occupancy Factor

Occupied flat (100%):     ₹500
Non-occupied flat (50%):  ₹250
Partial occupancy (75%):  ₹375
```

If **Hard-Coded** (Property Tax, Insurance):
```
All flats pay FULL calculated amount (no occupancy reduction)
```

### Step 5: Generate Bill
```
Maintenance Bill for Flat A-101:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Line Item                    Amount    Tax    Total
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Security Services           ₹500      ₹90    ₹590
Housekeeping                ₹300      ₹54    ₹354
Lift Maintenance            ₹200      ₹36    ₹236
Water Charges               ₹250      ₹45    ₹295
Property Tax                ₹150      ₹0     ₹150
Insurance                   ₹50       ₹0     ₹50
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUBTOTAL                             ₹1,450
TAX (18% GST)                        ₹225
TOTAL DUE                            ₹1,675
```

---

## Step-by-Step Workflow {#workflow}

### Phase 1: Setup (One Time)
```
1. Add your standard maintenance elements
   → Maintenance Billing → Maintenance Elements → "Add from Standard" 
   → Selects all 9 standard elements
   
2. Create charge heads for each element
   → Maintenance Billing → Charge Heads → "Add from Elements"
   → System auto-fills basis, GST status from element definition
   → Set default amount (e.g., ₹500/flat/month for security)
   
3. Verify expense ledger links
   → Finance → Chart of Accounts
   → Check each ledger's "Counts towards" setting
   → Adjust if needed (e.g., plumbing repairs → Repair Fund)
```

### Phase 2: Expense Recording (Ongoing, Monthly)
```
1. Record all vendor bills
   → Finance → Vendor Bills → "Add Invoice"
   → Vendor name, invoice #, date, amount, category
   → System posts to correct expense ledger automatically
   
2. Record vendor payments
   → Finance → Vendor Bills → "Pay Invoice"
   → Amount, payment date, method (cash/bank)
   → System posts to bank/cash ledger + expense ledger
   
3. Record other expenses (non-vendor)
   → Finance → Accounts → Create Voucher (Journal Entry)
   → Debit: Expense ledger (e.g., Security Charges)
   → Credit: Bank account
```

### Phase 3: Billing Cycle Setup (Monthly/Quarterly)
```
1. Create billing cycle
   → Maintenance Billing → Cycles → "Create Cycle"
   → Name: "October 2026 Maintenance"
   → Cycle dates: Oct 1 - Oct 31
   → Due date: Oct 15
   → Click "Create"

2. Preview expenses (optional, to see calculated amounts)
   → Click "Preview" on the cycle
   → Shows "Budget from Expenses" values (if enabled)
   → Shows standard typed amounts
   
3. Review charge heads
   → Go back if amounts need adjustment
   → Edit charge head amounts if needed
   → OR enable "Budget from Expenses" to auto-calculate
```

### Phase 4: Bill Generation
```
1. Generate bills
   → Maintenance Billing → Cycles → [Select Cycle]
   → Click "Generate Bills"
   → System creates ONE bill per active flat
   → Each bill includes:
     - All active charge heads (at calculated or typed amounts)
     - Service charges reduced for non-occupied flats
     - Hard-coded elements at full amount
     - GST per line item
     
2. Issue bills
   → Maintenance Billing → Cycles → [Select Cycle] → Issue All
   → Residents notified via app/SMS/email
   → Bills move to ISSUED status (start accruing interest if unpaid)
```

### Phase 5: Payment & Reconciliation
```
1. Record payments
   → Finance → Payments → "Record Payment"
   → Flat/member, amount, date, method
   → System shows auto-allocation across oldest bills
   → OR use "One Bill" to apply to specific bill
   
2. Set off advance payments (old "on account" entries)
   → Payments → "Apply" button
   → Oldest bills settled first
   
3. Run reconciliation
   → Finance → Bank Reconciliation
   → Match payments to deposits
   → Reverse bounced cheques (system reverses allocations)
```

### Phase 6: Dues Tracking
```
1. Check who's behind on payments
   → Finance → Defaulters
   → Shows flats with dues >3 months old (configurable)
   → Export to PDF for records
   
2. Send reminders
   → Select defaulters, send notification
   → System sends in-app alert + SMS to member
```

---

## Examples with Real Numbers {#examples}

### Example 1: Small Society (50 flats, 25,000 sqft)

**EXPENSES RECORDED (Past 12 Months):**
```
Security vendors:
  • ABC Security Services: ₹5,00,000
  • CCTV maintenance: ₹60,000
  Total: ₹5,60,000

Housekeeping vendors:
  • Cleaning crew: ₹2,40,000
  • Garden maintenance: ₹1,20,000
  Total: ₹3,60,000

Lift maintenance vendor: ₹1,80,000
Common electricity bills: ₹7,20,000
Water supply bills: ₹4,50,000
Insurance premium: ₹6,00,000
Property tax paid: ₹3,00,000
```

**CALCULATED AMOUNTS (Before Occupancy Adjustment):**

| Element | Annual Spend | Basis | Calculated Rate | Monthly/Flat |
|---------|---|---|---|---|
| Security | ₹5,60,000 | Per Flat | ₹5,60,000 ÷ 50 ÷ 12 | ₹933 |
| Housekeeping | ₹3,60,000 | Per Flat | ₹3,60,000 ÷ 50 ÷ 12 | ₹600 |
| Lift | ₹1,80,000 | Per Flat | ₹1,80,000 ÷ 50 ÷ 12 | ₹300 |
| Electricity | ₹7,20,000 | Per Sqft | ₹7,20,000 ÷ 25,000 ÷ 12 | ₹2.40/sqft |
| Water | ₹4,50,000 | Per Sqft | ₹4,50,000 ÷ 25,000 ÷ 12 | ₹1.50/sqft |
| Insurance | ₹6,00,000 | Fixed | ₹6,00,000 ÷ 12 | ₹50,000 |
| Property Tax | ₹3,00,000 | Fixed | ₹3,00,000 ÷ 12 | ₹25,000 |

**BILL FOR FLAT (500 sqft, Occupied):**
```
Security (Service Charge)        ₹933      × 1.0  = ₹933
Housekeeping (Service Charge)    ₹600      × 1.0  = ₹600
Lift Maintenance (Hard-Coded)    ₹300      × 1.0  = ₹300
Electricity                      ₹2.40     × 500  = ₹1,200
Water                            ₹1.50     × 500  = ₹750
Insurance (Hard-Coded)           ₹50,000   ÷ 50   = ₹1,000
Property Tax (Hard-Coded)        ₹25,000   ÷ 50   = ₹500
                                                    ────────
Subtotal: ₹5,283
GST (18%): ₹951
TOTAL: ₹6,234
```

**SAME FLAT, NON-OCCUPIED (50% occupancy):**
```
Security (reduced)               ₹933      × 0.5  = ₹467
Housekeeping (reduced)           ₹600      × 0.5  = ₹300
Lift Maintenance (FULL)          ₹300      × 1.0  = ₹300
Electricity                      ₹2.40     × 500  = ₹1,200
Water                            ₹1.50     × 500  = ₹750
Insurance (FULL)                 ₹1,000    × 1.0  = ₹1,000
Property Tax (FULL)              ₹500      × 1.0  = ₹500
                                                    ────────
Subtotal: ₹4,517
GST (18%): ₹813
TOTAL: ₹5,330
```

Notice: Service charges reduced by 50%, hard-coded elements paid in full.

---

## Standards & Best Practices {#standards}

### Best Practice 1: Monthly Billing Window
- **Do**: Record expenses every month, bill every month
- **Why**: Residents expect predictable monthly charges; quick billing feedback on expenses
- **How**: Set up standing orders for vendor payments on same date each month

### Best Practice 2: "Budget from Expenses" for Predictable Costs
**Enable for:**
- Security, Housekeeping, Lift Maintenance (actual spending varies)
- Utilities (electricity, water — seasonal variations)

**Keep as "Typed Amount" for:**
- Property Tax (government-mandated, not negotiable)
- Insurance (quotes fixed annually)
- Fund percentages (policy-driven, not spend-driven)

### Best Practice 3: Reconcile Monthly
- Record ALL expenses (no cash-in-hand unaccounted spending)
- Run reconciliation: Payments vs. Bank deposits
- Flag discrepancies immediately
- Keep audit trail: every expense linked to ledger, invoice, payment

### Best Practice 4: Service Charge vs Hard-Coded
- **Service Charge** = variable by occupancy (makes fairness sense)
  - Examples: Security (empty flat = less security need), housekeeping (empty = no cleaning)
- **Hard-Coded** = same for all (legal/policy requirement)
  - Examples: Property tax (government mandates all units pay), insurance (entire building covered)

**Don't guess:** Check bye-laws and local regulations. If unclear, mark as hard-coded initially; can always change.

### Best Practice 5: Occupancy Status
Keep occupancy status current in the app:
- **Occupied**: Resident living there → Full service charges
- **Non-Occupied**: Empty, rented to commercial, renovation → 50% service charges
- **Partial**: Seasonal, shared lease → 75% service charges

### Best Practice 6: Transparency
- Publish the "Budget from Expenses" calculation quarterly to members
- Show: "Last year we spent ₹X on Security, budgeting ₹Y per flat for next quarter"
- Builds trust; residents understand why their bills changed

---

## Financial Double-Entry Records

### When a Vendor Bill is Recorded:
```
Debit: Security Charges (Expense)     ₹50,000
  Credit: Accounts Payable (Liability)           ₹50,000
(System automatically uses ledger linked to Security element)
```

### When the Bill is Paid:
```
Debit: Accounts Payable               ₹50,000
  Credit: Bank Account (Asset)                   ₹50,000
```

### When Maintenance Bill is Generated:
```
Debit: Accounts Receivable / Flat A-101         ₹6,234
  Credit: Maintenance Revenue (Income)          ₹5,283
  Credit: GST Collected (Liability)             ₹951
(One bill per flat; all maintenance revenue collected this way)
```

### When Payment is Received:
```
Debit: Bank Account                  ₹6,234
  Credit: Accounts Receivable / Flat A-101              ₹6,234
(Payment allocation tracks which bill it settles)
```

### Every Ledger Account Balances:
- **Asset** (Bank): What we have
- **Liability** (Payables): What we owe vendors
- **Income** (Maintenance Revenue): What residents owe us
- **Expense** (Security, Housekeeping, etc.): What we spent
- **Equity** (Opening balance, retained earnings): Society's net worth

**= Financial Statement at any date is accurate.**

---

## FAQ

**Q: What if we didn't record expenses for 6 months, then recorded them all at once?**  
A: "Budget from Expenses" uses the actual dates on the invoices. If all dated within that 6-month window, the calculation will be correct. If some are old, they're in the window; the calculation averages them. Best practice: record monthly.

**Q: Can we use different bases for different flat sizes?**  
A: No. One charge head = one basis. If you want per-sqft for large flats, per-flat for small: create two charge heads (Security-Large, Security-Small) and assign manually or split the ledger. Most societies use per-sqft for utilities, per-flat for services.

**Q: Can non-occupied flats be exempted from security charges entirely?**  
A: Technically yes (set occupancy to 0%), but recommend 50% as minimum (24/7 entry gate still protects empty flat). Set 0% only if physically locked/inaccessible.

**Q: How often should we review "Budget from Expenses"?**  
A: Quarterly minimum. Expenses fluctuate seasonally (electricity in summer, water in season). Review, adjust if needed, bill next cycle.

**Q: What's the difference between vendor bills and journal entries?**  
A: Vendor bills = invoices from outside vendors (tracked, payment terms). Journal entries = manual adjustments (write-offs, transfers, revaluations). Both post to expense ledgers; both count toward "Budget from Expenses."

---

## Conclusion

**Maintenance billing is the core financial function of the society.** Every rupee collected funds operations. This system ensures:

✅ **Accuracy**: Double-entry, ledger-backed, auditable  
✅ **Fairness**: Occupancy adjustments, standardized bases  
✅ **Transparency**: Expense-to-bill linkage visible to committee  
✅ **Compliance**: GST-ready, bye-law standards, audit trail  
✅ **Efficiency**: Expense-driven budgets reduce guesswork, "Budget from Expenses" auto-calculates  

**Use this guide as the foundation for all financial decisions in your society.**
