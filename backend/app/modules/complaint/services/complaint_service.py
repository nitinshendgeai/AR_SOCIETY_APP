"""
ComplaintService — full lifecycle workflow engine.

FSM:
  OPEN → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED
                                            ↘ REOPENED → ASSIGNED
  Any (except CLOSED) → REJECTED (Admin only)
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.modules.complaint.models.complaint import (
    Complaint, ComplaintComment, ComplaintAttachment,
    ComplaintStatus, VALID_TRANSITIONS,
)
from app.modules.complaint.schemas.complaint import (
    ComplaintCreate, ComplaintAssignRequest, ComplaintStatusUpdateRequest,
    ComplaintReopenRequest, CommentCreate, AttachmentCreate,
)
from app.modules.complaint.repositories.complaint_repo import (
    ComplaintRepository, ComplaintCommentRepository,
    ComplaintAttachmentRepository, ComplaintStatusHistoryRepository,
)
from app.models.user import User
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel


class ComplaintService:

    def __init__(self, db: Session):
        self.db       = db
        self.repo     = ComplaintRepository(db)
        self.comment_repo    = ComplaintCommentRepository(db)
        self.attachment_repo = ComplaintAttachmentRepository(db)
        self.history_repo    = ComplaintStatusHistoryRepository(db)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_or_404(self, complaint_id: UUID) -> Complaint:
        c = self.repo.get(complaint_id)
        if not c:
            raise HTTPException(status_code=404, detail="Complaint not found")
        return c

    def _validate_transition(self, complaint: Complaint, new_status: ComplaintStatus):
        allowed = VALID_TRANSITIONS.get(complaint.status, set())
        if new_status not in allowed:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot transition from '{complaint.status.value}' to '{new_status.value}'. "
                       f"Allowed: {[s.value for s in allowed] or 'none'}"
            )

    def _record_transition(self, complaint: Complaint, new_status: ComplaintStatus,
                           user: User, notes: Optional[str] = None):
        self.history_repo.append(
            complaint_id=complaint.id,
            from_status=complaint.status,
            to_status=new_status,
            changed_by=user.id,
            notes=notes,
        )

    def _audit(self, action: AuditAction, complaint: Complaint,
               user: User, request: Optional[Request] = None, **kwargs):
        AuditService.log(
            db=self.db, action=action, module="complaint",
            entity_id=str(complaint.id), entity_type="Complaint",
            user=user, request=request, **kwargs,
        )

    def _notify_resident(self, complaint: Complaint, title: str, body: str,
                         type: NotificationType = NotificationType.INFO):
        NotificationService.send(
            db=self.db, user_id=complaint.raised_by,
            title=title, body=body, type=type,
            channel=NotificationChannel.IN_APP,
            module="complaint", entity_id=str(complaint.id),
        )

    def _notify_assignee(self, complaint: Complaint, title: str, body: str):
        if complaint.assigned_to:
            NotificationService.send(
                db=self.db, user_id=complaint.assigned_to,
                title=title, body=body, type=NotificationType.ALERT,
                channel=NotificationChannel.IN_APP,
                module="complaint", entity_id=str(complaint.id),
            )

    # ── Core workflow ─────────────────────────────────────────────────────────

    def create_complaint(self, data: ComplaintCreate, reporter: User,
                         request: Optional[Request] = None) -> Complaint:
        number = self.repo.next_complaint_number(data.society_id)
        complaint = Complaint(
            **data.model_dump(),
            complaint_number=number,
            raised_by=reporter.id,
            status=ComplaintStatus.OPEN,
        )
        self.db.add(complaint)
        self.db.flush()

        # Initial history entry
        self.history_repo.append(
            complaint_id=complaint.id,
            from_status=None,
            to_status=ComplaintStatus.OPEN,
            changed_by=reporter.id,
            notes="Complaint created",
        )

        self._audit(AuditAction.CREATE, complaint, reporter, request,
                    new_values={"number": number, "title": data.title,
                                "category": data.category.value, "priority": data.priority.value})

        self.db.commit()
        self.db.refresh(complaint)
        return complaint

    def assign_complaint(self, complaint_id: UUID, data: ComplaintAssignRequest,
                         assigner: User, request: Optional[Request] = None) -> Complaint:
        complaint = self._get_or_404(complaint_id)
        self._validate_transition(complaint, ComplaintStatus.ASSIGNED)

        prev_status       = complaint.status
        complaint.status      = ComplaintStatus.ASSIGNED
        complaint.assigned_to = data.assigned_to
        complaint.assigned_at = datetime.utcnow()
        if data.due_date:
            complaint.due_date = data.due_date

        self._record_transition(complaint, ComplaintStatus.ASSIGNED, assigner, data.notes)
        self._audit(AuditAction.UPDATE, complaint, assigner, request,
                    old_values={"status": prev_status.value},
                    new_values={"status": "assigned", "assigned_to": str(data.assigned_to)})

        # Notify assignee
        NotificationService.send(
            db=self.db, user_id=data.assigned_to,
            title="Complaint Assigned",
            body=f"Complaint #{complaint.complaint_number} — {complaint.title} has been assigned to you.",
            type=NotificationType.ALERT, channel=NotificationChannel.IN_APP,
            module="complaint", entity_id=str(complaint.id),
        )

        self.db.commit()
        self.db.refresh(complaint)
        return complaint

    def update_status(self, complaint_id: UUID, data: ComplaintStatusUpdateRequest,
                      user: User, request: Optional[Request] = None) -> Complaint:
        complaint = self._get_or_404(complaint_id)
        self._validate_transition(complaint, data.status)

        prev_status    = complaint.status
        complaint.status = data.status

        if data.status == ComplaintStatus.IN_PROGRESS:
            pass  # timestamp can be added here if needed

        elif data.status == ComplaintStatus.RESOLVED:
            complaint.resolved_at      = datetime.utcnow()
            complaint.resolution_notes = data.resolution_notes
            self._notify_resident(complaint,
                title="Complaint Resolved",
                body=f"Your complaint #{complaint.complaint_number} has been resolved. Please verify.",
                type=NotificationType.INFO)

        elif data.status == ComplaintStatus.CLOSED:
            complaint.closed_at = datetime.utcnow()
            self._notify_resident(complaint,
                title="Complaint Closed",
                body=f"Complaint #{complaint.complaint_number} has been closed.")

        elif data.status == ComplaintStatus.REJECTED:
            complaint.rejection_reason = data.rejection_reason
            self._notify_resident(complaint,
                title="Complaint Rejected",
                body=f"Your complaint #{complaint.complaint_number} was rejected. Reason: {data.rejection_reason}",
                type=NotificationType.WARNING)

        self._record_transition(complaint, data.status, user, data.notes)
        self._audit(AuditAction.UPDATE, complaint, user, request,
                    old_values={"status": prev_status.value},
                    new_values={"status": data.status.value, "notes": data.notes})

        self.db.commit()
        self.db.refresh(complaint)
        return complaint

    def reopen_complaint(self, complaint_id: UUID, data: ComplaintReopenRequest,
                         user: User, request: Optional[Request] = None) -> Complaint:
        complaint = self._get_or_404(complaint_id)
        if complaint.status != ComplaintStatus.RESOLVED:
            raise HTTPException(status_code=409,
                detail=f"Only resolved complaints can be reopened (current: {complaint.status.value})")

        complaint.status       = ComplaintStatus.REOPENED
        complaint.resolved_at  = None
        complaint.reopen_count += 1

        self._record_transition(complaint, ComplaintStatus.REOPENED, user, data.reason)
        self._audit(AuditAction.UPDATE, complaint, user, request,
                    new_values={"status": "reopened", "reason": data.reason,
                                "reopen_count": complaint.reopen_count})

        # Notify assignee if exists
        self._notify_assignee(complaint, "Complaint Reopened",
            f"Complaint #{complaint.complaint_number} was reopened. Reason: {data.reason}")

        self.db.commit()
        self.db.refresh(complaint)
        return complaint

    def add_comment(self, complaint_id: UUID, data: CommentCreate,
                    author: User, request: Optional[Request] = None) -> ComplaintComment:
        complaint = self._get_or_404(complaint_id)
        if complaint.status in (ComplaintStatus.CLOSED, ComplaintStatus.REJECTED):
            raise HTTPException(status_code=409,
                detail="Cannot comment on a closed or rejected complaint")

        comment = ComplaintComment(
            complaint_id=complaint.id,
            author_id=author.id,
            body=data.body,
            is_internal=data.is_internal,
        )
        self.db.add(comment)
        self._audit(AuditAction.UPDATE, complaint, author, request,
                    new_values={"action": "comment_added", "is_internal": data.is_internal})

        # Notify: if resident comments, notify assignee; if staff, notify resident
        if not data.is_internal:
            if complaint.assigned_to and str(author.id) != str(complaint.assigned_to):
                self._notify_assignee(complaint, "New Comment",
                    f"New comment on #{complaint.complaint_number}: {data.body[:80]}")
            elif str(author.id) != str(complaint.raised_by):
                self._notify_resident(complaint, "New Comment on Your Complaint",
                    f"Staff commented on #{complaint.complaint_number}: {data.body[:80]}")

        self.db.commit()
        self.db.refresh(comment)
        return comment

    def add_attachment(self, complaint_id: UUID, data: AttachmentCreate,
                       user: User) -> ComplaintAttachment:
        complaint = self._get_or_404(complaint_id)
        att = ComplaintAttachment(
            complaint_id=complaint.id,
            uploaded_by=user.id,
            **data.model_dump(),
        )
        self.db.add(att)
        self.db.commit()
        self.db.refresh(att)
        return att

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_complaint(self, complaint_id: UUID) -> Complaint:
        return self._get_or_404(complaint_id)

    def list_by_society(self, society_id: UUID, skip: int = 0, limit: int = 50) -> List[Complaint]:
        return self.repo.get_by_society(society_id, skip, limit)

    def list_my_complaints(self, user_id: UUID, skip: int = 0, limit: int = 50) -> List[Complaint]:
        return self.repo.get_by_resident(user_id, skip, limit)

    def list_assigned_to_me(self, user_id: UUID, skip: int = 0, limit: int = 50) -> List[Complaint]:
        return self.repo.get_assigned_to(user_id, skip, limit)

    def list_open(self, society_id: UUID) -> List[Complaint]:
        return self.repo.get_by_status(society_id, ComplaintStatus.OPEN)
