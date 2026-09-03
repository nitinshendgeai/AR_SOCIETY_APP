from typing import List
from uuid import UUID
from datetime import date as date_cls, datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.resident import Resident, CommunicationPreference
from app.models.resident_edit_request import ResidentEditRequest, ResidentEditRequestStatus
from app.models.user import User
from app.models.audit_log import AuditAction
from app.schemas.resident_edit_request import ResidentEditRequestCreate, ResidentEditRequestOut
from app.services.audit_service import AuditService

# Deliberately excludes resident_type, is_primary, flat_id, kyc_*, and
# move_in/out dates — those stay Admin/Committee-only via the existing
# direct PATCH /residents/{id}, since a resident self-editing them could
# affect billing, occupancy, or primary-resident status.
_EDITABLE_FIELDS = {
    "full_name", "phone", "email", "date_of_birth",
    "emergency_contact_name", "emergency_contact_phone",
    "comm_preference", "photo_url",
}


def _serialize(field: str, value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def _coerce(field: str, value):
    if value is None:
        return None
    if field == "date_of_birth":
        return date_cls.fromisoformat(value)
    if field == "comm_preference":
        return CommunicationPreference(value)
    return value


class ResidentEditRequestService:
    def __init__(self, db: Session):
        self.db = db

    def _enrich(self, req: ResidentEditRequest) -> ResidentEditRequestOut:
        out = ResidentEditRequestOut.model_validate(req)
        resident = self.db.get(Resident, req.resident_id)
        if resident:
            out.resident_name = resident.full_name
            if resident.flat:
                wing_name = resident.flat.wing.name if resident.flat.wing else None
                out.flat_display = (
                    f"{wing_name} - {resident.flat.flat_number}" if wing_name else resident.flat.flat_number
                )
        return out

    def _my_resident(self, current_user: User) -> Resident:
        resident = (
            self.db.query(Resident)
            .filter(Resident.user_id == current_user.id, Resident.is_active == True)  # noqa: E712
            .first()
        )
        if not resident:
            raise HTTPException(status_code=404, detail="No resident profile linked to this account")
        return resident

    # ── Resident-facing ──────────────────────────────────────────────────────

    def create_request(self, data: ResidentEditRequestCreate, current_user: User) -> ResidentEditRequestOut:
        resident = self._my_resident(current_user)

        existing = (
            self.db.query(ResidentEditRequest)
            .filter(
                ResidentEditRequest.resident_id == resident.id,
                ResidentEditRequest.status == ResidentEditRequestStatus.PENDING,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="You already have a pending change request")

        raw_changes = data.model_dump(exclude_none=True)
        if not raw_changes:
            raise HTTPException(status_code=422, detail="No changes provided")
        changes = {k: _serialize(k, v) for k, v in raw_changes.items()}

        req = ResidentEditRequest(
            resident_id=resident.id, requested_by=current_user.id,
            society_id=current_user.society_id, changes=changes,
            status=ResidentEditRequestStatus.PENDING,
        )
        self.db.add(req)
        self.db.commit()
        self.db.refresh(req)

        AuditService.log(
            db=self.db, action=AuditAction.CREATE, module="resident_edit_request",
            entity_id=str(req.id), entity_type="ResidentEditRequest", user=current_user,
            new_values=changes,
        )
        return self._enrich(req)

    def list_mine(self, current_user: User) -> List[ResidentEditRequestOut]:
        resident = self._my_resident(current_user)
        reqs = (
            self.db.query(ResidentEditRequest)
            .filter(ResidentEditRequest.resident_id == resident.id)
            .order_by(ResidentEditRequest.created_at.desc())
            .all()
        )
        return [self._enrich(r) for r in reqs]

    # ── Admin/Committee-facing ───────────────────────────────────────────────

    def list_pending(self, society_id: UUID) -> List[ResidentEditRequestOut]:
        reqs = (
            self.db.query(ResidentEditRequest)
            .filter(
                ResidentEditRequest.society_id == society_id,
                ResidentEditRequest.status == ResidentEditRequestStatus.PENDING,
            )
            .order_by(ResidentEditRequest.created_at.asc())
            .all()
        )
        return [self._enrich(r) for r in reqs]

    def _get_or_404(self, request_id: UUID, society_id: UUID) -> ResidentEditRequest:
        req = (
            self.db.query(ResidentEditRequest)
            .filter(ResidentEditRequest.id == request_id, ResidentEditRequest.society_id == society_id)
            .first()
        )
        if not req:
            raise HTTPException(status_code=404, detail="Edit request not found")
        return req

    def approve(self, request_id: UUID, current_user: User) -> ResidentEditRequestOut:
        req = self._get_or_404(request_id, current_user.society_id)
        if req.status != ResidentEditRequestStatus.PENDING:
            raise HTTPException(status_code=409, detail="This request has already been reviewed")

        resident = self.db.get(Resident, req.resident_id)
        if not resident:
            raise HTTPException(status_code=404, detail="Resident not found")

        old_values = {k: getattr(resident, k) for k in req.changes if k in _EDITABLE_FIELDS}
        for field, value in req.changes.items():
            if field in _EDITABLE_FIELDS:
                setattr(resident, field, _coerce(field, value))

        req.status      = ResidentEditRequestStatus.APPROVED
        req.reviewed_by = current_user.id
        req.reviewed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(req)

        AuditService.log(
            db=self.db, action=AuditAction.UPDATE, module="resident", entity_id=str(resident.id),
            entity_type="Resident", user=current_user,
            old_values={k: _serialize(k, v) for k, v in old_values.items()},
            new_values=req.changes, notes=f"Approved self-service edit request {req.id}",
        )
        return self._enrich(req)

    def reject(self, request_id: UUID, reason: str, current_user: User) -> ResidentEditRequestOut:
        req = self._get_or_404(request_id, current_user.society_id)
        if req.status != ResidentEditRequestStatus.PENDING:
            raise HTTPException(status_code=409, detail="This request has already been reviewed")

        req.status           = ResidentEditRequestStatus.REJECTED
        req.reviewed_by      = current_user.id
        req.reviewed_at      = datetime.utcnow()
        req.rejection_reason = reason
        self.db.commit()
        self.db.refresh(req)

        AuditService.log(
            db=self.db, action=AuditAction.UPDATE, module="resident_edit_request",
            entity_id=str(req.id), entity_type="ResidentEditRequest", user=current_user,
            notes=f"Rejected: {reason}",
        )
        return self._enrich(req)
