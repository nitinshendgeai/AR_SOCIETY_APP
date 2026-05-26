from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel as BM

from app.modules.notice.models.notice import (
    Notice, NoticeAcknowledgement, Announcement, CommunicationLog, EmergencyAlert,
    NoticeStatus, AlertStatus, AudienceType,
)
from app.models.user import User
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel


class NoticeService:

    def __init__(self, db: Session):
        self.db = db

    def _notice_or_404(self, notice_id: UUID) -> Notice:
        n = self.db.query(Notice).filter(Notice.id == notice_id, Notice.is_active == True).first()
        if not n: raise HTTPException(404, "Notice not found")
        return n

    def _audit(self, action, entity, entity_type, user, request=None, **kw):
        AuditService.log(db=self.db, action=action, module="notice",
                         entity_id=str(entity.id), entity_type=entity_type,
                         user=user, request=request, **kw)

    # ── Notice CRUD ───────────────────────────────────────────────────────────

    def create_notice(self, data: dict, user: User, request=None) -> Notice:
        notice = Notice(**data, created_by=user.id)
        self.db.add(notice)
        self.db.flush()
        self._audit(AuditAction.CREATE, notice, "Notice", user, request,
                    new_values={"title": data.get("title"), "category": str(data.get("category"))})
        self.db.commit()
        self.db.refresh(notice)
        return notice

    def publish_notice(self, notice_id: UUID, user: User, request=None) -> Notice:
        notice = self._notice_or_404(notice_id)
        if notice.status != NoticeStatus.DRAFT:
            raise HTTPException(409, f"Notice is already {notice.status.value}")

        notice.status       = NoticeStatus.PUBLISHED
        notice.publish_date = datetime.utcnow()

        self._audit(AuditAction.UPDATE, notice, "Notice", user, request,
                    new_values={"status": "published"})

        # Send in-app notification to audience (foundation — future: SMS/push)
        self._dispatch_notice_notification(notice, user)

        self.db.commit()
        self.db.refresh(notice)
        return notice

    def _dispatch_notice_notification(self, notice: Notice, user: User):
        """Send in-app notification. Future: extend to SMS, push, WhatsApp."""
        # For now: log the dispatch intent — full user resolution would need
        # audience query against residents/flats/wings which is society-specific
        log = CommunicationLog(
            society_id=notice.society_id, notice_id=notice.id,
            user_id=user.id, channel="in_app",
            status="sent", sent_at=datetime.utcnow(),
        )
        self.db.add(log)

    def archive_notice(self, notice_id: UUID, user: User) -> Notice:
        notice = self._notice_or_404(notice_id)
        notice.status = NoticeStatus.ARCHIVED
        self.db.commit()
        self.db.refresh(notice)
        return notice

    def get_notice(self, notice_id: UUID) -> Notice:
        return self._notice_or_404(notice_id)

    def list_notices(self, society_id: UUID, status: Optional[str] = None,
                     skip=0, limit=50) -> List[Notice]:
        q = self.db.query(Notice).filter(Notice.society_id == society_id, Notice.is_active == True)
        if status: q = q.filter(Notice.status == status)
        return q.order_by(Notice.created_at.desc()).offset(skip).limit(limit).all()

    def get_published_notices(self, society_id: UUID) -> List[Notice]:
        return self.db.query(Notice).filter(
            Notice.society_id == society_id,
            Notice.status     == NoticeStatus.PUBLISHED,
            Notice.is_active  == True,
        ).order_by(Notice.priority.desc(), Notice.publish_date.desc()).all()

    # ── Acknowledgement ───────────────────────────────────────────────────────

    def acknowledge_notice(self, notice_id: UUID, user: User,
                            flat_id: UUID = None, notes: str = None) -> NoticeAcknowledgement:
        notice = self._notice_or_404(notice_id)
        if notice.status != NoticeStatus.PUBLISHED:
            raise HTTPException(409, "Can only acknowledge published notices")

        # Duplicate prevention
        existing = self.db.query(NoticeAcknowledgement).filter(
            NoticeAcknowledgement.notice_id == notice_id,
            NoticeAcknowledgement.user_id   == user.id,
        ).first()
        if existing:
            raise HTTPException(409, "You have already acknowledged this notice")

        ack = NoticeAcknowledgement(
            notice_id=notice_id, user_id=user.id,
            flat_id=flat_id, ack_at=datetime.utcnow(), notes=notes,
        )
        self.db.add(ack)
        notice.acknowledgement_count += 1
        self.db.commit()
        self.db.refresh(ack)
        return ack

    def get_acknowledgement_report(self, notice_id: UUID) -> dict:
        notice = self._notice_or_404(notice_id)
        acks   = self.db.query(NoticeAcknowledgement).filter(
            NoticeAcknowledgement.notice_id == notice_id
        ).all()
        return {
            "notice_id":   str(notice_id),
            "title":       notice.title,
            "total_audience": notice.total_audience,
            "acknowledged": len(acks),
            "pending":     max(0, notice.total_audience - len(acks)),
            "rate_pct":    round(len(acks) / notice.total_audience * 100, 1) if notice.total_audience else 0,
            "acknowledgers": [{"user_id": str(a.user_id), "ack_at": str(a.ack_at)} for a in acks],
        }

    # ── Announcements ─────────────────────────────────────────────────────────

    def create_announcement(self, data: dict, user: User) -> Announcement:
        ann = Announcement(**data, created_by=user.id)
        self.db.add(ann)
        self.db.commit()
        self.db.refresh(ann)
        return ann

    def publish_announcement(self, ann_id: UUID, user: User) -> Announcement:
        ann = self.db.query(Announcement).filter(Announcement.id == ann_id).first()
        if not ann: raise HTTPException(404, "Announcement not found")
        ann.is_published = True
        ann.publish_date = datetime.utcnow()
        self.db.commit()
        self.db.refresh(ann)
        return ann

    def list_announcements(self, society_id: UUID) -> List[Announcement]:
        return self.db.query(Announcement).filter(
            Announcement.society_id  == society_id,
            Announcement.is_published == True,
            Announcement.is_active   == True,
        ).order_by(Announcement.publish_date.desc()).limit(50).all()

    # ── Emergency Alerts ──────────────────────────────────────────────────────

    def trigger_emergency_alert(self, data: dict, user: User, request=None) -> EmergencyAlert:
        alert = EmergencyAlert(**data, triggered_by=user.id, triggered_at=datetime.utcnow())
        self.db.add(alert)
        self.db.flush()

        self._audit(AuditAction.CREATE, alert, "EmergencyAlert", user, request,
                    new_values={"type": str(data.get("alert_type")), "title": data.get("title")})

        # In-app notification to triggerer (future: broadcast to all residents)
        NotificationService.send(
            db=self.db, user_id=user.id,
            title=f"🚨 EMERGENCY: {data.get('title')}",
            body=data.get("description", ""),
            type=NotificationType.ALERT, channel=NotificationChannel.IN_APP,
            module="emergency", entity_id=str(alert.id),
        )
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def resolve_emergency_alert(self, alert_id: UUID, notes: str, user: User) -> EmergencyAlert:
        alert = self.db.query(EmergencyAlert).filter(EmergencyAlert.id == alert_id).first()
        if not alert: raise HTTPException(404, "Alert not found")
        if alert.status != AlertStatus.ACTIVE:
            raise HTTPException(409, f"Alert is already {alert.status.value}")
        alert.status           = AlertStatus.RESOLVED
        alert.resolved_at      = datetime.utcnow()
        alert.resolved_by      = user.id
        alert.resolution_notes = notes
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def get_active_alerts(self, society_id: UUID) -> List[EmergencyAlert]:
        return self.db.query(EmergencyAlert).filter(
            EmergencyAlert.society_id == society_id,
            EmergencyAlert.status     == AlertStatus.ACTIVE,
            EmergencyAlert.is_active  == True,
        ).order_by(EmergencyAlert.triggered_at.desc()).all()

    def get_alert_history(self, society_id: UUID) -> List[EmergencyAlert]:
        return self.db.query(EmergencyAlert).filter(
            EmergencyAlert.society_id == society_id,
        ).order_by(EmergencyAlert.triggered_at.desc()).limit(50).all()

    # ── Communication logs ────────────────────────────────────────────────────

    def get_comm_logs(self, society_id: UUID, skip=0, limit=100) -> List[CommunicationLog]:
        return self.db.query(CommunicationLog).filter(
            CommunicationLog.society_id == society_id,
        ).order_by(CommunicationLog.sent_at.desc()).offset(skip).limit(limit).all()
