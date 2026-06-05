# Subscription Architecture — AR Society ERP

## Overview

The subscription model is architecture-complete but payment-gateway-deferred.
All data structures, status fields, and workflow hooks are implemented.
Actual payment processing is a future integration point.

## Database Schema (on `societies` table)

```sql
-- Trial fields
is_trial                 BOOLEAN   NOT NULL DEFAULT TRUE
trial_start_date         DATE      NOT NULL
trial_end_date           DATE      NOT NULL
account_status           VARCHAR   NOT NULL DEFAULT 'TRIAL'

-- Subscription fields (nullable until upgraded)
subscription_plan        VARCHAR   NULL  -- 'starter' | 'growth' | 'enterprise'
subscription_status      VARCHAR   NULL  -- 'active' | 'cancelled' | 'past_due'
subscription_start_date  DATE      NULL
subscription_expiry_date DATE      NULL

-- Usage limits
allowed_users       INTEGER NOT NULL DEFAULT 50
allowed_flats       INTEGER NOT NULL DEFAULT 100
allowed_storage_mb  INTEGER NOT NULL DEFAULT 1024

-- Setup tracking
setup_completed             BOOLEAN NOT NULL DEFAULT FALSE
setup_completion_percentage INTEGER NOT NULL DEFAULT 0
contact_person_name         VARCHAR NULL
```

## Account Status FSM

```
TRIAL ──────────────→ ACTIVE (platform admin activates)
  │                      │
  ↓                      ↓
EXPIRED             CANCELLED (future: user action)
  │
  ↓
SUSPENDED (platform admin action)
```

Valid transitions:
```python
ACCOUNT_STATUS_TRANSITIONS = {
    "TRIAL":     {"ACTIVE", "EXPIRED", "SUSPENDED"},
    "ACTIVE":    {"SUSPENDED", "CANCELLED", "EXPIRED"},
    "EXPIRED":   {"ACTIVE", "SUSPENDED"},
    "SUSPENDED": {"ACTIVE", "CANCELLED"},
    "CANCELLED": set(),  # terminal state
}
```

## Subscription Plans (Future Schema)

```json
{
  "starter": {
    "allowed_users": 50,
    "allowed_flats": 100,
    "allowed_storage_mb": 1024,
    "price_monthly_inr": 999
  },
  "growth": {
    "allowed_users": 150,
    "allowed_flats": 300,
    "allowed_storage_mb": 5120,
    "price_monthly_inr": 2499
  },
  "enterprise": {
    "allowed_users": -1,
    "allowed_flats": -1,
    "allowed_storage_mb": 20480,
    "price_monthly_inr": null
  }
}
```

## Usage Limit Enforcement (Future)

When implementing limits:
```python
# Before creating a new user:
if society.allowed_users != -1:
    count = db.query(User).filter(...).count()
    if count >= society.allowed_users:
        raise HTTPException(402, "User limit reached. Upgrade your plan.")
```

## Payment Integration Points (Future)

- `POST /api/v1/subscriptions/checkout` → Razorpay/Stripe payment link
- `POST /api/v1/webhooks/payment` → Update `account_status = ACTIVE`
- `POST /api/v1/subscriptions/cancel` → Set `account_status = CANCELLED`

All hooks are no-ops currently; structure is in place for drop-in implementation.

## Trial → Paid Conversion Flow

```
1. Platform Admin or automated job detects trial_end_date approaching
2. Warning email sent (future: email service)
3. Society Admin sees upgrade prompt in dashboard
4. Society Admin initiates payment → redirected to payment gateway
5. On success webhook → account_status = ACTIVE, subscription_plan = 'starter'
6. trial fields frozen (not deleted — historical record)
```
