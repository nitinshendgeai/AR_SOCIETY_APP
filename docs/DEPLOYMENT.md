# Deployment — AR Society ERP

## Platform
- **Backend**: Railway (auto-deploy on `main` branch push)
- **Database**: Railway PostgreSQL (internal network)
- **URL**: `https://arsocietyapp-production.up.railway.app`

## Environment Variables (Railway)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | `postgresql://user:pass@host:5432/railway` |
| `SECRET_KEY` | ✅ | JWT signing key (min 32 chars) |
| `RUN_MIGRATIONS` | ✅ | Set `true` to auto-run `alembic upgrade head` |
| `APP_ENV` | optional | `production` |
| `PORT` | auto | Set by Railway |

## Build Config (`nixpacks.toml`)
```toml
[phases.setup]
nixPkgs = ["python312", "gcc"]

[phases.install]
cmds = [
  "python3 -m venv /opt/venv",
  "/opt/venv/bin/pip install -r backend/requirements.txt --quiet"
]

[start]
cmd = "bash /app/start.sh"
```

## Start Sequence (`start.sh`)
1. Print environment info
2. `cd /app/backend`
3. If `RUN_MIGRATIONS=true`: `alembic upgrade head`
4. `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## Migration Workflow

```bash
# 1. Create revision (locally)
cd backend
DATABASE_URL="..." alembic revision -m "my_change"

# 2. Fill upgrade()/downgrade() manually

# 3. Test locally
DATABASE_URL="sqlite:///test.db" alembic upgrade head

# 4. Push — Railway runs migrations automatically
git push origin main
```

**Never use `--autogenerate` in production.**

## Deployment Checklist

```
□ requirements.txt has no test deps (pytest, faker)
□ No duplicate entries in requirements.txt
□ alembic heads shows exactly ONE head
□ App imports cleanly (python -c "from app.main import app")
□ All tests pass (make test)
□ DATABASE_URL and SECRET_KEY set in Railway
□ RUN_MIGRATIONS=true set in Railway
```

## Local Development

```bash
# Install deps
pip install -r backend/requirements-dev.txt

# Copy env
cp backend/.env.example backend/.env
# Edit .env with local DATABASE_URL and SECRET_KEY

# Run server
cd backend && make run

# Run tests (SQLite, no DB needed)
cd backend && make test

# Generate seed data (requires live DB)
cd backend && make seed
```

## Database: Internal vs External URL

| Context | URL |
|---------|-----|
| Railway services (internal) | `postgresql://...@postgres.railway.internal:5432/railway` |
| External access | `postgresql://...@monorail.proxy.rlwy.net:PORT/railway` |

Always use the **internal URL** in `DATABASE_URL` for Railway deployments.
