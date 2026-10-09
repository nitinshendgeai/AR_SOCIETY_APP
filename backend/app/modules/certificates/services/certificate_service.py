from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.tenant_scope import assert_society_access
from app.models.flat import Flat
from app.models.notification import NotificationType
from app.models.resident import Resident
from app.models.tenant import Tenant
from app.models.user import User
from app.models.wing import Wing
from app.modules.certificates.models.certificates import (
    CERTIFICATE_KINDS, CERTIFICATE_STATUSES, TENANT_KINDS, CertificateRequest,
)
from app.modules.governance.services.governance_service import is_office
from app.services.notification_service import NotificationService

ZERO = Decimal("0")


def financial_year(d: date) -> str:
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{str(start + 1)[2:]}"


class CertificateService:
    def __init__(self, db: Session):
        self.db = db

    # ── Who is asking, and for which flat ────────────────────────────────────

    def _own_flat(self, user: User, society_id: UUID):
        """(flat, applicant name, is_tenant) for the person's own home, or None."""
        r = (self.db.query(Resident).join(Flat, Resident.flat_id == Flat.id).join(Wing, Flat.wing_id == Wing.id)
             .filter(Resident.user_id == user.id, Resident.is_active == True, Wing.society_id == society_id)  # noqa: E712
             .first())
        if r:
            return r.flat, r.full_name, False
        t = (self.db.query(Tenant).join(Flat, Tenant.flat_id == Flat.id).join(Wing, Flat.wing_id == Wing.id)
             .filter(Tenant.user_id == user.id, Tenant.is_active == True, Wing.society_id == society_id)  # noqa: E712
             .first())
        if t:
            return t.flat, t.full_name, True
        return None

    def _flat_in_society(self, flat_id: UUID, society_id: UUID) -> Flat:
        flat = (self.db.query(Flat).join(Wing, Flat.wing_id == Wing.id)
                .filter(Flat.id == flat_id, Wing.society_id == society_id).first())
        if flat is None:
            raise HTTPException(404, "Flat not found in this society")
        return flat

    @staticmethod
    def _owner_name(flat: Flat) -> str:
        active = [r for r in flat.residents if r.is_active]
        active.sort(key=lambda r: (not r.is_primary, r.resident_type.value not in ("owner", "co_owner")))
        return active[0].full_name if active else "The member"

    # ── Dues ─────────────────────────────────────────────────────────────────

    def dues_of(self, society_id: UUID, flat_id: UUID) -> Decimal:
        from app.modules.billing.services.defaulters import MemberDues
        rows = MemberDues(self.db).flats(society_id, flat_ids=[flat_id])
        return Decimal(sum((fd.total for fd in rows), ZERO))

    # ── Requests ─────────────────────────────────────────────────────────────

    def create(self, society_id: UUID, data: dict, user: User) -> CertificateRequest:
        assert_society_access(user, society_id)
        kind = data["kind"]
        if kind not in CERTIFICATE_KINDS:
            raise HTTPException(422, "Unknown certificate type")
        flat_id = data.get("flat_id")
        if is_office(user) and flat_id:
            flat = self._flat_in_society(flat_id, society_id)
            applicant = data.get("applicant_name") or self._owner_name(flat)
        else:
            own = self._own_flat(user, society_id)
            if own is None:
                raise HTTPException(422, "Your login is not linked to a flat, so a certificate cannot be requested. "
                                         "Please ask the society office.")
            flat, applicant, is_tenant = own
            if is_tenant and kind not in TENANT_KINDS:
                raise HTTPException(403, "A tenant can ask for an address certificate; NOCs are for the flat's owner")
        # One open request of a kind per flat is enough.
        if (self.db.query(CertificateRequest)
                .filter(CertificateRequest.flat_id == flat.id, CertificateRequest.kind == kind,
                        CertificateRequest.status == "pending").first()):
            raise HTTPException(409, "There is already a pending request of this kind for the flat")
        req = CertificateRequest(society_id=society_id, flat_id=flat.id, requested_by=user.id,
                                 applicant_name=applicant, kind=kind, purpose=data.get("purpose"),
                                 party_name=data.get("party_name"), status="pending")
        self.db.add(req)
        self.db.commit()
        self._tell_office(req, flat)
        return req

    def _tell_office(self, req: CertificateRequest, flat: Flat) -> None:
        title = CERTIFICATE_KINDS[req.kind][0]
        users = (self.db.query(User).filter(User.society_id == req.society_id, User.is_active == True).all())  # noqa: E712
        for u in users:
            if is_office(u) and u.id != req.requested_by:
                NotificationService.send(
                    db=self.db, user_id=u.id, title="Certificate request",
                    body=f"{req.applicant_name} ({flat.wing.name} {flat.flat_number}) has asked for: {title}.",
                    type=NotificationType.APPROVAL, module="certificates", entity_id=str(req.id),
                    action_url="/certificates", push=True)

    def list(self, society_id: UUID, user: User, status: Optional[str] = None) -> List[CertificateRequest]:
        assert_society_access(user, society_id)
        q = self.db.query(CertificateRequest).filter(CertificateRequest.society_id == society_id)
        if status:
            if status not in CERTIFICATE_STATUSES:
                raise HTTPException(422, "Unknown status")
            q = q.filter(CertificateRequest.status == status)
        if not is_office(user):
            q = q.filter(CertificateRequest.requested_by == user.id)
        return q.order_by(CertificateRequest.created_at.desc()).all()

    def get(self, request_id: UUID, user: User) -> CertificateRequest:
        req = self.db.query(CertificateRequest).filter(CertificateRequest.id == request_id).first()
        if req is None:
            raise HTTPException(404, "Request not found")
        assert_society_access(user, req.society_id)
        if not is_office(user) and req.requested_by != user.id:
            raise HTTPException(404, "Request not found")
        return req

    def decide(self, request_id: UUID, user: User, approve: bool, note: Optional[str],
               override_dues: bool) -> CertificateRequest:
        req = self.get(request_id, user)
        if req.status != "pending":
            raise HTTPException(409, f"This request is already {req.status}")
        today = date.today()
        if not approve:
            if not (note or "").strip():
                raise HTTPException(422, "Please give a reason for turning the request down")
            req.status, req.decision_note = "rejected", note.strip()
        else:
            _, prefix, needs_clear = CERTIFICATE_KINDS[req.kind]
            dues = self.dues_of(req.society_id, req.flat_id)
            if needs_clear and dues > 0 and not override_dues:
                raise HTTPException(409, f"The flat has Rs. {dues:,.2f} in dues. Collect it first, or approve anyway "
                                         f"if the committee has decided so.")
            req.dues_at_decision = dues
            req.status, req.decision_note = "approved", (note or "").strip() or None
            req.certificate_no = self._next_number(req.society_id, prefix, today)
        req.decided_by, req.decided_on = user.id, today
        try:
            self.db.commit()
        except IntegrityError:          # two approvals at once took the same number
            self.db.rollback()
            raise HTTPException(409, "Another certificate was issued at the same moment; please try again")
        self._tell_requester(req)
        return req

    def _next_number(self, society_id: UUID, prefix: str, today: date) -> str:
        stem = f"{prefix}/{financial_year(today)}/"
        taken = (self.db.query(CertificateRequest.certificate_no)
                 .filter(CertificateRequest.society_id == society_id,
                         CertificateRequest.certificate_no.like(f"{stem}%")).all())
        top = max((int(n[0].rsplit("/", 1)[1]) for n in taken), default=0)
        return f"{stem}{top + 1:04d}"

    def _tell_requester(self, req: CertificateRequest) -> None:
        if req.requested_by is None:
            return
        title = CERTIFICATE_KINDS[req.kind][0]
        if req.status == "approved":
            body = f"Your request is approved: {title}. Certificate no. {req.certificate_no}. You can download it now."
        else:
            body = f"Your request for {title} was not approved. Reason: {req.decision_note}"
        NotificationService.send(db=self.db, user_id=req.requested_by, title="Certificate request", body=body,
                                 type=NotificationType.INFO, module="certificates", entity_id=str(req.id),
                                 action_url="/certificates", push=True)

    def cancel(self, request_id: UUID, user: User) -> CertificateRequest:
        req = self.get(request_id, user)
        if req.requested_by != user.id and not is_office(user):
            raise HTTPException(403, "Only the person who asked can withdraw the request")
        if req.status != "pending":
            raise HTTPException(409, f"This request is already {req.status}")
        req.status = "cancelled"
        self.db.commit()
        return req

    # ── Output ───────────────────────────────────────────────────────────────

    def out(self, req: CertificateRequest) -> dict:
        flat = req.flat if hasattr(req, "flat") else None
        flat = flat or self.db.query(Flat).filter(Flat.id == req.flat_id).first()
        return {
            "id": str(req.id), "society_id": str(req.society_id), "flat_id": str(req.flat_id),
            "flat": f"{flat.wing.name} {flat.flat_number}" if flat and flat.wing else None,
            "applicant_name": req.applicant_name, "kind": req.kind, "title": CERTIFICATE_KINDS[req.kind][0],
            "purpose": req.purpose, "party_name": req.party_name, "status": req.status,
            "decided_on": req.decided_on.isoformat() if req.decided_on else None,
            "decision_note": req.decision_note, "certificate_no": req.certificate_no,
            "dues_at_decision": float(req.dues_at_decision) if req.dues_at_decision is not None else None,
            "created_at": req.created_at,
        }
