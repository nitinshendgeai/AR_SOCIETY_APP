from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.modules.complaint.models.complaint import (
    Complaint, ComplaintComment, ComplaintAttachment,
    ComplaintStatusHistory, ComplaintStatus,
)
from app.repositories.base import BaseRepository


class ComplaintRepository(BaseRepository[Complaint]):
    def __init__(self, db: Session):
        super().__init__(Complaint, db)

    def get_by_society(self, society_id: UUID, skip: int = 0, limit: int = 50) -> List[Complaint]:
        return self.db.query(Complaint).filter(
            Complaint.society_id == society_id,
            Complaint.is_active  == True,
        ).order_by(Complaint.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_resident(self, user_id: UUID, skip: int = 0, limit: int = 50) -> List[Complaint]:
        return self.db.query(Complaint).filter(
            Complaint.raised_by == user_id,
            Complaint.is_active == True,
        ).order_by(Complaint.created_at.desc()).offset(skip).limit(limit).all()

    def get_assigned_to(self, user_id: UUID, skip: int = 0, limit: int = 50) -> List[Complaint]:
        return self.db.query(Complaint).filter(
            Complaint.assigned_to == user_id,
            Complaint.is_active   == True,
            Complaint.status.in_([ComplaintStatus.ASSIGNED, ComplaintStatus.IN_PROGRESS]),
        ).order_by(Complaint.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_status(self, society_id: UUID, status: ComplaintStatus) -> List[Complaint]:
        return self.db.query(Complaint).filter(
            Complaint.society_id == society_id,
            Complaint.status     == status,
            Complaint.is_active  == True,
        ).all()

    def next_complaint_number(self, society_id: UUID) -> str:
        count = self.db.query(Complaint).filter(
            Complaint.society_id == society_id
        ).count()
        return f"CMP-{str(count + 1).zfill(5)}"


class ComplaintCommentRepository(BaseRepository[ComplaintComment]):
    def __init__(self, db: Session):
        super().__init__(ComplaintComment, db)

    def get_by_complaint(self, complaint_id: UUID, include_internal: bool = True) -> List[ComplaintComment]:
        q = self.db.query(ComplaintComment).filter(
            ComplaintComment.complaint_id == complaint_id
        )
        if not include_internal:
            q = q.filter(ComplaintComment.is_internal == False)
        return q.order_by(ComplaintComment.created_at.asc()).all()


class ComplaintAttachmentRepository(BaseRepository[ComplaintAttachment]):
    def __init__(self, db: Session):
        super().__init__(ComplaintAttachment, db)

    def get_by_complaint(self, complaint_id: UUID) -> List[ComplaintAttachment]:
        return self.db.query(ComplaintAttachment).filter(
            ComplaintAttachment.complaint_id == complaint_id,
            ComplaintAttachment.is_active    == True,
        ).all()


class ComplaintStatusHistoryRepository(BaseRepository[ComplaintStatusHistory]):
    def __init__(self, db: Session):
        super().__init__(ComplaintStatusHistory, db)

    def append(self, complaint_id: UUID, from_status: Optional[ComplaintStatus],
               to_status: ComplaintStatus, changed_by: UUID,
               notes: Optional[str] = None) -> ComplaintStatusHistory:
        entry = ComplaintStatusHistory(
            complaint_id=complaint_id,
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            notes=notes,
        )
        self.db.add(entry)
        self.db.flush()
        return entry
