# AR Society ERP — Architecture

## Overview

A multi-tenant, cloud-ready Society ERP built on clean architecture principles.
Designed for horizontal scalability and future module extensibility.

## Tech Stack

| Layer       | Technology                         |
|-------------|-------------------------------------|
| API         | FastAPI 0.115                       |
| ORM         | SQLAlchemy 2.0 (async-ready)        |
| Database    | PostgreSQL 15+                      |
| Auth        | JWT (python-jose) + bcrypt          |
| Deployment  | Railway (Procfile + runtime.txt)    |
| Validation  | Pydantic v2                         |

## Layer Diagram

```
┌──────────────────────────────────────────────┐
│                   Client                     │
└─────────────────────┬────────────────────────┘
                      │ HTTP
┌─────────────────────▼────────────────────────┐
│           FastAPI (main.py)                  │
│  CORS middleware · JWT middleware            │
│  /api/v1  prefix                             │
└─────────────────────┬────────────────────────┘
                      │
┌─────────────────────▼────────────────────────┐
│              API Routes Layer                │
│   auth · society · wing · flat · user       │
└─────────────────────┬────────────────────────┘
                      │ calls
┌─────────────────────▼────────────────────────┐
│              Services Layer                  │
│  Business logic · validation · composition  │
└─────────────────────┬────────────────────────┘
                      │ calls
┌─────────────────────▼────────────────────────┐
│           Repositories Layer                 │
│   BaseRepository[T] + domain-specific repos │
└─────────────────────┬────────────────────────┘
                      │ queries
┌─────────────────────▼────────────────────────┐
│           SQLAlchemy Models                  │
│  Society · Wing · Flat · User · Role · ...  │
└─────────────────────┬────────────────────────┘
                      │
┌─────────────────────▼────────────────────────┐
│              PostgreSQL                      │
└──────────────────────────────────────────────┘
```

## Data Model ERD (simplified)

```
Society ──< Wing ──< Flat ──< Resident
                        └──< Tenant
User >──< UserRole >──< Role
Resident >── User
Tenant   >── User
```

## Multi-Tenancy Design

- Each Society is an isolated tenant
- `society_id` foreign key propagates through Wing → Flat
- Future: Row-level security (PostgreSQL RLS) per society
- JWT payload carries `society_id` for scoped queries

## Security

- Passwords: bcrypt (12 rounds)
- Access tokens: short-lived (60 min default)
- Refresh tokens: long-lived (7 days), rotated on use
- Role guards implemented as FastAPI `Depends` factories
- Soft-delete on all models (is_active flag)

## Extensibility Pattern

Each new module follows this pattern:

```
app/
├── models/     visitor.py        ← SQLAlchemy model
├── schemas/    visitor.py        ← Pydantic in/out
├── repositories/ visitor_repo.py ← DB queries
├── services/   visitor_service.py ← business logic
├── api/routes/ visitor.py        ← FastAPI router
```

Then register the router in `app/api/__init__.py`.

---

## Database & Migration Architecture

### Connection Strategy
- Engine created lazily in `app/db/session.py` — no crash on missing DB
- `pool_pre_ping=True` — stale connections detected automatically
- `check_db_connection()` — used by `/health` to report DB status live

### Alembic Migration Flow
```
Developer changes model
  → alembic revision --autogenerate -m "describe change"
  → alembic upgrade head
  → commit alembic/versions/*.py to git
  → Railway auto-applies on next deploy (RUN_MIGRATIONS=true)
```

### Railway PostgreSQL Integration
1. Add PostgreSQL plugin in Railway → `DATABASE_URL` auto-injected
2. Set `RUN_MIGRATIONS=true` in Railway Variables
3. Set `SECRET_KEY` to a strong random value
4. Deploy → `start.sh` runs `alembic upgrade head` then starts uvicorn

### startup sequence (Railway)
```
nixpacks build → pip install deps into /opt/venv
↓
bash /app/start.sh
  ├── cd /app/backend
  ├── alembic upgrade head  (if RUN_MIGRATIONS=true)
  └── uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
