# Trial Management — AR Society ERP

## Trial Lifecycle

```
Registration → TRIAL (30d) → EXPIRED → (Platform Admin) → ACTIVE or SUSPENDED
```

## Trial Status Endpoint

```
GET /api/v1/societies/{id}/trial-status
Authorization: Bearer <society_admin_token>
```

Response:
```json
{
  "account_status":   "TRIAL",
  "is_trial":         true,
  "trial_start_date": "2026-06-05",
  "trial_end_date":   "2026-07-05",
  "trial_days_remaining": 30,
  "trial_expired":    false,
  "expiry_warning":   false,
  "expiry_critical":  false,
  "subscription_plan": null
}
```

## Warning Thresholds

| `trial_days_remaining` | `expiry_warning` | `expiry_critical` |
|------------------------|-----------------|-------------------|
| > 7 | false | false |
| 4–7 | true | false |
| 1–3 | true | true |
| 0 | false | false (use `trial_expired`) |

## Platform Admin Trial Operations

```
POST /api/v1/platform-admin/societies/{id}/extend-trial
Body: { "extend_days": 15 }

POST /api/v1/platform-admin/societies/{id}/suspend
Body: { "reason": "Non-payment" }

POST /api/v1/platform-admin/societies/{id}/activate
Body: { "plan": "starter" }
```

## Read-Only Mode (Expired)

When `account_status = EXPIRED`:
- GET endpoints continue to work
- All POST/PATCH/DELETE endpoints return `402 Payment Required`
- Flutter shows a full-screen expired banner with "Contact Support" CTA
- Platform Admin can extend trial to restore access

## Auto-Expiry

Trial end date is evaluated at request time by comparing `trial_end_date` with `today`.
No background job required for status transition — the API computes it on-the-fly.
`account_status` is updated to `EXPIRED` lazily on first authenticated request after expiry.

## Suspension

Platform Admin can suspend a society at any time regardless of trial status.
Suspended societies receive `403 Forbidden` on all endpoints with message:
`"Your account has been suspended. Contact support@arsocietyapp.com."`
