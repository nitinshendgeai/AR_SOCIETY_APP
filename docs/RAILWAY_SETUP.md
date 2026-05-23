# Railway Setup Guide

## Step 1 — Variables to set in Railway Dashboard

Go to your service → **Variables** tab → add these:

| Variable | Value |
|---|---|
| `DATABASE_URL` | `postgresql://postgres:TVulfWPoqUanbCRMIQvomLMbQXQELEUA@kodama.proxy.rlwy.net:57666/railway` |
| `RUN_MIGRATIONS` | `true` |
| `SECRET_KEY` | `ar-society-erp-prod-2026-change-this-to-random` |
| `APP_ENV` | `production` |
| `ALLOWED_ORIGINS` | `["*"]` |

> **Tip:** For `DATABASE_URL`, Railway also provides an *internal* URL like
> `postgresql://postgres:PASSWORD@postgres.railway.internal:5432/railway`
> which is faster. Use that if your DB and app are in the same Railway project.

## Step 2 — Trigger a Deploy

After setting variables, go to **Deployments** → **Deploy** (or push a commit).

## Step 3 — Verify

Once deployed, visit:
- `https://YOUR_RAILWAY_URL/health` → should show `"database": {"status": "connected"}`
- `https://YOUR_RAILWAY_URL/docs` → Swagger UI

## Step 4 — First Admin User

Use Swagger `/api/v1/auth/register` to create your first user, then use
`/api/v1/users/{id}/roles` to assign the `Admin` role.

## Alembic Commands (local, with DB accessible)

```bash
cd backend

# Apply all migrations
DATABASE_URL="postgresql://..." alembic upgrade head

# Check state
DATABASE_URL="postgresql://..." alembic current

# New migration after model changes
DATABASE_URL="postgresql://..." alembic revision --autogenerate -m "add visitor table"
DATABASE_URL="postgresql://..." alembic upgrade head
```
