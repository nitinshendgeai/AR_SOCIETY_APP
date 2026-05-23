# Complaint Management — Workflow

## Status FSM

```
Resident creates
      │
      ▼
    OPEN ──────────────────────────────────► REJECTED
      │ Admin/Committee assigns                  ▲
      ▼                                          │
  ASSIGNED ──────────────────────────────────────┤
      │ Staff begins work                        │
      ▼                                          │
  IN_PROGRESS ────────────────────────────────────┤
      │ Staff resolves                           │
      ▼                                          │
  RESOLVED ──► REOPENED (resident rejects) ──────┘
      │
      ▼ Resident/Admin confirms
   CLOSED
```

## API Flow

| Step | Actor | Endpoint |
|------|-------|----------|
| 1. Create | Any member | `POST /api/v1/complaints/` |
| 2. Assign | Admin/Committee | `POST /api/v1/complaints/{id}/assign` |
| 3. Progress | Staff+ | `POST /api/v1/complaints/{id}/status` |
| 4. Resolve | Staff+ | `POST /api/v1/complaints/{id}/status` |
| 5. Reopen | Any member | `POST /api/v1/complaints/{id}/reopen` |
| 6. Close | Staff+ | `POST /api/v1/complaints/{id}/status` |

## Query Endpoints

| Endpoint | Access |
|----------|--------|
| `GET /complaints/{id}` | Any member |
| `GET /complaints/society/{id}` | Admin, Committee |
| `GET /complaints/society/{id}/open` | Admin, Committee |
| `GET /complaints/me/complaints` | Any member |
| `GET /complaints/me/assigned` | Staff+ |

## Auto-numbered
Each complaint gets a sequential number: `CMP-00001`, `CMP-00002` per society.

## Audit + Notifications
Every transition → AuditLog + StatusHistory entry + in-app notification to relevant parties.
