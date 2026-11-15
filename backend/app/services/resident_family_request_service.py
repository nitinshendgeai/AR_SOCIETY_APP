"""A resident asks to add a member of their family; the Admin or committee approves.

Why a request and not a direct add: the Residents list decides who may use society facilities (the gym's attendance book
reads it), so the office must say yes to each new name. Approval adds the person to the Residents list as Family or
Dependent; until then they are on no list that anything reads."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditAction
from app.models.flat import Flat
from app.models.resident import Resident, ResidentType
from app.models.resident_family_request import APPROVED, PENDING, REJECTED, ResidentFamilyRequest
from app.models.user import User
from app.models.wing import Wing
from app.repositories.resident_repo import ResidentRepository
from app.schemas.resident_family_request import FamilyRequestCreate, FamilyRequestOut
from app.services.audit_service import AuditService

MAX_PENDING_PER_FLAT = 10
OWNER_TYPES = (ResidentType.OWNER, ResidentType.CO_OWNER)


def _norm(name: str) -> str:
    return " ".join((name or "").lower().split())


def flat_display(flat: Optional[Flat]) -> Optional[str]:
    if flat is None:
        return None
    wing = flat.wing.name if flat.wing else None
    return f"{wing}-{flat.flat_number}" if wing else str(flat.flat_number)


class FamilyRequestService:
    def __init__(self, db: Session):
        self.db = db

    # ── shared ────────────────────────────────────────────────────────────────────────────────────────────────────

    def _out(self, req: ResidentFamilyRequest) -> FamilyRequestOut:
        out = FamilyRequestOut.model_validate(req)
        out.flat_display = flat_display(self.db.get(Flat, req.flat_id))
        return out

    def _flat_in_society(self, flat_id: UUID, society_id: UUID) -> Flat:
        flat = (self.db.query(Flat).join(Wing, Wing.id == Flat.wing_id)
                .filter(Flat.id == flat_id, Wing.society_id == society_id).first())
        if flat is None:
            raise HTTPException(404, "Flat not found")
        return flat

    def _already_listed(self, flat_id: UUID, name: str) -> bool:
        return self.db.query(Resident.id).filter(
            Resident.flat_id == flat_id, Resident.is_active == True,                     # noqa: E712
            func.lower(func.trim(Resident.full_name)) == _norm(name)).first() is not None

    def _pending_on(self, flat_id: UUID) -> List[ResidentFamilyRequest]:
        return self.db.query(ResidentFamilyRequest).filter(
            ResidentFamilyRequest.flat_id == flat_id, ResidentFamilyRequest.status == PENDING).all()

    # ── the resident ──────────────────────────────────────────────────────────────────────────────────────────────

    def create(self, data: FamilyRequestCreate, user: User) -> FamilyRequestOut:
        owners = [r for r in self.db.query(Resident).filter(
            Resident.user_id == user.id, Resident.is_active == True).all()                 # noqa: E712
            if r.resident_type in OWNER_TYPES]
        if not owners:
            raise HTTPException(403, "Only an owner or co-owner can add family members. Please ask the society office.")
        flat_ids = {r.flat_id for r in owners}
        if data.flat_id is not None:
            if data.flat_id not in flat_ids:
                raise HTTPException(404, "Flat not found")
            flat_id = data.flat_id
        elif len(flat_ids) == 1:
            flat_id = next(iter(flat_ids))
        else:
            raise HTTPException(422, "Choose the flat")
        flat = self._flat_in_society(flat_id, user.society_id)

        if self._already_listed(flat.id, data.full_name):
            raise HTTPException(409, f"{data.full_name.strip()} is already on the list for this flat")
        waiting = self._pending_on(flat.id)
        if any(_norm(p.full_name) == _norm(data.full_name) for p in waiting):
            raise HTTPException(409, f"{data.full_name.strip()} is already waiting for approval")
        if len(waiting) >= MAX_PENDING_PER_FLAT:
            raise HTTPException(409, "Too many requests are waiting for approval for this flat. Please ask the society office.")

        req = ResidentFamilyRequest(
            society_id=user.society_id, flat_id=flat.id, requested_by=user.id, requester_name=user.full_name,
            full_name=data.full_name, resident_type=data.resident_type, phone=data.phone,
            date_of_birth=data.date_of_birth, status=PENDING)
        self.db.add(req)
        self.db.commit()
        self.db.refresh(req)
        AuditService.log(
            db=self.db, action=AuditAction.CREATE, module="resident_family_request", entity_id=str(req.id),
            entity_type="ResidentFamilyRequest", user=user,
            new_values={"full_name": req.full_name, "resident_type": req.resident_type, "flat_id": str(req.flat_id)})
        return self._out(req)

    def list_mine(self, user: User) -> List[FamilyRequestOut]:
        rows = (self.db.query(ResidentFamilyRequest).filter(ResidentFamilyRequest.requested_by == user.id)
                .order_by(ResidentFamilyRequest.created_at.desc()).limit(50).all())
        return [self._out(r) for r in rows]

    # ── the office ────────────────────────────────────────────────────────────────────────────────────────────────

    def list_pending(self, society_id: UUID) -> List[FamilyRequestOut]:
        rows = (self.db.query(ResidentFamilyRequest).filter(
            ResidentFamilyRequest.society_id == society_id, ResidentFamilyRequest.status == PENDING)
            .order_by(ResidentFamilyRequest.created_at).all())
        return [self._out(r) for r in rows]

    def _get(self, request_id: UUID, society_id: UUID) -> ResidentFamilyRequest:
        req = self.db.query(ResidentFamilyRequest).filter(
            ResidentFamilyRequest.id == request_id, ResidentFamilyRequest.society_id == society_id).first()
        if req is None:
            raise HTTPException(404, "Request not found")
        if req.status != PENDING:
            raise HTTPException(409, "This request has already been reviewed")
        return req

    def approve(self, request_id: UUID, admin: User) -> FamilyRequestOut:
        req = self._get(request_id, admin.society_id)
        flat = self._flat_in_society(req.flat_id, admin.society_id)
        if self._already_listed(flat.id, req.full_name):
            raise HTTPException(409, f"{req.full_name} is already on the list for this flat. Reject this request instead.")
        # Added to the Residents list as Family or Dependent. No app login is made for them here: the office can give one
        # later from the Residents list if they need it.
        member = ResidentRepository(self.db).create(Resident(
            flat_id=flat.id, full_name=req.full_name, resident_type=ResidentType(req.resident_type),
            phone=req.phone, date_of_birth=req.date_of_birth, is_primary=False))
        req.status, req.reviewed_by, req.reviewed_at, req.resident_id = APPROVED, admin.id, datetime.utcnow(), member.id
        self.db.commit()
        self.db.refresh(req)
        AuditService.log(
            db=self.db, action=AuditAction.CREATE, module="resident", entity_id=str(member.id), entity_type="Resident",
            user=admin, new_values={"full_name": member.full_name, "resident_type": req.resident_type,
                                    "flat_id": str(flat.id), "is_primary": False},
            notes=f"Approved family member request {req.id}")
        return self._out(req)

    def reject(self, request_id: UUID, reason: str, admin: User) -> FamilyRequestOut:
        req = self._get(request_id, admin.society_id)
        req.status, req.reviewed_by, req.reviewed_at, req.rejection_reason = REJECTED, admin.id, datetime.utcnow(), reason
        self.db.commit()
        self.db.refresh(req)
        AuditService.log(
            db=self.db, action=AuditAction.UPDATE, module="resident_family_request", entity_id=str(req.id),
            entity_type="ResidentFamilyRequest", user=admin, notes=f"Rejected: {reason}")
        return self._out(req)

    # ── for others who read the list ──────────────────────────────────────────────────────────────────────────────

    @staticmethod
    def waiting_names(db: Session, society_id: UUID, flat_id: UUID) -> List[str]:
        """Names asked for on this flat and not yet approved (so the gym desk can say "waiting for approval")."""
        rows = db.query(ResidentFamilyRequest.full_name).filter(
            ResidentFamilyRequest.society_id == society_id, ResidentFamilyRequest.flat_id == flat_id,
            ResidentFamilyRequest.status == PENDING).order_by(ResidentFamilyRequest.created_at).all()
        return [r[0] for r in rows]
