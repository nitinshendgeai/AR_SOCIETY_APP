from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.core.dependencies import (
    get_current_user, require_roles,
    require_admin_committee, require_any_member, require_security,
)
from app.models.user import User
from app.modules.notice.models.notice import (
    NoticeCategory, NoticePriority, AudienceType, AlertType,
)
from app.modules.notice.services.notice_service import NoticeService
from app.schemas.common import OrmBase, TimestampSchema
from typing import Optional, List as TList

router = APIRouter(prefix="/notices", tags=["Notice & Communication"])

admin_committee = require_admin_committee
any_member      = require_any_member
alert_raisers   = require_security      # admin, committee, manager and the security team can raise or end an alert


# ── Schemas inline ────────────────────────────────────────────────────────────
class NoticeCreate(OrmBase):
    society_id: Optional[UUID] = None       # a society user's own society is used
    title: str; content: str
    category: NoticeCategory; priority: NoticePriority = NoticePriority.NORMAL
    expiry_date: Optional[datetime] = None
    acknowledgement_required: bool = False
    audience_type: AudienceType = AudienceType.ALL_RESIDENTS
    target_wing_ids: Optional[list] = None
    target_flat_ids: Optional[list] = None
    attachment_url: Optional[str] = None

class AckRequest(OrmBase):
    flat_id: Optional[UUID] = None; notes: Optional[str] = None

class NoticeUpdate(OrmBase):
    """Only fields sent are changed (a draft only); send null to clear an optional one."""
    title: Optional[str] = None; content: Optional[str] = None
    category: Optional[NoticeCategory] = None; priority: Optional[NoticePriority] = None
    expiry_date: Optional[datetime] = None
    acknowledgement_required: Optional[bool] = None
    audience_type: Optional[AudienceType] = None
    target_wing_ids: Optional[list] = None
    target_flat_ids: Optional[list] = None
    attachment_url: Optional[str] = None

class AnnouncementCreate(OrmBase):
    society_id: Optional[UUID] = None; title: str; content: str
    category: NoticeCategory; priority: NoticePriority = NoticePriority.NORMAL
    audience_type: AudienceType = AudienceType.ALL
    expiry_date: Optional[datetime] = None; image_url: Optional[str] = None

class AlertCreate(OrmBase):
    society_id: Optional[UUID] = None; alert_type: AlertType; title: str
    description: Optional[str] = None; location: Optional[str] = None
    notify_all_residents: bool = True; notify_security: bool = True
    notify_committee: bool = True

class AlertResolveRequest(OrmBase):
    notes: Optional[str] = None


# ── Notices ───────────────────────────────────────────────────────────────────
@router.post("/", status_code=201, dependencies=[Depends(admin_committee)])
def create_notice(data: NoticeCreate, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    svc = NoticeService(db)
    return svc.out(svc.create_notice(data.model_dump(), user, request))

@router.patch("/{notice_id}", dependencies=[Depends(admin_committee)])
def update_notice(notice_id: UUID, data: NoticeUpdate, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    svc = NoticeService(db)
    return svc.out(svc.update_notice(notice_id, data.model_dump(exclude_unset=True), user, request))

@router.delete("/{notice_id}", status_code=204, dependencies=[Depends(admin_committee)])
def delete_draft(notice_id: UUID, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    NoticeService(db).delete_draft(notice_id, user, request)

@router.post("/{notice_id}/publish", dependencies=[Depends(admin_committee)])
def publish_notice(notice_id: UUID, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    svc = NoticeService(db)
    return svc.out(svc.publish_notice(notice_id, user, request))

@router.post("/{notice_id}/archive", dependencies=[Depends(admin_committee)])
def archive_notice(notice_id: UUID, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    svc = NoticeService(db)
    return svc.out(svc.archive_notice(notice_id, user, request))

@router.get("/society/{society_id}/all", dependencies=[Depends(admin_committee)])
def list_all_notices(society_id: UUID, status: Optional[str] = None,
                     skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Every notice of the society, drafts and archived included, for the committee."""
    return NoticeService(db).list_notices(society_id, user, status, skip, limit)

@router.get("/society/{society_id}/mine", dependencies=[Depends(any_member)])
def my_notices(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The notice board: published, unexpired notices meant for the caller, urgent first."""
    return NoticeService(db).my_notices(society_id, user)

@router.get("/society/{society_id}/published", dependencies=[Depends(any_member)])
def published_notices(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Same as /mine (kept for older callers): a member only ever sees notices meant for them."""
    return NoticeService(db).my_notices(society_id, user)

@router.post("/{notice_id}/acknowledge")
def acknowledge(notice_id: UUID, data: AckRequest, db: Session = Depends(get_db),
                user: User = Depends(any_member)):
    ack = NoticeService(db).acknowledge_notice(notice_id, user, data.flat_id, data.notes)
    return {"notice_id": str(ack.notice_id), "acknowledged_at": ack.ack_at.isoformat()}

@router.get("/{notice_id}/acknowledgements", dependencies=[Depends(admin_committee)])
def ack_report(notice_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return NoticeService(db).get_acknowledgement_report(notice_id, user)


# ── Announcements ─────────────────────────────────────────────────────────────
@router.post("/announcements/", status_code=201, dependencies=[Depends(admin_committee)])
def create_announcement(data: AnnouncementCreate, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    return NoticeService(db).create_announcement(data.model_dump(), user)

@router.post("/announcements/{ann_id}/publish", dependencies=[Depends(admin_committee)])
def publish_announcement(ann_id: UUID, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    return NoticeService(db).publish_announcement(ann_id, user)

@router.get("/announcements/society/{society_id}", dependencies=[Depends(any_member)])
def list_announcements(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return NoticeService(db).list_announcements(society_id, user)


# ── Emergency alerts ──────────────────────────────────────────────────────────
@router.post("/emergency/", status_code=201)
def trigger_alert(data: AlertCreate, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(alert_raisers)):
    svc = NoticeService(db)
    return svc.alert_out(svc.trigger_emergency_alert(data.model_dump(), user, request))

@router.post("/emergency/{alert_id}/resolve")
def resolve_alert(alert_id: UUID, data: AlertResolveRequest, db: Session = Depends(get_db),
                  user: User = Depends(alert_raisers)):
    svc = NoticeService(db)
    return svc.alert_out(svc.resolve_emergency_alert(alert_id, data.notes, user))

@router.get("/emergency/active/{society_id}", dependencies=[Depends(any_member)])
def active_alerts(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = NoticeService(db)
    return [svc.alert_out(a) for a in svc.get_active_alerts(society_id, user)]

@router.get("/emergency/history/{society_id}", dependencies=[Depends(admin_committee)])
def alert_history(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = NoticeService(db)
    return [svc.alert_out(a) for a in svc.get_alert_history(society_id, user)]


# ── Communication logs ────────────────────────────────────────────────────────
@router.get("/comm-logs/{society_id}", dependencies=[Depends(admin_committee)])
def comm_logs(society_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
              db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return NoticeService(db).get_comm_logs(society_id, user, skip, limit)


# `/{notice_id}` is declared last so it never shadows the fixed paths above.
@router.get("/{notice_id}", dependencies=[Depends(any_member)])
def get_notice(notice_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return NoticeService(db).get_notice(notice_id, user)
