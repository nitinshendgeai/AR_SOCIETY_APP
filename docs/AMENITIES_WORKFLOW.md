# Amenity Management — Workflow

## Rule Engine (Database-driven)

Rules are stored in `amenity_rules` table — NOT hardcoded. Each rule has a `rule_type` and `rule_value`.

| Rule Type | Value Example | Effect |
|-----------|--------------|--------|
| `owners_only` | `true` | Only registered residents can book |
| `max_duration_hours` | `4` | Max 4h per booking |
| `max_bookings_per_week` | `2` | 2 bookings/week per user |
| `max_bookings_per_month` | `4` | 4 bookings/month per user |
| `min_advance_hours` | `24` | Must book 24h in advance |
| `max_advance_days` | `30` | Can't book more than 30 days ahead |
| `approval_required` | `true` | Committee must approve |
| `charge_per_hour` | `500.00` | ₹500/hour charge |
| `deposit_required` | `2000.00` | ₹2000 deposit |
| `max_guests` | `50` | Max 50 guests |

## Booking FSM

```
PENDING ──► APPROVED ──► COMPLETED
        ──► REJECTED
        ──► CANCELLED
APPROVED ──► CANCELLED
```

## API Flow

| Step | Actor | Endpoint |
|------|-------|----------|
| Setup amenity | Admin/Committee | `POST /amenities/` |
| Configure rules | Admin/Committee | `POST /amenities/{id}/rules` |
| Add blackout | Admin/Committee | `POST /amenities/{id}/blackouts` |
| Create booking | Any member | `POST /amenities/bookings` |
| Approve | Admin/Committee | `POST /amenities/bookings/{id}/approve` |
| Reject | Admin/Committee | `POST /amenities/bookings/{id}/reject` |
| Cancel | Any member | `POST /amenities/bookings/{id}/cancel` |
| Complete + log | Admin/Committee | `POST /amenities/bookings/{id}/complete` |

## Financial readiness
`charge_amount`, `deposit_amount`, `deposit_paid`, `deposit_refunded` on bookings.
`AmenityPricing` model supports hourly rates, flat rates, deposits.
Payment gateway integration ready when Finance module is built.
