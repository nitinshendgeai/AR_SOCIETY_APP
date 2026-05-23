"""
NotificationService — reusable foundation for all ERP notification events.

Channels supported (foundation only, no external provider yet):
- in_app  : stored in DB, polled by frontend
- email   : stub — ready for SendGrid / SES integration
- sms     : stub — ready for Twilio / MSG91 integration
- push    : stub — ready for Firebase FCM integration

Usage:
    NotificationService.send(
        db=db,
        user_id=user.id,
        title="Visitor Arrived",
        body="John Doe is at Gate 1 waiting for approval.",
        type=NotificationType.APPROVAL,
        channel=NotificationChannel.IN_APP,
        module="visitor",
        entity_id=str(visitor_log.id),
    )
"""
import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationChannel, NotificationStatus, NotificationType

logger = logging.getLogger(__name__)


class NotificationService:

    @staticmethod
    def send(
        db:         Session,
        user_id:    UUID,
        title:      str,
        body:       str,
        type:       NotificationType    = NotificationType.INFO,
        channel:    NotificationChannel = NotificationChannel.IN_APP,
        module:     Optional[str]       = None,
        entity_id:  Optional[str]       = None,
        action_url: Optional[str]       = None,
        metadata:   Optional[dict]      = None,
    ) -> Optional[Notification]:
        """Create and dispatch a notification. Never raises."""
        try:
            notif = Notification(
                user_id    = user_id,
                title      = title,
                body       = body,
                type       = type,
                channel    = channel,
                module     = module,
                entity_id  = str(entity_id) if entity_id else None,
                action_url = action_url,
                extra_data = metadata,
                status     = NotificationStatus.PENDING,
            )
            db.add(notif)
            db.flush()  # get ID before dispatch

            # Dispatch per channel
            dispatched = NotificationService._dispatch(notif)
            notif.status = NotificationStatus.SENT if dispatched else NotificationStatus.FAILED
            db.commit()
            return notif
        except Exception as e:
            logger.error(f"[notify] Failed to send notification: {e}")
            db.rollback()
            return None

    @staticmethod
    def _dispatch(notif: Notification) -> bool:
        """Route to the correct channel provider."""
        try:
            if notif.channel == NotificationChannel.IN_APP:
                # In-app: already stored in DB, frontend polls GET /notifications
                logger.info(f"[notify] in_app → user={notif.user_id} title={notif.title!r}")
                return True
            elif notif.channel == NotificationChannel.EMAIL:
                # TODO: integrate SendGrid / AWS SES
                logger.info(f"[notify] email stub → user={notif.user_id}")
                return True
            elif notif.channel == NotificationChannel.SMS:
                # TODO: integrate Twilio / MSG91
                logger.info(f"[notify] sms stub → user={notif.user_id}")
                return True
            elif notif.channel == NotificationChannel.PUSH:
                # TODO: integrate Firebase FCM
                logger.info(f"[notify] push stub → user={notif.user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"[notify] dispatch error: {e}")
            return False

    @staticmethod
    def get_unread(db: Session, user_id: UUID) -> list:
        return db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False,
            Notification.is_active == True,
        ).order_by(Notification.created_at.desc()).all()

    @staticmethod
    def mark_read(db: Session, notification_id: UUID, user_id: UUID) -> bool:
        notif = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        ).first()
        if notif:
            notif.is_read = True
            notif.status  = NotificationStatus.READ
            db.commit()
            return True
        return False
