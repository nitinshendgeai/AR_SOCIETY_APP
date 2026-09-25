"""
PushService — delivers notifications to users' phones and browsers through
Firebase Cloud Messaging (HTTP v1 API).

Configuration: FIREBASE_SERVICE_ACCOUNT_JSON holds the Firebase project's
service-account key (Project settings → Service accounts → Generate new
private key), pasted whole. While it's empty, push is off and every call is
a no-op, so the rest of the app works the same without Firebase.

Delivery runs on a background thread so a slow or failing FCM call never
holds up the request that triggered it (a guard logging a visitor). Tokens
FCM reports as no longer registered are switched off.
"""
import json
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

import httpx
from jose import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device_token import DeviceToken

logger = logging.getLogger(__name__)

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
# FCM answers these for a token that will never work again.
DEAD_TOKEN_ERRORS = {"UNREGISTERED", "NOT_FOUND"}


class PushService:
    # Tests set this to False to deliver inline.
    run_in_background = True

    _account: Optional[dict] = None
    _account_source: Optional[str] = None
    _access_token: Optional[str] = None
    _access_token_expires: float = 0
    _lock = threading.Lock()

    # ── Configuration ─────────────────────────────────────────────────────────

    @classmethod
    def _service_account(cls) -> Optional[dict]:
        raw = settings.FIREBASE_SERVICE_ACCOUNT_JSON.strip()
        if not raw:
            return None
        if cls._account_source != raw:
            try:
                account = json.loads(raw)
                assert account["project_id"] and account["client_email"] and account["private_key"]
            except Exception:
                logger.error("[push] FIREBASE_SERVICE_ACCOUNT_JSON is not a valid service-account key")
                return None
            cls._account, cls._account_source = account, raw
            cls._access_token, cls._access_token_expires = None, 0
        return cls._account

    @classmethod
    def enabled(cls) -> bool:
        return cls._service_account() is not None

    # ── Sending ───────────────────────────────────────────────────────────────

    @classmethod
    def send_to_user(cls, db: Session, user_id: UUID, title: str, body: str,
                     route: Optional[str] = None, data: Optional[Dict[str, str]] = None) -> int:
        """Push to every active device of `user_id`. `route` is the app
        screen a tap opens (e.g. "/visitors/pending"). Returns how many
        devices it was sent to. Never raises."""
        try:
            if not cls.enabled():
                return 0
            tokens = [t for (t,) in db.query(DeviceToken.token).filter(
                DeviceToken.user_id == user_id, DeviceToken.is_active == True).all()]
            if not tokens:
                return 0
            payload = {k: str(v) for k, v in (data or {}).items() if v is not None}
            if route:
                payload["route"] = route
            messages = [cls._message(t, title, body, route, payload) for t in tokens]
            if cls.run_in_background:
                threading.Thread(target=cls._deliver, args=(messages,), daemon=True).start()
            else:
                cls._deliver(messages, db)
            return len(messages)
        except Exception as e:
            logger.error(f"[push] send_to_user failed: {e}")
            return 0

    @staticmethod
    def _message(token: str, title: str, body: str, route: Optional[str], data: Dict[str, str]) -> dict:
        message = {
            "token": token,
            "notification": {"title": title, "body": body},
            "data": data,
            "android": {"priority": "high", "notification": {"sound": "default"}},
        }
        if route:
            # Web: the notification opens the app on that screen.
            message["webpush"] = {"fcm_options": {"link": f"{settings.WEB_APP_URL.rstrip('/')}/#{route}"}}
        return message

    @classmethod
    def _deliver(cls, messages: List[dict], db: Optional[Session] = None) -> None:
        account = cls._service_account()
        if not account:
            return
        url = f"https://fcm.googleapis.com/v1/projects/{account['project_id']}/messages:send"
        dead: List[str] = []
        try:
            headers = {"Authorization": f"Bearer {cls._token(account)}"}
            with httpx.Client(timeout=10) as client:
                for message in messages:
                    r = cls._post(client, url, headers, {"message": message})
                    if r.status_code == 200:
                        continue
                    if cls._error_code(r) in DEAD_TOKEN_ERRORS:
                        dead.append(message["token"])
                    else:
                        logger.warning(f"[push] FCM {r.status_code}: {r.text[:300]}")
        except Exception as e:
            logger.error(f"[push] delivery failed: {e}")
        if dead:
            cls._deactivate(dead, db)

    @staticmethod
    def _post(client: httpx.Client, url: str, headers: dict, body: dict) -> httpx.Response:
        return client.post(url, headers=headers, json=body)

    @staticmethod
    def _error_code(r: httpx.Response) -> Optional[str]:
        try:
            for detail in r.json()["error"].get("details", []):
                if detail.get("errorCode"):
                    return detail["errorCode"]
            return r.json()["error"].get("status")
        except Exception:
            return None

    @classmethod
    def _token(cls, account: dict) -> str:
        """OAuth access token for FCM, from a JWT signed with the service
        account's key (the service-account flow Google's client libraries
        use), cached until shortly before it expires."""
        with cls._lock:
            if cls._access_token and time.time() < cls._access_token_expires - 60:
                return cls._access_token
            now = int(time.time())
            token_uri = account.get("token_uri", "https://oauth2.googleapis.com/token")
            assertion = jwt.encode(
                {"iss": account["client_email"], "scope": FCM_SCOPE, "aud": token_uri,
                 "iat": now, "exp": now + 3600},
                account["private_key"], algorithm="RS256",
            )
            r = httpx.post(token_uri, timeout=10, data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            })
            r.raise_for_status()
            body = r.json()
            cls._access_token = body["access_token"]
            cls._access_token_expires = now + int(body.get("expires_in", 3600))
            return cls._access_token

    @staticmethod
    def _deactivate(tokens: List[str], db: Optional[Session] = None) -> None:
        """Switch the tokens off — in `db` when delivering inline, otherwise
        (background thread) in a session of its own."""
        own = db is None
        if own:
            from app.db.session import get_session_factory
            db = get_session_factory()()
        try:
            db.query(DeviceToken).filter(DeviceToken.token.in_(tokens)).update(
                {DeviceToken.is_active: False, DeviceToken.updated_at: datetime.utcnow()},
                synchronize_session=False)
            db.commit()
            logger.info(f"[push] switched off {len(tokens)} unregistered device token(s)")
        except Exception as e:
            logger.error(f"[push] could not switch off tokens: {e}")
        finally:
            if own:
                db.close()

    # ── Devices ───────────────────────────────────────────────────────────────

    @staticmethod
    def register_device(db: Session, user_id: UUID, token: str, platform: str) -> DeviceToken:
        """Remember `token` for `user_id`. A token already known (the same
        browser/phone) moves to this user — whoever signed in on it last."""
        now = datetime.utcnow()
        device = db.query(DeviceToken).filter(DeviceToken.token == token).first()
        if device:
            device.user_id, device.platform, device.is_active, device.last_seen_at = user_id, platform, True, now
        else:
            device = DeviceToken(user_id=user_id, token=token, platform=platform, last_seen_at=now)
            db.add(device)
        db.commit()
        db.refresh(device)
        return device

    @staticmethod
    def unregister_device(db: Session, user_id: UUID, token: str) -> bool:
        device = db.query(DeviceToken).filter(
            DeviceToken.token == token, DeviceToken.user_id == user_id).first()
        if not device:
            return False
        device.is_active = False
        db.commit()
        return True
