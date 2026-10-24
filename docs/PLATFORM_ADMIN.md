# Platform Admin — AR Society ERP

## What Is Platform Admin

Platform Admin is the AR Society App internal operations role.
It is NOT a society-level role — it is cross-society.

Platform Admin users:
- Are identified by `User.is_superadmin = True`
- Do not belong to any single society
- Access all societies from a single dashboard
- Use the same auth system (JWT) but get a different permission check

## How Platform Admin Is Identified

```python
# In dependencies.py
def require_platform_admin():
    def _checker(current_user: User = Depends(get_current_user)):
        if not current_user.is_superadmin:
            raise HTTPException(403, "Platform Admin access required")
        return current_user
    return _checker
```

## Platform Console (screens)
A platform admin signs in to the same app and lands on the **Platform Console** (sidebar: Platform Console only, since
the society screens need a society). *Societies* tab: tiles (societies, on trial, paid, suspended, with the people and flats
on the platform), search, a status filter and a card per society (standing, people and flats against their limits, last
sign-in, setup progress). *Activity* tab: what platform admins have done, across societies. Opening a society shows its
standing, usage bars, who runs it (its admins and last sign-in), the contact on file and its history, with the actions
**Extend trial**, **Put on a paid plan** (plan, optional paid-until date) / **Let them back in**, **Limits** and **Suspend**.
Form code `platform_admin` is granted only to the Platform Admin role (migration `5f2a3b4c5d6e`), is hidden from society
admins' Forms Matrix, and only a platform admin can change the Platform Admin role.

## Platform Admin Capabilities

| Action | Endpoint |
|--------|----------|
| List societies (usage, plan, contact; `q`, `status`) | `GET /api/v1/platform-admin/societies` |
| One society (profile, admins, history) | `GET /api/v1/platform-admin/societies/{id}` |
| Extend trial (TRIAL or EXPIRED) | `POST /api/v1/platform-admin/societies/{id}/extend-trial` |
| Suspend (a reason is required) | `POST /api/v1/platform-admin/societies/{id}/suspend` |
| Activate on a plan, optional `expires_on` | `POST /api/v1/platform-admin/societies/{id}/activate` |
| Set limits (users, flats, storage; not below current use) | `PUT /api/v1/platform-admin/societies/{id}/limits` |
| Every optional service and whether it is on for a society | `GET /api/v1/platform-admin/societies/{id}/services` |
| Switch one service on or off for a society | `PUT /api/v1/platform-admin/societies/{id}/services/{key}` body `{"enabled": false}` |
| Preview what **Clean data** would delete (rows per table; deletes nothing) | `GET /api/v1/platform-admin/societies/{id}/clean-data` |
| **Clean data**: delete all of the society's rows (tables, the society record, other societies and platform admins stay); body `{"confirm": "<society code>"}` | `POST /api/v1/platform-admin/societies/{id}/clean-data` |
| What platform admins have done | `GET /api/v1/platform-admin/activity` |
| Platform-wide counts | `GET /api/v1/platform-admin/stats` |

## Clean data
*Clean data* (red button on a society's page) permanently deletes everything the society has entered: its people and logins,
flats, bills, vouchers, complaints and so on, but keeps the four default logins onboarding created
(`admin@`, `chairman@`, `secretary@`, `treasurer@<society code>.com`) so the society can sign in and start again. Only rows go; no table is touched, and the society record, its code, other
societies, platform admins and the shared roles/forms stay. The admin sees the row counts first and must type the society code
to confirm. It is recorded under *Activity* as "Data cleaned". The same logic runs from the command line:
`python scripts/purge_society.py <CODE> [--dry-run] [--delete-society] [--wipe-logins]` (code in `app/services/society_purge.py`).
Uploaded files on disk or storage are not removed.

## What suspending does
A suspended or closed society is **locked out**: its people cannot sign in or refresh a session, and every API call
returns `403 "Your society's account is suspended. Please contact support."` Only `/auth/me` and `/auth/logout` still work, so
the app can say who they are and sign out. Platform admins are never blocked. Their data is kept. Letting them back in
(**Activate**) restores access at once. Enforcement is in `app/core/society_gate.py`, called from `get_current_user`,
login and refresh.

An **ended trial is not blocked.** It is flagged (*Trial ended* on the society, and counted on the *On trial* tile) so you can
extend it, activate it or suspend it, but the society keeps working. `docs/TRIAL_MANAGEMENT.md` describes a read-only mode
for expired trials; that is not built, and the status only flips to EXPIRED when someone opens the trial-status call.
**Limits are recorded, not enforced:** a society can go over its user or flat allowance.

## Switching services on and off for a society
Only the platform admin does this, by hand, one society at a time: open the society in the Platform Console and use the
**Services** switches (each asks for confirmation when turning one off). Every society has every service until one is
switched off. The catalogue is `app/core/services_catalog.py`: visitors, complaints, notices, amenities, parking,
staff & duty, vendors & work orders, stores & assets, meetings/polls/documents, certificates & NOC, parcels & domestic
help, shops, the manager's checklist and accounts (books). Everything else (sign-in, wings/floors/flats, residents,
tenants, vehicles, users and roles, maintenance billing and payments, notifications, the dashboard) is core and always on.

A service that is off is closed in three places:
- **The API** refuses its calls for that society's people with `403 "<Service> is not enabled for your society. Please
  contact support."` (checked in `get_current_user` via `society_gate.service_block_reason`, by the first path segment
  under `/api/v1`). A platform admin is never refused, and a suspended society still gets the suspended message first.
- **The menu**: its form codes are dropped from `/roles/forms/mine`, so it leaves the sidebar, drawer and phone bar.
- **The dashboards**: `/auth/me` carries `enabled_services`, and the role dashboards leave out that service's cards, quick
  actions and banners. The admin overview's *Needs attention* list, *Money* row and *Visitors today* are omitted
  server-side for a service that is off.

Records are kept; switching a service back on restores it at once. Only switched-off services are stored
(`society_services`, migration `e1b4c8d6f3a2`), and each switch is recorded in the society's history. Internal links
still work: for example the books keep receiving postings from billing even if *Accounts* is off.

## Creating a Platform Admin User

There is no API for the first one. Run, once per database (it is safe to run again):

```bash
cd backend
DATABASE_URL="..." PLATFORM_ADMIN_PASSWORD='a-strong-password-1' \
  python -m app.utils.create_platform_admin ops@yourdomain.com "Platform Operations"
```

It creates the `Platform Admin` role and a user with `is_superadmin = true`, no society, and the first-login wizards
switched off. The password (10+ characters, letters and digits) comes from `PLATFORM_ADMIN_PASSWORD` or a prompt.
An existing user is promoted and keeps their password unless you pass `--reset-password`. See
`DEPLOYMENT.md` → *Starting with a blank database*.

## Security Isolation

- Platform Admin routes are under `/api/v1/platform-admin/` prefix
- All routes require `require_platform_admin()` dependency — no exceptions
- Society admin tokens cannot access platform admin routes
- Platform admin tokens CAN access society-level routes (for support purposes)
- All platform admin actions are audit-logged with `module="platform_admin"` and shown in the app's Activity tab

## Not built
Cancelling a society, deleting one, impersonating a society admin, billing and invoices, e-mailing a society, and enforcing
limits or read-only for ended trials.
