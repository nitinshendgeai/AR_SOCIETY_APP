# Accounts Module

## Purpose
The society's double-entry books, kept the way a Maharashtra co-operative housing society keeps them: a standard chart of accounts (funds, members' dues, service charges and recoveries, running expenses), vouchers numbered per financial year, cash and bank books, the general ledger and the members' (flat-wise) ledger. Maintenance bills, payments received and vendor bills are posted automatically, so they are never entered twice.

Part 2 (planned): Trial Balance, Income & Expenditure account, Balance Sheet, fund statements and year-end closing.

## Core Entities
| Entity | Table | Purpose |
|--------|-------|---------|
| AccountGroup | `account_groups` | Balance Sheet / I&E heads — nature: asset, liability, income, expense |
| Account | `accounts` | Ledger under a group; opening balance (Dr/Cr); cash and bank flags and bank details |
| Voucher | `vouchers` | One transaction, `RV/2026-27/0001`; `source_type`/`source_id` on automatic postings |
| VoucherEntry | `voucher_entries` | Debit or credit line; `flat_id` on Members' Dues, `vendor_id` on Sundry Creditors |

## Standard chart
Created the first time a society's books are opened (`chart_of_accounts.py`). Codes: 1xxx liabilities and funds, 2xxx assets, 3xxx income, 4xxx expenses. Standard ledgers carry a `system_key` and can be renamed but not moved or deactivated. The default bank ledger is named from the bank details on the maintenance bill settings.

## Voucher types
| Type | Prefix | Entered by | Rule |
|------|--------|------------|------|
| Receipt | RV | Society | Debit cash/bank, credit the rest |
| Payment | PV | Society | Credit cash/bank, debit the rest |
| Contra | CV | Society | Cash and bank ledgers only |
| Journal | JV | Society | Never cash or bank |
| Member Bill | BV | Automatic | Maintenance bill issued |
| Purchase | PU | Automatic | Vendor bill entered |

Every voucher balances (total debit = total credit). Cancelling strikes a voucher out of every ledger but keeps it on record; automatic vouchers are cancelled from their source (bill, payment), not directly.

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

## API (`/api/v1/accounts`)
| Endpoint | Purpose |
|----------|---------|
| `GET /summary/{society_id}` | Cash, bank, members' dues, creditors, FY income/expenditure, pending postings |
| `GET /chart/{society_id}` | Groups with ledgers and balances |
| `GET /ledgers/{society_id}` · `POST /ledgers` · `PATCH /ledgers/{id}` | Ledger master |
| `GET /ledgers/{id}/statement?date_from&date_to&flat_id&vendor_id` | Ledger / cash book / bank book / member or vendor account |
| `GET /members/{society_id}` | Flat-wise balances on Members' Dues |
| `GET /vouchers/society/{society_id}` · `POST /vouchers` · `GET /vouchers/{id}` · `POST /vouchers/{id}/cancel` | Day book and voucher entry |
| `POST /sync/{society_id}` | Catch up automatic postings |

## RBAC
All endpoints: `manager_above` (Society Admin, committee, Manager). Screen: `accounts` form, granted to the same roles.
