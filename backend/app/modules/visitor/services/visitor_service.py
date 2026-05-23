"""
VisitorService — full workflow engine for Gate & Visitor Management.

Workflow:
  Guard: create visitor (PENDING)
  Resident: approve → APPROVED | reject → REJECTED
  Guard: check_in → CHECKED_IN
  Guard: check_out → CHECKED_OUT
"""
import secrets
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.modules.visitor.models.visitor import (
    Visitor, VisitorVehicle, VisitorLog, Gate,
    VisitorStatus, VisitorType,
)
from app.modules.visitor.schemas.visitor import VisitorCreate, VisitorApproveRequest, VisitorRejectRequest
from app.modules.visitor.repositories.visitor_repo import VisitorRepository, VisitorLogRepository, GateRepository
from app.models.user import User
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel


class VisitorService:

    def __init__(self, db: Session):
        self.db       = db
        self.repo     = VisitorRepository(db)
        self.log_repo = VisitorLogRepository(db)
        self.gate_repo= GateRepository(db)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_or_404(self, visitor_id: UUID) -> Visitor:
        v = self.repo.get(visitor_id)
        if not v:
            raise HTTPException(status_code=404, detail="Visitor not found")
        return v

    def _assert_status(self, visitor: Visitor, expected: VisitorStatus, action: str):
        if visitor.status != expected:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot {action}: visitor is currently '{visitor.status.value}'"
            )

    def _log(self, visitor_id: UUID, action: str, user: User,
             gate_id: Optional[UUID] = None, notes: Optional[str] = None):
        self.log_repo.append(visitor_id, action,
                             performed_by=user.id if user else None,
                             gate_id=gate_id, notes=notes)

    def _audit(self, action: AuditAction, visitor: Visitor,
               user: User, request: Optional[Request] = None, **kwargs):
        AuditService.log(
            db=self.db, action=action, module="visitor",
            entity_id=str(visitor.id), entity_type="Visitor",
            user=user, request=request, **kwargs,
        )

    # ── Gate CRUD ─────────────────────────────────────────────────────────────

    def create_gate(self, data, user: User) -> Gate:
        gate = Gate(**data.model_dump())
        return self.gate_repo.create(gate)

    def list_gates(self, society_id: UUID) -> List[Gate]:
        return self.gate_repo.get_by_society(society_id)

    def get_gate_or_404(self, gate_id: UUID) -> Gate:
        g = self.gate_repo.get(gate_id)
        if not g:
            raise HTTPException(status_code=404, detail="Gate not found")
        return g

    # ── Visitor Workflow ──────────────────────────────────────────────────────

    def create_visitor(self, data: VisitorCreate, logged_by: User,
                       request: Optional[Request] = None) -> Visitor:
        # Duplicate check
        existing = self.repo.get_active_by_mobile(data.mobile, data.society_id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Visitor with mobile {data.mobile} already has an active entry (status: {existing.status.value})"
            )

        vehicle_data = data.vehicle
        visitor_data = data.model_dump(exclude={"vehicle"})

        visitor = Visitor(**visitor_data, logged_by=logged_by.id, status=VisitorStatus.PENDING)
        self.db.add(visitor)
        self.db.flush()

        # Vehicle
        if vehicle_data:
            veh = VisitorVehicle(visitor_id=visitor.id, **vehicle_data.model_dump())
            self.db.add(veh)

        # Log
        self._log(visitor.id, "CREATED", logged_by, notes=f"Type: {data.visitor_type.value}")

        # Audit
        self._audit(AuditAction.CREATE, visitor, logged_by, request,
                    new_values={"name": visitor.name, "mobile": visitor.mobile,
                                "type": visitor.visitor_type.value})

        # Notify resident
        if visitor.resident_id:
            NotificationService.send(
                db=self.db, user_id=visitor.resident_id,
                title="Visitor at Gate",
                body=f"{visitor.name} ({visitor.visitor_type.value}) is at the gate. Purpose: {visitor.purpose or 'Not specified'}",
                type=NotificationType.APPROVAL,
                channel=NotificationChannel.IN_APP,
                module="visitor", entity_id=str(visitor.id),
                action_url=f"/visitors/{visitor.id}/approve",
            )

        self.db.commit()
        self.db.refresh(visitor)
        return visitor

    def approve_visitor(self, visitor_id: UUID, data: VisitorApproveRequest,
                        approver: User, request: Optional[Request] = None) -> Visitor:
        visitor = self._get_or_404(visitor_id)

        # Validate: only the target resident or admin/committee can approve
        self._assert_status(visitor, VisitorStatus.PENDING, "approve")

        visitor.status      = VisitorStatus.APPROVED
        visitor.approved_by = approver.id
        visitor.approved_at = datetime.utcnow()

        # QR token for future gate-pass scanning
        visitor.qr_token      = secrets.token_urlsafe(32)
        visitor.qr_expires_at = datetime.utcnow() + timedelta(hours=12)

        self._log(visitor.id, "APPROVED", approver, notes=data.notes)
        self._audit(AuditAction.APPROVE, visitor, approver, request,
                    new_values={"status": "approved", "approved_by": str(approver.id)})

        # Notify guard/logged_by
        if visitor.logged_by:
            NotificationService.send(
                db=self.db, user_id=visitor.logged_by,
                title="Visitor Approved",
                body=f"{visitor.name} has been approved by resident. Allow entry.",
                type=NotificationType.ALERT,
                channel=NotificationChannel.IN_APP,
                module="visitor", entity_id=str(visitor.id),
            )

        self.db.commit()
        self.db.refresh(visitor)
        return visitor

    def reject_visitor(self, visitor_id: UUID, data: VisitorRejectRequest,
                       rejector: User, request: Optional[Request] = None) -> Visitor:
        visitor = self._get_or_404(visitor_id)
        self._assert_status(visitor, VisitorStatus.PENDING, "reject")

        visitor.status           = VisitorStatus.REJECTED
        visitor.rejection_reason = data.reason
        visitor.approved_by      = rejector.id
        visitor.approved_at      = datetime.utcnow()

        self._log(visitor.id, "REJECTED", rejector, notes=data.reason)
        self._audit(AuditAction.REJECT, visitor, rejector, request,
                    new_values={"status": "rejected", "reason": data.reason})

        # Notify guard
        if visitor.logged_by:
            NotificationService.send(
                db=self.db, user_id=visitor.logged_by,
                title="Visitor Rejected",
                body=f"{visitor.name} has been rejected. Reason: {data.reason}",
                type=NotificationType.WARNING,
                channel=NotificationChannel.IN_APP,
                module="visitor", entity_id=str(visitor.id),
            )

        self.db.commit()
        self.db.refresh(visitor)
        return visitor

    def check_in(self, visitor_id: UUID, gate_id: Optional[UUID],
                 guard: User, notes: Optional[str] = None,
                 request: Optional[Request] = None) -> Visitor:
        visitor = self._get_or_404(visitor_id)

        if visitor.status not in (VisitorStatus.APPROVED, VisitorStatus.PENDING):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot check-in: visitor status is '{visitor.status.value}'"
            )

        visitor.status        = VisitorStatus.CHECKED_IN
        visitor.checked_in_at = datetime.utcnow()
        if gate_id:
            visitor.gate_id = gate_id

        self._log(visitor.id, "CHECKED_IN", guard, gate_id=gate_id, notes=notes)
        self._audit(AuditAction.UPDATE, visitor, guard, request,
                    new_values={"status": "checked_in", "checked_in_at": str(visitor.checked_in_at)})

        self.db.commit()
        self.db.refresh(visitor)
        return visitor

    def check_out(self, visitor_id: UUID, gate_id: Optional[UUID],
                  guard: User, notes: Optional[str] = None,
                  request: Optional[Request] = None) -> Visitor:
        visitor = self._get_or_404(visitor_id)
        self._assert_status(visitor, VisitorStatus.CHECKED_IN, "check-out")

        visitor.status         = VisitorStatus.CHECKED_OUT
        visitor.checked_out_at = datetime.utcnow()
        visitor.qr_token       = None  # invalidate QR on exit

        self._log(visitor.id, "CHECKED_OUT", guard, gate_id=gate_id, notes=notes)
        self._audit(AuditAction.UPDATE, visitor, guard, request,
                    new_values={"status": "checked_out",
                                "checked_out_at": str(visitor.checked_out_at),
                                "duration_minutes": str(
                                    int((visitor.checked_out_at - visitor.checked_in_at).total_seconds() / 60)
                                    if visitor.checked_in_at else "N/A"
                                )})

        self.db.commit()
        self.db.refresh(visitor)
        return visitor

    # ── Query methods ─────────────────────────────────────────────────────────

    def list_by_society(self, society_id: UUID, skip: int = 0, limit: int = 50) -> List[Visitor]:
        return self.repo.get_by_society(society_id, skip, limit)

    def get_pending_approvals(self, resident_id: UUID) -> List[Visitor]:
        return self.repo.get_pending_for_resident(resident_id)

    def get_my_visitors(self, resident_id: UUID, skip: int = 0, limit: int = 50) -> List[Visitor]:
        return self.repo.get_by_resident(resident_id, skip, limit)

    def get_currently_inside(self, society_id: UUID) -> List[Visitor]:
        return self.repo.get_checked_in(society_id)

    def get_visitor(self, visitor_id: UUID) -> Visitor:
        return self._get_or_404(visitor_id)
