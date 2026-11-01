"""A starting password for resident logins that have never been used: who gets it and who is left alone."""
from datetime import datetime

from app.core.security import verify_password
from app.models.resident import Resident
from tests.conftest import make_flat, make_society, make_user, make_wing

URL = "/api/v1/users/starting-password"
PASSWORD = "Admin@1234"


def _rig(db, tag):
    society = make_society(db, f"Starting Password Society {tag}")
    admin = make_user(db, f"sp-admin-{tag}@x.test", role="Society Admin")
    admin["user"].society_id = society.id
    wing = make_wing(db, society.id, "A")
    flats = {n: make_flat(db, wing.id, n) for n in ("101", "102", "103", "104", "105")}
    db.commit()
    return society, admin, flats


def _resident_login(db, society, flat, email, role="Resident", last_login=None, phone=None, name="Owner"):
    login = make_user(db, email, role=role, full_name=name)["user"]
    login.society_id, login.last_login, login.phone = society.id, last_login, phone
    db.add(Resident(flat_id=flat.id, full_name=name, user_id=login.id))
    db.commit()
    return login


def test_only_resident_logins_never_signed_in_get_it_and_must_change_it(client, db):
    society, admin, flats = _rig(db, "p1")
    fresh = _resident_login(db, society, flats["101"], "sp-fresh-p1@x.test", phone="9000000101", name="Fresh")
    used = _resident_login(db, society, flats["102"], "sp-used-p1@x.test", last_login=datetime.utcnow(), name="Used")
    committee = _resident_login(db, society, flats["103"], "sp-comm-p1@x.test", role="Committee Member", name="Comm")
    manager = _resident_login(db, society, flats["104"], "sp-mgr-p1@x.test", role="Manager", name="Mgr")
    before = {u.id: u.hashed_password for u in (used, committee, manager)}
    r = client.post(URL, headers=admin["headers"], json={"password": PASSWORD})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["set"] == 1 and out["skipped_signed_in"] == 1 and out["skipped_other_roles"] == 2
    assert out["people"] == [{"name": "Fresh", "flat": "A / 101", "mobile": "9000000101"}]
    assert PASSWORD not in r.text                                               # the password is never echoed
    for u in (fresh, used, committee, manager, admin["user"]):
        db.refresh(u)
    assert verify_password(PASSWORD, fresh.hashed_password) and fresh.must_change_password is True
    assert all(u.hashed_password == before[u.id] for u in (used, committee, manager))
    assert not verify_password(PASSWORD, admin["user"].hashed_password)          # admins untouched


def test_a_dry_run_changes_nothing_and_a_short_password_is_refused(client, db):
    society, admin, flats = _rig(db, "p2")
    fresh = _resident_login(db, society, flats["101"], "sp-fresh-p2@x.test")
    old = fresh.hashed_password
    r = client.post(URL, headers=admin["headers"], json={"password": PASSWORD, "dry_run": True})
    assert r.json()["dry_run"] is True and r.json()["set"] == 1
    db.refresh(fresh)
    assert fresh.hashed_password == old and fresh.must_change_password is False
    assert client.post(URL, headers=admin["headers"], json={"password": "short"}).status_code == 422


def test_it_is_admin_only_and_never_reaches_another_society(client, db):
    society, admin, flats = _rig(db, "p3")
    other, other_admin, other_flats = _rig(db, "p3b")
    theirs = _resident_login(db, other, other_flats["101"], "sp-theirs-p3@x.test")
    old = theirs.hashed_password
    mine = _resident_login(db, society, flats["101"], "sp-mine-p3@x.test")
    assert client.post(URL, headers=admin["headers"], json={"password": PASSWORD}).json()["set"] == 1
    db.refresh(theirs); db.refresh(mine)
    assert theirs.hashed_password == old and verify_password(PASSWORD, mine.hashed_password)
    resident = make_user(db, "sp-res-p3@x.test")
    assert client.post(URL, headers=resident["headers"], json={"password": PASSWORD}).status_code == 403


def test_a_resident_can_sign_in_with_it_and_is_told_to_change_it(client, db):
    society, admin, flats = _rig(db, "p4")
    _resident_login(db, society, flats["101"], "sp-login-p4@x.test", phone="9000000104")
    client.post(URL, headers=admin["headers"], json={"password": PASSWORD})
    r = client.post("/api/v1/auth/login", json={"email": "9000000104", "password": PASSWORD})   # by mobile number
    assert r.status_code == 200, r.text
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["must_change_password"] is True
