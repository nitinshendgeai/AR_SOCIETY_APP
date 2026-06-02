# Railway Setup Guide

## Railway Variables — set these in your service → Variables tab

| Variable | Value |
|---|---|
| `DATABASE_URL` | `<railway_database_url>` (copy from Railway → Postgres → Connect tab) |
| `RUN_MIGRATIONS` | `true` |
| `SECRET_KEY` | `<generate_new_secret>` (e.g. `openssl rand -hex 32`) |
| `APP_ENV` | `production` |
| `ALLOWED_ORIGINS` | `["*"]` |

> The internal URL (`postgres.railway.internal`) is only reachable from within
> Railway. Use the public proxy URL only for external tools (TablePlus, DBeaver).

## Public URL (for local DB tools only)
```
postgresql://postgres:<DB_PASSWORD>@<proxy_host>:<proxy_port>/railway
```
Find the real values in Railway → Postgres service → Connect tab.

## After deploying — verify

- `https://YOUR_RAILWAY_URL/health` → `"database": {"status": "connected"}`
- `https://YOUR_RAILWAY_URL/docs` → Swagger UI

## First Admin User

1. POST `/api/v1/auth/register` — create your user
2. POST `/api/v1/users/{id}/roles` body: `{"role_name": "Admin"}`

## Local Alembic (using public URL)

```bash
cd backend
DATABASE_URL="<public_proxy_url_from_railway>" \
  alembic upgrade head

# New migration after model changes (manual only — never --autogenerate in prod)
DATABASE_URL="<public_proxy_url_from_railway>" alembic revision -m "describe_change"
DATABASE_URL="<public_proxy_url_from_railway>" alembic upgrade head
```
