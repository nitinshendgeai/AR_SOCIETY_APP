# Depreciation of fixed assets

Where: **Accounts → All Registers → Depreciation** (web and phone). Managers and the committee can read it; only the
Admin and committee change the setup. **It posts nothing to the books.**

## What it does

1. **Setup** - for each kind of asset (lift, pump, furniture, IT equipment...): the method, the yearly rate, the life (straight
   line) and the value kept at the end. An asset can have its own setting: a different method or rate, a value kept, the date it
   was put to use, the date it stopped being used (sold, scrapped, lost), or "do not depreciate" (land).
2. **Schedule** - for any financial year (April to March), each asset's cost, book value at the start, depreciation for the year
   and book value at the end, with totals, a PDF, and the **journal that would book it** (Dr Depreciation, Cr the fixed-asset
   ledgers). The Treasurer reviews it and enters it as a Journal voucher; the app does not.
3. Assets that cannot be worked out yet (no cost, no date, no rate, or disposed with no stop date) are **listed as left out**, with
   what is missing, rather than guessed.

## How it is calculated

- **Reducing balance (WDV)**: book value at the start of the year x rate x share of the year.
- **Straight line (SLM)**: cost x rate x share of the year; the rate is the one entered or 100 / life in years.
- **Share of the year** = days the asset was in use in that financial year / days in the year. The day it was put to use and the
  day it stopped both count. An asset bought on 1 Oct 2026 is depreciated for 182 of 365 days in 2026-27.
- Depreciation never takes the book value below the value kept at the end. Each year is rounded to the paisa before it carries on.
- Worked example: cost 1,00,000 at 15% WDV from 1 April 2026: 15,000.00 in 2026-27 (book value 85,000.00), 12,750.00 in 2027-28.

## Starting values (to be confirmed)

The first time the setup is opened every kind of asset gets a starting rule: reducing balance at the usual income-tax block rates
(plant and machinery 15%, furniture and electrical fittings 10%, computers 40%, solar 40%, tanks 10%, vehicles 15%).
**These are starting points, not advice: the society's chartered accountant must confirm the method and rates.**
Co-operative societies are often required to follow their own bye-laws or the state's rules, which may differ.

## Things to know

- The schedule is worked out from the purchase date every time. **Changing a rate or a date changes every year's figures**, so do
  not change the setup after a year's depreciation has been entered in the books.
- The fixed-asset ledgers in the books are not changed or checked against the schedule. If assets were entered into the ledgers as
  an opening balance, compare the schedule's book value with the ledger before entering the journal.
- Settings are stored in `depreciation_rules` and `asset_depreciation` (migration `c3e5a7b9d1f3`, additive).
- API: `GET/PATCH /accounts/depreciation/rules`, `GET /accounts/depreciation/assets/{society}`,
  `PUT /accounts/depreciation/assets/{asset}`, `GET /accounts/depreciation/schedule/{society}?fy=2026-27[&format=pdf]`.
