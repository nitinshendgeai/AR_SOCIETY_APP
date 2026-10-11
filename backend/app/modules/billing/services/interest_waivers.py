"""
Interest waivers (InterestWaiver): the committee waives the interest on one flat's arrears, or charges a lower rate,
for a stretch of days, with a reason. The maintenance calculator applies it when it works out the interest on the
flat's next bill (see maintenance_calculator.py); bills already issued don't change. A waiver is cancelled with a
reason rather than deleted, so the record of who gave what stays.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.tenant_scope import resolve_create_society_id
from app.models.audit_log import AuditAction
from app.models.flat import Flat
from app.models.user import User
from app.modules.billing.models.billing import InterestWaiver
from app.services.audit_service import AuditService


class InterestWaiverService:

    def __init__(self, db: Session):
        self.db = db

    def get(self, waiver_id: UUID, user: Optional[User] = None) -> InterestWaiver:
        w = self.db.get(InterestWaiver, waiver_id)
        if w is None or not w.is_active or (user is not None and user.society_id is not None
                                            and w.society_id != user.society_id):
            raise HTTPException(404, "Interest waiver not found")
        return w

    def create(self, data: dict, user: User, request=None) -> InterestWaiver:
        society_id = resolve_create_society_id(user, data["society_id"])
        flat = self.db.get(Flat, data["flat_id"])
        if flat is None or not flat.is_active or not flat.wing or flat.wing.society_id != society_id:
            raise HTTPException(422, "Flat not found in this society")
        w = InterestWaiver(
            society_id=society_id, flat_id=flat.id, created_by=user.id, mode=data["mode"],
            rate_pct=data.get("rate_pct") if data["mode"] == "rate" else None,
            from_date=data["from_date"], to_date=data.get("to_date"), reason=data["reason"],
        )
        self.db.add(w)
        self.db.flush()
        AuditService.log(db=self.db, action=AuditAction.CREATE, module="billing", entity_id=str(w.id),
                         entity_type="InterestWaiver", user=user, request=request,
                         new_values={"flat": str(flat.id), "mode": w.mode,
                                     "rate_pct": str(w.rate_pct) if w.rate_pct is not None else None,
                                     "from": w.from_date.isoformat(),
                                     "to": w.to_date.isoformat() if w.to_date else None, "reason": w.reason})
        self.db.commit()
        self.db.refresh(w)
        return w

    def list_for_society(self, society_id: UUID, status: Optional[str] = None,
                         flat_id: Optional[UUID] = None) -> List[InterestWaiver]:
        q = self.db.query(InterestWaiver).filter(InterestWaiver.society_id == society_id,
                                                 InterestWaiver.is_active == True)  # noqa: E712
        if status:
            q = q.filter(InterestWaiver.status == status)
        if flat_id:
            q = q.filter(InterestWaiver.flat_id == flat_id)
        return q.order_by(InterestWaiver.created_at.desc()).all()

    def cancel(self, waiver_id: UUID, reason: str, user: User, request=None) -> InterestWaiver:
        w = self.get(waiver_id, user)
        if w.status == "cancelled":
            raise HTTPException(409, "This waiver is already cancelled")
        w.status = "cancelled"
        w.cancelled_at = datetime.utcnow()
        w.cancelled_by = user.id
        w.cancel_reason = reason
        AuditService.log(db=self.db, action=AuditAction.UPDATE, module="billing", entity_id=str(w.id),
                         entity_type="InterestWaiver", user=user, request=request,
                         old_values={"status": "active"}, new_values={"status": "cancelled", "reason": reason})
        self.db.commit()
        self.db.refresh(w)
        return w
