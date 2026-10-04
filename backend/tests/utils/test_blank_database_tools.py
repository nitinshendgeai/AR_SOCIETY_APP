"""Starting from a blank database: the wipe keeps the schema and the reference
data and refuses unless told exactly which database to empty; the first
Platform Admin can be created on an empty database and is safe to run again."""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (every table on Base.metadata)
from app.db.base import Base
from app.utils.create_platform_admin import create_platform_admin
from app.utils.reset_data import KEEP_TABLES, reset, row_counts, tables_to_clear
from tests.conftest import make_user

S = "/api/v1"


@pytest.fixture
def scratch(tmp_path):
    """A throwaway SQLite database with the real schema and a few rows in it."""
    engine = create_engine(f"sqlite:///{tmp_path / 'scratch.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text("INSERT INTO alembic_version VALUES ('fe4f5a6b7c8d')"))
    from app.models.permission import Permission
    from app.models.role import Role
    from app.models.society import Society
    with Session(engine) as session:
        session.add(Permission(code="admin", name="Admin", description="x"))
        session.add(Society(name="Old Society", city="Pune", state="Maharashtra"))
        session.flush()
        session.add(Role(name="Society Admin"))        # also grants it the default permissions
        session.commit()
    yield engine
    engine.dispose()


def test_a_dry_run_deletes_nothing_and_says_what_it_would_do(scratch):
    lines = []
    assert reset(scratch, out=lines.append) is False
    assert row_counts(scratch, ["societies", "roles"]) == {"societies": 1, "roles": 1}
    text_out = "\n".join(lines)
    assert "Dry run" in text_out and "societies: 1" in text_out and "--confirm-db" in text_out


def test_it_refuses_without_the_exact_database_name_and_yes(scratch):
    name = scratch.url.database
    with pytest.raises(SystemExit, match="not this database"):
        reset(scratch, confirm_db="production", yes=True, out=lambda *_: None)
    with pytest.raises(SystemExit, match="add --yes"):
        reset(scratch, confirm_db=name, yes=False, out=lambda *_: None)
    assert row_counts(scratch, ["societies"]) == {"societies": 1}


def test_a_confirmed_wipe_clears_the_data_and_keeps_the_schema_and_reference_rows(scratch):
    tables_before = set(tables_to_clear(scratch)) | KEEP_TABLES
    assert reset(scratch, confirm_db=scratch.url.database, yes=True, out=lambda *_: None) is True
    assert row_counts(scratch, ["societies", "roles"]) == {"societies": 0, "roles": 0}
    kept = row_counts(scratch, sorted(KEEP_TABLES))
    assert kept == {"alembic_version": 1, "forms": 0, "permissions": 1}      # untouched (forms was empty here)
    from sqlalchemy import inspect
    assert set(inspect(scratch).get_table_names()) == tables_before          # no table dropped


def test_the_kept_tables_are_named_in_the_reference_list():
    assert {"alembic_version", "forms", "permissions"} == set(KEEP_TABLES)


# ── The first Platform Admin ──────────────────────────────────────────────────

def test_the_first_platform_admin_is_made_and_can_log_in(client, db):
    assert create_platform_admin(db, " Ops@Example.COM ", "Platform Operations", "Ops-Secure-2026") == "created"
    r = client.post(f"{S}/auth/login", json={"email": "ops@example.com", "password": "Ops-Secure-2026"})
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get(f"{S}/platform-admin/stats", headers=headers).status_code == 200

    from app.models.user import User
    user = db.query(User).filter(User.email == "ops@example.com").one()
    assert user.is_superadmin and user.society_id is None and not user.must_change_password
    assert [ur.role.name for ur in user.user_roles] == ["Platform Admin"]


def test_running_it_again_changes_nothing_and_keeps_the_password(client, db):
    create_platform_admin(db, "ops2@example.com", "Ops", "First-Password-1")
    assert create_platform_admin(db, "ops2@example.com", "Ops", "Different-Password-2") == "unchanged"
    assert client.post(f"{S}/auth/login", json={"email": "ops2@example.com", "password": "First-Password-1"}).status_code == 200
    assert client.post(f"{S}/auth/login", json={"email": "ops2@example.com", "password": "Different-Password-2"}).status_code != 200


def test_an_existing_user_is_promoted_without_losing_their_password(client, db):
    make_user(db, "someone@example.com", password="Their-Own-Pass-9", role="Resident")
    assert create_platform_admin(db, "someone@example.com", "Someone") == "updated"
    assert client.post(f"{S}/auth/login", json={"email": "someone@example.com", "password": "Their-Own-Pass-9"}).status_code == 200
    assert create_platform_admin(db, "someone@example.com", "Someone", "Brand-New-Pass-3", reset_password=True) == "updated"
    assert client.post(f"{S}/auth/login", json={"email": "someone@example.com", "password": "Brand-New-Pass-3"}).status_code == 200


@pytest.mark.parametrize("password", ["short1", "onlyletterslong", "1234567890123"])
def test_a_weak_password_is_refused(db, password):
    with pytest.raises(SystemExit, match="10 characters"):
        create_platform_admin(db, "weak@example.com", "Weak", password)


def test_a_new_user_needs_a_password(db):
    with pytest.raises(SystemExit, match="password is needed"):
        create_platform_admin(db, "nopass@example.com", "No Pass", None)
