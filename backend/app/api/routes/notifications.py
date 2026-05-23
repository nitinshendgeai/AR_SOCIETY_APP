from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.notification_service import NotificationService
from app.schemas.common import OrmBase, TimestampSchema
from app.models.notification import NotificationType, NotificationChannel, NotificationStatus
from typing import Optional

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
