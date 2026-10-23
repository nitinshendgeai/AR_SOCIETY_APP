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
- **Day Book** and **ledgers** show Entered by too (and Approved by where there is one).

The registers only read what is already posted; they change nothing.

## API

`GET /api/v1/accounts/registers/cash-bank/{society_id}`, `/registers/invoices/{society_id}`,
`/registers/bills/{society_id}` (query: `date_from`, `date_to`, plus `account_id`, `status`, `vendor_id`, `q`;
`format=pdf` for the printed register). `GET /accounts/vouchers/{society_id}/pending-approvals` returns the waiting
vouchers with `can_approve`; `POST /accounts/vouchers/{id}/approve` and `/reject` act on them.

## Entering vouchers fast (computer)

Add Expense and New Voucher work from the keyboard: type to find a ledger, head or flat, **Enter** to take it and move on,
**Ctrl+S** to save, **Ctrl+Enter** to save and start the next voucher, **Alt+L** to add a line, **F4 / F5 / F6 / F7** for Contra / Payment / Receipt / Journal, and **Alt+C** (or Enter when nothing matches) to create a ledger from inside a voucher. See the help guide
("Entering many vouchers: the keyboard").
