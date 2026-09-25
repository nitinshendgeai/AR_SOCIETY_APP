"""Push notifications — device registration, and a visitor at the gate being
pushed to the flat resident's devices through FCM (HTTP calls faked)."""
import json

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from app.core.config import settings
from app.models.device_token import DeviceToken
from app.services.push_service import PushService
from tests.conftest import make_user
from tests.visitor.test_visitor import _flat_with_people, _visitor_payload

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
SERVICE_ACCOUNT = {
    "type": "service_account",
    "project_id": "dux-test",
    "client_email": "push@dux-test.iam.gserviceaccount.com",
    "private_key": _key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption()).decode(),
    "token_uri": "https://oauth2.googleapis.com/token",
}


@pytest.fixture
def fcm(monkeypatch):
    """Firebase configured; FCM calls recorded instead of sent."""
    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", json.dumps(SERVICE_ACCOUNT))
    monkeypatch.setattr(PushService, "run_in_background", False)
    monkeypatch.setattr(PushService, "_token", classmethod(lambda cls, account: "access-token"))
    sent, replies = [], {}

    def post(client, url, headers, body):
        sent.append({"url": url, "auth": headers["Authorization"], **body["message"]})
        status, payload = replies.get(body["message"]["token"], (200, {"name": "projects/dux-test/messages/1"}))
        return httpx.Response(status, json=payload)

    monkeypatch.setattr(PushService, "_post", staticmethod(post))
    return sent, replies


def _register(client, headers, token, platform="android"):
    r = client.post("/api/v1/notifications/devices", json={"token": token, "platform": platform}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_device_registration_moves_a_token_to_whoever_signs_in_last(client, db):
    alice = make_user(db, "alice@push1.com")
    bob   = make_user(db, "bob@push1.com")
    assert _register(client, alice["headers"], "shared-browser-token-1", "web") == \
        {"registered": True, "push_enabled": False}
    _register(client, bob["headers"], "shared-browser-token-1", "web")

    device = db.query(DeviceToken).filter_by(token="shared-browser-token-1").one()
    assert (device.user_id, device.platform, device.is_active) == (bob["user"].id, "web", True)

    # Only the device's current user can unregister it.
    r = client.post("/api/v1/notifications/devices/unregister",
                    json={"token": "shared-browser-token-1"}, headers=alice["headers"])
    assert r.json() == {"success": False}
    r = client.post("/api/v1/notifications/devices/unregister",
                    json={"token": "shared-browser-token-1"}, headers=bob["headers"])
    assert r.json() == {"success": True}
    db.refresh(device)
    assert device.is_active is False


def test_device_platform_is_validated(client, db):
    user = make_user(db, "carol@push2.com")
    r = client.post("/api/v1/notifications/devices",
                    json={"token": "some-device-token", "platform": "fridge"}, headers=user["headers"])
    assert r.status_code == 422


def test_visitor_at_the_gate_is_pushed_to_the_flat_residents_devices(client, db, fcm):
    sent, _ = fcm
    security = make_user(db, "sec@push3.com", role="Security Staff")
    society, flat, owner, _ = _flat_with_people(db, "push3")
    assert _register(client, owner["headers"], "owner-phone-token", "android")["push_enabled"] is True
    _register(client, owner["headers"], "owner-laptop-token", "web")

    r = client.post("/api/v1/visitors/", json=_visitor_payload(society.id, flat.id), headers=security["headers"])
    assert r.status_code == 201, r.text

    assert sorted(m["token"] for m in sent) == ["owner-laptop-token", "owner-phone-token"]
    m = sent[0]
    assert m["url"] == "https://fcm.googleapis.com/v1/projects/dux-test/messages:send"
    assert m["auth"] == "Bearer access-token"
    assert m["notification"]["title"] == "Visitor at Gate"
    assert "John Visitor (guest) is at the gate for Tower B-302" in m["notification"]["body"]
    assert m["data"] == {"module": "visitor", "entity_id": r.json()["id"], "route": "/visitors/pending"}
    assert m["webpush"]["fcm_options"]["link"] == "https://society.duxos.in/#/visitors/pending"


def test_guard_is_pushed_the_residents_decision(client, db, fcm):
    sent, _ = fcm
    security = make_user(db, "sec@push4.com", role="Security Staff")
    society, flat, owner, _ = _flat_with_people(db, "push4")
    _register(client, security["headers"], "gate-tablet-token")
    visitor = client.post("/api/v1/visitors/", json=_visitor_payload(society.id, flat.id),
                          headers=security["headers"]).json()

    r = client.post(f"/api/v1/visitors/{visitor['id']}/approve", json={}, headers=owner["headers"])
    assert r.status_code == 200, r.text
    assert [(m["token"], m["notification"]["title"], m["data"]["route"]) for m in sent] == [
        ("gate-tablet-token", "Visitor Approved", f"/visitors/society/{society.id}")]


def test_tokens_fcm_no_longer_knows_are_switched_off(client, db, fcm):
    sent, replies = fcm
    security = make_user(db, "sec@push5.com", role="Security Staff")
    society, flat, owner, _ = _flat_with_people(db, "push5")
    _register(client, owner["headers"], "uninstalled-app-token")
    _register(client, owner["headers"], "working-phone-token")
    replies["uninstalled-app-token"] = (404, {"error": {"code": 404, "status": "NOT_FOUND", "details": [
        {"@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError", "errorCode": "UNREGISTERED"}]}})

    client.post("/api/v1/visitors/", json=_visitor_payload(society.id, flat.id), headers=security["headers"])

    active = {d.token: d.is_active for d in db.query(DeviceToken).filter_by(user_id=owner["user"].id)}
    assert active == {"uninstalled-app-token": False, "working-phone-token": True}


def test_nothing_is_pushed_while_firebase_is_not_configured(client, db, fcm, monkeypatch):
    sent, _ = fcm
    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", "")
    security = make_user(db, "sec@push6.com", role="Security Staff")
    society, flat, owner, _ = _flat_with_people(db, "push6")
    _register(client, owner["headers"], "owner-phone-token-6")

    r = client.post("/api/v1/visitors/", json=_visitor_payload(society.id, flat.id), headers=security["headers"])
    assert r.status_code == 201
    assert sent == []


def test_access_token_comes_from_a_jwt_signed_with_the_service_account_key(monkeypatch):
    posted = {}

    def fake_post(url, timeout, data):
        posted.update(url=url, **data)
        return httpx.Response(200, json={"access_token": "ya29.token", "expires_in": 3599},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(PushService, "_access_token", None)
    monkeypatch.setattr(PushService, "_access_token_expires", 0)

    assert PushService._token(SERVICE_ACCOUNT) == "ya29.token"
    assert posted["url"] == "https://oauth2.googleapis.com/token"
    assert posted["grant_type"] == "urn:ietf:params:oauth:grant-type:jwt-bearer"
    public = _key.public_key().public_bytes(serialization.Encoding.PEM,
                                            serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    claims = jwt.decode(posted["assertion"], public, algorithms=["RS256"],
                        audience="https://oauth2.googleapis.com/token")
    assert claims["iss"] == SERVICE_ACCOUNT["client_email"]
    assert claims["scope"] == "https://www.googleapis.com/auth/firebase.messaging"
    # Cached for the next call.
    assert PushService._token(SERVICE_ACCOUNT) == "ya29.token"
