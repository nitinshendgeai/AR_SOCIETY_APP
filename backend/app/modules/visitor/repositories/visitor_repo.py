from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.modules.visitor.models.visitor import Visitor, VisitorLog, Gate, VisitorStatus
from app.repositories.base import BaseRepository


class GateRepository(BaseRepository[Gate]):
    def __init__(self, db: Session):
        super().__init__(Gate, db)

    def get_by_society(self, society_id: UUID) -> List[Gate]:
        return self.db.query(Gate).filter(
            Gate.society_id == society_id, Gate.is_active == True
        ).all()


class VisitorRepository(BaseRepository[Visitor]):
    def __init__(self, db: Session):
        super().__init__(Visitor, db)

    def get_pending_for_resident(self, resident_id: UUID) -> List[Visitor]:
        return self.db.query(Visitor).filter(
            Visitor.resident_id == resident_id,
            Visitor.status == VisitorStatus.PENDING,
            Visitor.is_active == True,
        ).order_by(Visitor.created_at.desc()).all()

    def get_by_society(self, society_id: UUID, skip: int = 0, limit: int = 50) -> List[Visitor]:
        return self.db.query(Visitor).filter(
            Visitor.society_id == society_id,
            Visitor.is_active == True,
        ).order_by(Visitor.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_resident(self, resident_id: UUID, skip: int = 0, limit: int = 50) -> List[Visitor]:
        return self.db.query(Visitor).filter(
            Visitor.resident_id == resident_id,
            Visitor.is_active == True,
        ).order_by(Visitor.created_at.desc()).offset(skip).limit(limit).all()

    def get_active_by_mobile(self, mobile: str, society_id: UUID) -> Optional[Visitor]:
        """Check for duplicate active visitor."""
        return self.db.query(Visitor).filter(
            Visitor.mobile == mobile,
            Visitor.society_id == society_id,
            Visitor.status.in_([VisitorStatus.PENDING, VisitorStatus.APPROVED, VisitorStatus.CHECKED_IN]),
            Visitor.is_active == True,
        ).first()

    def get_checked_in(self, society_id: UUID) -> List[Visitor]:
        return self.db.query(Visitor).filter(
            Visitor.society_id == society_id,
            Visitor.status == VisitorStatus.CHECKED_IN,
            Visitor.is_active == True,
        ).all()


class VisitorLogRepository(BaseRepository[VisitorLog]):
    def __init__(self, db: Session):
        super().__init__(VisitorLog, db)

    def get_by_visitor(self, visitor_id: UUID) -> List[VisitorLog]:
        return self.db.query(VisitorLog).filter(
            VisitorLog.visitor_id == visitor_id
        ).order_by(VisitorLog.created_at.asc()).all()

    def append(self, visitor_id: UUID, action: str,
               performed_by: Optional[UUID] = None,
               gate_id: Optional[UUID] = None,
               notes: Optional[str] = None) -> VisitorLog:
        log = VisitorLog(
            visitor_id=visitor_id, action=action,
            performed_by=performed_by, gate_id=gate_id, notes=notes,
        )
        self.db.add(log)
        self.db.flush()
        return log
