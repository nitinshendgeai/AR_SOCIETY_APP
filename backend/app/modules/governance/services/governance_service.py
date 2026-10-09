from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.tenant_scope import assert_society_access
from app.models.flat import Flat
from app.models.notification import NotificationType
from app.models.resident import Resident
from app.models.tenant import Tenant
from app.models.user import User
from app.models.wing import Wing
from app.modules.governance.models.governance import (
    DOCUMENT_CATEGORIES, DOCUMENT_VISIBILITY, MEETING_STATUSES, MEETING_TYPES, RESOLUTION_OUTCOMES,
    Meeting, MeetingAttendee, MeetingResolution, Poll, PollOption, PollVote, SocietyDocument,
)
from app.services.notification_service import NotificationService

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
ALLOWED_DOCUMENT_TYPES = {
    "application/pdf", "image/png", "image/jpeg", "text/plain",
    "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
OFFICE_ROLES = {"Society Admin", "Committee Chairman", "Committee Secretary", "Committee Treasurer",
                "Committee Member", "Platform Admin"}


def is_office(user: User) -> bool:
    return any(r in OFFICE_ROLES for r in _role_names(user))


def _role_names(user: User) -> List[str]:
    return [ur.role.name for ur in user.user_roles if ur.role is not None]


class GovernanceService:
    def __init__(self, db: Session):
        self.db = db

    # ── Who to tell ──────────────────────────────────────────────────────────

    def _member_user_ids(self, society_id: UUID) -> List[UUID]:
        res = (self.db.query(Resident.user_id).join(Flat, Resident.flat_id == Flat.id)
               .join(Wing, Flat.wing_id == Wing.id)
               .filter(Wing.society_id == society_id, Resident.is_active == True, Resident.user_id != None).all())
        ten = (self.db.query(Tenant.user_id).join(Flat, Tenant.flat_id == Flat.id)
               .join(Wing, Flat.wing_id == Wing.id)
               .filter(Wing.society_id == society_id, Tenant.is_active == True, Tenant.user_id != None).all())
        return list({r[0] for r in (*res, *ten)})

    def _announce(self, society_id: UUID, title: str, body: str, module: str, entity_id: str, route: str) -> int:
        n = 0
        for uid in self._member_user_ids(society_id):
            if NotificationService.send(db=self.db, user_id=uid, title=title, body=body,
                                        type=NotificationType.INFO, module=module, entity_id=entity_id,
                                        action_url=route, push=True):
                n += 1
        return n

    # ── Meetings ─────────────────────────────────────────────────────────────

    @staticmethod
    def _check_meeting(data: dict) -> None:
        if data.get("meeting_type") is not None and data["meeting_type"] not in MEETING_TYPES:
            raise HTTPException(422, "Unknown meeting type")
        if data.get("status") is not None and data["status"] not in MEETING_STATUSES:
            raise HTTPException(422, "Unknown meeting status")

    def create_meeting(self, society_id: UUID, data: dict, user: User, announce: bool) -> Meeting:
        assert_society_access(user, society_id)
        self._check_meeting(data)
        m = Meeting(society_id=society_id, created_by=user.id, **data)
        self.db.add(m)
        self.db.commit()
        if announce:
            when = f"{m.meeting_date:%d %b %Y}" + (f" at {m.start_time:%I:%M %p}".replace(" 0", " ") if m.start_time else "")
            self._announce(society_id, f"Meeting: {m.title}", f"{when}" + (f", {m.venue}" if m.venue else "") + ".",
                           "meeting", str(m.id), "/meetings")
        self.db.refresh(m)
        return m

    def get_meeting(self, meeting_id: UUID, user: User) -> Meeting:
        m = self.db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.is_active == True).first()
        if m is None:
            raise HTTPException(404, "Meeting not found")
        assert_society_access(user, m.society_id)   # 403/404 for another society, like the other modules
        return m

    def list_meetings(self, society_id: UUID, user: User) -> List[Meeting]:
        assert_society_access(user, society_id)
        return (self.db.query(Meeting).filter(Meeting.society_id == society_id, Meeting.is_active == True)
                .order_by(Meeting.meeting_date.desc()).all())

    def update_meeting(self, meeting_id: UUID, changes: dict, user: User) -> Meeting:
        m = self.get_meeting(meeting_id, user)
        self._check_meeting(changes)
        for k, v in changes.items():
            setattr(m, k, v)
        self.db.commit()
        self.db.refresh(m)
        return m

    def record_minutes(self, meeting_id: UUID, data: dict, user: User) -> Meeting:
        m = self.get_meeting(meeting_id, user)
        for r in data.get("resolutions") or []:
            if r.get("outcome") not in RESOLUTION_OUTCOMES:
                raise HTTPException(422, "A resolution's outcome must be carried, rejected or deferred")
        m.minutes = data.get("minutes")
        m.attendees[:] = [MeetingAttendee(**a) for a in (data.get("attendees") or [])]
        m.resolutions[:] = [MeetingResolution(number=i + 1, **r) for i, r in enumerate(data.get("resolutions") or [])]
        if m.status == "scheduled":
            m.status = "held"
        publish = bool(data.get("publish"))
        if publish and not m.minutes_published:
            m.minutes_published, m.minutes_published_on = True, date.today()
            self._announce(m.society_id, f"Minutes published: {m.title}",
                           f"The minutes of the meeting on {m.meeting_date:%d %b %Y} are available.",
                           "meeting", str(m.id), "/meetings")
        elif not publish:
            m.minutes_published = False
        self.db.commit()
        self.db.refresh(m)
        return m

    @staticmethod
    def meeting_out(m: Meeting, user: User) -> dict:
        """Minutes, attendance and resolutions are shown to the office, and to everyone once published."""
        show = is_office(user) or m.minutes_published
        out = {
            "id": str(m.id), "society_id": str(m.society_id), "title": m.title, "meeting_type": m.meeting_type,
            "meeting_date": m.meeting_date.isoformat(),
            "start_time": m.start_time.strftime("%H:%M") if m.start_time else None,
            "venue": m.venue, "agenda": m.agenda, "status": m.status,
            "minutes_published": m.minutes_published,
            "minutes_published_on": m.minutes_published_on.isoformat() if m.minutes_published_on else None,
            "minutes": m.minutes if show else None,
            "attendees": [], "resolutions": [],
        }
        if show:
            out["attendees"] = [{"name": a.name, "flat_label": a.flat_label, "designation": a.designation,
                                 "present": a.present} for a in m.attendees]
            out["resolutions"] = [{"number": r.number, "text": r.text, "proposed_by": r.proposed_by,
                                   "seconded_by": r.seconded_by, "outcome": r.outcome} for r in m.resolutions]
        return out

    # ── Polls ────────────────────────────────────────────────────────────────

    def create_poll(self, society_id: UUID, data: dict, user: User) -> Poll:
        assert_society_access(user, society_id)
        labels = [o.strip() for o in data.pop("options") if o and o.strip()]
        if len(labels) < 2 or len(set(x.lower() for x in labels)) != len(labels):
            raise HTTPException(422, "A poll needs at least two different options")
        if len(labels) > 10:
            raise HTTPException(422, "A poll can have at most 10 options")
        if data["closes_on"] < date.today():
            raise HTTPException(422, "The closing date cannot be in the past")
        poll = Poll(society_id=society_id, created_by=user.id, **data)
        poll.options = [PollOption(label=l, position=i) for i, l in enumerate(labels)]
        self.db.add(poll)
        self.db.commit()
        self._announce(society_id, "New poll", f"{poll.question} Vote by {poll.closes_on:%d %b %Y}.",
                       "poll", str(poll.id), "/polls")
        self.db.refresh(poll)
        return poll

    def _poll(self, poll_id: UUID, user: User) -> Poll:
        p = self.db.query(Poll).filter(Poll.id == poll_id, Poll.is_active == True).first()
        if p is None:
            raise HTTPException(404, "Poll not found")
        assert_society_access(user, p.society_id)
        return p

    @staticmethod
    def is_open(p: Poll, today: Optional[date] = None) -> bool:
        return (not p.closed_early) and p.closes_on >= (today or date.today())

    def _voting_flat(self, user: User, society_id: UUID) -> Optional[UUID]:
        row = (self.db.query(Resident.flat_id).join(Flat, Resident.flat_id == Flat.id)
               .join(Wing, Flat.wing_id == Wing.id)
               .filter(Resident.user_id == user.id, Resident.is_active == True, Wing.society_id == society_id)
               .order_by(Resident.is_primary.desc()).first())
        return row[0] if row else None

    def poll_out(self, p: Poll, user: User) -> dict:
        flat_id = self._voting_flat(user, p.society_id)
        votes = self.db.query(PollVote).filter(PollVote.poll_id == p.id).all()
        mine = next((v for v in votes if flat_id is not None and v.flat_id == flat_id), None)
        open_ = self.is_open(p)
        eligible = (self.db.query(func.count(Flat.id)).join(Wing, Flat.wing_id == Wing.id)
                    .filter(Wing.society_id == p.society_id, Flat.is_active == True).scalar()) or 0
        show = (not open_) or (p.results_after == "vote" and mine is not None)
        tallies = {o.id: 0 for o in p.options}
        for v in votes:
            tallies[v.option_id] = tallies.get(v.option_id, 0) + 1
        return {
            "id": str(p.id), "society_id": str(p.society_id), "question": p.question,
            "description": p.description, "closes_on": p.closes_on.isoformat(), "open": open_,
            "closed_early": p.closed_early, "results_after": p.results_after,
            "votes": len(votes), "flats": int(eligible),
            "can_vote": open_ and flat_id is not None and mine is None,
            "my_option_id": str(mine.option_id) if mine else None,
            "options": [{"id": str(o.id), "label": o.label, "votes": tallies[o.id] if show else None}
                        for o in p.options],
            "results_visible": show,
        }

    def list_polls(self, society_id: UUID, user: User) -> List[dict]:
        assert_society_access(user, society_id)
        polls = (self.db.query(Poll).filter(Poll.society_id == society_id, Poll.is_active == True)
                 .order_by(Poll.created_at.desc()).all())
        return [self.poll_out(p, user) for p in polls]

    def vote(self, poll_id: UUID, option_id: UUID, user: User) -> dict:
        p = self._poll(poll_id, user)
        if not self.is_open(p):
            raise HTTPException(409, "This poll is closed")
        if option_id not in {o.id for o in p.options}:
            raise HTTPException(422, "That is not an option of this poll")
        flat_id = self._voting_flat(user, p.society_id)
        if flat_id is None:
            raise HTTPException(403, "Only residents can vote")
        try:
            with self.db.begin_nested():
                self.db.add(PollVote(poll_id=p.id, option_id=option_id, flat_id=flat_id, user_id=user.id,
                                     voted_at=datetime.utcnow()))
                self.db.flush()
        except IntegrityError:
            raise HTTPException(409, "Your flat has already voted in this poll")
        self.db.commit()
        return self.poll_out(p, user)

    def close_poll(self, poll_id: UUID, user: User) -> dict:
        p = self._poll(poll_id, user)
        p.closed_early = True
        self.db.commit()
        return self.poll_out(p, user)

    # ── Documents ────────────────────────────────────────────────────────────

    def add_document(self, society_id: UUID, *, title: str, category: str, description: Optional[str],
                     visibility: str, file_name: str, mime_type: str, data: bytes, user: User) -> SocietyDocument:
        assert_society_access(user, society_id)
        if category not in DOCUMENT_CATEGORIES:
            raise HTTPException(422, "Unknown document category")
        if visibility not in DOCUMENT_VISIBILITY:
            raise HTTPException(422, "Visibility must be everyone or committee")
        if not data:
            raise HTTPException(422, "The file is empty")
        if len(data) > MAX_DOCUMENT_BYTES:
            raise HTTPException(413, "The file is larger than 10 MB")
        if mime_type not in ALLOWED_DOCUMENT_TYPES:
            raise HTTPException(415, "Use a PDF, image, Word, Excel or text file")
        d = SocietyDocument(society_id=society_id, title=title.strip(), category=category,
                            description=description, visibility=visibility, file_name=file_name[:255],
                            mime_type=mime_type, size_bytes=len(data), data=data, uploaded_by=user.id)
        self.db.add(d)
        self.db.commit()
        self.db.refresh(d)
        return d

    def _visible(self, d: SocietyDocument, user: User) -> bool:
        return d.visibility == "everyone" or is_office(user)

    def list_documents(self, society_id: UUID, user: User) -> List[SocietyDocument]:
        assert_society_access(user, society_id)
        rows = (self.db.query(SocietyDocument).filter(SocietyDocument.society_id == society_id,
                                                      SocietyDocument.is_active == True)
                .order_by(SocietyDocument.created_at.desc()).all())
        return [d for d in rows if self._visible(d, user)]

    def get_document(self, doc_id: UUID, user: User) -> SocietyDocument:
        d = self.db.query(SocietyDocument).filter(SocietyDocument.id == doc_id,
                                                  SocietyDocument.is_active == True).first()
        if d is None:
            raise HTTPException(404, "Document not found")
        assert_society_access(user, d.society_id)
        if not self._visible(d, user):
            raise HTTPException(404, "Document not found")
        return d

    def delete_document(self, doc_id: UUID, user: User) -> None:
        d = self.get_document(doc_id, user)
        d.is_active = False
        self.db.commit()

    @staticmethod
    def document_out(d: SocietyDocument) -> dict:
        return {"id": str(d.id), "title": d.title, "category": d.category, "description": d.description,
                "visibility": d.visibility, "file_name": d.file_name, "mime_type": d.mime_type,
                "size_bytes": d.size_bytes, "created_at": d.created_at.isoformat()}
