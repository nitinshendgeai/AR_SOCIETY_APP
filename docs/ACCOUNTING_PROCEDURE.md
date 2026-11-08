# Accounting procedure and registers

Nothing is paid through the app. Entries are made **after** a payment or receipt has happened, so the books follow the
usual society procedure: every entry is a numbered voucher, whoever makes it is recorded, a payment or journal is
checked by a second person, and nothing is deleted.

## Who does what

| Step | Done by | Recorded |
|---|---|---|
| Enter a voucher (Receipt, Payment, Journal, Contra, or Add Expense) | Admin, committee or manager | Entered by, date and time |
| Approve or reject a **Payment** or **Journal** | Admin or a committee member, not the person who entered it | Approved by, date, note; or the reason for rejecting |
| Edit a voucher | Same people; a reason is required | Every earlier version, who changed it |
| Cancel a voucher | Same people; a reason is required | It stays on record, marked cancelled |
| Year-end | Admin or committee | The year's books are closed; later changes are reversal entries |

- **Receipts and Contra vouchers** count in the books at once. **Payments and Journals** count once approved. Until
  then they show as "Waiting for approval" in the Day Book, the Accounts page shows how many are waiting, and
  **Accounts → Approvals** lists them with Approve and Reject.
- **Maker and checker are two people.** Whoever entered a voucher cannot approve it while another admin or committee
  member could. If nobody else could (a society with a single admin), the admin may approve their own entry and the
  approval note says so.
- Maintenance invoices, receipts from residents and vendor bills/payments are **posted automatically** by the app when
  they are entered in Billing or Vendors; they need no approval and carry the name of the person who entered them.

## Registers (Accounts → Books)

Each register can be filtered by period, printed or shared as a PDF, and names the person who made every entry.

- **Cash & Bank Book** – every cash and bank account: opening balance, receipts, payments, the balance after each line,
  and closing balance. Columns: Entered by, Approved by (or "Auto-posted"). Only approved, live vouchers appear.
- **Invoice Register** – the maintenance invoices raised on members: date, invoice number, flat, member, billed, paid,
  due, status and who generated it. Filter by status; search by invoice number, flat or member.
- **Bills Register** – the bills received from vendors: date, bill number, vendor, expense head, total, paid, still to
  pay, status and who entered it.
- **Outstanding Receivable / Payable** – what members owe and what the society owes vendors, party by party, aged in days
  past the due date (not yet due, 1-30, 31-60, 61-90, over 90) with the bills behind each; printable. Members' figures
  match the defaulters list; vendors' are bills not yet paid (less TDS booked and payments). A bill without a due date
  is aged from its bill date.
- **Day Book** and **ledgers** show Entered by too (and Approved by where there is one).

The registers only read what is already posted; they change nothing.

## Which entry for which transaction

| What happened | Enter it as | What the books do |
|---|---|---|
| A vendor's **bill arrives** (paid now or later) | **Vendors → Bills → New bill** | Dr expense head (+ input GST), Cr Sundry Creditors (that vendor). The expense belongs to the month of the bill; the vendor is now owed the money. |
| The vendor is **paid** | **Vendors → the vendor's open bills → Pay** (tick the bills; one cheque can settle several) | Dr Sundry Creditors, Cr the bank or cash ledger chosen, Cr TDS Payable when TDS applies. Each bill's balance falls; the Outstanding Payable report, the vendor's ledger and the bill all agree. |
| A supplier's bill **not paid yet**, entered from the expense form | **Add Expense → Pay later** (vendor, supplier's bill no., optional due date) | Saved as a vendor bill: the same entries as a bill entered under Vendor Bills. Pay it later from **Pay Vendor**. |
| **Petty cash** (a float for small daily expenses) | **Accounts → Petty Cash**: *Top up from bank*, then *Add expenses* each day | Top-up: Dr Petty Cash, Cr Bank (Contra). A day's expenses: one Payment voucher, Dr each expense head, Cr Petty Cash; approval as for any payment. *Count the cash* records a shortage or excess without posting. The *Petty Cash Book* shows it day by day. |
| A **petty purchase paid on the spot** | **Add Expense** (cash or bank) | Dr expense head, Cr cash / bank. No payable is created because nothing is owed afterwards. |
| A bill was **entered wrongly** | **Cancel the bill** (admin / committee; only while nothing is paid on it, else reverse the payment first) | The bill's voucher is cancelled (or reversed in the open year if its year is closed); it leaves the payables. Enter the bill again correctly. |
| Money **paid in advance** to a vendor with nothing outstanding | Payment voucher: Dr Sundry Creditors (choose the vendor), Cr bank | Shown as "Advances paid to vendors" on the Balance Sheet. A vendor who has unpaid bills cannot be paid by a loose voucher: pay the bills instead, so each is marked paid. |
| A **resident pays** maintenance | **Online Payments → Record payment** (choose the bank ledger it was deposited into). A Receipt voucher on Members' Dues is refused for a flat with unpaid bills, since it would leave them unpaid; with none, it is an advance and may be entered | Dr bank / cash, Cr Members' Dues (that flat); set off against the oldest bills; any excess is the member's advance. |
| **Other income** (hall rent, interest, scrap) | Receipt voucher | Dr bank / cash, Cr the income ledger. |
| **Amenity / hall booking charge** | Automatic | Added to the flat's next bill: Dr Members' Dues, Cr Amenities income. |
| **Amenity deposit** (received / refunded) | Booking → Deposit | Receipt: Dr bank/cash, Cr Amenity Deposits Held. Refund: Dr deposit; Cr bank/cash, and Cr Amenities income for any part kept. |
| **Parking violation fine** | Violation → Charge fine | Added to the flat's next bill: Dr Members' Dues, Cr Fines & Penalties. |
| **TDS / GST deposited** with the government | Payment voucher | Dr TDS Payable / GST Payable, Cr bank. |

**In the app:** *Vendor Bills → Pay Vendor* (also *Pay several bills of this vendor* inside a bill, and *Pay bills* from the
note a Payment voucher shows when its vendor has unpaid bills). Choose the vendor, tick the bills, lower an amount to part-pay,
choose the payment mode and the bank or cash ledger it is paid from, and save: every bill is paid (with its own TDS) and
posted, or none is. A bill's own sheet also has *Cancel this bill* for the admin or committee while nothing is paid on it.

## Bank reconciliation (Accounts → Bank Reconciliation)

The bank ledger says what the society thinks is in the bank; the statement says what the bank thinks. Marking each line of
the bank ledger with the day the bank cleared it leaves the **Bank Reconciliation Statement**:

    Balance as per the books
    Add:   payments not yet cleared (cheques issued, transfers the bank has not debited)
    Less:  deposits not yet cleared
    Balance as per the bank statement

**In the app:** *Accounts → Books → Bank Reconciliation* (Gateway of Accounts: **K**). Choose the bank account and the date.
*Statement* shows the Bank Reconciliation Statement; tick the payments and deposits the bank's statement shows and
*Mark cleared* with the day the bank cleared them. *Bank rows* imports the bank's CSV, lists its rows (credits and debits)
for that account and matches each to a line of the books (*Match*), or *Auto-match* the unambiguous ones; a row that is not
a transaction of the society is ignored with a reason. *Cleared* lists what is cleared, with *Undo*.

- **The simple way:** choose the bank and tap **Upload bank statement** on the *Statement* tab. The app reads the PDF (any bank),
  checks it adds up, stores its closing balance, matches what can only mean one entry of the books, and shows the result as
  on the statement's last day: **Reconciled**, or the difference and what explains it.
- **The proof (standard BRS logic):** *Balance as per the books* + payments not yet cleared − deposits not yet cleared must equal
  the *balance the bank statement shows*. If it does not, the difference is the bank's own items the books lack (charges,
  interest, direct credits), listed under **In the bank, not in your books**: open one and **Record in books** (a Receipt or
  Payment against the ledger you choose - Bank Charges / Interest on Savings Bank are suggested - dated the day the bank did
  it and cleared at once). Whatever is left after those is shown as *unexplained*: check that the whole statement is uploaded
  and that *As on* is the statement's last day. For a CSV (which has no balance) use **Enter balance** to type the closing
  balance for that day.
- **Match by hand (two grids):** the *Match* tab shows *Our bank entries* (not yet cleared) beside the *Bank statement rows*
  (not yet matched). Tick what belongs together; when the totals are equal, **Match selected** clears them. Credits go with
  deposits, debits with payments. One bank row may clear several entries (a deposit slip of cheques), or several bank rows one
  entry (a payment the bank took in parts) - not several against several. Taking the match back (*Take back* on the row, or
  *Undo* on any of the entries) releases the whole group. A search box filters both lists by amount, reference or name.
- Reconcile each bank ledger separately; cash has no statement. Opening balances count as cleared.
- Only approved, live vouchers appear: a payment waiting for approval, a rejected or a cancelled one is not on it.
- **Clear a line** by hand (with the date on the bank statement), or **import the statement** (CSV with Date, Description,
  Reference and either Amount — negative is a debit — or Debit and Credit columns) and **match** each row to the books'
  line of the same amount and side (the one whose reference agrees comes first). *Auto-match* takes only the rows that
  can mean one line; the rest are left for a person. A matched line can be taken back; cancelling a voucher frees its
  statement row.
- A resident's online payment is confirmed once its money shows in the bank: clearing its line in the books reconciles the
  payment, and confirming the payment against the statement in Billing clears its line.
- Only the admin or a committee member clears lines (the manager can read the statement).

## Reports read the books one way

Every report counts **approved, live vouchers only**. A payment or journal waiting for approval, a rejected one, or a
cancelled one is not in the Trial Balance, Income & Expenditure, Receipts & Payments, Schedule of Funds, the dashboard
figures or the spend per maintenance element. The year-end closing entry (which moves each income and expense ledger to
the Income & Expenditure Account) is not counted as a refund in the spend per element.

## API

`GET /api/v1/accounts/registers/cash-bank/{society_id}`, `/registers/invoices/{society_id}`,
`/registers/bills/{society_id}` (query: `date_from`, `date_to`, plus `account_id`, `status`, `vendor_id`, `q`;
`format=pdf` for the printed register). `GET /accounts/vouchers/{society_id}/pending-approvals` returns the waiting
vouchers with `can_approve`; `POST /accounts/vouchers/{id}/approve` and `/reject` act on them.

Vendors: `GET /vendors/invoices/vendor/{vendor_id}/open` (bills still to pay), `POST /vendors/invoices/vendor/{vendor_id}/pay`
(`items: [{invoice_id, amount}]`, `paid_date`, `payment_mode`, `payment_ref`, optional `bank_account_id`),
`POST /vendors/invoices/{id}/payments` (one bill; same optional `bank_account_id`), `POST /vendors/invoices/{id}/cancel`.

Bank reconciliation: `GET /accounts/bank-reconciliation/{society_id}?account_id=&as_on=` (the statement),
`.../cleared`, `POST .../clear` and `.../unclear` (`entry_ids`, `cleared_date`), `POST .../auto-match`,
`GET .../rows/{row_id}/suggestions`, `POST .../rows/{row_id}/match` (`entry_id`) and `/unmatch`,
`POST .../rows/{row_id}/book` (`account_id` of the ledger, optional `narration`: records a bank-only row in the books, cleared at once),
`POST .../match-selected` (`row_ids`, `entry_ids`: the two grids), `PUT .../statement-balance` (`account_id`, `as_on`, `balance`). The statement answers also with `statement_balance`, `difference`,
`unexplained`, `status` (`reconciled | bank_items_to_book | difference | no_statement_balance`) and `bank_only_rows`; `?bank_balance=`
checks it against a typed figure without storing it. The statement is imported with
`POST /billing/bank-reconciliation/society/{society_id}/import?include_debits=true&bank_account_id=` (add `&detail=true` to
get `{entries, summary}` instead of just the entries).

### Importing the bank's statement (PDF or CSV)

**Each line once, under its own bank.** A statement imported with the bank not chosen is saved against the society's only bank
ledger when there is just one; with several banks, a row saved with no bank (older imports) is listed under the *default* bank
only, never under every bank, and a copy with no bank is hidden when the same line is stored against a bank. Importing the same
file again, with or without the bank chosen, adds nothing. The app lists the rows of the chosen bank with
`GET /accounts/bank-reconciliation/{society_id}/rows?account_id=&match_status=`. The *Cleared* tab shows the last 90 days; the
*Statement* tab lists the first five of the bank's own items and leaves the rest to the *Match* tab.

**Import statement** takes a **bank statement PDF from any bank**, or a CSV with Date, Description, Amount (or Debit and Credit)
and an optional Reference. The PDF's layout does not have to be one the app has seen: the app finds the statement's table by
its column headings (Date or Txn Date, Value Date, Description or Narration or Particulars, Chq/Ref No, Debit or Withdrawal or
Dr, Credit or Deposit or Cr, or a single Amount column with Dr/Cr marks, and Balance), also when a heading is split over two
lines, and reads each line of the table. It must be a **text PDF downloaded from net banking**; a scan or photo has no text to
read, and a password-protected file must be saved without the password first.

The app then **proves the reading against the statement itself before storing anything**:

- every line's running balance must follow from the line before it (opening balance plus credits less debits). This also tells a
  debit from a credit when the statement does not mark them, and a line marked one way but moving the balance the other way is refused;
- the debits, the credits and the closing balance must equal the totals and closing balance the statement prints, where it prints them;
- a statement with no running balance and no totals cannot be checked, so it is refused.

If anything does not agree, the whole file is refused with a message and nothing is imported (use the CSV instead).

- The statement's account number must be the chosen bank ledger's account number when the ledger has one on file (a masked
  number such as XXXXXXXX1234 is compared by the digits it shows; only the last four digits are ever shown in a message). With no
  ledger chosen, the bank ledger carrying that number is used.
- Credits are always imported; debits too when the bank reconciliation asks for them (it does).
- A line already imported - **from a PDF or a CSV** (the same bank reference; or, where the bank prints none, the same description, date, amount and
  direction; in the same bank ledger or in none) is skipped, once per stored copy, so a statement that overlaps the last one adds only what is new, importing the
  same file twice adds nothing, and two genuinely identical lines in one statement are both kept. The result says how many were skipped.
- Each line keeps the bank's reference (or reference/cheque number) and its description, with the bank's wrapped lines joined
  back together. Matching to the books is then done as before (**Auto-match**, or by hand). A bank's reference agrees with a
  voucher's when the numbers are the same ignoring spaces, dashes and leading zeros (cheque 000123 = 123), or when a voucher's
  UTR of six or more characters appears in the bank's narration. The statement's closing balance is stored for its last day.
- The PDF reader is the `pdfminer.six` package. Files up to 8 MB are accepted.

## Entering vouchers fast (computer)

Add Expense and New Voucher work from the keyboard: type to find a ledger, head or flat, **Enter** to take it and move on,
**Ctrl+S** to save, **Ctrl+Enter** to save and start the next voucher, **Alt+L** to add a line, **F4 / F5 / F6 / F7** for Contra / Payment / Receipt / Journal, and **Alt+C** (or Enter when nothing matches) to create a ledger from inside a voucher. **Alt+G** opens the Gateway of Accounts, a keyboard menu (arrows and Enter, or the letter on each line) for every voucher, book and report. See the help guide
("Entering many vouchers: the keyboard").
