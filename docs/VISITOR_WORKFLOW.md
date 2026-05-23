# Visitor & Gate Management — Workflow

## State Machine

```
Guard logs visitor
     │
     ▼
  PENDING ──────────────────────► REJECTED (resident rejects)
     │                                │
     │ Resident approves              │ Notify guard
     ▼                                ▼
  APPROVED                       [Entry denied]
     │
     │ Guard checks in
     ▼
  CHECKED_IN
     │
     │ Guard checks out
     ▼
  CHECKED_OUT
```

Also: EXPIRED (no action within timeout — future cron job)

## API Flow

| Step | Actor | Endpoint |
|------|-------|----------|
| 1. Log visitor | Security | `POST /api/v1/visitors/` |
| 2. Approve | Resident | `POST /api/v1/visitors/{id}/approve` |
| 2. Reject | Resident | `POST /api/v1/visitors/{id}/reject` |
| 3. Check-in | Security | `POST /api/v1/visitors/{id}/checkin` |
| 4. Check-out | Security | `POST /api/v1/visitors/{id}/checkout` |

## Query Endpoints

| Endpoint | Access |
|----------|--------|
| `GET /visitors/{id}` | Any authenticated |
| `GET /visitors/society/{id}` | Admin, Committee, Security |
| `GET /visitors/society/{id}/inside` | Admin, Committee, Security |
| `GET /visitors/me/pending-approvals` | Resident |
| `GET /visitors/me/visitors` | Resident |
| `GET /visitors/gates/{society_id}` | Any authenticated |

## Visitor Types
guest · delivery · cab · maintenance · vendor · emergency

## Notifications (in-app)
- Resident notified when visitor is logged (APPROVAL type)
- Guard notified when visitor is approved/rejected (ALERT/WARNING type)

## Audit Trail
Every state change → AuditLog entry + VisitorLog entry (append-only)
