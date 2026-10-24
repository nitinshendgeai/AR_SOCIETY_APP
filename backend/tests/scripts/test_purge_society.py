"""scripts/purge_society.py — wipes one society's data and nothing else."""
import os
import sys

import pytest
from sqlalchemy import func, select

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import purge_society as ps  # noqa: E402

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

    result = ps.purge_society(db, "aaa1")
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
    preview = ps.purge_society(db, "AAA2", dry_run=True, delete_society=True)
    assert preview["counts"]["flats"] == 1 and preview["counts"]["societies"] == 1
    assert db.query(Flat).count() == 1

    ps.purge_society(db, "AAA2", delete_society=True)
    db.commit()
    assert db.query(Society).filter_by(society_code="AAA2").count() == 0


def test_unknown_code_raises(db):
    with pytest.raises(LookupError):
        ps.purge_society(db, "NOPE")
