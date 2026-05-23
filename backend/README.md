# AR Society ERP — Backend

Production-grade FastAPI backend for Society Management.

## Quick Start (Local)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in your values
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs  
Health: http://localhost:8000/health

## Architecture

```
routes → services → repositories → models → PostgreSQL
```

## Roles

| Role      | Description                      |
|-----------|----------------------------------|
| Admin     | Full system access               |
| Committee | Society management               |
| Resident  | Own flat data                    |
| Security  | Gate & visitor access            |
| Staff     | Operational tasks                |

## Railway Deployment

1. Connect your GitHub repo to Railway
2. Add a PostgreSQL plugin — `DATABASE_URL` is auto-injected
3. Set remaining env vars in Railway dashboard
4. Deploy — Railway uses `Procfile` automatically

## Key Endpoints

| Method | Path                     | Auth       |
|--------|--------------------------|------------|
| POST   | /api/v1/auth/register    | Public     |
| POST   | /api/v1/auth/login       | Public     |
| GET    | /api/v1/auth/me          | Any user   |
| GET    | /api/v1/societies/       | Any user   |
| POST   | /api/v1/societies/       | Admin      |
| GET    | /api/v1/wings/           | Any user   |
| GET    | /api/v1/flats/           | Any user   |
| GET    | /api/v1/users/           | Admin      |
| POST   | /api/v1/users/{id}/roles | Admin      |
| GET    | /health                  | Public     |
