"""Signed-in devices: one login can be used on several devices, each is a session the user can see and
end; signing out, changing the password and an admin reset take effect at once; guessing a password is
throttled."""
import uuid
from datetime import datetime, timedelta

import pytest

from app.core.security import create_access_token, create_refresh_token
from app.services.session_service import describe_device
from tests.conftest import make_society, make_user

A = "/api/v1/auth"
CHROME_WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
SAFARI_IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
                 "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")


def _login(client, email, password="Test@1234", ua=CHROME_WIN):
    r = client.post(f"{A}/login", json={"email": email, "password": password}, headers={"User-Agent": ua})
    assert r.status_code == 200, r.text
    d = r.json()
    return {"access": d["access_token"], "refresh": d["refresh_token"],
            "h": {"Authorization": f"Bearer {d['access_token']}"}}


@pytest.fixture
def person(db):
    return make_user(db, "sessions@test.com", role="Resident")


def _me(client, dev):
    return client.get(f"{A}/me", headers=dev["h"]).status_code


def test_one_login_on_two_devices_shows_two_sessions_and_marks_this_one(client, person):
    laptop = _login(client, "sessions@test.com", ua=CHROME_WIN)
    phone = _login(client, "sessions@test.com", ua=SAFARI_IPHONE)
    assert _me(client, laptop) == 200 and _me(client, phone) == 200
    rows = client.get(f"{A}/sessions", headers=laptop["h"]).json()
    assert len(rows) == 2
    assert {r["device"] for r in rows} == {"Chrome on Windows", "Safari on iPhone"}
    assert [r["device"] for r in rows if r["current"]] == ["Chrome on Windows"]
    assert all(r["signed_in_at"] and r["last_seen_at"] for r in rows)


def test_logging_out_ends_only_this_device_at_once(client, person):
    laptop = _login(client, "sessions@test.com")
    phone = _login(client, "sessions@test.com", ua=SAFARI_IPHONE)
    assert client.post(f"{A}/logout", headers=laptop["h"]).status_code == 204
    assert _me(client, laptop) == 401                                       # the access token stops working...
    assert client.post(f"{A}/refresh", json={"refresh_token": laptop["refresh"]}).status_code == 401   # ...and can't be renewed
    assert _me(client, phone) == 200                                        # the other device is untouched
    assert len(client.get(f"{A}/sessions", headers=phone["h"]).json()) == 1


def test_a_device_can_be_signed_out_from_another(client, person):
    laptop = _login(client, "sessions@test.com")
    phone = _login(client, "sessions@test.com", ua=SAFARI_IPHONE)
    rows = client.get(f"{A}/sessions", headers=laptop["h"]).json()
    phone_id = next(r["id"] for r in rows if not r["current"])
    assert client.delete(f"{A}/sessions/{phone_id}", headers=laptop["h"]).status_code == 204
    assert _me(client, phone) == 401
    assert client.post(f"{A}/refresh", json={"refresh_token": phone["refresh"]}).status_code == 401
    assert _me(client, laptop) == 200
    assert client.delete(f"{A}/sessions/{phone_id}", headers=laptop["h"]).status_code == 404   # already gone


def test_you_cannot_end_someone_elses_device(client, db, person):
    other = make_user(db, "someone-else@test.com", role="Resident")
    theirs = _login(client, "someone-else@test.com")
    mine = _login(client, "sessions@test.com")
    their_id = client.get(f"{A}/sessions", headers=theirs["h"]).json()[0]["id"]
    assert client.delete(f"{A}/sessions/{their_id}", headers=mine["h"]).status_code == 404
    assert client.delete(f"{A}/sessions/{uuid.uuid4()}", headers=mine["h"]).status_code == 404
    assert _me(client, theirs) == 200


def test_sign_out_other_devices_keeps_this_one(client, person):
    laptop = _login(client, "sessions@test.com")
    phone = _login(client, "sessions@test.com", ua=SAFARI_IPHONE)
    tablet = _login(client, "sessions@test.com", ua="Mozilla/5.0 (Linux; Android 14) Chrome/129.0 Mobile Safari/537.36")
    assert client.post(f"{A}/sessions/revoke-others", headers=laptop["h"]).status_code == 204
    assert (_me(client, laptop), _me(client, phone), _me(client, tablet)) == (200, 401, 401)
    assert len(client.get(f"{A}/sessions", headers=laptop["h"]).json()) == 1


def test_refreshing_keeps_the_same_device_session(client, person):
    laptop = _login(client, "sessions@test.com")
    r = client.post(f"{A}/refresh", json={"refresh_token": laptop["refresh"]})
    assert r.status_code == 200
    renewed = {"h": {"Authorization": f"Bearer {r.json()['access_token']}"}}
    assert _me(client, renewed) == 200
    assert len(client.get(f"{A}/sessions", headers=renewed["h"]).json()) == 1


def test_changing_the_password_signs_out_the_other_devices_not_this_one(client, person):
    laptop = _login(client, "sessions@test.com")
    phone = _login(client, "sessions@test.com", ua=SAFARI_IPHONE)
    r = client.post(f"{A}/change-password", headers=laptop["h"],
                    json={"current_password": "Test@1234", "new_password": "Brand-New-Pass-77"})
    assert r.status_code == 204, r.text
    assert _me(client, laptop) == 200
    assert _me(client, phone) == 401
    assert client.post(f"{A}/refresh", json={"refresh_token": phone["refresh"]}).status_code == 401
    assert client.post(f"{A}/login", json={"email": "sessions@test.com", "password": "Brand-New-Pass-77"}).status_code == 200


def test_an_admin_reset_signs_the_user_out_everywhere(client, db):
    society = make_society(db, "Reset Society")
    admin = make_user(db, "reset-admin@test.com", role="Society Admin")
    member = make_user(db, "reset-member@test.com", role="Resident")
    for who in (admin, member):
        who["user"].society_id = society.id
    db.commit()
    laptop = _login(client, "reset-member@test.com")
    phone = _login(client, "reset-member@test.com", ua=SAFARI_IPHONE)
    r = client.post(f"/api/v1/users/{member['user'].id}/reset-password", headers=admin["headers"])
    assert r.status_code == 200, r.text
    assert (_me(client, laptop), _me(client, phone)) == (401, 401)
    assert client.post(f"{A}/refresh", json={"refresh_token": laptop["refresh"]}).status_code == 401


def test_a_login_from_before_sessions_existed_keeps_working_and_upgrades_on_refresh(client, db, person):
    uid = str(person["user"].id)
    old_access = create_access_token(uid, {"roles": ["Resident"]})          # no device id in it
    old_refresh = create_refresh_token(uid)
    assert client.get(f"{A}/me", headers={"Authorization": f"Bearer {old_access}"}).status_code == 200
    r = client.post(f"{A}/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200
    new = {"h": {"Authorization": f"Bearer {r.json()['access_token']}"}}
    assert len(client.get(f"{A}/sessions", headers=new["h"]).json()) == 1   # now it is a device you can see and end
    assert client.post(f"{A}/logout", headers=new["h"]).status_code == 204
    assert _me(client, new) == 401


def test_a_suspended_account_is_locked_out_straight_away(client, db, person):
    from app.models.user import UserStatus
    laptop = _login(client, "sessions@test.com")
    person["user"].status = UserStatus.SUSPENDED
    db.commit()
    assert _me(client, laptop) == 401


def test_too_many_wrong_passwords_lock_the_account_for_a_while(client, db, person):
    other = make_user(db, "bystander@test.com", role="Resident")
    for _ in range(10):
        assert client.post(f"{A}/login", json={"email": "sessions@test.com", "password": "wrong-password-1"}).status_code == 401
    locked = client.post(f"{A}/login", json={"email": "sessions@test.com", "password": "Test@1234"})
    assert locked.status_code == 429 and "15 minutes" in locked.text          # even the right password waits
    assert client.post(f"{A}/login", json={"email": "bystander@test.com", "password": "Test@1234"}).status_code == 200


def test_the_lock_lifts_after_the_window_and_unknown_accounts_get_the_same_plain_refusal(client, db, person):
    from app.models.audit_log import AuditLog
    for _ in range(10):
        client.post(f"{A}/login", json={"email": "sessions@test.com", "password": "wrong-password-1"})
    for row in db.query(AuditLog).filter(AuditLog.notes == "Failed login attempt").all():
        row.created_at = datetime.utcnow() - timedelta(minutes=20)
    db.commit()
    assert client.post(f"{A}/login", json={"email": "sessions@test.com", "password": "Test@1234"}).status_code == 200
    ghost = client.post(f"{A}/login", json={"email": "nobody@test.com", "password": "whatever-123"})
    assert ghost.status_code == 401 and "Invalid" in ghost.text


@pytest.mark.parametrize("ua,expected", [
    (CHROME_WIN, "Chrome on Windows"), (SAFARI_IPHONE, "Safari on iPhone"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605 Version/17 Safari/605", "Safari on Mac"),
    ("Mozilla/5.0 (Windows NT 10.0) Chrome/129.0 Edg/129.0 Safari/537", "Edge on Windows"),
    ("Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0", "Firefox on Linux"),
    ("Dart/3.5 (dart:io)", "DUX OS app"), ("", "Unknown device"), (None, "Unknown device"),
])
def test_devices_are_named_in_plain_words(ua, expected):
    assert describe_device(ua) == expected
