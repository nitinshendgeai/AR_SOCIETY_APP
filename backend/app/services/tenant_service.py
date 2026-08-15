from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from datetime import date
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.agreement_tracker import AgreementTracker, AgreementStatus
from app.models.user import User
from app.models.audit_log import AuditAction
from app.repositories.tenant_repo import TenantRepository
from app.repositories.flat_repo import FlatRepository
from app.schemas.tenant import TenantCreate, TenantUpdate, TenantOut, TenantCreateOut
from app.services.audit_service import AuditService
from app.services.occupancy_service import OccupancyService


class TenantService:
    def __init__(self, db: Session):
        self.db        = db
        self.repo       = TenantRepository(db)
        self.flat_repo  = FlatRepository(db)

    def _active_agreement_id(self, tenant_id: UUID) -> Optional[UUID]:
        agr = self.db.query(AgreementTracker).filter(
            AgreementTracker.tenant_id == tenant_id,
            AgreementTracker.status == AgreementStatus.ACTIVE,
        ).first()
        return agr.id if agr else None

    def _enrich(self, tenant: Tenant) -> TenantOut:
        out = TenantOut.model_validate(tenant)
        out.active_agreement_id = self._active_agreement_id(tenant.id)
        return out

    # ── Create ───────────────────────────────────────────────────────────────

    def create(self, data: TenantCreate, current_user: User) -> TenantCreateOut:
        flat = self.flat_repo.get(data.flat_id, society_id=current_user.society_id)
        if not flat:
            raise HTTPException(status_code=404, detail="Flat not found")

        warnings = self.repo.find_duplicate_warnings(
            society_id=current_user.society_id,
            phone=data.phone, email=data.email,
            id_proof_type=data.id_proof_type, id_proof_number=data.id_proof_number,
        )

        payload = data.model_dump(exclude={"move_in_date"})
        tenant = Tenant(**payload)
        created = self.repo.create(tenant)

        AuditService.log(
            db=self.db, action=AuditAction.CREATE, module="tenant",
            entity_id=str(created.id), entity_type="Tenant", user=current_user,
            new_values={"full_name": created.full_name, "flat_id": str(created.flat_id)},
        )

        # Reuse the already-fixed, already-tested OccupancyService rather
        # than re-implementing move-in (status update, OccupancyLog entry,
        # AgreementTracker creation, its own audit calls) here — mirrors
        # ResidentService.create() (Phase M1.2).
        if data.move_in_date is not None:
            OccupancyService(self.db).tenant_move_in(
                data.flat_id, created.id, data.move_in_date, current_user,
                create_agreement=bool(data.agreement_start_date and data.agreement_end_date),
            )
            self.db.refresh(created)

        out = TenantCreateOut.model_validate(created)
        out.active_agreement_id = self._active_agreement_id(created.id)
        out.warnings = warnings
        return out

    # ── Read ─────────────────────────────────────────────────────────────────

    def get_or_404(self, id: UUID, current_user: User) -> TenantOut:
        tenant = self.repo.get(id, society_id=current_user.society_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return self._enrich(tenant)

    def list(
        self,
        current_user: User,
        flat_id: Optional[UUID] = None,
        is_active: Optional[bool] = True,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[TenantOut]:
        if flat_id is not None:
            flat = self.flat_repo.get(flat_id, society_id=current_user.society_id)
            if not flat:
                raise HTTPException(status_code=404, detail="Flat not found")
        tenants = self.repo.list_scoped(
            society_id=current_user.society_id, flat_id=flat_id,
            is_active=is_active, search=search, skip=skip, limit=limit,
        )
        return [self._enrich(t) for t in tenants]

    # ── Update ───────────────────────────────────────────────────────────────

    def update(self, id: UUID, data: TenantUpdate, current_user: User) -> TenantOut:
        tenant = self.repo.get(id, society_id=current_user.society_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        patch = data.model_dump(exclude_none=True)
        old_values = {k: getattr(tenant, k) for k in patch}
        updated = self.repo.update(tenant, patch)

        AuditService.log(
            db=self.db, action=AuditAction.UPDATE, module="tenant",
            entity_id=str(updated.id), entity_type="Tenant", user=current_user,
            old_values={k: (v.value if hasattr(v, "value") else v) for k, v in old_values.items()},
            new_values={k: (v.value if hasattr(v, "value") else v) for k, v in patch.items()},
        )
        return self._enrich(updated)

    # ── Agreement renewal ────────────────────────────────────────────────────

    def renew_agreement(self, id: UUID, start_date: date, end_date: date, current_user: User,
                         monthly_rent: Decimal = None, security_deposit: Decimal = None,
                         document_url: str = None) -> AgreementTracker:
        # Society scoping is enforced inside OccupancyService.renew_agreement
        # itself (via the tenant's flat), so this is a thin passthrough —
        # OccupancyService remains the single owner of AgreementTracker
        # mutations, matching tenant_move_in/tenant_move_out.
        return OccupancyService(self.db).renew_agreement(
            id, start_date, end_date, current_user,
            monthly_rent=monthly_rent, security_deposit=security_deposit,
            document_url=document_url,
        )
