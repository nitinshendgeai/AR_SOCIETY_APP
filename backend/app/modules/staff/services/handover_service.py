from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.staff.models.handover import (
    StaffHandover, HandoverItem,
    HandoverStatus, HandoverItemType, HANDOVER_TRANSITIONS,
)
from app.models.user import User
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel


class HandoverService:

    def __init__(self, db: Session):
        self.db = db

    def _get_or_404(self, handover_id: UUID) -> StaffHandover:
        h = self.db.query(StaffHandover).filter(
            StaffHandover.id == handover_id, StaffHandover.is_active == True
        ).first()
        if not h: raise HTTPException(404, "Handover not found")
        return h

    def _transition(self, handover: StaffHandover, new_status: HandoverStatus):
        allowed = HANDOVER_TRANSITIONS.get(handover.status, set())
        if new_status not in allowed:
            raise HTTPException(409,
                f"Cannot transition handover from '{handover.status.value}' to '{new_status.value}'")

    def _audit(self, action, entity, user, **kw):
        AuditService.log(db=self.db, action=action, module="handover",
                         entity_id=str(entity.id), entity_type="StaffHandover",
                         user=user, **kw)

    # ── Create handover ───────────────────────────────────────────────────────

    def create_handover(self, data: dict, user: User) -> StaffHandover:
        items_data = data.pop("items", [])
        handover = StaffHandover(**data)
        self.db.add(handover)
        self.db.flush()

        for item in items_data:
            self.db.add(HandoverItem(handover_id=handover.id, **item))

        self._audit(AuditAction.CREATE, handover, user,
                    new_values={"area": data.get("area"), "items": len(items_data)})
        self.db.commit()
        self.db.refresh(handover)
        return handover

    def add_item(self, handover_id: UUID, item_data: dict) -> HandoverItem:
        handover = self._get_or_404(handover_id)
        if handover.status not in (HandoverStatus.DRAFT,):
            raise HTTPException(409, "Can only add items to DRAFT handover")
        item = HandoverItem(handover_id=handover_id, **item_data)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    # ── Submit handover (outgoing staff sends to incoming) ────────────────────

    def submit_handover(self, handover_id: UUID, user: User) -> StaffHandover:
        handover = self._get_or_404(handover_id)
        self._transition(handover, HandoverStatus.SUBMITTED)

        if not handover.incoming_staff_id:
            raise HTTPException(422, "Incoming staff must be assigned before submission")

        handover.status = HandoverStatus.SUBMITTED
        self._audit(AuditAction.UPDATE, handover, user,
                    new_values={"status": "submitted"})

        # Notify incoming staff
        incoming = self.db.query(
            __import__('app.modules.staff.models.staff', fromlist=['Staff']).Staff
        ).filter_by(id=handover.incoming_staff_id).first()
        if incoming and incoming.user_id:
            NotificationService.send(
                db=self.db, user_id=incoming.user_id,
                title="Shift Handover Pending",
                body=f"A handover for {handover.area or 'your area'} is waiting for your acceptance.",
                type=NotificationType.ALERT, channel=NotificationChannel.IN_APP,
                module="handover", entity_id=str(handover.id),
            )
        self.db.commit()
        self.db.refresh(handover)
        return handover

    # ── Accept takeover (incoming staff confirms) ─────────────────────────────

    def accept_takeover(self, handover_id: UUID, notes: str, user: User) -> StaffHandover:
        handover = self._get_or_404(handover_id)
        self._transition(handover, HandoverStatus.ACCEPTED)

        handover.status           = HandoverStatus.ACCEPTED
        handover.accepted_at      = datetime.utcnow()
        handover.acceptance_notes = notes

        # Auto-acknowledge all items
        for item in handover.items:
            item.acknowledged = True

        self._audit(AuditAction.APPROVE, handover, user,
                    new_values={"status": "accepted"})
        self.db.commit()
        self.db.refresh(handover)
        return handover

    # ── Dispute handover ──────────────────────────────────────────────────────

    def dispute_handover(self, handover_id: UUID, reason: str, user: User) -> StaffHandover:
        handover = self._get_or_404(handover_id)
        self._transition(handover, HandoverStatus.DISPUTED)

        handover.status         = HandoverStatus.DISPUTED
        handover.dispute_reason = reason

        self._audit(AuditAction.UPDATE, handover, user,
                    new_values={"status": "disputed", "reason": reason})
        self.db.commit()
        self.db.refresh(handover)
        return handover

    # ── Verify handover (supervisor) ──────────────────────────────────────────

    def verify_handover(self, handover_id: UUID, notes: str, user: User) -> StaffHandover:
        handover = self._get_or_404(handover_id)
        self._transition(handover, HandoverStatus.VERIFIED)

        handover.status             = HandoverStatus.VERIFIED
        handover.verified_by        = user.id
        handover.verified_at        = datetime.utcnow()
        handover.verification_notes = notes

        self._audit(AuditAction.APPROVE, handover, user,
                    new_values={"status": "verified"})
        self.db.commit()
        self.db.refresh(handover)
        return handover

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_handover(self, handover_id: UUID) -> StaffHandover:
        return self._get_or_404(handover_id)

    def get_pending_for_staff(self, staff_id: UUID) -> List[StaffHandover]:
        return self.db.query(StaffHandover).filter(
            StaffHandover.incoming_staff_id == staff_id,
            StaffHandover.status == HandoverStatus.SUBMITTED,
            StaffHandover.is_active == True,
        ).order_by(StaffHandover.created_at.desc()).all()

    def get_by_society(self, society_id: UUID, skip=0, limit=50) -> List[StaffHandover]:
        return self.db.query(StaffHandover).filter(
            StaffHandover.society_id == society_id,
            StaffHandover.is_active  == True,
        ).order_by(StaffHandover.created_at.desc()).offset(skip).limit(limit).all()

    def get_staff_history(self, staff_id: UUID, skip=0, limit=30) -> List[StaffHandover]:
        from sqlalchemy import or_
        return self.db.query(StaffHandover).filter(
            or_(
                StaffHandover.outgoing_staff_id == staff_id,
                StaffHandover.incoming_staff_id == staff_id,
            ),
            StaffHandover.is_active == True,
        ).order_by(StaffHandover.created_at.desc()).offset(skip).limit(limit).all()
