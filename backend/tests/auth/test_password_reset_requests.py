""""Forgot password?" — the member asks from the login screen, the society's
admins are notified and reset it from the requests list."""
from app.models.notification import Notification
from app.models.password_reset_request import PasswordResetRequest
from app.models.resident import Resident
from tests.conftest import make_flat, make_society, make_user, make_wing

GENERIC = ("If an account exists for these details, your society office has been asked to reset "
           "your password. They will give you a temporary password to sign in with.")


def _rig(db, tag):
    society = make_society(db, f"Reset Society {tag}")
    flat = make_flat(db, make_wing(db, society.id, "Tower A").id, "302")
    admin = make_user(db, f"admin@reset{tag}.com", role="Society Admin")
    manager = make_user(db, f"mgr@reset{tag}.com", role="Manager")
    member = make_user(db, f"resident.98765{tag[-5:].rjust(5, '0')}@duxos.local", role="Resident",
                       full_name="Meera Joshi")
    member["user"].phone = f"98765{tag[-5:].rjust(5, '0')}"
    for u in (admin, manager, member):
        u["user"].society_id = society.id
    db.add(Resident(full_name="Meera Joshi", flat_id=flat.id, user_id=member["user"].id, is_primary=True))
    db.commit()
    return society, admin, manager, member


def _forgot(client, identifier):
    r = client.post("/api/v1/auth/forgot-password", json={"identifier": identifier})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == GENERIC
    return r


def _pending(client, admin):
    r = client.get("/api/v1/users/password-reset-requests", headers=admin["headers"])
    assert r.status_code == 200, r.text
    return r.json()


def test_member_request_reaches_the_society_admins(client, db):
    society, admin, manager, member = _rig(db, "00001")
    _forgot(client, "+91 98765 00001")   # typed the way the login form accepts it

    [req] = _pending(client, admin)
    assert (req["full_name"], req["contact"], req["flats"], req["status"]) == \
        ("Meera Joshi", "9876500001", ["Tower A-302"], "pending")
    assert req["roles"] == ["Resident"]
    notes = db.query(Notification).filter_by(user_id=admin["user"].id, module="auth").all()
    assert [(n.title, n.action_url) for n in notes] == [("Password reset requested", "/users/password-requests")]
    assert "Meera" not in "".join(n.body for n in db.query(Notification).filter_by(user_id=manager["user"].id))


def test_unknown_account_gets_the_same_reply_and_records_nothing(client, db):
    _rig(db, "00002")
    before = db.query(PasswordResetRequest).count()
    _forgot(client, "nobody@nowhere.com")
    _forgot(client, "9999999999")
    assert db.query(PasswordResetRequest).count() == before


def test_asking_again_does_not_duplicate_or_renotify(client, db):
    society, admin, manager, member = _rig(db, "00003")
    _forgot(client, "9876500003")
    _forgot(client, "9876500003")
    assert len(_pending(client, admin)) == 1
    assert db.query(Notification).filter_by(user_id=admin["user"].id, module="auth").count() == 1


def test_admin_reset_gives_a_temporary_password_the_member_must_change(client, db):
    society, admin, manager, member = _rig(db, "00004")
    _forgot(client, "9876500004")
    [req] = _pending(client, admin)

    r = client.post(f"/api/v1/users/password-reset-requests/{req['id']}/reset", headers=admin["headers"])
    assert r.status_code == 200, r.text
    temp = r.json()["temporary_password"]

    login = client.post("/api/v1/auth/login", json={"email": "9876500004", "password": temp})
    assert login.status_code == 200, login.text
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.json()["must_change_password"] is True

    assert _pending(client, admin) == []
    done = client.get("/api/v1/users/password-reset-requests?status=completed", headers=admin["headers"]).json()
    assert done[0]["status"] == "completed" and done[0]["resolved_by"] == admin["user"].full_name
    again = client.post(f"/api/v1/users/password-reset-requests/{req['id']}/reset", headers=admin["headers"])
    assert again.status_code == 409


def test_dismiss_and_direct_reset_close_requests(client, db):
    society, admin, manager, member = _rig(db, "00005")
    _forgot(client, "9876500005")
    [req] = _pending(client, admin)
    r = client.post(f"/api/v1/users/password-reset-requests/{req['id']}/dismiss", headers=admin["headers"])
    assert r.status_code == 200 and r.json()["status"] == "dismissed"

    _forgot(client, "9876500005")                      # asks again later
    assert len(_pending(client, admin)) == 1
    client.post(f"/api/v1/users/{member['user'].id}/reset-password", headers=admin["headers"])
    assert _pending(client, admin) == []                # reset from the user screen closes it


def test_only_admins_of_the_same_society_see_and_handle_requests(client, db):
    society, admin, manager, member = _rig(db, "00006")
    other_society, other_admin, _, _ = _rig(db, "00007")
    _forgot(client, "9876500006")
    [req] = _pending(client, admin)

    assert _pending(client, other_admin) == []
    r = client.post(f"/api/v1/users/password-reset-requests/{req['id']}/reset", headers=other_admin["headers"])
    assert r.status_code == 404
    r = client.get("/api/v1/users/password-reset-requests", headers=manager["headers"])
    assert r.status_code == 403


def test_temporary_passwords_avoid_look_alike_characters():
    from app.services.user_service import _generate_temp_password
    for _ in range(200):
        pwd = _generate_temp_password()
        assert len(pwd) == 12 and not set(pwd) & set("0Oo1lI")
        assert any(c.isupper() for c in pwd) and any(c.islower() for c in pwd) and any(c.isdigit() for c in pwd)
