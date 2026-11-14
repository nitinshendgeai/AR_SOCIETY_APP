import re
from typing import List, Optional
from uuid import UUID
from sqlalchemy import and_, exists, func, or_
from sqlalchemy.orm import Session, joinedload
from app.modules.visitor.models.visitor import Visitor, VisitorLog, VisitorVehicle, Gate, VisitorStatus
from app.models.flat import Flat
from app.models.wing import Wing
from app.repositories.base import BaseRepository

# Lists show each visitor's wing and flat number.
_WITH_FLAT = joinedload(Visitor.flat).joinedload(Flat.wing)


_NOT_ALNUM = re.compile(r"[^a-z0-9\u0900-\u097f]")


def _squash(text: str) -> str:
    """Lower case with everything but letters, digits and Devanagari letters taken out, so "mh 12-ab 1234" and
    "MH12AB1234", or "A - 101" and "a101", compare equal. Mirrors the phone app's own search."""
    return _NOT_ALNUM.sub("", (text or "").lower())


def _squashed(column):
    """The same squashing in SQL, for spaces, hyphens and dots (all that people type between parts of a number)."""
    out = func.lower(column)
    for ch in (" ", "-", "."):
        out = func.replace(out, ch, "")
    return out


def search_words(query: Optional[str]) -> List[str]:
    return [w for w in (_squash(x) for x in (query or "").split()) if w]


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
        return self.db.query(Visitor).options(_WITH_FLAT).filter(
            Visitor.resident_id == resident_id,
            Visitor.status == VisitorStatus.PENDING,
            Visitor.is_active == True,
        ).order_by(Visitor.created_at.desc()).all()

    def get_by_society(self, society_id: UUID, skip: int = 0, limit: int = 50,
                       q: Optional[str] = None) -> List[Visitor]:
        """The society's visitors, latest first. With `q`, only those where every word of it is found in the visitor's
        name, mobile number, purpose, flat (as "101" or "A-101") or vehicle number. The pass code is deliberately
        not searchable: it is a secret the guest reads out at the gate."""
        query = self.db.query(Visitor).options(_WITH_FLAT).filter(
            Visitor.society_id == society_id,
            Visitor.is_active == True,
        )
        for word in search_words(q):
            flat_hit = exists().where(and_(
                Flat.id == Visitor.flat_id, Wing.id == Flat.wing_id,
                or_(_squashed(Flat.flat_number).contains(word),
                    _squashed(func.coalesce(Wing.name, "") + Flat.flat_number).contains(word))))
            vehicle_hit = exists().where(and_(
                VisitorVehicle.visitor_id == Visitor.id, _squashed(VisitorVehicle.vehicle_number).contains(word)))
            query = query.filter(or_(
                _squashed(Visitor.name).contains(word), _squashed(Visitor.mobile).contains(word),
                _squashed(func.coalesce(Visitor.purpose, "")).contains(word), flat_hit, vehicle_hit))
        return query.order_by(Visitor.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_resident(self, resident_id: UUID, skip: int = 0, limit: int = 50) -> List[Visitor]:
        return self.db.query(Visitor).options(_WITH_FLAT).filter(
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
        return self.db.query(Visitor).options(_WITH_FLAT).filter(
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
