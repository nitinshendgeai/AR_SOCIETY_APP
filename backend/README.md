# AR Society ERP — Backend

Production-grade FastAPI backend for Society Management.

## Quick Start (Local)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in DATABASE_URL and SECRET_KEY
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs
Health:   http://localhost:8000/health

## Database Migrations (Alembic)

### First-time setup (once DB is connected)
```bash
cd backend

# Apply all migrations — creates all tables
alembic upgrade head

# Check current migration state
alembic current

# View migration history
alembic history --verbose
```

### Create a new migration after model changes
```bash
# Auto-generate from model diff (requires live DB)
alembic revision --autogenerate -m "describe your change"

# Apply it
alembic upgrade head
```

### Rollback
```bash
# Rollback one step
alembic downgrade -1

# Rollback to base (empty DB)
alembic downgrade base
```

### Railway: auto-run migrations on deploy
Set this env var in Railway dashboard:
```
RUN_MIGRATIONS=true
```
This runs `alembic upgrade head` automatically on every boot.

## Architecture

```
routes → services → repositories → models → PostgreSQL
```

## Roles

| Role      | Description              |
|-----------|--------------------------|
| Admin     | Full system access       |
| Committee | Society management       |
| Resident  | Own flat data            |
| Security  | Gate & visitor access    |
| Staff     | Operational tasks        |

## Railway Deployment

1. Connect GitHub repo to Railway
2. Add PostgreSQL plugin → `DATABASE_URL` auto-injected
3. Set env vars: `SECRET_KEY`, `RUN_MIGRATIONS=true`
4. Deploy — Railway uses `nixpacks.toml` + `railway.json`

## Key Endpoints

| Method | Path                       | Auth     |
|--------|----------------------------|----------|
| GET    | /health                    | Public   |
| POST   | /api/v1/auth/register      | Public   |
| POST   | /api/v1/auth/login         | Public   |
| GET    | /api/v1/auth/me            | Any user |
| GET    | /api/v1/societies/         | Any user |
| POST   | /api/v1/societies/         | Admin    |
| GET    | /api/v1/wings/             | Any user |
| GET    | /api/v1/flats/             | Any user |
| GET    | /api/v1/users/             | Admin    |
| POST   | /api/v1/users/{id}/roles   | Admin    |
