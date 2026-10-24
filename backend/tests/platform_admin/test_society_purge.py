"""Deleting one society's data (app.services.society_purge, scripts/purge_society.py, Platform Admin "Clean data")."""

import pytest
from sqlalchemy import func, select



from app.services import society_purge as ps
from app.models.flat import Flat
from app.models.floor import Floor
from app.models.resident import Resident
from app.models.role import Role
from app.models.society import Society
from app.models.user import User
from app.models.wing import Wing
from tests.conftest import make_user, place_in


def _seed(db, code, name):
    soc = Society(name=name, society_code=code, city="Pune", state="MH")
    db.add(soc); db.flush()
    login = place_in(db, make_user(db, f"u@{code.lower()}.test"), soc)
    wing = Wing(society_id=soc.id, name="A", code="A")
    db.add(wing); db.flush()
    flat = Flat(wing_id=wing.id, flat_number="101")
    db.add(flat); db.flush()
    db.add(Resident(flat_id=flat.id, user_id=login["user"].id, full_name="R", is_primary=True))
    db.commit()
    return soc


def _count(db, model, **kw):
    return db.query(model).filter_by(**kw).count()


def test_purge_removes_only_the_given_society(db):
    a = _seed(db, "AAA1", "Alpha"); b = _seed(db, "BBB1", "Beta")
    superadmin = User(email="root@x.test", full_name="Root", hashed_password="x", is_superadmin=True)
    db.add(superadmin); db.commit()
    roles_before = db.query(Role).count()

    result = ps.purge_society(db, a.id)
    db.commit()

    for model in (User, Wing):
        assert _count(db, model, society_id=a.id) == 0
        assert _count(db, model, society_id=b.id) == 1
    assert db.query(Flat).count() == 1 and db.query(Resident).count() == 1   # only society B's remain
    assert db.get(Society, a.id) is not None          # society row kept by default
    assert db.query(User).filter_by(email="root@x.test").count() == 1
    assert db.query(Role).count() == roles_before
    assert result["counts"]["wings"] == 1


def test_dry_run_deletes_nothing_and_delete_society_removes_row(db):
    a = _seed(db, "AAA2", "Alpha2")
    preview = ps.purge_society(db, a.id, dry_run=True, delete_society=True)
    assert preview["counts"]["flats"] == 1 and preview["counts"]["societies"] == 1
    assert db.query(Flat).count() == 1

    ps.purge_society(db, a.id, delete_society=True)
    db.commit()
    assert db.query(Society).filter_by(society_code="AAA2").count() == 0


def test_find_society_by_code_and_unknown_society(db):
    a = _seed(db, "AAA3", "Alpha3")
    assert ps.find_society(db, " aaa3 ")[0] == a.id
    assert ps.find_society(db, "NOPE") is None
    import uuid
    with pytest.raises(LookupError):
        ps.purge_society(db, uuid.uuid4())


# ── Platform console endpoint ─────────────────────────────────────────────────

from tests.platform_admin.test_platform_admin import make_superadmin  # noqa: E402

P = "/api/v1/platform-admin"


def test_clean_data_endpoint_needs_platform_admin_and_the_code(client, db):
    a = _seed(db, "AAA4", "Alpha4"); b = _seed(db, "BBB4", "Beta4")
    _, h = make_superadmin(db)
    society_admin = make_user(db, "sa@alpha4.test", role="Society Admin")
    place_in(db, society_admin, a)

    # a society admin may not use it
    assert client.post(f"{P}/societies/{a.id}/clean-data", json={"confirm": "AAA4"},
                       headers=society_admin["headers"]).status_code == 403

    preview = client.get(f"{P}/societies/{a.id}/clean-data", headers=h)
    assert preview.status_code == 200 and preview.json()["confirm_with"] == "AAA4"
    assert preview.json()["counts"]["wings"] == 1
    assert db.query(Wing).filter_by(society_id=a.id).count() == 1        # preview deletes nothing

    wrong = client.post(f"{P}/societies/{a.id}/clean-data", json={"confirm": "BBB4"}, headers=h)
    assert wrong.status_code == 400
    assert db.query(Wing).filter_by(society_id=a.id).count() == 1

    ok = client.post(f"{P}/societies/{a.id}/clean-data", json={"confirm": "aaa4"}, headers=h)
    assert ok.status_code == 200, ok.text
    assert db.query(Wing).filter_by(society_id=a.id).count() == 0
    assert db.query(Wing).filter_by(society_id=b.id).count() == 1
    assert db.query(Society).filter_by(society_code="AAA4").count() == 1   # society record kept

    events = client.get(f"{P}/activity", headers=h).json()
    assert any(e["event"] == "data_cleaned" and e["society_id"] == str(a.id) for e in events)


def test_delete_order_removes_children_before_their_parents():
    """Deleting a parent first fires ON DELETE SET NULL / RESTRICT on rows still to be deleted (e.g. flats before
    maintenance_bills nulls the NOT NULL bills.flat_id and fails on PostgreSQL). SQLite tests with few rows miss it."""
    from app.db.base import Base
    md = Base.metadata
    order = ps.delete_order(md, list(ps.build_scope(md, "x")))
    position = {name: i for i, name in enumerate(order)}
    for name in order:
        for fk in md.tables[name].foreign_keys:
            parent = fk.column.table.name
            if parent != name and parent in position:
                assert position[name] < position[parent], f"{name} must be deleted before {parent}"


def test_default_logins_are_kept_and_other_users_go(db):
    from app.models.user import UserRole
    a = _seed(db, "AAA5", "Alpha5")
    admin = make_user(db, "admin@aaa5.com", role="Society Admin"); place_in(db, admin, a)
    treasurer = make_user(db, "treasurer@aaa5.com", role="Committee Treasurer"); place_in(db, treasurer, a)

    preview = ps.purge_society(db, a.id, dry_run=True)
    assert sorted(preview["kept_logins"]) == sorted(ps.default_login_emails("AAA5"))

    ps.purge_society(db, a.id)
    db.commit()
    left = sorted(u.email for u in db.query(User).filter_by(society_id=a.id))
    assert left == ["admin@aaa5.com", "treasurer@aaa5.com"]        # the seeded resident login is gone
    assert db.query(UserRole).filter_by(user_id=admin["user"].id).count() == 1   # and they can still act

    ps.purge_society(db, a.id, keep_default_logins=False)
    db.commit()
    assert db.query(User).filter_by(society_id=a.id).count() == 0
