# Maintenance Billing — Element-wise Help Manual

A step-by-step manual for setting up maintenance elements, linking them to the accounts, making the day-to-day
entries and generating the bills. It follows the Maharashtra model bye-laws for co-operative housing societies
(bye-laws 13(c), 65–71) and the 2001 Cooperation Department circular on service charges. **Check every rule below
against your society's registered bye-laws and general body (GB) resolutions** — the app lets you set them.

For how the calculator works inside, see `MAINTENANCE_BILLING_COMPLETE_GUIDE.md`.

---

## Part 1 — The idea

```
Vendor bill / voucher → Expense ledger → Element → Charge head → Cycle → Bill per flat
     (Part 4)            (Part 3)        (Part 2)    (Part 5)     (Part 7)
```

1. Money spent is booked to an **expense ledger**.
2. Each expense ledger **counts towards one element** (Security, Lift, Water …).
3. Each element has a **charge head** that says how its cost is shared among flats.
4. A **billing cycle** collects the heads and produces one bill per flat.

If a ledger is not linked to an element, its spend is **never billed** to anyone. Linking is the step people forget.

---

## Part 2 — Elements: which rule for which element

**Where:** Finance & Maintenance → Maintenance Elements. Open a row to edit.

Keep these as the society standard. Leave **Category**, **Bye-law reference**, **Description** and **Active** as they
are, and keep **GST applicable** off unless the society is GST-registered (turnover above ₹20 lakh).

| # | Element | Default calculation | Amount to type | Service charge switch |
|---|---|---|---|---|
| 1 | Service Charges | Same for every flat | blank | **ON** |
| 2 | Property Tax | Per sq ft | blank | off |
| 3 | Water Charges | Annual budget, split by area | blank | off |
| 4 | Common Electricity | Annual budget, split equally | blank | **ON** |
| 5 | Repairs & Maintenance Fund | **% of service charges** (this society) | **0.75** (% of the monthly service charges) | off |
| 6 | Sinking Fund | **% of service charges** (this society) | **0.25** (% of the monthly service charges) | off |
| 7 | Lift Maintenance | Annual budget, split equally | blank | **ON** |
| 8 | Security Services | Annual budget, split equally | blank | **ON** |
| 9 | Housekeeping | Annual budget, split equally | blank | **ON** |
| 10 | Parking Charges | Per parking slot | per the GB resolution | off |
| 11 | Building Insurance | Annual budget, split by area | blank | off |
| 12 | Lease Rent / NA Tax | Annual budget, split by area | blank | off |
| 13 | Education & Training Fund | Annual budget, split equally | blank | off |
| 14 | Amenities / Clubhouse | Same for every flat | only if charged | off |

**Why each rule**

| Group | Elements | Reason |
|---|---|---|
| Running costs of common services, shared **equally per flat** | 1, 4, 7, 8, 9, 13 | The bye-laws share service charges equally, whatever the flat's size. Lift: every flat pays, ground floor included. |
| Levied by area, shared **by built-up area** | 2, 3, 11, 12 | The authority or insurer assesses these by area. |
| Funds, a **% of the monthly service charges** | 5, 6 | This society charges 0.75% and 0.25% of the flat's monthly service-charge lines. (The bye-law default is 0.75% and 0.25% of construction cost a year; use *% of construction cost* if your general body resolved that.) |
| Fixed by the general body | 10, 14 | A rate the GB resolves. |

The **Service charge** switch matters for one thing only: the non-occupancy charge (up to 10%) on tenant-let flats
is a percentage of the service-charge lines. It never lowers anyone's bill.

---

## Part 3 — Linking expense ledgers to elements

**Where:** Finance & Maintenance → Accounts → Chart of Accounts → open an expense ledger → **Counts towards**.

### 3.1 Linked by default
**A new society, and a society whose data was cleaned, starts with all of these already set** — the 14 elements
of Part 2 and the links below — without anyone having to open the screens first. They only need checking, not
doing. (A society created before this change keeps whatever links it has; link the missing ones as in the table.)

| Ledger | Counts towards |
|---|---|
| Security Charges (4101), CCTV & Security Systems Maintenance (4109) | Security Services |
| Housekeeping & Cleaning (4102), Garden Maintenance (4103), Pest Control (4108) | Housekeeping |
| Lift Maintenance (AMC) (4104) | Lift Maintenance |
| Electricity Charges, Common Areas (4201), Generator (DG Set) Maintenance (4110) | Common Electricity |
| Water Charges (4202) | Water Charges |
| Property Tax (4203) | Property Tax |
| Insurance Premium (4204) | Building Insurance |
| Lease Rent / NA Tax (4205) | Lease Rent / NA Tax |
| Salaries & Wages (4001), Audit Fees (4002), Legal & Professional Fees (4003), Printing & Stationery (4004), Postage, Telephone & Internet (4005), Office & General Expenses (4007), Meeting Expenses (4008), Computer & Software Expenses (4009), Miscellaneous Expenses (4303) | Service Charges |

If the wages are of security or housekeeping staff the society employs directly, re-link Salaries & Wages to Security
Services or Housekeeping. Link Bank Charges (4006) to Service Charges only if the committee wants it recovered from
members.

### 3.2 Check these
- A society created before the defaults were added may have the ledgers above unlinked. On **Maintenance Elements**
  tap **Apply standard links**: it links every standard expense ledger that has no link yet to the element in the
  table above, adds any standard element or ledger that is missing, and **never changes a link already set**. Or
  open each ledger → **Counts towards** and set it by hand.

### 3.3 Leave unlinked

| Ledger | Why |
|---|---|
| Repairs & Maintenance — Building, Electrical, Plumbing, General (4105–4107, 4111) | Paid from the Repairs Fund or one-off. Note: **Repairs — Electrical is not the electricity bill.** The monthly bill is 4201. |
| Interest on Loans (4301), Depreciation (4302) | Not recovered from members. |

Link a repairs ledger only if the society recovers it through a monthly head.

### 3.4 Ledgers you may need to create
There is no standard ledger for the **Education & Training Fund** or **Amenities / Clubhouse** costs. If you incur
them, add an expense ledger and link it, or those elements will have no spend.

---

## Part 4 — Making the entries

### 4.1 Every cost must reach the right ledger
A vendor bill is booked to, in this order:

1. the expense head chosen on the bill, else
2. the work order's expense head (bills against a work order), else
3. the ledger for the vendor's category (set in Vendor Masters).

So always choose the **expense head** on the bill, and make sure each vendor's category is right (a lift vendor must
be category Lift). Electricity bills go to **4201**, not to a repairs ledger.

### 4.2 Where to enter
| Cost | Where | Notes |
|---|---|---|
| Vendor invoice | Finance & Maintenance → Vendor Bills, or a work order's **Record bill** | Enter every bill with its expense head. |
| Payment to vendor | Vendor Bills → pay | Record cheque/NEFT and reference. |
| Cost with no vendor bill (electricity bill, tax) | Accounts → payment voucher | Choose the expense ledger. |
| Month-by-month standing expenses | Recurring expenses | Shows as due each month; nothing posts until someone confirms it. |

### 4.3 Dates and approval decide what is billed
Only expenses that are **approved** and **dated inside the cycle** (first to last day) count for a head that bills
actual expenses. Pending, rejected, cancelled and reversed vouchers are left out.

- By default a payment waits for a second admin or committee member (maker and checker).
- A society whose treasurer is also the admin can turn on **Rules → Who approves payments → Post admin and committee
  payments without a second approver**.
- Date every bill and voucher in the month it belongs to. A voucher dated after the cycle ends goes to the next cycle.

---

### 4.4 Correcting a wrong vendor bill
Open the bill (Vendors → Vendor Bills) and use the buttons at the bottom of its details:
- **Cancel this bill** (admin and committee) — for a bill with no payment. The bill leaves the payables and its
  accounting entry is reversed. Enter it again, correctly, if the vendor is still to be paid.
- **Reverse** beside a payment (manager and above) — undoes one payment: the money goes back to the bank or cash
  ledger it was paid from and the bill is owed again.
- **Cancel bill and reverse payments** (admin and committee) — for a bill that has been paid: reverses every payment
  and cancels the bill in one step, all or nothing. Check the bank statement first: if the vendor really was paid,
  this is not what you want.

Cancelling or reversing also removes the cost from the cycle it was counted in, so use it before you generate the
cycle, or regenerate the unissued bills afterwards.

## Part 5 — Charge heads: setting each one

**Where:** Maintenance Billing → **Charge Heads**. Use **Add from elements** to make a head from an element. Changes
apply only to bills generated from then on; bills already generated are never recalculated.

### 5.1 Three ways a head can bill

| Mode | Bills | Use for |
|---|---|---|
| **Typed amount** | The rate someone typed | Funds, parking, amenities |
| **Budget from expenses — Recent average** | The last N months (1–36) of spend on the linked ledgers, scaled to a year and turned into a monthly rate | Costs paid **once a year** |
| **Budget from expenses — Actual expenses of each billing cycle** | Exactly what was spent in the cycle's dates, to the paisa | Costs paid **monthly** |

**Why yearly costs use Recent average.** In the actual-expense mode a lift AMC paid once a year would land wholly
on one month's bills and the other eleven months would carry nothing. The bye-laws have the GB approve an annual
budget, levied periodically, and the accounts are kept on the accrual basis — so a yearly cost should be spread over
the year. Recent average (12 months) does that.

### 5.2 Setting for each head

| Head | How is it calculated | Mode | Service charge on the head |
|---|---|---|---|
| Service Charges | Same for every flat | **Actual expenses** | **ON** |
| Common Electricity | Annual budget, split equally | **Actual expenses** | **ON** |
| Security Services | Annual budget, split equally | **Actual expenses** | **ON** |
| Housekeeping | Annual budget, split equally | **Actual expenses** | **ON** |
| Lift Maintenance (AMC paid yearly) | Annual budget, split equally | **Recent average, 12 months** | **ON** |
| Water Charges | Annual budget, split by area | Actual expenses if billed monthly; Recent average (12) if yearly | off |
| Property Tax | Per sq ft | Recent average (12) if paid yearly, else typed | off |
| Building Insurance | Annual budget, split by area | **Recent average, 12 months** | off |
| Lease Rent / NA Tax | Annual budget, split by area | **Recent average, 12 months** | off |
| Education & Training Fund | Annual budget, split equally | **Recent average, 12 months** | off |
| Repairs & Maintenance Fund | **% of service charges**, 0.75 | Typed | off |
| Sinking Fund | **% of service charges**, 0.25 | Typed | off |
| Parking Charges | Per parking slot | Typed | off |
| Amenities / Clubhouse | Same for every flat | Typed | off |

Notes:
- The **Service charge** switch on a head is separate from the one on the element. Set it on both.
- **Amount** is required on every head. On an actual-expense head it is never used for billing (the panel says so);
  type a rough figure. On a Recent-average head it is used only until the first spend is recorded.
- Only one Budget-from-expenses head is allowed per element (two would bill the same spend twice).
- A new head made from a yearly-budget element starts on actual expenses by itself. Change it to Recent average for
  the yearly-paid ones.
- **Bill actual expenses** (a button on the Charge Heads tab) lists the heads that can follow spend, with a tick
  box for each.
- Repairs Fund and Sinking Fund use **% of service charges** with 0.75 and 0.25: each is that percentage of the flat's
  service-charge lines (the heads with *Service charge* on) on the same bill. Make sure those heads have Service
  charge ON, or the funds will be ₹0.

### 5.3 How each mode shares the cost
- **Actual expenses:** the pool is shared **by flat area** for per-sq-ft and area-budget heads, **equally** for fixed
  and equal-budget heads. A flat billed for part of the cycle carries a proportionate share. Shares are rounded to
  the paisa so the lines on all bills add up to the pool exactly. If nothing was spent, the head puts no line on any
  bill.
- **Recent average:** annual = spent × 12 ÷ months covered. Equal head: annual ÷ flats ÷ 12. Area head:
  annual × flat area ÷ total area ÷ 12.

---

## Part 6 — Once: Rules

**Where:** Maintenance Billing → **Rules**.

| Setting | What to enter |
|---|---|
| Construction cost per sq ft | Architect-certified, excluding land. Needed only for a head on *% of construction cost*; not needed when the funds are % of service charges. |
| Non-occupancy % | As the GB resolves, at most 10. Applied to the service-charge lines of tenant-let flats. |
| Interest % and grace days | Simple interest on arrears, 12% a year by default. |
| GST | Only if the society is registered. When a flat's monthly GST-able amount is above ₹7,500, 18% applies to all its GST-able lines. |
| Billing start date | The first date any flat is billed from. |
| Who approves payments | See 4.3. |

---

## Part 7 — The monthly routine: generate the bills

| Step | Where | What to do |
|---|---|---|
| 1 | Vendor Bills / vouchers | Enter and pay every cost of the month with its expense head and the right date. |
| 2 | Same | Get pending vouchers **approved**. |
| 3 | Maintenance Billing → **Cycles** | Create the **New cycle** with its start and end dates. |
| 4 | The cycle → **Preview** | Read the **month-end checklist** at the top (below) and the warnings. |
| 5 | Preview | Fix what the checklist names. Missing area, unlinked ledgers or pending vouchers each have a one-tap fix. |
| 6 | Preview → **Generate** | Bills are made as drafts and the working is saved. |
| 7 | The cycle → **Issue All** | Issues the bills to residents. |
| 8 | Payments | Record receipts. They settle the oldest bills first. |

### The month-end checklist in Preview
| It says | What it means | Tap |
|---|---|---|
| Expenses waiting for approval | These are left out of the bills | **Approve all** |
| A ledger with spend that no element covers | Nobody would be billed for it | **Link** |
| An element with spend but no head billing it as actual expenses | The head is missing or on a typed rate | **Add head** or **Switch head** |
| A head with no spend in the period | Nothing is billed for it | For information |

Nothing here blocks **Generate**; it says what to look at first.

### Two safeguards
- The same dates of an element cannot be billed twice. A cycle overlapping an earlier cycle's dates (whose bills
  still stand) is refused. Cancel the earlier bills to free the dates.
- Bills already generated are not changed by later entries. To pick up expenses booked after Generate, use
  **Regenerate bills** (next section).

### Regenerate bills
Use it after fixing the books (approving vouchers, adding a late expense, correcting a charge head).
- It **deletes the unissued bills** of the cycle, and cancelled bills that were never issued, and makes them again
  from all the approved expenses dated in the cycle as they are now.
- A bill that is **issued, paid or part-paid stays exactly as it is**, with its invoice number. A cancelled bill that
  was issued stays as a record, and its flat gets a new bill.
- For a head that bills actual expenses, the new bills share only the spend the issued bills did not take. Together the
  bills still add up to the month's spend. Because late expenses fall on the flats billed again, issue the bills of a
  cycle together where you can.
- It is refused only when every bill is issued or has a payment. Cancel a bill first to make it again.
- If the new bills cannot be made, the old ones stay.

---

## Part 8 — What goes on each flat's bill besides the heads
- **Non-occupancy:** a let-out flat pays the Rules percentage of its service-charge lines. Owner-occupied and vacant
  flats don't.
- **Fines and extra charges:** Maintenance Billing → **Fines & Charges**, on one flat, from an effective date.
- **GST:** see Part 6.
- **Interest on arrears:** from each earlier bill's due date plus grace days. Fines and interest are not charged
  interest.

---

## Part 9 — Year end
Compare what was billed with what was spent, head by head (**Suggest from expenses** on the Charge Heads tab, and
**Spend by element** on the Maintenance Elements page). A surplus or shortfall goes into next year's budget as the
GB decides.

---

## Part 10 — Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| A head shows ₹0 on every bill | Actual-expense head and nothing approved in the cycle's dates | Approve the vouchers; check the date and the ledger's link |
| A cost never reaches the bills | Ledger not linked to an element | Chart of Accounts → Counts towards |
| Charge didn't change after spending more | Head not on Budget from expenses, or bills were already generated | Switch the head; bills are not recalculated |
| One month has a huge lift or insurance line | A yearly cost on the actual-expense mode | Move the head to Recent average (12 months) |
| Funds are ₹0, too small or too large | Fund head on the wrong basis, or the service-charge heads do not have Service charge ON | Set the funds to % of service charges, 0.75 and 0.25, and check Service charge on the five service heads |
| Preview says a flat has no area | Flat area missing | Add the area in the flat master; area-based heads give ₹0 for it |
| Generate refused: dates overlap | An earlier cycle covers the same dates | Cancel that cycle's bills, or fix the dates |
| Electricity bill not in Common Electricity | Booked to a repairs ledger | Book to 4201 |
| A payment you entered isn't counted | It is pending approval | Have a second admin or committee member approve it |

---

## Part 11 — One-page checklist

**Once**
- [ ] Rules: construction cost, non-occupancy %, interest, GST if registered.
- [ ] Elements: set as in Part 2.
- [ ] Chart of Accounts: link ledgers as in Part 3.
- [ ] Charge heads: set as in Part 5.2.
- [ ] Vendor Masters: each vendor's category is right.

**Every month**
- [ ] All bills and payments entered with the right expense head and date.
- [ ] Pending vouchers approved.
- [ ] New cycle → Preview → clear the checklist → Generate → Issue All.
- [ ] Record receipts; review Defaulters.

**Every year**
- [ ] Compare billed against spent per element; carry the difference into next year's budget.
