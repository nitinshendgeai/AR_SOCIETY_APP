"""Phase 1 — token handling gaps not covered by tests/auth: expiry, 'none' algorithm, a foreign signing key,
the claims a token carries, and what the login/me responses never contain."""
import base64
import json
from datetime import datetime, timedelta

import pytest
from jose import jwt

from app.core.config import settings
from tests.conftest import make_user

API = "/api/v1"


def _me(client, token):
    return client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})


def _payload(user, **over):
    p = {"sub": str(user.id), "type": "access", "exp": datetime.utcnow() + timedelta(minutes=5)}
    p.update(over)
    return p


@pytest.fixture
def person(db):
    return make_user(db, "tokens@sec.test", role="Resident")


def test_a_valid_token_works(client, person):
    assert _me(client, person["token"]).status_code == 200


def test_an_expired_token_is_refused(client, person):
    t = jwt.encode(_payload(person["user"], exp=datetime.utcnow() - timedelta(seconds=5)),
                   settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    r = _me(client, t)
    assert r.status_code == 401


def test_a_token_signed_with_another_key_is_refused(client, person):
    t = jwt.encode(_payload(person["user"]), "not-the-servers-secret-0123456789abcdef", algorithm=settings.ALGORITHM)
    assert _me(client, t).status_code == 401


def test_an_unsigned_token_is_refused(client, person):
    b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    claims = _payload(person["user"]); claims["exp"] = int(claims["exp"].timestamp())
    t = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(claims)}."
    assert _me(client, t).status_code == 401


def test_a_token_naming_no_user_or_garbage_is_refused(client, person):
    t = jwt.encode({"type": "access", "exp": datetime.utcnow() + timedelta(minutes=5)}, settings.SECRET_KEY,
                   algorithm=settings.ALGORITHM)
    assert _me(client, t).status_code == 401
    t = jwt.encode(_payload(person["user"], sub="not-a-uuid"), settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    assert _me(client, t).status_code == 401


def test_a_forged_roles_claim_grants_nothing(client, db, person):
    """Authorisation reads the database, never the roles written in the token."""
    t = jwt.encode(_payload(person["user"], roles=["Society Admin", "Platform Admin"]), settings.SECRET_KEY,
                   algorithm=settings.ALGORITHM)
    assert client.get(f"{API}/users/", headers={"Authorization": f"Bearer {t}"}).status_code == 403


def test_a_token_without_peers_cannot_switch_society(client, db, person):
    """Switching society needs the signed `peers` list the login put in the token; a plain token has none."""
    from tests.conftest import make_society
    other_soc = make_society(db, "Elsewhere")
    r = client.post(f"{API}/auth/switch-society", json={"society_id": str(other_soc.id)},
                    headers={"Authorization": "Bearer " + person["token"]})
    assert r.status_code == 403


def test_responses_never_carry_password_material(client, person):
    login = client.post(f"{API}/auth/login", json={"email": "tokens@sec.test", "password": "Test@1234"})
    assert login.status_code == 200
    me = client.get(f"{API}/auth/me", headers={"Authorization": "Bearer " + login.json()["access_token"]})
    for body in (login.text, me.text):
        low = body.lower()
        assert "hashed_password" not in low and "$2b$" not in body and "test@1234" not in low


def test_the_error_for_a_wrong_password_does_not_reveal_whether_the_account_exists(client, person):
    wrong = client.post(f"{API}/auth/login", json={"email": "tokens@sec.test", "password": "Wrong@1234"})
    none = client.post(f"{API}/auth/login", json={"email": "nobody@sec.test", "password": "Wrong@1234"})
    assert wrong.status_code == none.status_code == 401
    assert wrong.json()["detail"] == none.json()["detail"]


def test_access_tokens_are_short_lived_and_refresh_tokens_are_not_accepted_as_access(client, person):
    login = client.post(f"{API}/auth/login", json={"email": "tokens@sec.test", "password": "Test@1234"}).json()
    access = jwt.decode(login["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    refresh = jwt.decode(login["refresh_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert access["type"] == "access" and refresh["type"] == "refresh"
    assert timedelta(minutes=1) < datetime.utcfromtimestamp(access["exp"]) - datetime.utcnow() <= timedelta(hours=2)
    assert _me(client, login["refresh_token"]).status_code == 401
