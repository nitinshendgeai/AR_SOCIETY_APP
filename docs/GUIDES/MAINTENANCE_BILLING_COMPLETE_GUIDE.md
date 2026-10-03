# Maintenance Billing — Complete Guide

How the app works out each flat's maintenance bill, where every rupee comes from, and the order in which the
committee and manager do things. Written against the code (`backend/app/modules/billing/services/maintenance_calculator.py`,
`budget_suggestions.py`, `standard_elements.py`) and the Maharashtra model bye-laws for co-operative housing
societies (bye-laws 13(c), 65–71). Check figures against your society's registered bye-laws and general body
resolutions — the app lets you set them.

---

## 1. The idea in one picture

```
Vendor bills, payment vouchers, journals
        │  booked to an expense ledger (Accounts → Chart of Accounts)
        ▼
Expense ledger  ──linked to──▶  Maintenance element (Security, Lift, Water …)
                                        │
                                        ▼
                       Charge head (how the element is shared per flat)
                                        │  typed amount, or "budget from expenses"
                                        ▼
Billing cycle ──▶ Maintenance calculator ──▶ one bill per flat
                     + non-occupancy charges (tenant-let flats)
                     + fines / extra charges on that flat
                     + GST (only above the threshold)
                     + interest on arrears
                                        │
                                        ▼
               Issue ──▶ payments set off oldest bill first ──▶ dues & defaulters
```

---

## 2. Maintenance elements (the master list)

**Where:** Finance → Maintenance Elements.

A society starts with these standard elements (it can edit them, deactivate them, or add its own):

| Element | Default way of sharing | Service charge? | Bye-law |
|---|---|---|---|
| Service Charges (office, staff, stationery, audit fees) | Same amount per flat | Yes | 66–67 |
| Common Electricity | Annual budget split equally | Yes | 66–67 |
| Lift Maintenance | Annual budget split equally (every flat, lift users or not) | Yes | 66–67 |
| Security Services | Annual budget split equally | Yes | 66–67 |
| Housekeeping | Annual budget split equally | Yes | 66–67 |
| Property Tax | ₹ per sq ft (as the municipality levies) | No | 66–67 |
| Water Charges | Annual budget split by area | No | 66–67 |
| Repairs & Maintenance Fund | 0.75% a year of the flat's construction cost | No | 67(a)(iii) |
| Sinking Fund | at least 0.25% a year of the flat's construction cost | No | 13(c), 67(a)(v) |
| Parking Charges | Per allotted slot | No | 66–67 |
| Building Insurance | Annual budget split by area | No | 66–67 |
| Lease Rent / NA Tax | Annual budget split by area | No | 66–67 |
| Education & Training Fund | Annual budget split equally | No | 66–67 |
| Amenities / Clubhouse | Same amount per flat | No | — |

**"Service charge" matters for one thing only:** the non-occupancy charge (section 5.2) is a percentage of a
flat's service-charge lines. It does **not** reduce anyone's bill.

---

## 3. Charge heads — how an element becomes a per-flat amount

**Where:** Finance → Maintenance Billing → **Charge Heads**. A charge head is made from an element and picks a
*basis*. The amount you type means something different for each basis:

| Basis | You enter | Per flat per month |
|---|---|---|
| Same for every flat | ₹ per flat per month | the amount |
| Per sq ft | ₹ per sq ft per month | rate × flat area |
| % of construction cost | % per year | flat area × construction cost per sq ft × % ÷ 100 ÷ 12 |
| Annual budget, split equally | ₹ per year | budget ÷ number of active flats ÷ 12 |
| Annual budget, split by area | ₹ per year | budget × flat area ÷ total area ÷ 12 |
| Per parking slot | ₹ per slot per month | rate × the flat's allotted slots |

A quarterly cycle multiplies every monthly figure by 3, half-yearly by 6, yearly by 12.

The **construction cost per sq ft** (architect-certified, excluding land) is set once under **Rules**; the sinking and
repair funds can't be worked out without it, and the preview warns. Flats without an area get ₹0 on area-based heads
(also warned).

---

## 4. Linking expenses to elements ("budget from expenses")

### 4.1 Expense ledgers count towards an element

**Where:** Finance → Accounts → Chart of Accounts → edit an expense ledger → **Counts towards**.

New books come with these links:

| Expense ledger | Counts towards |
|---|---|
| Security Charges, CCTV Maintenance | Security Services |
| Housekeeping, Garden, Pest Control | Housekeeping |
| Lift Maintenance | Lift Maintenance |
| Electricity, Generator Maintenance | Common Electricity |
| Water Charges | Water Charges |
| Property Tax | Property Tax |
| Insurance | Building Insurance |
| Lease Rent | Lease Rent / NA Tax |

Repairs ledgers (plumbing, electrical, building …) are **not linked** — they are usually paid from the Repairs Fund or
are one-off. Link them only if your society recovers them through a monthly head.

Everything posted to a linked ledger counts: vendor bills (Vendor Bills, or bills against a work order), payment
vouchers and journals. Cancelled vouchers don't.

### 4.2 Where vendor spending lands

A vendor's bill is booked to an expense ledger:
1. the expense head chosen on the bill, else
2. the work order's expense head (bills recorded against a work order), else
3. the ledger for the vendor's category.

So a Lift AMC bill lands in *Lift Maintenance*, which counts towards the **Lift Maintenance** element.

### 4.3 Suggest from expenses

**Where:** Charge Heads → **Suggest from expenses**. For each charge head made from an element, the app takes the last
N months (12 by default) of net spend on the linked ledgers and:

1. **Annualises** it: `annual = spent × 12 ÷ months covered`. A society with only 8 months of postings has those 8
   months scaled up to a year, not treated as a year.
2. **Converts** it to the head's unit:
   - Annual budget (equal or by area): `annual`
   - Same for every flat: `annual ÷ flats ÷ 12`
   - Per sq ft: `annual ÷ total area ÷ 12`
   - % of construction cost and parking: not suggested — those are policy rates, not costs to recover.

It also lists expense ledgers with spend that **no element covers**, so nothing is missed. Nothing changes until you
apply a figure.

### 4.4 Budget from expenses (automatic)

On a charge head, switch on **Budget from expenses** and choose the months (1–36). Every preview and bill generation
then uses the spend-based figure instead of the typed amount. If nothing was spent in the window, the typed amount is
used and the preview says so. **Bills already generated are never recalculated.**

---

## 5. What goes on each flat's bill

### 5.1 Charge-head lines
One line per active charge head, worked out as in section 3.

### 5.2 Non-occupancy charges
**Where:** Maintenance Billing → **Rules → Non-occupancy %** (0 by default, at most 10%).

A flat **let out to a tenant** pays this percentage of its **service-charge lines** as an extra line. Owner-occupied and
vacant flats don't. It is an addition, never a discount.

### 5.3 Fines and additional charges on one flat
**Where:** Maintenance Billing → **Fines & Charges**. A fine or extra charge on one flat, with a reason, from an
effective date, once or every bill until an end date. Fines go on the bill as a penalty line (no GST, and no interest
is charged on them); extra charges as their own line, with GST only if marked. Members are notified when one is added.

### 5.4 GST
**Where:** Rules → GST registered / rate / threshold. Only if the society is registered (turnover above ₹20 lakh):
when a flat's monthly GST-able contribution is **more than ₹7,500**, 18% is charged on **all** its GST-able lines (not
just the excess). At or below ₹7,500, no GST.

### 5.5 Interest on arrears
**Where:** Rules → Interest % (12% p.a. simple by default) and grace days. Charged on the unpaid principal of earlier
issued bills from their due date (plus grace), up to this bill's date. Fines and interest itself are not charged
interest.

---

## 6. A worked example

**Society:** 50 flats — 40 of 500 sq ft and 10 of 1,000 sq ft (total 30,000 sq ft). Construction cost ₹2,500/sq ft.
Non-occupancy 10%. Not GST-registered.

| Charge head | Basis | Entered | Flat A-101 (500 sq ft) per month |
|---|---|---|---|
| Service Charges | Same per flat | ₹600 | ₹600.00 |
| Security Services | Budget, equal | ₹5,40,000 / yr | 5,40,000 ÷ 50 ÷ 12 = ₹900.00 |
| Housekeeping | Budget, equal | ₹3,00,000 / yr | ₹500.00 |
| Lift Maintenance | Budget, equal | ₹1,80,000 / yr | ₹300.00 |
| Common Electricity | Budget, equal | ₹2,40,000 / yr | ₹400.00 |
| Water Charges | Budget, by area | ₹3,60,000 / yr | 3,60,000 × 500 ÷ 30,000 ÷ 12 = ₹500.00 |
| Property Tax | Per sq ft | ₹1.20 | 500 × 1.20 = ₹600.00 |
| Repairs & Maintenance Fund | % of cost | 0.75% | 500 × 2,500 × 0.75% ÷ 12 = ₹781.25 |
| Sinking Fund | % of cost | 0.25% | 500 × 2,500 × 0.25% ÷ 12 = ₹260.42 |
| Building Insurance | Budget, by area | ₹60,000 / yr | 60,000 × 500 ÷ 30,000 ÷ 12 = ₹83.33 |
| **Total (owner-occupied)** | | | **₹4,925.00** |

Service-charge lines: 600 + 900 + 500 + 300 + 400 = ₹2,700.
If A-101 is **let to a tenant**: + 10% × 2,700 = **₹270.00** non-occupancy → **₹5,195.00**.

A 1,000 sq ft flat pays the same equal-share lines, and double the area-based ones.

**With budget from expenses:** if the Security Charges and CCTV ledgers show ₹3,60,000 spent over the last 8 months,
annual = 3,60,000 × 12 ÷ 8 = ₹5,40,000, the same Security line as above, now kept in step with what is actually paid
to the security agency.

**GST check:** ₹4,925 is below ₹7,500, so even a registered society charges no GST on this flat.

---

## 7. The monthly routine

| When | Who | Where | What |
|---|---|---|---|
| Once | Committee | Maintenance Elements, Charge Heads, Rules | Elements, heads and amounts as resolved by the general body; construction cost, interest, non-occupancy %, GST |
| Once | Committee | Chart of Accounts | Check each expense ledger's **Counts towards** |
| As work is given | Manager / committee | Vendors & Work | Quotations → sanction → work order → bills (see the Vendor Masters guide) |
| As bills come | Manager | Vendor Bills, or a work order's **Record bill** | Enter every vendor bill with its expense head |
| As payments go | Manager / Treasurer | Vendor Bills → pay | Record each payment (cheque/NEFT, reference) |
| Any time | Committee | Fines & Charges | Fines and extra charges on flats |
| Each cycle | Manager | Maintenance Billing → Cycles | New cycle → **Preview** (warnings!) → **Generate** → **Issue** |
| As money comes | Manager | Payments | Record payments; they settle the oldest bills first; advances go to the next bill |
| Monthly | Treasurer | Bank Reconciliation | Match the bank statement; bounced cheques reopen the bills |
| Monthly | Committee | Defaulters | Dues aged from due date; 3 months overdue = defaulter; send reminders |
| Quarterly | Committee | Charge Heads → Suggest from expenses | Compare spend with what is billed; adjust or switch on budget from expenses |

---

## 8. The books behind it (double entry)

| Event | Debit | Credit |
|---|---|---|
| Bill issued to a flat | Member's account (receivable) | Each income head (maintenance, funds …), GST payable |
| Member pays | Bank / cash | Member's account |
| Vendor bill recorded | Expense ledger (e.g. Lift Maintenance) | Sundry creditors (vendor) |
| Vendor paid | Sundry creditors (vendor) | Bank / cash |
| Fine billed | Member's account | Fines & Penalties |

Every posting can be traced back to the bill, receipt or vendor bill that made it.

---

## 9. Questions

**Do empty flats pay less?** No. The bye-laws share expenses among all members; only tenant-let flats pay *more*
(non-occupancy, up to 10% of service charges).

**Why didn't a charge change after we spent more?** Either the head isn't on **budget from expenses**, the ledger isn't
linked to its element, or the bill was already generated (bills are never recalculated). Use **Suggest from expenses**
to see the figures.

**A one-time repair costs ₹2 lakh — should it go into monthly maintenance?** Usually not. Pay it from the Repairs Fund
(after the sanction the bye-laws require — see the Vendor Masters guide), or levy it separately as the general body
decides.
