# Automatic tasks

Reminders and housekeeping that used to wait for someone to press a button. Switch them on or off, see what each did
last, and run one by hand from **Administration → Automatic tasks** (Society Admin and committee).

| Task | When | What it does | Default |
|------|------|--------------|---------|
| Maintenance dues reminders | daily | Reminds members (with an app login) whose dues are older than the set months, no more often than every N days | **off** (it goes to members) |
| Tenant agreement alerts | daily | Tells the office, and the tenant if they have a login, 30 days and again 7 days before an agreement ends (uses `alert_sent_30` / `alert_sent_7`) | on |
| Asset service and warranty digest | weekly | One note to the office: assets due for service (and overdue), warranties ending soon | on |
| Billing cycle reminder | weekly | From the 3rd, if no cycle covers today and the society has billed before | on |
| Expire unanswered visitor requests | daily | `pending` visitor requests older than 24 hours become `expired` | on |

## How it runs
- A background thread in the API (`app/modules/automation/scheduler.py`) wakes every 10 minutes and runs what is due.
  A society's tasks start once its own clock reaches 08:00. Societies that are suspended, expired or cancelled are skipped.
- Each run for a period (a day, or an ISO week) is claimed by a row in `scheduled_job_runs`
  (unique on task + society + period), so with several workers a task still runs once.
- Settings live in `society_automation` (no row = the defaults above). A failing task is recorded as `error` with its
  message and never stops the others.
- `SCHEDULER_ENABLED=false` turns the loop off (the tests do). "Run now" always works.

## API (admin / committee, own society)
- `GET /api/v1/automation/{society_id}` – settings and each task with its last run
- `PUT /api/v1/automation/{society_id}` – change any of `dues_reminders`, `reminder_every_days`, `reminder_min_months`,
  `agreement_alerts`, `asset_alerts`, `billing_nudge`, `visitor_expiry`
- `POST /api/v1/automation/{society_id}/run` `{ "job": "agreement_alerts" }` – run one now (recorded as a manual run)

## Not automatic (on purpose)
Late fees, bill generation and posting recurring expenses move money, so they stay a person's decision; the dashboard and
the billing reminder tell the office when they are due.
