# Manager's daily checklist

The society manager's working day on one screen: **Operations → Manager's Checklist** (admin, committee and manager).

## How an item gets on today's list

An item is one of:

| Frequency | Shows |
|---|---|
| Every day | every day |
| Every week | from its weekday until ticked that week |
| Every month | from *lead days* before its day of the month until ticked |
| On fixed dates | the same, in the months chosen (quarterly, half-yearly, yearly) |
| Licence | when the date a licence or certificate runs to is near or past |

An item tied to an **asset kind** or a **staff department** is on the list only while the society has an active asset
of that kind or active staff in that department (`assets` register, `staff` register). Retire the last lift and the lift
checks go; register a generator and the generator checks appear.

Alongside the routine, **Needs your attention** is counted live from the society's records (nothing is stored, so a line
clears itself when the work is done): assets overdue for service or past warranty or AMC; vendor contracts and work
orders running out or late; staff on duty today who have not checked in, staff on leave, staff without a duty, duties
left open; punch and leave approvals; open and week-old complaints; overdue bills and vendor bills; vouchers awaiting
approval; recurring expenses to book; low stock; expiring rent agreements; NOC requests; parcels waiting at the gate.

## Ticking, skipping, signing off

- Tick a routine item: it records who and when. Tap again to undo.
- **Skip with a reason** for something that does not apply today (the reason is kept).
- Statutory dates and licences are **recorded**: date done, reference (certificate, challan, policy number), and for a
  licence the date it runs to, which sets its next due date.
- **Close the day** saves a sign-off (what was done, what was left, remarks). Signing again the same day updates it.
- **Download PDF** prints the day's sheet: boxes to tick, the attention list, remarks and signature lines.

## The law

Built-in legal items are grouped in packs: **central** (all of India) always, and a state pack where one is built in
(**Maharashtra** now). The society's `state` (Society Settings) picks the packs. Each item shows its legal basis.

> These items are a working starting list, **not legal advice**. Dates, forms and thresholds change by notification, and a
> society's registration and bye-laws decide what applies to it. The committee or its auditor/advisor should check each
> item, switch off what does not apply, and reword or re-date what differs. For a state without a pack, add that state's
> rules as the society's own items (The list → Add item, tick *statutory*).

A statutory date that had already passed when the item first appeared is not treated as overdue: it is listed once under
**To confirm** in the Compliance tab, to be recorded as done (with the date) or marked as not applicable.

## Adding or changing items

The list tab has every item with a switch. Built-in items can be reworded and re-dated and switched off (never deleted, so
an update does not add them back). Items the society adds can be deleted. Only the admin or a committee member may change
or switch off a **statutory** built-in item.

## Technical

- Tables `manager_checklist_items`, `manager_checklist_logs` (one row per item per due date), `manager_checklist_signoffs`
  (one per society per day). Built-in items are copied into a society the first time the checklist is opened, and any
  built-ins added later are added on the next open.
- API under `/api/v1/manager-checklist` (`/society/{id}/today`, `/today.pdf`, `/compliance`, `/items`, `/signoff`,
  `/history`; `/items/{id}/complete`, PATCH/DELETE `/items/{id}`). All need *manager and above* and the caller's society.
- Built-in definitions: `backend/app/modules/checklist/services/standard_items.py`.
