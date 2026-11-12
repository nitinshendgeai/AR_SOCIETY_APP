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
from tests.conftest import make_society, make_user, place_in
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
    home = make_society(db, "Push Society 1")
    place_in(db, alice, home); place_in(db, bob, home)
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
    place_in(db, user, make_society(db, "Push Society 2"))
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
    assert m["data"] == {"module": "visitor", "entity_id": r.json()["id"], "route": "/visitors/pending",
                         "urgent": "1"}
    # Android: the ring-style channel at top priority, not the default chime
    assert m["android"]["priority"] == "high"
    assert m["android"]["notification"]["channel_id"] == "visitor_alerts"
    assert m["android"]["notification"]["notification_priority"] == "PRIORITY_MAX"
    assert m["webpush"]["fcm_options"]["link"] == "https://society.duxos.in/#/visitors/pending"
    # Web: delivered at once and kept on screen until answered (a browser cannot ring for a push)
    assert m["webpush"]["headers"] == {"Urgency": "high"}
    assert m["webpush"]["notification"]["requireInteraction"] is True
    assert m["webpush"]["notification"]["tag"] == "visitor-at-gate" and m["webpush"]["notification"]["renotify"] is True


def test_other_pushes_keep_the_default_chime(client, db, fcm):
    sent, _ = fcm
    security = make_user(db, "sec@push3b.com", role="Security Staff")
    society, flat, owner, _ = _flat_with_people(db, "push3b")
    _register(client, security["headers"], "gate-tablet-token")
    visitor = client.post("/api/v1/visitors/", json=_visitor_payload(society.id, flat.id),
                          headers=security["headers"]).json()
    sent.clear()
    assert client.post(f"/api/v1/visitors/{visitor['id']}/approve", json={}, headers=owner["headers"]).status_code == 200
    m = sent[0]
    assert "urgent" not in m["data"]
    assert m["android"]["notification"] == {"sound": "default"}


def test_the_ring_channel_and_sound_exist_in_the_android_app():
    """The channel id the server names must be created by the app, with the ring sound it ships."""
    from pathlib import Path
    from app.services.push_service import URGENT_CHANNEL_ID
    android = Path(__file__).resolve().parents[3] / "mobile" / "android" / "app" / "src" / "main"
    activity = (android / "kotlin" / "in" / "duxos" / "society" / "MainActivity.kt").read_text()
    assert f'"{URGENT_CHANNEL_ID}"' in activity
    assert "R.raw.visitor_ring" in activity
    sound = android / "res" / "raw" / "visitor_ring.wav"
    assert sound.read_bytes()[:4] == b"RIFF" and 20_000 < sound.stat().st_size < 600_000


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


def test_push_status_says_whether_the_server_can_send_and_how_many_devices_are_registered(client, db, monkeypatch):
    home, other = make_society(db, "Push Status Society"), make_society(db, "Other Push Status Society")
    admin = make_user(db, "admin@pushstatus.com", role="Society Admin")
    resident = make_user(db, "res@pushstatus.com")
    stranger = make_user(db, "stranger@pushstatus.com")
    place_in(db, admin, home); place_in(db, resident, home); place_in(db, stranger, other)
    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", "")
    _register(client, admin["headers"], "status-admin-phone-1", "android")
    _register(client, resident["headers"], "status-resident-web-1", "web")
    _register(client, stranger["headers"], "status-stranger-phone1", "android")      # another society: not counted
    r = client.get("/api/v1/notifications/push-status", headers=admin["headers"])
    assert r.status_code == 200, r.text
    assert r.json() == {"enabled": False, "devices": 2, "platforms": {"android": 1, "web": 1}, "my_devices": 1}
    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", json.dumps(SERVICE_ACCOUNT))
    assert client.get("/api/v1/notifications/push-status", headers=admin["headers"]).json()["enabled"] is True
    assert client.get("/api/v1/notifications/push-status", headers=resident["headers"]).status_code == 403


def test_a_test_push_goes_to_the_callers_own_devices_only(client, db, fcm, monkeypatch):
    sent, _ = fcm
    home = make_society(db, "Push Test Society")
    admin = make_user(db, "admin@pushtest.com", role="Society Admin")
    resident = make_user(db, "res@pushtest.com")
    place_in(db, admin, home); place_in(db, resident, home)
    _register(client, admin["headers"], "test-admin-phone-token1", "android")
    _register(client, admin["headers"], "test-admin-web-token-01", "web")
    _register(client, resident["headers"], "test-resident-token-01", "android")
    r = client.post("/api/v1/notifications/push-test", headers=admin["headers"])
    assert r.status_code == 200 and r.json() == {"enabled": True, "sent": 2}
    assert {m["token"] for m in sent} == {"test-admin-phone-token1", "test-admin-web-token-01"}
    assert sent[0]["notification"]["title"] == "Test notification"
    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", "")
    assert client.post("/api/v1/notifications/push-test", headers=admin["headers"]).json() == {"enabled": False, "sent": 0}
    assert client.post("/api/v1/notifications/push-test", headers=resident["headers"]).status_code == 403


def test_the_web_app_ships_the_ring_and_the_service_worker_tells_an_open_tab():
    """A browser rings from the open page: it needs web/visitor_ring.wav, and the service worker must pass an urgent
    push to the page (the page's web_ring_web.dart listens for source 'dux-push')."""
    from pathlib import Path
    mobile = Path(__file__).resolve().parents[3] / "mobile"
    ring = mobile / "web" / "visitor_ring.wav"
    assert ring.read_bytes()[:4] == b"RIFF" and 20_000 < ring.stat().st_size < 600_000
    worker = (mobile / "web" / "firebase-messaging-sw.js").read_text()
    assert "addEventListener('push'" in worker and "source: 'dux-push'" in worker and "'1'" in worker
    page = (mobile / "lib" / "core" / "push" / "web_ring_web.dart").read_text()
    assert "'dux-push'" in page and "visitor_ring.wav" in page
