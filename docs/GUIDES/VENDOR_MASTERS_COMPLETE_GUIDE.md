# Vendors, Work Orders and Contracts — Complete Guide

Where to make entries when the society gives work to a vendor, and the rules the app enforces so that it is done
the way the Maharashtra model bye-laws for co-operative housing societies require.

**Where in the app:** Operations → **Vendors & Work** (tabs: Work Orders, Contracts, Vendors, Limits). Bills and
payments: Finance → **Vendor Bills**. Admin, the managing committee and the Manager see it; the Manager prepares, the
committee decides.

> The bye-law figures below are the 2014 model bye-laws. Your society's registered bye-laws, later amendments and
> general body resolutions govern; set the limits your general body has resolved (Limits tab).

---

## 1. What the bye-laws require

| Rule | Model bye-law | How the app enforces it |
|---|---|---|
| The committee may spend on repairs and maintenance on its own only up to ₹25,000 (up to 25 members), ₹50,000 (26–50) or ₹1,00,000 (51+), unless the general body fixes another limit | 157 | **Limits** tab works out the slab from the number of flats; a different figure needs a general body resolution no. and date. A sanction above the limit needs the general body's resolution. |
| The general body fixes the amount above which tenders are needed. Tenders are opened by the Secretary in a committee meeting, scrutinised, and placed before the general body, which decides | 157 | Above the tender limit: at least 3 quotations (configurable) from different vendors, the date the tenders were opened, no tender dated after that, and the general body's resolution dated on/after the opening. |
| A committee member with an interest in a contract with the society is disqualified | (disqualification of committee members) | Every sanction needs the committee's declaration; a vendor whose mobile number or email matches a committee member's login is refused. |
| Cheques / transfers are signed by two office-bearers | (operation of bank account) | Not enforced by the app — follow it at the bank. |

The app also applies sound practice that societies' contracts usually contain: the lowest quotation, or a written
reason for not taking it; a written, numbered work order; payment only after the committee certifies completion
(except an agreed advance); retention held for the defect liability period; no billing beyond the sanctioned amount
without a fresh resolution.

---

## 2. Vendor master

**Where:** Vendors & Work → **Vendors** → Add Vendor (committee).

Name, category, mobile, contact person, email, address, city, pincode, GSTIN, PAN, bank account, bank, IFSC, notes.
The name and GSTIN must be unique in the society; GSTIN, PAN and IFSC are checked and upper-cased. The vendor gets a
code (VND-0001).

- **Edit:** tap the vendor. Status: Active, Inactive, Under review.
- **Blacklist:** the block icon; a reason is required. A blacklisted vendor can't quote or be given work. Setting the
  status back to Active clears the blacklisting.
- Only **Active** vendors can be sanctioned or issued work.

---

## 3. Work orders (one-time work)

Use a work order for any repair or job: terrace waterproofing, tank replacement, painting, pump overhaul, an urgent
plumbing job. Statuses:

```
Collecting quotations ──▶ Sanctioned ──▶ Work order issued ──▶ Completed ──▶ Closed
        (draft)              │                 │                    │
                             └──── Cancelled ◀─┘ (only while no bill is recorded)
```

### Step 1 — Create (Manager or committee)
Work Orders → **New Work Order**: the work, category, location, scope (one item per line — printed on the order),
estimated cost, expense head (where its bills are booked; else by the vendor's category), start and completion dates,
and the terms: advance, retention %, defect liability months, payment terms. It gets a number (WO-2026-0001).

The page shows straight away what the estimate needs, e.g. *"Work of ₹60,000 is above the tender limit of ₹25,000:
tenders from at least 3 vendors, opened in a committee meeting. The general body must sanction it."*

### Step 2 — Quotations (Manager or committee)
**Add quotation** for each vendor: reference, date, valid until, amount, GST, remarks. One per vendor (remove and
re-enter a revised one). The lowest is marked.

### Step 3 — Sanction (committee)
**Sanction** opens the decision form. Choose the quotation accepted, and enter:

| Always | Committee resolution no. and meeting date; the no-interest declaration |
|---|---|
| Not the lowest | Why not the lowest quotation |
| Above the tender limit | Date the tenders were opened in the committee meeting (needs the minimum number of quotations, none dated after it) |
| Above the committee's limit, or tenders were needed | General body resolution no. and date |

The app refuses an expired quotation, a quotation dated after the meeting, a future date, an inactive or blacklisted
vendor, and a vendor whose phone or email is a committee member's. The sanctioned amount is the quotation's total
(with GST). The scope and terms are locked from here.

### Step 4 — Issue (committee)
**Issue work order** with the date (not before the sanction). **Download PDF** prints the work order on the society's
letterhead: number and date, vendor with GSTIN/PAN, subject, the quotation and resolutions it rests on, scope, value
in figures and words, terms, standard conditions, and signature lines for the Hon. Secretary, the Chairman and the
contractor's acceptance.

### Step 5 — Bills (Manager or committee)
**Record bill** on the work order page (bills entered directly in Vendor Bills are not tied to a work order). Bills can be recorded once the order is
issued, only from its vendor, and **never beyond the sanctioned amount** — more needs **Revise sanction** (a fresh
committee resolution, and the general body's if the new amount needs it, with the reason). Each bill is booked to the
expense head and posted to the books.

### Step 6 — Payments
Pay from **Vendor Bills**. What can be paid depends on the stage:

| Stage | Can be paid |
|---|---|
| Issued, not yet certified complete | Up to the **advance** agreed in the work order |
| Completed, retention held | Bills less the retention (e.g. 10% of ₹61,000 = ₹6,100 held) |
| Retention released | Everything billed |

The work order shows **Billed**, **Paid**, **Retention held … until …** and **Can be paid now**.

### Step 7 — Certify completion (committee)
**Certify completion**: date, what was checked (required), and the architect's or engineer's certificate reference if
any. The certifier's name is recorded.

### Step 8 — Release retention and close (committee)
After the defect liability period (completion date + months), **Release retention** once the work has been inspected.
When every bill is paid, **Close**.

---

## 4. Annual contracts (AMC)

Lift, security, housekeeping, pumps, generator, pest control — anything recurring.

**Where:** Vendors & Work → **Contracts** → New Contract: name, category, visit frequency, present vendor, from/to
dates, scope. It gets a number (AMC-2026-0001) and starts as a draft.

1. **Add quotation** from each vendor (annual charges).
2. **Sanction** — the same form and rules as a work order, applied to the annual value. The contract goes to the
   vendor whose quotation is accepted, and its annual value is set from it.
3. **Start contract** — refused until it is sanctioned.

Active contracts ending within 60 days are flagged on the Contracts tab. Bills under a contract are recorded in Vendor
Bills and booked to the expense head of the vendor's category (e.g. Lift Maintenance), which counts towards the
matching maintenance element — see the Maintenance Billing guide, section 4.

---

## 5. Example: replacing the terrace water tanks

Society of 12 flats → committee limit and tender limit ₹25,000; 3 quotations needed.

1. Manager creates **WO-2026-0001** "Replacement of terrace water tanks", estimate ₹60,000, advance ₹10,000,
   retention 10%, defect liability 12 months.
2. Quotations: Aqua Plumbing ₹60,000 (lowest), Tank World ₹61,000, Shiv Plumbers ₹66,500.
3. Committee meeting MC/9/2026-27 opens the tenders and recommends Tank World (ISI-marked tanks, 10-year warranty);
   special general body SGM/2/2026 approves. Secretary records the sanction: Tank World, reason, both resolutions,
   tenders-opened date, declaration. Sanctioned ₹61,000 by the general body.
4. Work order issued and printed; Secretary and Chairman sign, Tank World signs acceptance.
5. Tank World bills ₹61,000 (TW/88). Before completion only ₹10,000 could be paid.
6. Committee certifies completion ("tanks filled and checked 24 h, no leaks"). ₹54,900 can now be paid; ₹6,100
   retention held until a year after completion.
7. After a year, retention released, last ₹6,100 paid, work order closed.

---

## 6. Not covered by the app yet

- **TDS on contractor payments** (Income-tax Act s.194C — a co-operative society deducts 1% / 2% above ₹30,000 per
  payment or ₹1,00,000 in a year): deduct and record it outside the app for now.
- **Two signatories** on payments: follow your bank mandate.
- **Contract expiry reminders** by notification: the Contracts tab shows contracts ending within 60 days, but no
  reminder is sent.
- **Service requests** (complaint → vendor visit) exist on the server but have no screen; use a work order.
