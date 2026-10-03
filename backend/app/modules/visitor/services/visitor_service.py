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
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.visitor.models.visitor import (
    Visitor, VisitorVehicle, VisitorLog, Gate,
    VisitorStatus, VisitorType,
)
from app.modules.visitor.schemas.visitor import VisitorCreate, VisitorApproveRequest, VisitorRejectRequest
from app.modules.visitor.repositories.visitor_repo import VisitorRepository, VisitorLogRepository, GateRepository
from app.models.user import User
from app.models.flat import Flat, OccupancyStatus
from app.models.resident import Resident
from app.models.tenant import Tenant
from app.models.audit_log import AuditAction
from app.core.dependencies import _user_has_permission
from app.core.tenant_scope import resolve_create_society_id
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

    def _own_flat_ids(self, user: User) -> set:
        """The flats a resident or tenant lives in."""
        flats = {r.flat_id for r in self.db.query(Resident).filter(
            Resident.user_id == user.id, Resident.is_active == True)}  # noqa: E712
        flats |= {t.flat_id for t in self.db.query(Tenant).filter(
            Tenant.user_id == user.id, Tenant.is_active == True)}  # noqa: E712
        return flats

    def _is_own(self, visitor: Visitor, user: User) -> bool:
        """Expected at the user's flat, or addressed to the user."""
        return visitor.resident_id == user.id or (
            visitor.flat_id is not None and visitor.flat_id in self._own_flat_ids(user))

    def _get_or_404(self, visitor_id: UUID, user: Optional[User] = None) -> Visitor:
        """The visitor, if the caller may see it: its own society's, and for a
        plain resident or tenant only visitors for their own flat."""
        v = self.repo.get(visitor_id)
        if not v:
            raise HTTPException(status_code=404, detail="Visitor not found")
        if user is not None:
            if user.society_id is not None and v.society_id != user.society_id:
                raise HTTPException(status_code=404, detail="Visitor not found")
            if not _user_has_permission(user, "security") and not self._is_own(v, user):
                raise HTTPException(status_code=404, detail="Visitor not found")
        return v

    def _assert_can_decide(self, visitor: Visitor, user: User) -> None:
        """Approving or rejecting entry is for the people of the flat visited —
        or the committee/manager answering for them. Not the guard, not another
        flat."""
        if self._is_own(visitor, user) or _user_has_permission(user, "manager_above"):
            return
        raise HTTPException(status_code=403, detail="Only the resident of the flat visited can decide this")

    def _gate_in_society(self, gate_id: Optional[UUID], society_id: UUID) -> None:
        if gate_id is None:
            return
        gate = self.gate_repo.get(gate_id)
        if not gate or gate.society_id != society_id:
            raise HTTPException(status_code=422, detail="Gate not found in this society")

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

    def _flat_in_society_or_422(self, flat_id: UUID, society_id: UUID) -> Flat:
        flat = self.db.get(Flat, flat_id)
        if not flat or not flat.is_active or not flat.wing or flat.wing.society_id != society_id:
            raise HTTPException(status_code=422, detail="Flat not found in this society")
        return flat

    def _flat_contact(self, flat: Flat) -> Optional[UUID]:
        """The app user who answers for a flat's visitors: the current tenant
        of a rented flat, otherwise the primary owner, otherwise any resident
        of the flat with a login."""
        tenants = [t for t in flat.tenants
                   if t.is_active and t.user_id and not t.move_out_date]
        residents = sorted((r for r in flat.residents if r.is_active and r.user_id),
                           key=lambda r: not r.is_primary)
        if flat.occupancy_status == OccupancyStatus.TENANT_OCCUPIED and tenants:
            return tenants[0].user_id
        if residents:
            return residents[0].user_id
        return tenants[0].user_id if tenants else None

    # ── Gate CRUD ─────────────────────────────────────────────────────────────

    def create_gate(self, data, user: User) -> Gate:
        society_id = resolve_create_society_id(user, data.society_id)
        taken = self.db.query(Gate).filter(
            Gate.society_id == society_id, Gate.is_active == True,  # noqa: E712
            func.lower(Gate.name) == data.name.lower()).first()
        if taken:
            raise HTTPException(status_code=409, detail=f"A gate named '{taken.name}' already exists")
        payload = data.model_dump()
        payload["society_id"] = society_id
        return self.gate_repo.create(Gate(**payload))

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
        society_id = resolve_create_society_id(logged_by, data.society_id)
        data.society_id = society_id
        self._gate_in_society(data.gate_id, society_id)
        if data.resident_id is not None:
            named = self.db.get(User, data.resident_id)
            if not named or named.society_id != society_id:
                raise HTTPException(status_code=422, detail="Resident not found in this society")

        # Duplicate check
        existing = self.repo.get_active_by_mobile(data.mobile, data.society_id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Visitor with mobile {data.mobile} already has an active entry (status: {existing.status.value})"
            )

        vehicle_data = data.vehicle
        visitor_data = data.model_dump(exclude={"vehicle"})

        # A visitor comes to a flat: check it's in this society and, unless
        # the guard named someone, send the approval to that flat's resident.
        if data.flat_id:
            flat = self._flat_in_society_or_422(data.flat_id, data.society_id)
            if not data.resident_id:
                visitor_data["resident_id"] = self._flat_contact(flat)

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
                body=f"{visitor.name} ({visitor.visitor_type.value}) is at the gate"
                     + (f" for {visitor.wing_name}-{visitor.flat_number}" if visitor.flat_number else "")
                     + f". Purpose: {visitor.purpose or 'Not specified'}",
                type=NotificationType.APPROVAL,
                channel=NotificationChannel.IN_APP,
                module="visitor", entity_id=str(visitor.id),
                action_url="/visitors/pending",   # the resident's approvals screen
                push=True,
            )

        self.db.commit()
        self.db.refresh(visitor)
        return visitor

    def approve_visitor(self, visitor_id: UUID, data: VisitorApproveRequest,
                        approver: User, request: Optional[Request] = None) -> Visitor:
        visitor = self._get_or_404(visitor_id, approver)
        self._assert_can_decide(visitor, approver)
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
                action_url=f"/visitors/society/{visitor.society_id}",   # the guard's visitor log
                push=True,
            )

        self.db.commit()
        self.db.refresh(visitor)
        return visitor

    def reject_visitor(self, visitor_id: UUID, data: VisitorRejectRequest,
                       rejector: User, request: Optional[Request] = None) -> Visitor:
        visitor = self._get_or_404(visitor_id, rejector)
        self._assert_can_decide(visitor, rejector)
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
                action_url=f"/visitors/society/{visitor.society_id}",   # the guard's visitor log
                push=True,
            )

        self.db.commit()
        self.db.refresh(visitor)
        return visitor

    def check_in(self, visitor_id: UUID, gate_id: Optional[UUID],
                 guard: User, notes: Optional[str] = None,
                 request: Optional[Request] = None) -> Visitor:
        visitor = self._get_or_404(visitor_id, guard)
        self._gate_in_society(gate_id, visitor.society_id)

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
        visitor = self._get_or_404(visitor_id, guard)
        self._gate_in_society(gate_id, visitor.society_id)
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

    def get_visitor(self, visitor_id: UUID, user: Optional[User] = None) -> Visitor:
        return self._get_or_404(visitor_id, user)
