"""
Pytest configuration — shared fixtures for all tests.

Uses SQLite with JSON column type substitution for JSONB fields.
No external database required for unit/integration tests.
"""
import os
import sys
import pytest
from typing import Generator

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ar_society.db")
os.environ.setdefault("SECRET_KEY",   "test-secret-key-for-pytest-only")
os.environ.setdefault("APP_ENV",      "test")

# Patch JSONB → JSON for SQLite compatibility BEFORE any model imports
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy import JSON as SA_JSON
import sqlalchemy.dialects.postgresql as pg_dialect

# Override JSONB to use plain JSON in test environment
class _JSONBCompat(SA_JSON):
    """Drop-in JSONB replacement that works with SQLite."""
    pass

pg_dialect.JSONB = _JSONBCompat
pg_dialect.base.JSONB = _JSONBCompat

import sqlalchemy.dialects.postgresql.base as pg_base
pg_base.JSONB = _JSONBCompat

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

# Now safe to import app (models use JSONB which is now patched)
from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DB_URL = "sqlite:///./test_ar_society.db"

engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    import app.models  # noqa — register all models
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    try: os.remove("./test_ar_society.db")
    except FileNotFoundError: pass


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    connection  = engine.connect()
    transaction = connection.begin()
    session     = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db: Session) -> TestClient:
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ── Seed helpers ──────────────────────────────────────────────────────────────

def make_user(db: Session, email: str, password: str = "Test@1234",
              full_name: str = "Test User", role: str = "Resident"):
    from app.models.user import User, UserRole, UserStatus
    from app.models.role import Role
    from app.core.security import hash_password, create_access_token

    r = db.query(Role).filter(Role.name == role).first()
    if not r:
        r = Role(name=role); db.add(r); db.flush()

    user = User(
        email=email, phone=None, full_name=full_name,
        hashed_password=hash_password(password),
        status=UserStatus.ACTIVE,
    )
    db.add(user); db.flush()
    db.add(UserRole(user_id=user.id, role_id=r.id))
    db.commit(); db.refresh(user)

    token = create_access_token(str(user.id), {"roles": [role]})
    return {"user": user, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


def make_society(db: Session, name: str = "Test Society"):
    from app.models.society import Society
    s = Society(name=name, city="Mumbai", state="Maharashtra")
    db.add(s); db.commit(); db.refresh(s)
    return s


def make_wing(db: Session, society_id, name: str = "Wing A"):
    from app.models.wing import Wing
    w = Wing(society_id=society_id, name=name, code="A")
    db.add(w); db.commit(); db.refresh(w)
    return w


def make_flat(db: Session, wing_id, flat_number: str = "101"):
    from app.models.flat import Flat
    f = Flat(wing_id=wing_id, flat_number=flat_number)
    db.add(f); db.commit(); db.refresh(f)
    return f
