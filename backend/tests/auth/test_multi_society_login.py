"""One person, several societies: a mobile number or email is a login per society (unique within a society among
active users), sign-in offers the societies whose password matches, and only active users of active societies count."""
import pytest

from app.core.security import hash_password
from app.models.society import AccountStatus
from app.models.user import User, UserStatus
from tests.conftest import make_flat, make_society, make_user, make_wing

API = "/api/v1"
PHONE = "9876500001"
DEFAULT = "admin1234"


@pytest.fixture(autouse=True)
def _same_password_in_every_society(monkeypatch):
    """New logins get a random temporary password each, so a person in two societies starts with two different ones.
    These tests are about the sign-in that offers the societies whose password matches, which is what a person gets
    once they have set the same password in each; this makes the new logins start out that way."""
    monkeypatch.setattr("app.services.user_provisioning.generate_temp_password", lambda *a, **k: DEFAULT)


def _admin(db, society, email):
    who = make_user(db, email, role="Society Admin")
    who["user"].society_id = society.id
    db.commit()
    return who["headers"]


def _rig(db, tag="x"):
    a, b = make_society(db, f"Alpha {tag}"), make_society(db, f"Beta {tag}")
    fa1 = make_flat(db, make_wing(db, a.id, "A").id, "101")
    fa2 = make_flat(db, db.get(type(fa1), fa1.id).wing_id, "102")
    fb1 = make_flat(db, make_wing(db, b.id, "B").id, "201")
    return a, b, fa1, fa2, fb1, _admin(db, a, f"adm.a.{tag}@example.com"), _admin(db, b, f"adm.b.{tag}@example.com")


def _add(client, h, flat, name="Same Person", phone=PHONE):
    r = client.post(f"{API}/residents/", json={"flat_id": str(flat.id), "full_name": name, "resident_type": "owner",
                                               "is_primary": True, "phone": phone}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _login(client, who=PHONE, password=DEFAULT, **extra):
    return client.post(f"{API}/auth/login", json={"email": who, "password": password, **extra})


def _auth(r):
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def _two_logins(client, db, tag):
    a, b, fa1, fa2, fb1, ha, hb = _rig(db, tag)
    _add(client, ha, fa1)
    _add(client, hb, fb1)
    return a, b, fa1, fa2, fb1, ha, hb


def test_the_same_mobile_in_two_societies_is_two_logins(client, db):
    a, b, *_ = _two_logins(client, db, "m1")
    users = db.query(User).filter(User.phone == PHONE).all()
    assert len(users) == 2 and {u.society_id for u in users} == {a.id, b.id}


def test_a_second_flat_in_the_same_society_reuses_the_login(client, db):
    a, b, fa1, fa2, fb1, ha, hb = _two_logins(client, db, "m2")
    out = _add(client, ha, fa2)
    assert "already exists for mobile number" in out["warnings"][0]
    assert db.query(User).filter(User.phone == PHONE, User.society_id == a.id).count() == 1


def test_sign_in_offers_the_societies_the_password_matches(client, db):
    a, b, *_ = _two_logins(client, db, "m3")
    r = _login(client)
    assert r.status_code == 200 and r.json()["requires_society_choice"] is True
    assert {c["society_name"] for c in r.json()["choices"]} == {a.name, b.name}
    assert "access_token" not in r.json()

    chosen = _login(client, society_id=str(b.id))
    assert chosen.status_code == 200 and "access_token" in chosen.json()
    me = client.get(f"{API}/auth/me", headers=_auth(chosen)).json()
    assert me["society_id"] == str(b.id)
    assert {s["society_name"] for s in me["societies"]} == {a.name, b.name}
    assert [s["society_name"] for s in me["societies"] if s["current"]] == [b.name]


def test_a_society_that_isnt_yours_cant_be_chosen(client, db):
    a, b, *_ = _two_logins(client, db, "m4")
    other = make_society(db, "Gamma m4")
    assert _login(client, society_id=str(other.id)).status_code == 403


def test_switching_society_needs_no_password_and_ends_the_old_session(client, db):
    a, b, *_ = _two_logins(client, db, "m5")
    in_a = _login(client, society_id=str(a.id))
    sw = client.post(f"{API}/auth/switch-society", json={"society_id": str(b.id)}, headers=_auth(in_a))
    assert sw.status_code == 200, sw.text
    assert client.get(f"{API}/auth/me", headers=_auth(sw)).json()["society_id"] == str(b.id)
    assert client.get(f"{API}/auth/me", headers=_auth(in_a)).status_code == 401       # this device's old session ended
    back = client.post(f"{API}/auth/switch-society", json={"society_id": str(a.id)}, headers=_auth(sw))
    assert back.status_code == 200
    assert client.get(f"{API}/auth/me", headers=_auth(back)).json()["society_id"] == str(a.id)
    # Tokens refresh without losing the other society
    ref = client.post(f"{API}/auth/refresh", json={"refresh_token": back.json()["refresh_token"]})
    assert ref.status_code == 200
    assert len(client.get(f"{API}/auth/me", headers=_auth(ref)).json()["societies"]) == 2


def test_a_login_with_a_different_password_is_not_a_peer(client, db):
    a, b, *_ = _two_logins(client, db, "m6")
    ub = db.query(User).filter(User.phone == PHONE, User.society_id == b.id).one()
    ub.hashed_password = hash_password("Another#Pass9"); db.commit()
    only_a = _login(client)                                    # the default password matches society A only
    assert only_a.status_code == 200 and "access_token" in only_a.json()
    me = client.get(f"{API}/auth/me", headers=_auth(only_a)).json()
    assert me["society_id"] == str(a.id) and not me["societies"]
    sw = client.post(f"{API}/auth/switch-society", json={"society_id": str(b.id)}, headers=_auth(only_a))
    assert sw.status_code == 403
    only_b = _login(client, password="Another#Pass9")
    assert client.get(f"{API}/auth/me", headers=_auth(only_b)).json()["society_id"] == str(b.id)
    assert _login(client, password="wrong-password").status_code == 401


def test_a_suspended_society_is_left_out(client, db):
    a, b, *_ = _two_logins(client, db, "m7")
    in_a = _login(client, society_id=str(a.id))
    b.account_status = AccountStatus.SUSPENDED; db.commit()
    direct = _login(client)                                    # only one active society left: straight in
    assert direct.status_code == 200 and "access_token" in direct.json()
    assert client.get(f"{API}/auth/me", headers=_auth(direct)).json()["society_id"] == str(a.id)
    assert client.get(f"{API}/auth/me", headers=_auth(in_a)).json()["societies"] == []
    assert client.post(f"{API}/auth/switch-society", json={"society_id": str(b.id)}, headers=_auth(in_a)).status_code == 403
    a.account_status = AccountStatus.SUSPENDED; db.commit()      # now neither
    r = _login(client)
    assert r.status_code == 403 and "suspended" in r.json()["detail"]
    b.account_status = AccountStatus.TRIAL; a.account_status = AccountStatus.TRIAL; db.commit()
    assert _login(client).json()["requires_society_choice"] is True


def test_a_disabled_user_is_left_out(client, db):
    a, b, *_ = _two_logins(client, db, "m8")
    ub = db.query(User).filter(User.phone == PHONE, User.society_id == b.id).one()
    ub.status = UserStatus.SUSPENDED; db.commit()
    r = _login(client)
    assert r.status_code == 200 and "access_token" in r.json()
    assert client.get(f"{API}/auth/me", headers=_auth(r)).json()["society_id"] == str(a.id)


def test_the_failed_attempt_lock_covers_all_the_societies(client, db):
    _two_logins(client, db, "m9")
    for _ in range(10):
        assert _login(client, password="nope-nope-1").status_code == 401
    assert _login(client).status_code == 429


def test_a_forged_peer_list_is_not_trusted(client, db):
    a, b, *_ = _two_logins(client, db, "m10")
    ub = db.query(User).filter(User.phone == PHONE, User.society_id == b.id).one()
    ub.hashed_password = hash_password("Another#Pass9"); db.commit()
    only_a = _login(client)
    # A token that was never signed with peers gives no right to switch, whatever the body says
    assert client.post(f"{API}/auth/switch-society", json={"society_id": str(b.id)}, headers=_auth(only_a)).status_code == 403


def test_forgot_password_asks_each_societys_admin(client, db):
    a, b, fa1, fa2, fb1, ha, hb = _two_logins(client, db, "m11")
    assert client.post(f"{API}/auth/forgot-password", json={"identifier": PHONE}).status_code == 200
    for h in (ha, hb):
        rows = client.get(f"{API}/users/password-reset-requests", headers=h).json()
        assert len(rows) == 1


# ── Only active users of an active society count when checking for a duplicate ──────────────────────────────────────

def test_the_same_email_may_be_a_login_in_another_society_but_not_twice_in_one(client, db):
    a, b, fa1, fa2, fb1, ha, hb = _rig(db, "d1")
    body = {"email": "shared@example.com", "full_name": "Shared Person", "phone": "9876500002"}
    assert client.post(f"{API}/users/", json=body, headers=ha).status_code == 201
    assert client.post(f"{API}/users/", json=body, headers=hb).status_code == 201       # another society
    again = client.post(f"{API}/users/", json=body, headers=ha)
    assert again.status_code == 409


def test_a_disabled_user_does_not_hold_their_email_or_mobile(client, db):
    a, b, fa1, fa2, fb1, ha, hb = _rig(db, "d2")
    body = {"email": "gone@example.com", "full_name": "Gone Person", "phone": "9876500003"}
    first = client.post(f"{API}/users/", json=body, headers=ha).json()
    assert client.patch(f"{API}/users/{first['id']}", json={"status": "inactive"}, headers=ha).status_code == 200
    second = client.post(f"{API}/users/", json=body, headers=ha)
    assert second.status_code == 201, second.text
    # Turning the first back on would make two active holders
    assert client.patch(f"{API}/users/{first['id']}", json={"status": "active"}, headers=ha).status_code == 409
    # A removed user doesn't hold it either
    assert client.delete(f"{API}/users/{second.json()['id']}", headers=ha).status_code == 204
    assert client.patch(f"{API}/users/{first['id']}", json={"status": "active"}, headers=ha).status_code == 200


def test_changing_a_mobile_to_one_in_use_in_the_society_is_refused(client, db):
    a, b, fa1, fa2, fb1, ha, hb = _rig(db, "d3")
    u1 = client.post(f"{API}/users/", json={"email": "u1@example.com", "full_name": "User One", "phone": "9876500004"}, headers=ha).json()
    client.post(f"{API}/users/", json={"email": "u2@example.com", "full_name": "User Two", "phone": "9876500005"}, headers=ha)
    assert client.patch(f"{API}/users/{u1['id']}", json={"phone": "9876500005"}, headers=ha).status_code == 409


def test_self_registration_ignores_a_suspended_society_and_a_disabled_user(client, db):
    from app.modules.onboarding.services.onboarding_service import OnboardingService
    a, *_ = _rig(db, "d4")
    ua = _admin(db, a, "owner.d4@example.com")
    owner = db.query(User).filter(User.email == "owner.d4@example.com").one()
    owner.phone = "9876500009"; db.commit()
    svc = OnboardingService(db)

    class _Req:                      # what _validate_uniqueness reads
        society_name, society_code = "Brand New d4", "BN4"
        contact_email, contact_mobile = "owner.d4@example.com", "9876500009"
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:
        svc._validate_uniqueness(_Req)
    assert "already registered" in e.value.detail
    a.account_status = AccountStatus.SUSPENDED; db.commit()
    svc._validate_uniqueness(_Req)           # the society that held them is suspended: free again
    a.account_status = AccountStatus.TRIAL; owner.status = UserStatus.INACTIVE; db.commit()
    svc._validate_uniqueness(_Req)           # a disabled user doesn't hold them either


# ── Several flats in one society ────────────────────────────────────────────────────────────────────────────────────

def test_a_person_with_two_flats_can_pick_one(client, db):
    a, b, fa1, fa2, fb1, ha, hb = _two_logins(client, db, "f1")
    _add(client, ha, fa2)
    me = _auth(_login(client, society_id=str(a.id)))
    mine = client.get(f"{API}/residents/mine", headers=me).json()
    assert {r["flat_id"] for r in mine} == {str(fa1.id), str(fa2.id)}
    for flat in (fa1, fa2):
        r = client.get(f"{API}/residents/me", params={"flat_id": str(flat.id)}, headers=me)
        assert r.status_code == 200 and r.json()["flat_id"] == str(flat.id)
    assert client.get(f"{API}/residents/me", headers=me).status_code == 200            # no flat given: the first
    assert client.get(f"{API}/residents/me", params={"flat_id": str(fb1.id)}, headers=me).status_code == 404


def test_my_bills_can_be_narrowed_to_one_of_my_flats(client, db):
    a, b, fa1, fa2, fb1, ha, hb = _two_logins(client, db, "f2")
    _add(client, ha, fa2)
    me = _auth(_login(client, society_id=str(a.id)))
    assert client.get(f"{API}/billing/bills/me", headers=me).status_code == 200
    assert client.get(f"{API}/billing/bills/me", params={"flat_id": str(fa2.id)}, headers=me).status_code == 200
    # a flat that isn't mine (even in another of my societies) is not found
    assert client.get(f"{API}/billing/bills/me", params={"flat_id": str(fb1.id)}, headers=me).status_code == 404
