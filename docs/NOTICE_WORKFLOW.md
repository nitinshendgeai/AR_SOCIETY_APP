# Notice & Communication — Workflow

## Notice FSM
```
DRAFT → PUBLISHED → EXPIRED/ARCHIVED
```

## Audience Targeting
all_residents · owners_only · tenants_only · specific_wings · specific_flats · all_staff · security_team · committee · all

## Acknowledgement Flow
Notice published → Resident reads → POST /acknowledge → ack_count++
GET /{notice_id}/acknowledgements → rate, pending count, list of acknowledgers

## Emergency Alerts
Trigger (active) → Resolve (resolved/cancelled)
Alert types: fire · water_leakage · lift_failure · power_failure · security_threat · medical · gas_leak
Channel flags: push_sent · sms_sent · whatsapp_sent (future integration)

## Communication Log
Every dispatch attempt → CommunicationLog with channel, status, sent_at
Channels: in_app · sms · email · push · whatsapp


## Notice board (how it works now)

**Audience** is worked out from each person's roles and the flats they live in: `all`, `all_residents`, `owners_only`
(owners and co-owners), `tenants_only`, `specific_wings`, `specific_flats` (targets must be wings/flats of the society),
`all_staff`, `security_team`, `committee`. It is computed when a notice is published (`total_audience`) and again
whenever someone opens the board, so a person only ever sees notices meant for them. An audience with nobody in it
can't be published.

**Lifecycle**: draft → published → archived. A draft can be edited (`PATCH /notices/{id}`) or deleted
(`DELETE`); a published notice is fixed (archive it and write another). A notice past its `expiry_date` leaves the board.

| Endpoint | Who | Purpose |
|----------|-----|---------|
| `POST /notices/` · `PATCH` · `DELETE` | admin, committee | Write, change, delete a draft |
| `POST /notices/{id}/publish` · `/archive` | admin, committee | Publish to the audience; archive |
| `GET /notices/society/{sid}/all?status=` | admin, committee | Every notice, drafts included |
| `GET /notices/society/{sid}/mine` | any member | The caller's board: unexpired, in the audience, urgent first, each with `acknowledged` |
| `GET /notices/{id}` | member in the audience, or the committee | One notice |
| `POST /notices/{id}/acknowledge` | audience only | "I have read this" (once; the flat must be the caller's own) |
| `GET /notices/{id}/acknowledgements` | admin, committee | Totals, who has read it (name, flat), who has not |
| `POST /notices/emergency/` · `/{id}/resolve` | admin, committee, manager, security | Raise or end an alert |
| `GET /notices/emergency/active/{sid}` | any member | Alerts in force |
| `GET /notices/emergency/history/{sid}` | admin, committee | Past alerts |

**Emergency alerts** create an in-app notification for everyone the alert is meant to reach (residents, security team,
committee; each can be switched off), and the app shows a red bar on every page while one is active (checked every minute).

Everything is confined to the caller's society (another society's notice or alert reads as not found; its society-wide
lists are refused). The Announcements endpoints are kept but the app uses notices only.

App: **Community → Notices** (everyone). The committee gets *Manage* (drafts, published, archived), *New notice*,
who-has-read-it, and *Emergency alert*.
