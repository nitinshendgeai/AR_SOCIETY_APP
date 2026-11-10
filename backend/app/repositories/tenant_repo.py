from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.tenant import PoliceVerificationStatus, Tenant
from app.models.resident import Resident
from app.models.flat import Flat
from app.models.wing import Wing
from app.repositories.base import BaseRepository


# An agreement ending within this many days is "expiring" (the tenant list shows it in amber).
AGREEMENT_EXPIRING_DAYS = 30


class TenantRepository(BaseRepository[Tenant]):
    def __init__(self, db: Session):
        super().__init__(Tenant, db)

    # Tenant has no society_id column of its own (Phase M1.1 §7 — same
    # reasoning as Resident: it would be a redundant denormalization of
    # flat.wing.society_id). Override get()/get_all() with the same
    # Flat -> Wing join used by ResidentRepository/FlatRepository.

    def get(self, id, society_id=None) -> Optional[Tenant]:              # type: ignore[override]
        q = self.db.query(Tenant).filter(Tenant.id == id, Tenant.is_active == True)
        if society_id is not None:
            q = q.join(Flat, Tenant.flat_id == Flat.id).join(Wing, Flat.wing_id == Wing.id) \
                 .filter(Wing.society_id == society_id)
        return q.first()

    def get_any(self, id, society_id=None) -> Optional[Tenant]:
        """Like get(), but WITHOUT the is_active filter — a tenant who has
        moved out (is_active=False, set by OccupancyService.tenant_move_out)
        must still be look-up-able by history/audit-style reads (Phase
        M1.4-R: GET /tenants/{id}/agreements). Society scoping is enforced
        identically to get()."""
        q = self.db.query(Tenant).filter(Tenant.id == id)
        if society_id is not None:
            q = q.join(Flat, Tenant.flat_id == Flat.id).join(Wing, Flat.wing_id == Wing.id) \
                 .filter(Wing.society_id == society_id)
        return q.first()

    @staticmethod
    def _apply_filters(q, society_id, flat_id, is_active, search, search_contacts, wing_id, moved_in, agreement,
                       police, kyc_verified):
        """The filters of the tenant list. Shared by the list and its count so the two can never disagree."""
        if society_id is not None or wing_id is not None:
            q = q.join(Flat, Tenant.flat_id == Flat.id).join(Wing, Flat.wing_id == Wing.id)
            if society_id is not None:
                q = q.filter(Wing.society_id == society_id)
            if wing_id is not None:
                q = q.filter(Flat.wing_id == wing_id)
        if flat_id is not None:
            q = q.filter(Tenant.flat_id == flat_id)
        if is_active is not None:
            q = q.filter(Tenant.is_active == is_active)
        if moved_in is True:                    # living there now: a move-in date and no move-out
            q = q.filter(Tenant.move_in_date.isnot(None), Tenant.move_out_date.is_(None))
        elif moved_in is False:                 # on record, but no move-in date yet
            q = q.filter(Tenant.move_in_date.is_(None))
        if agreement:
            # The same four states the tenant list shows by the agreement's end date (red once past, amber in the last
            # 30 days): running, expiring (within 30 days), expired, or no end date on record.
            end = func.coalesce(Tenant.agreement_end_date, Tenant.lease_end_date)
            today = date.today()
            q = q.filter({
                "none": end.is_(None),
                "expired": end < today,
                "expiring": (end >= today) & (end <= today + timedelta(days=AGREEMENT_EXPIRING_DAYS)),
                "running": end > today + timedelta(days=AGREEMENT_EXPIRING_DAYS),
            }[agreement])
        if police:
            q = q.filter(Tenant.police_verification_status == PoliceVerificationStatus(police))
        if kyc_verified is not None:
            q = q.filter(Tenant.kyc_verified == kyc_verified)
        if search:
            like = f"%{search}%"
            if search_contacts:
                q = q.filter(
                    (Tenant.full_name.ilike(like)) |
                    (Tenant.phone.ilike(like)) |
                    (Tenant.email.ilike(like))
                )
            else:   # a member may search names only
                q = q.filter(Tenant.full_name.ilike(like))
        return q

    def count_scoped(
        self,
        society_id: Optional[UUID],
        flat_id: Optional[UUID] = None,
        is_active: Optional[bool] = True,
        search: Optional[str] = None,
        search_contacts: bool = True,
        wing_id: Optional[UUID] = None,
        moved_in: Optional[bool] = None,
        agreement: Optional[str] = None,
        police: Optional[str] = None,
        kyc_verified: Optional[bool] = None,
    ) -> int:
        """How many tenants list_scoped would return with no paging."""
        return self._apply_filters(self.db.query(Tenant), society_id, flat_id, is_active, search, search_contacts,
                                   wing_id, moved_in, agreement, police, kyc_verified).count()

    def list_scoped(
        self,
        society_id: Optional[UUID],
        flat_id: Optional[UUID] = None,
        is_active: Optional[bool] = True,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
        search_contacts: bool = True,
        wing_id: Optional[UUID] = None,
        moved_in: Optional[bool] = None,
        agreement: Optional[str] = None,
        police: Optional[str] = None,
        kyc_verified: Optional[bool] = None,
    ) -> List[Tenant]:
        q = self._apply_filters(self.db.query(Tenant), society_id, flat_id, is_active, search, search_contacts,
                                wing_id, moved_in, agreement, police, kyc_verified)
        return q.order_by(Tenant.full_name).offset(skip).limit(limit).all()

    def find_duplicate_warnings(
        self,
        society_id: Optional[UUID],
        phone: Optional[str] = None,
        email: Optional[str] = None,
        id_proof_type: Optional[str] = None,
        id_proof_number: Optional[str] = None,
        exclude_tenant_id: Optional[UUID] = None,
    ) -> List[str]:
        """Mirrors ResidentRepository.find_duplicate_warnings (Phase M1.2
        §10) from the Tenant side — checks both active Tenants and active
        Residents in the same society. Warning only, never blocking."""
        warnings: List[str] = []
        if not any([phone, email, (id_proof_type and id_proof_number)]):
            return warnings

        def _scope(q, model):
            if society_id is not None:
                q = q.join(Flat, model.flat_id == Flat.id).join(Wing, Flat.wing_id == Wing.id) \
                     .filter(Wing.society_id == society_id)
            return q.filter(model.is_active == True)

        if phone:
            tq = _scope(self.db.query(Tenant), Tenant).filter(Tenant.phone == phone)
            if exclude_tenant_id is not None:
                tq = tq.filter(Tenant.id != exclude_tenant_id)
            if self.db.query(tq.exists()).scalar():
                warnings.append(f"Another active tenant in this society already uses phone {phone}")
            rq = _scope(self.db.query(Resident), Resident).filter(Resident.phone == phone)
            if self.db.query(rq.exists()).scalar():
                warnings.append(f"An active resident in this society already uses phone {phone}")

        if email:
            tq = _scope(self.db.query(Tenant), Tenant).filter(Tenant.email == email)
            if exclude_tenant_id is not None:
                tq = tq.filter(Tenant.id != exclude_tenant_id)
            if self.db.query(tq.exists()).scalar():
                warnings.append(f"Another active tenant in this society already uses email {email}")
            rq = _scope(self.db.query(Resident), Resident).filter(Resident.email == email)
            if self.db.query(rq.exists()).scalar():
                warnings.append(f"An active resident in this society already uses email {email}")

        if id_proof_type and id_proof_number:
            tq = _scope(self.db.query(Tenant), Tenant).filter(
                Tenant.id_proof_type == id_proof_type,
                Tenant.id_proof_number == id_proof_number,
            )
            if exclude_tenant_id is not None:
                tq = tq.filter(Tenant.id != exclude_tenant_id)
            if self.db.query(tq.exists()).scalar():
                warnings.append("Another active tenant in this society has the same ID proof on file")
            rq = _scope(self.db.query(Resident), Resident).filter(
                Resident.id_proof_type == id_proof_type,
                Resident.id_proof_number == id_proof_number,
            )
            if self.db.query(rq.exists()).scalar():
                warnings.append("An active resident in this society has the same ID proof on file")

        return warnings
