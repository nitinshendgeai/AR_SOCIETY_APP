# Railway Setup Guide

## Railway Variables — set these in your service → Variables tab

| Variable | Value |
|---|---|
| `DATABASE_URL` | `postgresql://postgres:TVulfWPoqUanbCRMIQvomLMbQXQELEUA@postgres.railway.internal:5432/railway` |
| `RUN_MIGRATIONS` | `true` |
| `SECRET_KEY` | `ar-society-erp-prod-2026-nitin` |
| `APP_ENV` | `production` |
| `ALLOWED_ORIGINS` | `["*"]` |

> The internal URL (`postgres.railway.internal`) is only reachable from within
> Railway. Use the public proxy URL only for external tools (TablePlus, DBeaver).

## Public URL (for local DB tools only)
```
postgresql://postgres:TVulfWPoqUanbCRMIQvomLMbQXQELEUA@kodama.proxy.rlwy.net:57666/railway
```

## After deploying — verify

- `https://YOUR_RAILWAY_URL/health` → `"database": {"status": "connected"}`
- `https://YOUR_RAILWAY_URL/docs` → Swagger UI

## First Admin User

1. POST `/api/v1/auth/register` — create your user
2. POST `/api/v1/users/{id}/roles` body: `{"role_name": "Admin"}`

## Local Alembic (using public URL)

```bash
cd backend
DATABASE_URL="postgresql://postgres:TVulfWPoqUanbCRMIQvomLMbQXQELEUA@kodama.proxy.rlwy.net:57666/railway" \
  alembic upgrade head

# New migration after model changes
DATABASE_URL="postgresql://..." alembic revision --autogenerate -m "add visitor table"
DATABASE_URL="postgresql://..." alembic upgrade head
```
