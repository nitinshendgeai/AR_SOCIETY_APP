"""The agent's worker rolls failed jobs back, exactly as production does. The shared `db` fixture joins an outer
transaction in "rollback_only" style, where a session rollback would also discard the test's own setup. These tests use a
dedicated SQLite database with SQLAlchemy's documented pysqlite SAVEPOINT recipe, and a session whose every commit or
rollback is a SAVEPOINT of the per-test outer transaction — so rollback behaves as it does against PostgreSQL."""
import os

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

_WORKER = os.environ.get("PYTEST_XDIST_WORKER")          # one database file per pytest-xdist worker
AGENT_DB = f"./test_ar_society_agent_{_WORKER}.db" if _WORKER else "./test_ar_society_agent.db"
_engine = create_engine(f"sqlite:///{AGENT_DB}", connect_args={"check_same_thread": False})


@event.listens_for(_engine, "connect")
def _connect(dbapi_connection, record):
    dbapi_connection.isolation_level = None            # take control of BEGIN (pysqlite otherwise breaks SAVEPOINTs)
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


@event.listens_for(_engine, "begin")
def _begin(conn):
    conn.exec_driver_sql("BEGIN")


@pytest.fixture(scope="session", autouse=True)
def agent_tables():
    import tests.conftest  # noqa: F401 — applies the UUID/JSONB SQLite shims before models are created
    import app.models  # noqa: F401
    from app.core.rbac_seed import seed_form_definitions, seed_permission_definitions
    from app.db.base import Base
    Base.metadata.create_all(bind=_engine)
    with _engine.connect() as conn:
        seed_permission_definitions(conn)
        seed_form_definitions(conn)
        conn.commit()
    yield
    Base.metadata.drop_all(bind=_engine)
    _engine.dispose()
    try:
        os.remove(AGENT_DB)
    except FileNotFoundError:
        pass


@pytest.fixture(scope="function")
def db(agent_tables):
    connection = _engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, autoflush=False, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()
