# AR Society ERP

A production-grade, cloud-ready Society Management ERP built with FastAPI, PostgreSQL, and clean architecture principles.

## Project Structure

```
AR_SOCIETY_APP/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI entrypoint
│   │   ├── core/
│   │   │   ├── config.py         # Pydantic settings
│   │   │   ├── security.py       # JWT + bcrypt
│   │   │   └── dependencies.py   # Auth + RBAC guards
│   │   ├── db/
│   │   │   ├── base.py           # DeclarativeBase + TimestampMixin
│   │   │   └── session.py        # Engine + get_db
│   │   ├── models/               # SQLAlchemy ORM models
│   │   ├── schemas/              # Pydantic request/response schemas
│   │   ├── repositories/         # Data access layer
│   │   ├── services/             # Business logic layer
│   │   ├── api/routes/           # FastAPI routers
│   │   └── utils/                # Helpers
│   ├── requirements.txt
│   ├── Procfile                  # Railway deployment
│   ├── runtime.txt
│   └── .env.example
├── docs/
│   ├── ARCHITECTURE.md
│   ├── RBAC_MATRIX.md
│   ├── WORKFLOWS.md
│   └── ROADMAP.md
└── README.md
```

## Quick Start

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set DATABASE_URL and SECRET_KEY
uvicorn app.main:app --reload --app-dir .
```

Open http://localhost:8000/docs for the interactive API explorer.

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [RBAC Matrix](docs/RBAC_MATRIX.md)
- [Workflows](docs/WORKFLOWS.md)
- [Roadmap](docs/ROADMAP.md)
