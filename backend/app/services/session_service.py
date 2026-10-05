"""Signed-in devices: one UserSession per login, shared by that login's access and refresh tokens.

A token without a session id (issued before sessions existed) still works until it expires; the
first refresh swaps it for session-bound tokens. Revoking a session makes its tokens fail at once.
"""
import re
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_session import UserSession

# last_seen is refreshed at most this often, so a busy screen doesn't write on every request
TOUCH_EVERY = timedelta(minutes=5)


def describe_device(user_agent: Optional[str]) -> str:
    """'Chrome on Windows' from a User-Agent string; short and good enough to recognise a device."""
    ua = user_agent or ""
    if not ua:
        return "Unknown device"
    if "Dart/" in ua or "okhttp" in ua or "CFNetwork" in ua:
        return "DUX OS app"
    browser = next((name for token, name in (
        ("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("SamsungBrowser/", "Samsung Internet"),
        ("Chrome/", "Chrome"), ("CriOS/", "Chrome"), ("Safari/", "Safari")) if token in ua), "Browser")
    os_name = next((name for token, name in (
        ("Windows", "Windows"), ("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"),
        ("Mac OS X", "Mac"), ("Macintosh", "Mac"), ("CrOS", "ChromeOS"), ("Linux", "Linux")) if token in ua), None)
    return f"{browser} on {os_name}" if os_name else browser


class SessionService:
    def __init__(self, db: Session):
        self.db = db

    def start(self, user: User, user_agent: Optional[str], ip: Optional[str]) -> UserSession:
        now = datetime.utcnow()
        row = UserSession(user_id=user.id, device=describe_device(user_agent), ip_address=ip[:64] if ip else None,
                          last_seen_at=now)
        self.db.add(row)
        self.db.flush()
        return row

    def get(self, session_id) -> Optional[UserSession]:
        try:
            sid = session_id if isinstance(session_id, uuid.UUID) else uuid.UUID(str(session_id))
        except (ValueError, AttributeError, TypeError):
            return None
        return self.db.query(UserSession).filter(UserSession.id == sid).first()

    def is_live(self, session: Optional[UserSession], user_id) -> bool:
        return (session is not None and session.revoked_at is None and str(session.user_id) == str(user_id))

    def touch(self, session: UserSession) -> None:
        now = datetime.utcnow()
        if session.last_seen_at is None or now - session.last_seen_at >= TOUCH_EVERY:
            session.last_seen_at = now
            self.db.commit()

    def live_for(self, user_id) -> List[UserSession]:
        return self.db.query(UserSession).filter(
            UserSession.user_id == user_id, UserSession.revoked_at.is_(None),
        ).order_by(UserSession.last_seen_at.desc()).all()

    def revoke(self, session: UserSession, reason: str) -> None:
        if session.revoked_at is None:
            session.revoked_at = datetime.utcnow()
            session.revoked_reason = reason

    def revoke_all(self, user_id, reason: str, keep: Optional[uuid.UUID] = None) -> int:
        """Sign a user out everywhere (except `keep`, the device making the request). Caller commits."""
        n = 0
        for row in self.live_for(user_id):
            if keep is not None and str(row.id) == str(keep):
                continue
            self.revoke(row, reason)
            n += 1
        return n
