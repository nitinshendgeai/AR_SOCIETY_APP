# Accounts Module

## Purpose
The society's double-entry books, kept the way a Maharashtra co-operative housing society keeps them: a standard chart of accounts (funds, members' dues, service charges and recoveries, running expenses), vouchers numbered per financial year, cash and bank books, the general ledger and the members' (flat-wise) ledger. Maintenance bills, payments received and vendor bills are posted automatically, so they are never entered twice.

Financial statements for each financial year (1 April – 31 March), with previous-year figures, and year-end closing of the books.

## Core Entities
| Entity | Table | Purpose |
|--------|-------|---------|
| AccountGroup | `account_groups` | Balance Sheet / I&E heads — nature: asset, liability, income, expense |
| Account | `accounts` | Ledger under a group; opening balance (Dr/Cr); cash and bank flags and bank details |
| Voucher | `vouchers` | One transaction, `RV/2026-27/0001`; `source_type`/`source_id` on automatic postings |
| VoucherEntry | `voucher_entries` | Debit or credit line; `flat_id` on Members' Dues, `vendor_id` on Sundry Creditors |
| VoucherRevision | `voucher_revisions` | A voucher as it stood before an edit (number, date, amount, narration, lines), with who changed it, when and why |
| FinancialYearClosing | `account_year_closings` | A closed year: income, expenditure, surplus, Reserve Fund transfer, closing voucher; reopening keeps the row |

## Standard chart
Created the first time a society's books are opened (`chart_of_accounts.py`). Codes: 1xxx liabilities and funds, 2xxx assets, 3xxx income, 4xxx expenses. Standard ledgers carry a `system_key` and can be renamed but not moved or deactivated. The default bank ledger is named from the bank details on the maintenance bill settings.

## Expense ledgers and maintenance elements
An expense ledger can "count towards" a maintenance element (`maintenance_element_id`, set from the ledger form,
`PATCH /accounts/ledgers/{id}`; `null` clears it). It must be an expense-nature ledger and the element must belong to
the same society (422 otherwise). What is posted to the ledger feeds that element's budget in the monthly maintenance
calculation — see BILLING.md, *Expense-driven budgets*. Moving a ledger out of an expense group clears the link.
Bill lines of type PENALTY post to **Fines & Penalties** (3013), except interest lines (Interest on Arrears).

## Voucher types
| Type | Prefix | Entered by | Rule |
|------|--------|------------|------|
| Receipt | RV | Society | Debit cash/bank, credit the rest |
| Payment | PV | Society | Credit cash/bank, debit the rest |
| Contra | CV | Society | Cash and bank ledgers only |
| Journal | JV | Society | Never cash or bank |
| Member Bill | BV | Automatic | Maintenance bill issued |
| Purchase | PU | Automatic | Vendor bill entered |
| Year-end Closing | YC | Automatic | The year's books closed (dated 31 March) |

Every voucher balances (total debit = total credit). Cancelling strikes a voucher out of every ledger but keeps it on record; automatic vouchers are cancelled from their source (bill, payment), not directly. Vouchers are never deleted.

**Editing.** A Receipt, Payment, Contra or Journal the society entered can be corrected while its year is open: date, reference, narration and lines (the type stays), with a reason. The same rules as entering one apply, and both the old and new date must be in an open year. The voucher keeps its number unless it moves to another financial year. The version before each edit is kept in `voucher_revisions` and shown as the voucher's edit history; `edited_at` / `edited_by` record the latest change, and the audit log has each one. Automatic vouchers, closing and reversal entries, cancelled vouchers and those of a closed year can't be edited.

## Printed documents (`documents_pdf.py`)
| Document | Layout |
|----------|--------|
| Voucher | Half sheet (A5 landscape): letterhead, "PAYMENT VOUCHER" etc., number and date, paid to / received from, Dr/Cr lines, amount in words, narration, reference; signature boxes — Prepared by (who entered it), Checked by, Hon. Secretary / Treasurer and, on a payment, Receiver's Signature. Cancelled and revised vouchers say so |
| Ledger account | A4: opening balance, each posting with particulars, narration and running balance, totals, closing balance; for a ledger, a member's or a vendor's account, for any period; "For the society — Hon. Treasurer" |
| Day book | A4: every voucher of the period (or one type) with its lines and narration; cancelled ones greyed and left out of the total |
| Members' ledger | A4: each flat's balance as dues (Dr) or advance (Cr), totals and the net receivable |

## Automatic postings (`postings.py`)
```
Bill issued        Dr Members' Dues (flat)          Cr Service Charges / recoveries / Sinking Fund /
                                                       Repairs Fund / Interest on Arrears / GST Payable
Bill cancelled     its Member Bill voucher cancelled
Payment received   Dr Cash in Hand (cash) or bank   Cr Members' Dues (flat)
Payment rejected   its Receipt voucher cancelled
Vendor bill        Dr expense head                  Cr Sundry Creditors (vendor)
Vendor paid        Dr Sundry Creditors (vendor)     Cr Cash in Hand (cash) or bank
```
A bill line goes to the ledger of the standard element its charge head came from; fund contributions (sinking, repairs, education) are credited to the fund, never to income. A vendor bill goes to the expense head chosen on the bill, else by the vendor's category.

Hooks run in a savepoint and never fail the billing or vendor action. **Sync postings** (`POST /accounts/sync/{society_id}`, "Post now" on the Accounts screen) posts whatever is missing — including everything recorded before the books were opened — and is idempotent.

## Financial statements (`reports.py`, PDF: `reports_pdf.py`)
| Statement | Shows |
|-----------|-------|
| Trial Balance | Every ledger's balance at the year end, before the closing entry; debits = credits |
| Income & Expenditure Account | Expenditure vs income by group and ledger; surplus or deficit carried to the Balance Sheet; previous year alongside |
| Balance Sheet | Funds & liabilities vs property & assets as at 31 March, previous year alongside. Members' dues split into receivable (asset) and advance received (liability); vendors into payable and advances paid. I&E Account: balance b/f, surplus/(deficit), transfer to Reserve Fund |
| Receipts & Payments Account | Opening cash & bank, receipts and payments by head (counterpart ledgers of cash/bank vouchers; contras excluded), closing cash & bank |
| Schedule of Funds | Each fund: opening, additions, utilised, closing |

The running year is shown "as on" today and marked provisional. Statements of a year are built from the vouchers before its own closing entry, so they read the same before and after closing. If opening balances don't agree, the difference is shown (TB row / Balance Sheet "Suspense") with a note. PDFs: society letterhead, two-sided statements side by side on landscape A4 (previous year | particulars | current year on each side), signature lines for the Statutory Auditor ("As per our report of even date") and Hon. Chairman / Secretary / Treasurer.

## Year-end closing
- Only a year that is over, and only after every earlier year with entries is closed (years close in order). Admin and committee only.
- Closing first posts any bills and payments of the year not yet in the books, then posts a Year-end Closing voucher dated 31 March: every income and expenditure ledger to the Income & Expenditure Account, and the chosen share of a surplus (default 25%, the MCS Act minimum) from it to the Reserve Fund.
- A closed year is locked: no voucher can be entered or cancelled in it, and opening balances can no longer change. Automatic postings dated in it go on 1 April of the next open year (narration says so); a bill or payment of a closed year cancelled later is reversed by a journal in the open year (`reversal_of_id`), the original stays in its year.
- Reopening (latest closed year first, with a reason) cancels the closing voucher and unlocks the year.
- Income and expenditure ledgers have no opening balance — a surplus brought forward goes on the Income & Expenditure Account ledger.

## API (`/api/v1/accounts`)
| Endpoint | Purpose |
|----------|---------|
| `GET /summary/{society_id}` | Cash, bank, members' dues, creditors, FY income/expenditure, pending postings |
| `GET /chart/{society_id}` | Groups with ledgers and balances |
| `GET /ledgers/{society_id}` · `POST /ledgers` · `PATCH /ledgers/{id}` | Ledger master |
| `GET /ledgers/{id}/statement?date_from&date_to&flat_id&vendor_id&format=json\|pdf` | Ledger / cash book / bank book / member or vendor account |
| `GET /members/{society_id}?format=json\|pdf` | Flat-wise balances on Members' Dues |
| `GET /vouchers/society/{society_id}` · `POST /vouchers` · `GET /vouchers/{id}` · `POST /vouchers/{id}/cancel` | Day book and voucher entry |
| `PUT /vouchers/{id}` `{voucher_date, narration, reference, entries, reason}` | Correct a voucher the society entered |
| `GET /vouchers/{id}/pdf` · `GET /day-book/{society_id}/pdf?date_from&date_to&voucher_type` | Printed voucher and day book |
| `POST /sync/{society_id}` | Catch up automatic postings |
| `GET /reports/{society_id}/{report}?fy=2025-26&format=json\|pdf` | `trial-balance`, `income-expenditure`, `balance-sheet`, `receipts-payments`, `funds` |
| `GET /years/{society_id}` | Financial years with result, closed status, whether they can be closed/reopened |
| `POST /years/{society_id}/{fy}/close` `{reserve_pct}` · `POST /years/{society_id}/{fy}/reopen` `{reason}` | Admin / committee only |

## RBAC
All endpoints: `manager_above` (Society Admin, committee, Manager); closing and reopening a year: `admin_committee`. Screen: `accounts` form, granted to the same roles.
