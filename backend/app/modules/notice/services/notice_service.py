"""Notices, announcements and emergency alerts.

A notice is written as a **draft**, then **published** to an audience (everyone, the owners, the tenants, some
wings or flats, the staff, the security team, the committee). Who is in the audience is worked out from each
person's roles and the flats they live in, both when it is published (to count the audience) and whenever
someone opens the notice board, so a resident only ever sees notices meant for them. A notice can ask for an
**acknowledgement** ("I have read this"); the report lists who has and who has not.

Everything is confined to the caller's society: something that belongs to another society reads as not found,
a society-wide list for another society is refused.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.tenant_scope import assert_society_access, resolve_create_society_id
from app.models.audit_log import AuditAction
from app.models.flat import Flat
from app.models.notification import Notification, NotificationChannel, NotificationStatus, NotificationType
from app.models.resident import Resident
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User, UserRole, UserStatus
from app.models.wing import Wing
from app.modules.notice.models.notice import (
    Announcement, AlertStatus, AudienceType, CommunicationLog, EmergencyAlert, Notice, NoticeAcknowledgement,
    NoticeStatus,
)
from app.services.audit_service import AuditService

COMMITTEE_ROLES = {"Society Admin", "Committee Chairman", "Committee Secretary", "Committee Treasurer", "Committee Member"}
SECURITY_ROLES = {"Security Supervisor", "Security Staff"}
STAFF_ROLES = {"Manager", "Security Supervisor", "Housekeeping Supervisor", "Technical Supervisor",
               "Security Staff", "Housekeeping Staff", "Technical Staff", "Gym Trainer"}
OWNER_TYPES = {"owner", "co_owner"}

EDITABLE_FIELDS = ("title", "content", "category", "priority", "expiry_date", "acknowledgement_required",
                   "audience_type", "target_wing_ids", "target_flat_ids", "attachment_url")


@dataclass
class Profile:
    """What decides whether a notice is for someone: roles, the flats they live in, and how."""
    user_id: UUID
    name: str = ""
    roles: Set[str] = field(default_factory=set)
    flat_ids: Set[str] = field(default_factory=set)
    wing_ids: Set[str] = field(default_factory=set)
    owner_flats: Set[str] = field(default_factory=set)
    tenant_flats: Set[str] = field(default_factory=set)

    @property
    def is_resident(self) -> bool:
        return bool(self.flat_ids) or bool(self.roles & {"Resident", "Tenant"})

    @property
    def is_owner(self) -> bool:
        return bool(self.owner_flats) or (not self.flat_ids and "Resident" in self.roles)

    @property
    def is_tenant(self) -> bool:
        return bool(self.tenant_flats) or "Tenant" in self.roles


def in_audience(p: Profile, audience: AudienceType, wing_ids=None, flat_ids=None) -> bool:
    wings = {str(w) for w in (wing_ids or [])}
    flats = {str(f) for f in (flat_ids or [])}
    return {
        AudienceType.ALL: True,
        AudienceType.ALL_RESIDENTS: p.is_resident,
        AudienceType.OWNERS_ONLY: p.is_owner,
        AudienceType.TENANTS_ONLY: p.is_tenant,
        AudienceType.SPECIFIC_WINGS: bool(p.wing_ids & wings),
        AudienceType.SPECIFIC_FLATS: bool(p.flat_ids & flats),
        AudienceType.ALL_STAFF: bool(p.roles & STAFF_ROLES),
        AudienceType.SECURITY_TEAM: bool(p.roles & SECURITY_ROLES),
        AudienceType.COMMITTEE: bool(p.roles & COMMITTEE_ROLES),
    }[audience]


class NoticeService:

    def __init__(self, db: Session):
        self.db = db

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _in_scope(user: Optional[User], society_id) -> bool:
        return user is None or user.society_id is None or user.society_id == society_id

    def _scoped_or_404(self, row, user: Optional[User], what: str):
        if row is None or not self._in_scope(user, row.society_id):
            raise HTTPException(404, f"{what} not found")
        return row

    def _notice_or_404(self, notice_id: UUID, user: Optional[User] = None) -> Notice:
        n = self.db.query(Notice).filter(Notice.id == notice_id, Notice.is_active == True).first()
        return self._scoped_or_404(n, user, "Notice")

    def _audit(self, action, entity, entity_type, user, request=None, **kw):
        AuditService.log(db=self.db, action=action, module="notice", entity_id=str(entity.id),
                         entity_type=entity_type, user=user, request=request, **kw)

    def profiles(self, society_id: UUID, only: Optional[UUID] = None) -> Dict[UUID, Profile]:
        """Roles and flats of the society's active users (or of one), in a handful of queries."""
        q = self.db.query(User).filter(User.society_id == society_id, User.status == UserStatus.ACTIVE,
                                       User.is_active == True)
        if only is not None:
            q = q.filter(User.id == only)
        out = {u.id: Profile(user_id=u.id, name=u.full_name or u.email or "") for u in q.all()}
        if not out:
            return out
        ids = list(out)
        for uid, role in (self.db.query(UserRole.user_id, Role.name).join(Role, Role.id == UserRole.role_id)
                          .filter(UserRole.user_id.in_(ids)).all()):
            out[uid].roles.add(role)
        for model, kind in ((Resident, "resident"), (Tenant, "tenant")):
            rows = (self.db.query(model.user_id, model.flat_id, Flat.wing_id,
                                  getattr(model, "resident_type", None) if kind == "resident" else Flat.id)
                    .join(Flat, Flat.id == model.flat_id)
                    .filter(model.user_id.in_(ids), model.is_active == True).all())
            for uid, flat_id, wing_id, rtype in rows:
                p = out[uid]
                p.flat_ids.add(str(flat_id))
                p.wing_ids.add(str(wing_id))
                if kind == "tenant":
                    p.tenant_flats.add(str(flat_id))
                elif getattr(rtype, "value", rtype) in OWNER_TYPES:
                    p.owner_flats.add(str(flat_id))
        return out

    def audience_of(self, notice: Notice) -> List[Profile]:
        return [p for p in self.profiles(notice.society_id).values()
                if in_audience(p, notice.audience_type, notice.target_wing_ids, notice.target_flat_ids)]

    @staticmethod
    def _uuids(values, what: str) -> List[UUID]:
        try:
            return list({UUID(str(v)) for v in values})
        except ValueError:
            raise HTTPException(422, f"A {what} chosen isn't valid")

    def _check_targets(self, society_id: UUID, audience: AudienceType, wing_ids, flat_ids) -> None:
        if audience == AudienceType.SPECIFIC_WINGS:
            if not wing_ids:
                raise HTTPException(422, "Choose the wings this notice is for")
            ids = self._uuids(wing_ids, "wing")
            found = self.db.query(Wing.id).filter(Wing.id.in_(ids), Wing.society_id == society_id).count()
            if found != len(ids):
                raise HTTPException(422, "A wing chosen is not in this society")
        if audience == AudienceType.SPECIFIC_FLATS:
            if not flat_ids:
                raise HTTPException(422, "Choose the flats this notice is for")
            ids = self._uuids(flat_ids, "flat")
            found = (self.db.query(Flat.id).join(Wing, Wing.id == Flat.wing_id)
                     .filter(Flat.id.in_(ids), Wing.society_id == society_id).count())
            if found != len(ids):
                raise HTTPException(422, "A flat chosen is not in this society")

    @staticmethod
    def _expired(n: Notice) -> bool:
        return n.expiry_date is not None and n.expiry_date < datetime.utcnow()

    def out(self, n: Notice, acknowledged: Optional[bool] = None) -> dict:
        creator = self.db.query(User).filter(User.id == n.created_by).first() if n.created_by else None
        d = {
            "id": str(n.id), "society_id": str(n.society_id), "title": n.title, "content": n.content,
            "category": n.category.value, "priority": n.priority.value, "status": n.status.value,
            "publish_date": n.publish_date.isoformat() if n.publish_date else None,
            "expiry_date": n.expiry_date.isoformat() if n.expiry_date else None,
            "acknowledgement_required": n.acknowledgement_required,
            "audience_type": n.audience_type.value,
            "target_wing_ids": n.target_wing_ids or [], "target_flat_ids": n.target_flat_ids or [],
            "attachment_url": n.attachment_url,
            "total_audience": n.total_audience, "acknowledgement_count": n.acknowledgement_count,
            "created_by_name": creator.full_name if creator else None,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "is_expired": self._expired(n),
        }
        if acknowledged is not None:
            d["acknowledged"] = acknowledged
        return d

    # ── Notices ───────────────────────────────────────────────────────────────

    def create_notice(self, data: dict, user: User, request=None) -> Notice:
        society_id = resolve_create_society_id(user, data.get("society_id"))
        data = {**data, "society_id": society_id}
        for key in ("title", "content"):
            if not (data.get(key) or "").strip():
                raise HTTPException(422, f"{key.capitalize()} is required")
        data["title"], data["content"] = data["title"].strip(), data["content"].strip()
        if data.get("expiry_date") and data["expiry_date"] < datetime.utcnow():
            raise HTTPException(422, "The expiry date can't be in the past")
        self._check_targets(society_id, data["audience_type"], data.get("target_wing_ids"), data.get("target_flat_ids"))
        notice = Notice(**data, created_by=user.id)
        self.db.add(notice)
        self.db.flush()
        self._audit(AuditAction.CREATE, notice, "Notice", user, request,
                    new_values={"title": data.get("title"), "category": str(data.get("category"))})
        self.db.commit()
        self.db.refresh(notice)
        return notice

    def update_notice(self, notice_id: UUID, data: dict, user: User, request=None) -> Notice:
        notice = self._notice_or_404(notice_id, user)
        if notice.status != NoticeStatus.DRAFT:
            raise HTTPException(409, "A published notice can't be changed. Archive it and write a new one.")
        changes = {k: v for k, v in data.items() if k in EDITABLE_FIELDS}
        for key in ("title", "content"):
            if key in changes and not (changes[key] or "").strip():
                raise HTTPException(422, f"{key.capitalize()} is required")
        for key in ("category", "priority", "audience_type", "acknowledgement_required"):
            if key in changes and changes[key] is None:
                changes.pop(key)
        if changes.get("expiry_date") and changes["expiry_date"] < datetime.utcnow():
            raise HTTPException(422, "The expiry date can't be in the past")
        audience = changes.get("audience_type", notice.audience_type)
        self._check_targets(notice.society_id, audience,
                            changes.get("target_wing_ids", notice.target_wing_ids),
                            changes.get("target_flat_ids", notice.target_flat_ids))
        for key, value in changes.items():
            setattr(notice, key, value.strip() if key in ("title", "content") else value)
        self._audit(AuditAction.UPDATE, notice, "Notice", user, request, new_values={k: str(v) for k, v in changes.items()})
        self.db.commit()
        self.db.refresh(notice)
        return notice

    def delete_draft(self, notice_id: UUID, user: User, request=None) -> None:
        notice = self._notice_or_404(notice_id, user)
        if notice.status != NoticeStatus.DRAFT:
            raise HTTPException(409, "Only a draft can be deleted. Archive a published notice instead.")
        notice.is_active = False
        self._audit(AuditAction.DELETE, notice, "Notice", user, request)
        self.db.commit()

    def publish_notice(self, notice_id: UUID, user: User, request=None) -> Notice:
        notice = self._notice_or_404(notice_id, user)
        if notice.status != NoticeStatus.DRAFT:
            raise HTTPException(409, f"Notice is already {notice.status.value}")
        if self._expired(notice):
            raise HTTPException(422, "The expiry date has passed. Change it before publishing.")
        self._check_targets(notice.society_id, notice.audience_type, notice.target_wing_ids, notice.target_flat_ids)
        audience = self.audience_of(notice)
        if not audience:
            raise HTTPException(422, "Nobody is in this audience yet. Check who the notice is for.")
        notice.status = NoticeStatus.PUBLISHED
        notice.publish_date = datetime.utcnow()
        notice.total_audience = len(audience)
        self.db.add(CommunicationLog(society_id=notice.society_id, notice_id=notice.id, user_id=user.id,
                                     channel="in_app", status="sent", sent_at=datetime.utcnow()))
        self._audit(AuditAction.UPDATE, notice, "Notice", user, request,
                    new_values={"status": "published", "audience": len(audience)})
        self.db.commit()
        self.db.refresh(notice)
        return notice

    def archive_notice(self, notice_id: UUID, user: User, request=None) -> Notice:
        notice = self._notice_or_404(notice_id, user)
        if notice.status == NoticeStatus.DRAFT:
            raise HTTPException(409, "A draft has not been published. Delete it instead.")
        notice.status = NoticeStatus.ARCHIVED
        self._audit(AuditAction.UPDATE, notice, "Notice", user, request, new_values={"status": "archived"})
        self.db.commit()
        self.db.refresh(notice)
        return notice

    def get_notice(self, notice_id: UUID, user: User) -> dict:
        """One notice. Anyone may open one meant for them; the committee may open any."""
        notice = self._notice_or_404(notice_id, user)
        managing = bool(self.profiles(notice.society_id, user.id).get(user.id, Profile(user.id)).roles & COMMITTEE_ROLES) \
            or user.society_id is None
        if not managing:
            p = self.profiles(notice.society_id, user.id).get(user.id)
            if (p is None or notice.status != NoticeStatus.PUBLISHED
                    or not in_audience(p, notice.audience_type, notice.target_wing_ids, notice.target_flat_ids)):
                raise HTTPException(404, "Notice not found")
        acked = self.db.query(NoticeAcknowledgement.id).filter(
            NoticeAcknowledgement.notice_id == notice.id, NoticeAcknowledgement.user_id == user.id).first() is not None
        return self.out(notice, acked)

    def list_notices(self, society_id: UUID, user: User, status: Optional[str] = None, skip=0, limit=50) -> List[dict]:
        assert_society_access(user, society_id)
        q = self.db.query(Notice).filter(Notice.society_id == society_id, Notice.is_active == True)
        if status:
            q = q.filter(Notice.status == status)
        rows = q.order_by(Notice.created_at.desc()).offset(skip).limit(limit).all()
        return [self.out(n) for n in rows]

    def my_notices(self, society_id: UUID, user: User) -> List[dict]:
        """The published, unexpired notices meant for the caller, urgent first then newest, each with whether
        they have acknowledged it."""
        assert_society_access(user, society_id)
        p = self.profiles(society_id, user.id).get(user.id)
        if p is None:
            return []
        rows = self.db.query(Notice).filter(
            Notice.society_id == society_id, Notice.status == NoticeStatus.PUBLISHED, Notice.is_active == True).all()
        rows = [n for n in rows if not self._expired(n)
                and in_audience(p, n.audience_type, n.target_wing_ids, n.target_flat_ids)]
        acked = {a for (a,) in self.db.query(NoticeAcknowledgement.notice_id)
                 .filter(NoticeAcknowledgement.user_id == user.id).all()}
        rank = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        rows.sort(key=lambda n: (rank[n.priority.value], -(n.publish_date or n.created_at).timestamp()))
        return [self.out(n, n.id in acked) for n in rows]

    # ── Acknowledgement ───────────────────────────────────────────────────────

    def acknowledge_notice(self, notice_id: UUID, user: User, flat_id: UUID = None, notes: str = None):
        notice = self._notice_or_404(notice_id, user)
        if notice.status != NoticeStatus.PUBLISHED:
            raise HTTPException(409, "Can only acknowledge published notices")
        p = self.profiles(notice.society_id, user.id).get(user.id)
        if p is None or not in_audience(p, notice.audience_type, notice.target_wing_ids, notice.target_flat_ids):
            raise HTTPException(404, "Notice not found")
        if flat_id is not None and str(flat_id) not in p.flat_ids:
            raise HTTPException(422, "That isn't your flat")
        if self.db.query(NoticeAcknowledgement.id).filter(
                NoticeAcknowledgement.notice_id == notice_id, NoticeAcknowledgement.user_id == user.id).first():
            raise HTTPException(409, "You have already acknowledged this notice")
        if flat_id is None and len(p.flat_ids) == 1:
            flat_id = UUID(next(iter(p.flat_ids)))
        ack = NoticeAcknowledgement(notice_id=notice_id, user_id=user.id, flat_id=flat_id,
                                    ack_at=datetime.utcnow(), notes=notes)
        self.db.add(ack)
        notice.acknowledgement_count += 1
        self.db.commit()
        self.db.refresh(ack)
        return ack

    def get_acknowledgement_report(self, notice_id: UUID, user: User) -> dict:
        notice = self._notice_or_404(notice_id, user)
        acks = self.db.query(NoticeAcknowledgement).filter(NoticeAcknowledgement.notice_id == notice_id).all()
        profiles = self.profiles(notice.society_id)
        flats = {str(f.id): f"{w.name} / {f.flat_number}" for f, w in
                 self.db.query(Flat, Wing).join(Wing, Wing.id == Flat.wing_id).filter(Wing.society_id == notice.society_id).all()}

        def label(p: Profile) -> str:
            return ", ".join(sorted(flats.get(f, "") for f in p.flat_ids))

        acked_ids = {a.user_id for a in acks}
        audience = [p for p in profiles.values()
                    if in_audience(p, notice.audience_type, notice.target_wing_ids, notice.target_flat_ids)]
        pending = sorted((p for p in audience if p.user_id not in acked_ids), key=lambda p: label(p) or p.name)
        total = len(audience) if notice.status == NoticeStatus.PUBLISHED else notice.total_audience
        done = len(acks)
        return {
            "notice_id": str(notice_id), "title": notice.title,
            "acknowledgement_required": notice.acknowledgement_required,
            "total_audience": total, "acknowledged": done, "pending": max(0, total - done),
            "rate_pct": round(done / total * 100, 1) if total else 0,
            "acknowledgers": [{"user_id": str(a.user_id), "name": profiles[a.user_id].name if a.user_id in profiles else "",
                               "flat": label(profiles[a.user_id]) if a.user_id in profiles else "",
                               "ack_at": a.ack_at.isoformat()} for a in sorted(acks, key=lambda a: a.ack_at)],
            "pending_people": [{"user_id": str(p.user_id), "name": p.name, "flat": label(p)} for p in pending[:300]],
        }

    # ── Announcements ─────────────────────────────────────────────────────────

    def create_announcement(self, data: dict, user: User) -> Announcement:
        data = {**data, "society_id": resolve_create_society_id(user, data.get("society_id"))}
        ann = Announcement(**data, created_by=user.id)
        self.db.add(ann)
        self.db.commit()
        self.db.refresh(ann)
        return ann

    def publish_announcement(self, ann_id: UUID, user: User) -> Announcement:
        ann = self._scoped_or_404(self.db.query(Announcement).filter(Announcement.id == ann_id).first(), user, "Announcement")
        ann.is_published = True
        ann.publish_date = datetime.utcnow()
        self.db.commit()
        self.db.refresh(ann)
        return ann

    def list_announcements(self, society_id: UUID, user: User) -> List[Announcement]:
        assert_society_access(user, society_id)
        return self.db.query(Announcement).filter(
            Announcement.society_id == society_id, Announcement.is_published == True,
            Announcement.is_active == True,
        ).order_by(Announcement.publish_date.desc()).limit(50).all()

    # ── Emergency alerts ──────────────────────────────────────────────────────

    def trigger_emergency_alert(self, data: dict, user: User, request=None) -> EmergencyAlert:
        society_id = resolve_create_society_id(user, data.get("society_id"))
        if not (data.get("title") or "").strip():
            raise HTTPException(422, "Say what the emergency is")
        alert = EmergencyAlert(**{**data, "society_id": society_id}, triggered_by=user.id,
                               triggered_at=datetime.utcnow())
        self.db.add(alert)
        self.db.flush()
        self._audit(AuditAction.CREATE, alert, "EmergencyAlert", user, request,
                    new_values={"type": str(data.get("alert_type")), "title": data.get("title")})
        # An in-app notification for everyone the alert is meant to reach (no push gateway needed).
        body = " · ".join(x for x in (data.get("description"), data.get("location")) if x)
        reached = 0
        for p in self.profiles(society_id).values():
            wanted = ((alert.notify_all_residents and p.is_resident)
                      or (alert.notify_security and bool(p.roles & SECURITY_ROLES))
                      or (alert.notify_committee and bool(p.roles & COMMITTEE_ROLES)))
            if not wanted:
                continue
            self.db.add(Notification(user_id=p.user_id, title=f"EMERGENCY: {alert.title}", body=body,
                                     type=NotificationType.ALERT, channel=NotificationChannel.IN_APP,
                                     module="emergency", entity_id=str(alert.id),
                                     status=NotificationStatus.SENT))
            reached += 1
        self.db.commit()
        self.db.refresh(alert)
        alert.reached = reached
        return alert

    def resolve_emergency_alert(self, alert_id: UUID, notes: str, user: User) -> EmergencyAlert:
        alert = self._scoped_or_404(self.db.query(EmergencyAlert).filter(EmergencyAlert.id == alert_id).first(),
                                    user, "Alert")
        if alert.status != AlertStatus.ACTIVE:
            raise HTTPException(409, f"Alert is already {alert.status.value}")
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = user.id
        alert.resolution_notes = notes
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def get_active_alerts(self, society_id: UUID, user: User) -> List[EmergencyAlert]:
        assert_society_access(user, society_id)
        return self.db.query(EmergencyAlert).filter(
            EmergencyAlert.society_id == society_id, EmergencyAlert.status == AlertStatus.ACTIVE,
            EmergencyAlert.is_active == True,
        ).order_by(EmergencyAlert.triggered_at.desc()).all()

    def get_alert_history(self, society_id: UUID, user: User) -> List[EmergencyAlert]:
        assert_society_access(user, society_id)
        return self.db.query(EmergencyAlert).filter(EmergencyAlert.society_id == society_id) \
            .order_by(EmergencyAlert.triggered_at.desc()).limit(50).all()

    def alert_out(self, a: EmergencyAlert) -> dict:
        by = self.db.query(User).filter(User.id == a.triggered_by).first() if a.triggered_by else None
        return {
            "id": str(a.id), "society_id": str(a.society_id), "alert_type": a.alert_type.value,
            "status": a.status.value, "title": a.title, "description": a.description, "location": a.location,
            "triggered_at": a.triggered_at.isoformat() + "Z", "triggered_by_name": by.full_name if by else None,
            "resolved_at": a.resolved_at.isoformat() + "Z" if a.resolved_at else None,
            "resolution_notes": a.resolution_notes, "reached": getattr(a, "reached", None),
        }

    # ── Communication logs ────────────────────────────────────────────────────

    def get_comm_logs(self, society_id: UUID, user: User, skip=0, limit=100) -> List[CommunicationLog]:
        assert_society_access(user, society_id)
        return self.db.query(CommunicationLog).filter(CommunicationLog.society_id == society_id) \
            .order_by(CommunicationLog.sent_at.desc()).offset(skip).limit(limit).all()
