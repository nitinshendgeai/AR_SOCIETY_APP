"""Phase 1 — start-up and readiness: /health stays a liveness probe and stops publishing where the database is;
/health/ready tells the truth; a failed start-up migration is neither silent nor leaks credentials; the migration
graph is a single chain."""
import logging

import pytest

from app.db import migrate

API = "/api/v1"


@pytest.fixture(autouse=True)
def _reset_startup_result():
    saved = dict(migrate.startup_result)
    migrate.startup_result.update(attempted=False, ok=None, error=None)
    yield
    migrate.startup_result.update(saved)


def _ready_world(monkeypatch, *, db="connected", migrations=None):
    import app.main as main
    import app.db.session as session
    monkeypatch.setattr(session, "check_db_connection", lambda: {"status": db})
    monkeypatch.setattr(main, "migration_status", lambda: migrations if migrations is not None
                        else {"current": ["x"], "head": ["x"], "up_to_date": True})


# ── /health ──────────────────────────────────────────────────────────────────

def test_health_is_still_a_200_liveness_probe(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.json()["database"]["status"] in ("connected", "unavailable")


def test_health_does_not_publish_where_the_database_is(client, monkeypatch):
    import app.db.session as session
    monkeypatch.setattr(session, "check_db_connection",
                        lambda: {"status": "unavailable", "error": "connection to server at \"db.internal\" failed",
                                 "url": "postgresql://admin:***@db.internal:5432/prod"})
    body = client.get("/health").text
    assert "db.internal" not in body and "admin" not in body and "5432" not in body and "postgresql" not in body


def test_health_does_not_echo_a_migration_check_error(client, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "migration_status", lambda: {"status": "unknown", "error": "password authentication failed for user admin"})
    body = client.get("/health").json()
    assert body["migrations"] == {"status": "unknown"}


# ── /health/ready ────────────────────────────────────────────────────────────

def test_ready_when_database_is_up_and_schema_is_current(client, monkeypatch):
    _ready_world(monkeypatch)
    r = client.get("/health/ready")
    assert r.status_code == 200 and r.json()["status"] == "ready"


def test_not_ready_when_the_database_is_down(client, monkeypatch):
    _ready_world(monkeypatch, db="unavailable")
    r = client.get("/health/ready")
    assert r.status_code == 503 and r.json()["database"] == "unavailable"


@pytest.mark.parametrize("migrations", [
    {"current": ["old"], "head": ["new"], "up_to_date": False},
    {"status": "unknown", "error": "boom"},
])
def test_not_ready_when_the_schema_is_behind_or_unknown(client, monkeypatch, migrations):
    _ready_world(monkeypatch, migrations=migrations)
    r = client.get("/health/ready")
    assert r.status_code == 503 and r.json()["status"] == "not_ready"
    assert "boom" not in r.text


def test_not_ready_after_a_failed_start_up_migration(client, monkeypatch):
    _ready_world(monkeypatch)
    migrate.startup_result.update(attempted=True, ok=False, error="x")
    r = client.get("/health/ready")
    assert r.status_code == 503 and r.json()["startup_migration"] == {"attempted": True, "ok": False}


def test_ready_after_a_successful_start_up_migration(client, monkeypatch):
    _ready_world(monkeypatch)
    migrate.startup_result.update(attempted=True, ok=True)
    assert client.get("/health/ready").status_code == 200


def test_readiness_needs_no_login(client, monkeypatch):
    _ready_world(monkeypatch)
    assert client.get("/health/ready").status_code != 401


# ── start-up migration run ───────────────────────────────────────────────────

def test_redact_hides_credentials_in_connection_urls():
    msg = "could not connect: postgresql://admin:S3cr3tPw@db.internal:5432/prod and postgresql+psycopg2://u:p@h/db"
    out = migrate.redact(msg)
    assert "S3cr3tPw" not in out and "admin" not in out and ":p@" not in out
    assert "db.internal" in out            # the host is kept for diagnosis; only the credentials go


def test_a_failed_migration_is_loud_remembered_and_free_of_secrets(monkeypatch, caplog):
    monkeypatch.setenv("RUN_MIGRATIONS", "true")
    import alembic.command
    def boom(*a, **k):
        raise RuntimeError("connection to postgresql://admin:S3cr3tPw@db.internal:5432/prod refused")
    monkeypatch.setattr(alembic.command, "upgrade", boom)
    with caplog.at_level(logging.CRITICAL, logger="app.db.migrate"):
        assert migrate.run_migrations() is False
    assert migrate.startup_result["attempted"] is True and migrate.startup_result["ok"] is False
    assert "S3cr3tPw" not in migrate.startup_result["error"]
    assert any("Migration FAILED" in r.getMessage() for r in caplog.records if r.levelno == logging.CRITICAL)
    assert "S3cr3tPw" not in caplog.text


def test_migrations_are_not_run_unless_asked(monkeypatch):
    monkeypatch.delenv("RUN_MIGRATIONS", raising=False)
    import alembic.command
    called = []
    monkeypatch.setattr(alembic.command, "upgrade", lambda *a, **k: called.append(1))
    assert migrate.run_migrations() is False and not called
    assert migrate.startup_result["attempted"] is False


# ── migration graph ──────────────────────────────────────────────────────────

def test_the_migration_history_is_one_unbroken_chain_with_one_head():
    import os
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cfg = Config(os.path.join(backend, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(backend, "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert len(script.get_heads()) == 1, f"several heads: {script.get_heads()}"
    revisions = list(script.walk_revisions())           # raises on a missing parent or a cycle
    ids = {r.revision for r in revisions}
    for r in revisions:
        parents = (r.down_revision,) if isinstance(r.down_revision, str) else tuple(r.down_revision or ())
        assert all(p in ids for p in parents), f"{r.revision} has an unknown parent"
    assert len(revisions) >= 80
