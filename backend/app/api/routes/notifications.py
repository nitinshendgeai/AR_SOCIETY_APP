from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.core.dependencies import get_current_user, require_admin_committee
from app.models.device_token import DeviceToken
from app.models.user import User
from app.services.notification_service import NotificationService
from app.services.push_service import PushService
from app.schemas.common import OrmBase, TimestampSchema
from app.models.notification import NotificationType, NotificationChannel, NotificationStatus
from typing import Literal, Optional
from pydantic import Field

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class NotificationOut(TimestampSchema):
    title:      str
    body:       str
    type:       NotificationType
    channel:    NotificationChannel
    status:     NotificationStatus
    is_read:    bool
    module:     Optional[str]
    entity_id:  Optional[str]
    action_url: Optional[str]


@router.get("/", response_model=List[NotificationOut])
def get_my_notifications(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Get all unread notifications for the current user."""
    return NotificationService.get_unread(db, current_user.id)


@router.patch("/{notification_id}/read", response_model=dict)
def mark_notification_read(
    notification_id: UUID,
    current_user:    User    = Depends(get_current_user),
    db:              Session = Depends(get_db),
):
    ok = NotificationService.mark_read(db, notification_id, current_user.id)
    return {"success": ok}


# ── Push devices ──────────────────────────────────────────────────────────────

class DeviceIn(OrmBase):
    token:    str = Field(min_length=10, max_length=512)
    platform: Literal["web", "android", "ios"]


class DeviceTokenIn(OrmBase):
    token: str = Field(min_length=10, max_length=512)


@router.post("/devices", response_model=dict)
def register_device(
    data:         DeviceIn,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """The app registers this browser/phone's Firebase token after sign-in so
    the user's alerts (a visitor at the gate…) reach it as push notifications."""
    PushService.register_device(db, current_user.id, data.token, data.platform)
    return {"registered": True, "push_enabled": PushService.enabled()}


@router.post("/devices/unregister", response_model=dict)
def unregister_device(
    data:         DeviceTokenIn,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """On sign-out: stop pushing this user's alerts to this device."""
    return {"success": PushService.unregister_device(db, current_user.id, data.token)}


# ── Push status (Society Settings) ────────────────────────────────────────────

@router.get("/push-status", response_model=dict)
def push_status(
    current_user: User    = Depends(require_admin_committee),
    db:           Session = Depends(get_db),
):
    """Whether the server can send push notifications (Firebase key set) and how many phones and browsers are
    registered to receive them: the society's, and the caller's own. Nothing secret is returned."""
    q = db.query(DeviceToken).join(User, User.id == DeviceToken.user_id).filter(DeviceToken.is_active == True)  # noqa: E712
    if current_user.society_id is not None:
        q = q.filter(User.society_id == current_user.society_id)
    platforms: dict = {}
    for (platform,) in q.with_entities(DeviceToken.platform).all():
        platforms[platform] = platforms.get(platform, 0) + 1
    mine = db.query(DeviceToken).filter(DeviceToken.user_id == current_user.id,
                                        DeviceToken.is_active == True).count()          # noqa: E712
    return {"enabled": PushService.enabled(), "devices": sum(platforms.values()), "platforms": platforms,
            "my_devices": mine}


@router.post("/push-test", response_model=dict)
def push_test(
    current_user: User    = Depends(require_admin_committee),
    db:           Session = Depends(get_db),
):
    """Send a test push to the caller's own registered devices. `sent` is how many devices it went to (0 when push is
    off on the server or this person has no device registered)."""
    sent = PushService.send_to_user(db, current_user.id, "Test notification",
                                    "Push notifications are working on this device.", route="/")
    return {"enabled": PushService.enabled(), "sent": sent}
