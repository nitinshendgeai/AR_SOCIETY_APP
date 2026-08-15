from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.tenant import Tenant
from app.models.resident import Resident
from app.models.flat import Flat
from app.models.wing import Wing
from app.repositories.base import BaseRepository


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

    def list_scoped(
        self,
        society_id: Optional[UUID],
        flat_id: Optional[UUID] = None,
        is_active: Optional[bool] = True,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Tenant]:
        q = self.db.query(Tenant)
        if society_id is not None:
            q = q.join(Flat, Tenant.flat_id == Flat.id).join(Wing, Flat.wing_id == Wing.id) \
                 .filter(Wing.society_id == society_id)
        if flat_id is not None:
            q = q.filter(Tenant.flat_id == flat_id)
        if is_active is not None:
            q = q.filter(Tenant.is_active == is_active)
        if search:
            like = f"%{search}%"
            q = q.filter(
                (Tenant.full_name.ilike(like)) |
                (Tenant.phone.ilike(like)) |
                (Tenant.email.ilike(like))
            )
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
