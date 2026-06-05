# SaaS Trial Model — AR Society ERP

## Overview

AR Society ERP is a multi-tenant SaaS platform. Every new society onboards via a
30-day free trial. No payment is required to start. After trial, the society upgrades
to a paid subscription plan.

## Account Lifecycle

```
[Self-Registration]
       ↓
[TRIAL — 30 days]
       ↓
   ┌───┴───┐
   │       │
[ACTIVE] [EXPIRED]
   │       │
   │    [SUSPENDED] ← Platform Admin action
   │
[CANCELLED]
```

## Account Status Values

| Status | Description |
|--------|-------------|
| `TRIAL` | 30-day free period, full access |
| `ACTIVE` | Paid subscription, full access |
| `EXPIRED` | Trial or subscription ended; read-only |
| `SUSPENDED` | Suspended by Platform Admin; blocked access |
| `CANCELLED` | Society voluntarily cancelled |

## Trial Rules

| Condition | Behaviour |
|-----------|-----------|
| Days remaining > 7 | Normal access, no warning |
| Days remaining ≤ 7 | Show yellow warning banner |
| Days remaining ≤ 3 | Show red critical warning |
| Days remaining = 0 | Read-only mode; blocks write operations |
| Suspended | Access fully blocked; show suspension notice |

## Subscription Plans (Future)

| Plan | Flats | Users | Storage | Price |
|------|-------|-------|---------|-------|
| Starter | 100 | 50 | 1 GB | ₹999/mo |
| Growth | 300 | 150 | 5 GB | ₹2499/mo |
| Enterprise | Unlimited | Unlimited | 20 GB | Custom |

Payment gateway integration is deferred. Only the data model is implemented now.

## Database Fields on `societies`

```
account_status          TRIAL | ACTIVE | EXPIRED | SUSPENDED | CANCELLED
is_trial                Boolean
trial_start_date        Date
trial_end_date          Date
subscription_plan       String (nullable)
subscription_status     String (nullable)
subscription_start_date Date (nullable)
subscription_expiry_date Date (nullable)
allowed_users           Integer (default 50)
allowed_flats           Integer (default 100)
allowed_storage_mb      Integer (default 1024)
setup_completed         Boolean (default False)
setup_completion_percentage Integer (default 0)
```
