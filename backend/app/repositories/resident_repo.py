from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.resident import Resident, ResidentType
from app.models.tenant import Tenant
from app.models.flat import Flat
from app.models.wing import Wing
from app.repositories.base import BaseRepository


class ResidentRepository(BaseRepository[Resident]):
    def __init__(self, db: Session):
        super().__init__(Resident, db)

    # Resident has no society_id column of its own (Phase M1.1 §5 — deliberately
    # not adding one; it's a redundant denormalization of flat.wing.society_id).
    # Scoping has to join through Flat -> Wing, exactly like FlatRepository does
    # for the same reason — override rather than rely on BaseRepository's
    # generic _scope(), which no-ops for models without a society_id attribute.

    def get(self, id, society_id=None) -> Optional[Resident]:          # type: ignore[override]
        q = self.db.query(Resident).filter(Resident.id == id, Resident.is_active == True)
        if society_id is not None:
            q = q.join(Flat, Resident.flat_id == Flat.id).join(Wing, Flat.wing_id == Wing.id) \
                 .filter(Wing.society_id == society_id)
        return q.first()

    def get_any(self, id, society_id=None) -> Optional[Resident]:
        """Like get(), but WITHOUT the is_active filter — a resident who has
        moved out (is_active=False, set by OccupancyService.resident_move_out)
        must still be viewable (Phase M1.4-R: found live that GET
        /residents/{id} 404'd for every moved-out resident, making their
        detail page — and therefore their occupancy history — completely
        unreachable). Society scoping is enforced identically to get()."""
        q = self.db.query(Resident).filter(Resident.id == id)
        if society_id is not None:
            q = q.join(Flat, Resident.flat_id == Flat.id).join(Wing, Flat.wing_id == Wing.id) \
                 .filter(Wing.society_id == society_id)
        return q.first()

    def list_scoped(
        self,
        society_id: Optional[UUID],
        flat_id: Optional[UUID] = None,
        resident_type: Optional[ResidentType] = None,
        is_active: Optional[bool] = True,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Resident]:
        q = self.db.query(Resident)
        if society_id is not None:
            q = q.join(Flat, Resident.flat_id == Flat.id).join(Wing, Flat.wing_id == Wing.id) \
                 .filter(Wing.society_id == society_id)
        if flat_id is not None:
            q = q.filter(Resident.flat_id == flat_id)
        if resident_type is not None:
            q = q.filter(Resident.resident_type == resident_type)
        if is_active is not None:
            q = q.filter(Resident.is_active == is_active)
        if search:
            like = f"%{search}%"
            q = q.filter(
                (Resident.full_name.ilike(like)) |
                (Resident.phone.ilike(like)) |
                (Resident.email.ilike(like))
            )
        return q.order_by(Resident.full_name).offset(skip).limit(limit).all()

    def count_family_members(self, flat_id: UUID) -> int:
        """Active FAMILY/DEPENDENT residents on a flat — the authoritative,
        computed value for ResidentOut.family_member_count (Phase M1.1 §6;
        the physical residents.family_member_count column is legacy/unused
        and never written to)."""
        return self.db.query(Resident).filter(
            Resident.flat_id == flat_id,
            Resident.is_active == True,
            Resident.resident_type.in_([ResidentType.FAMILY, ResidentType.DEPENDENT]),
        ).count()

    def has_active_primary(self, flat_id: UUID, exclude_id: Optional[UUID] = None) -> bool:
        """Friendly pre-check before insert/update, ahead of the DB partial
        unique index (uq_resident_primary_per_flat) — lets the service raise
        a clean 409 instead of a raw IntegrityError."""
        q = self.db.query(Resident).filter(
            Resident.flat_id == flat_id,
            Resident.is_primary == True,
            Resident.is_active == True,
        )
        if exclude_id is not None:
            q = q.filter(Resident.id != exclude_id)
        return self.db.query(q.exists()).scalar()

    def find_duplicate_warnings(
        self,
        society_id: Optional[UUID],
        phone: Optional[str] = None,
        email: Optional[str] = None,
        id_proof_type: Optional[str] = None,
        id_proof_number: Optional[str] = None,
        exclude_resident_id: Optional[UUID] = None,
    ) -> List[str]:
        """Non-blocking duplicate detection across active Residents AND
        Tenants in the same society (Phase M1.1 §10 — phone/email/identity
        collisions are a warning, never a hard constraint). Tenant is
        queried directly here, the same way occupancy_service.py already
        queries Tenant for conflict-checking elsewhere in this codebase —
        this does not require a TenantService/TenantRepository to exist."""
        warnings: List[str] = []
        if not any([phone, email, (id_proof_type and id_proof_number)]):
            return warnings

        def _scope(q, model):
            if society_id is not None:
                q = q.join(Flat, model.flat_id == Flat.id).join(Wing, Flat.wing_id == Wing.id) \
                     .filter(Wing.society_id == society_id)
            return q.filter(model.is_active == True)

        if phone:
            rq = _scope(self.db.query(Resident), Resident).filter(Resident.phone == phone)
            if exclude_resident_id is not None:
                rq = rq.filter(Resident.id != exclude_resident_id)
            if self.db.query(rq.exists()).scalar():
                warnings.append(f"Another active resident in this society already uses phone {phone}")
            tq = _scope(self.db.query(Tenant), Tenant).filter(Tenant.phone == phone)
            if self.db.query(tq.exists()).scalar():
                warnings.append(f"An active tenant in this society already uses phone {phone}")

        if email:
            rq = _scope(self.db.query(Resident), Resident).filter(Resident.email == email)
            if exclude_resident_id is not None:
                rq = rq.filter(Resident.id != exclude_resident_id)
            if self.db.query(rq.exists()).scalar():
                warnings.append(f"Another active resident in this society already uses email {email}")
            tq = _scope(self.db.query(Tenant), Tenant).filter(Tenant.email == email)
            if self.db.query(tq.exists()).scalar():
                warnings.append(f"An active tenant in this society already uses email {email}")

        if id_proof_type and id_proof_number:
            rq = _scope(self.db.query(Resident), Resident).filter(
                Resident.id_proof_type == id_proof_type,
                Resident.id_proof_number == id_proof_number,
            )
            if exclude_resident_id is not None:
                rq = rq.filter(Resident.id != exclude_resident_id)
            if self.db.query(rq.exists()).scalar():
                warnings.append("Another active resident in this society has the same ID proof on file")
            tq = _scope(self.db.query(Tenant), Tenant).filter(
                Tenant.id_proof_type == id_proof_type,
                Tenant.id_proof_number == id_proof_number,
            )
            if self.db.query(tq.exists()).scalar():
                warnings.append("An active tenant in this society has the same ID proof on file")

        return warnings
