# Society Self-Registration — AR Society ERP

## Overview

Public self-service registration. No admin required. Society registers itself,
trial starts automatically, and default roles + users are created in one transaction.

## API Endpoint

```
POST /api/v1/public/register
Content-Type: application/json
Authorization: None (public endpoint)
```

## Request Body

```json
{
  "society_name":       "Sunrise Apartments",
  "society_code":       "SUNAP",
  "contact_person_name": "Rajesh Kumar",
  "contact_email":      "rajesh@example.com",
  "contact_mobile":     "9876543210",
  "city":               "Pune",
  "state":              "Maharashtra",
  "country":            "India",
  "total_wings":        3,
  "total_flats":        60,
  "terms_accepted":     true
}
```

## Validations

| Field | Rule |
|-------|------|
| `society_name` | Required, unique |
| `society_code` | Required, unique, 3–10 chars, alphanumeric uppercase |
| `contact_email` | Required, unique, valid email |
| `contact_mobile` | Required, unique, 10-digit Indian mobile |
| `terms_accepted` | Must be `true` |
| `total_flats` | ≥ 1, ≤ 10000 |

## Response

```json
{
  "society_id":    "uuid",
  "society_name":  "Sunrise Apartments",
  "society_code":  "SUNAP",
  "trial_end_date": "2026-07-05",
  "trial_days":    30,
  "credentials": [
    {"role": "Society Admin",  "email": "admin@sunap.arsociety.com",     "password": "TempPwd@123"},
    {"role": "Chairman",       "email": "chairman@sunap.arsociety.com",  "password": "TempPwd@456"},
    {"role": "Secretary",      "email": "secretary@sunap.arsociety.com", "password": "TempPwd@789"},
    {"role": "Treasurer",      "email": "treasurer@sunap.arsociety.com", "password": "TempPwd@012"}
  ],
  "message": "Society registered successfully. Trial starts now."
}
```

## Registration Flow

```
Client → POST /api/v1/public/register
  │
  ├── Validate uniqueness (society_name, society_code, contact_email, contact_mobile)
  ├── Create Society (account_status=TRIAL, trial_start=today, trial_end=+30d)
  ├── Create Default Roles (13 roles, idempotent)
  ├── Create Default Users (4 users: admin, chairman, secretary, treasurer)
  │     └── All: must_change_password=True
  ├── Audit log: "society_self_registered"
  ├── Email admin@duxos.in — registration details + default user credentials
  └── Return society + credentials
```

## Admin Notification Email

On every successful registration, `admin@duxos.in` (configurable via the
`ADMIN_NOTIFICATION_EMAIL` env var) is emailed:

- The new society's registration details (name, code, contact, location, trial end date)
- Every default user created, with role, email, and temporary password

This is sent over SMTP (`SMTP_HOST`/`SMTP_PORT`/`SMTP_USERNAME`/`SMTP_PASSWORD`/
`SMTP_FROM_EMAIL`/`SMTP_USE_TLS` env vars — see `backend/.env.example`). While
`SMTP_HOST` is unset, sending is a no-op and registration is unaffected — the
credentials are still returned once in the API response either way. Delivery
runs on a background thread so a slow or failing SMTP call never blocks the
registration request.

## Security Notes

- Endpoint is rate-limited (10 req/min per IP — to be enforced via middleware)
- Credentials are returned **once only** — not stored in plain text
- society_code is normalised to UPPERCASE before uniqueness check
- contact_mobile is stored as-is; E.164 normalisation is future work
