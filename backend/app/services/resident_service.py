from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.resident import Resident, ResidentType
from app.models.user import User
from app.models.audit_log import AuditAction
from app.repositories.resident_repo import ResidentRepository
from app.repositories.flat_repo import FlatRepository
from app.schemas.resident import ResidentCreate, ResidentUpdate, ResidentOut, ResidentCreateOut
from app.services.audit_service import AuditService
from app.services.occupancy_service import OccupancyService
from app.services.user_provisioning import provision_login_by_phone

_PRIMARY_ALLOWED_TYPES = (ResidentType.OWNER, ResidentType.CO_OWNER)


class ResidentService:
    def __init__(self, db: Session):
        self.db         = db
        self.repo       = ResidentRepository(db)
        self.flat_repo  = FlatRepository(db)

    def _enrich(self, resident: Resident) -> ResidentOut:
        out = ResidentOut.model_validate(resident)
        out.family_member_count = self.repo.count_family_members(resident.flat_id)
        return out

    # ── Create ───────────────────────────────────────────────────────────────

    def create(self, data: ResidentCreate, current_user: User) -> ResidentCreateOut:
        # 1-3: flat must exist and belong to the caller's own society (or,
        # for a platform admin, exist at all) — this is what confines the
        # whole operation to the right tenant, since Resident itself has no
        # society_id to check.
        flat = self.flat_repo.get(data.flat_id, society_id=current_user.society_id)
        if not flat:
            raise HTTPException(status_code=404, detail="Flat not found")

        # 5: primary/type is already validated at the schema level
        # (ResidentCreate.check_primary_type); this is the DB-aware half —
        # give a clean 409 instead of letting the partial unique index
        # surface as a raw IntegrityError.
        if data.is_primary and self.repo.has_active_primary(data.flat_id):
            raise HTTPException(
                status_code=409,
                detail="This flat already has an active primary resident",
            )

        # 6-7: duplicate phone/email/ID — warning only, never blocking.
        warnings = self.repo.find_duplicate_warnings(
            society_id=current_user.society_id,
            phone=data.phone, email=data.email,
            id_proof_type=data.id_proof_type, id_proof_number=data.id_proof_number,
        )

        payload = data.model_dump(exclude={"move_in_date"})
        resident = Resident(**payload)
        created = self.repo.create(resident)

        AuditService.log(
            db=self.db, action=AuditAction.CREATE, module="resident",
            entity_id=str(created.id), entity_type="Resident", user=current_user,
            new_values={"full_name": created.full_name, "resident_type": created.resident_type.value,
                        "flat_id": str(created.flat_id), "is_primary": created.is_primary},
        )

        # 9: reuse the already-fixed, already-tested OccupancyService rather
        # than re-implementing move-in (status update, OccupancyLog entry,
        # its own audit call) here.
        if data.move_in_date is not None:
            OccupancyService(self.db).resident_move_in(
                data.flat_id, created.id, data.move_in_date, current_user,
            )
            self.db.refresh(created)

        # 10: auto-provision app login by mobile number, unless the caller
        # already linked an existing account via ResidentCreate.user_id.
        # Inserted at the front of `warnings` (mobile UI currently only
        # surfaces warnings[0] in its post-save snackbar) since this message
        # carries the one-time initial password — it must never be
        # eclipsed by an unrelated duplicate-phone/email notice.
        if created.user_id is None:
            if created.phone:
                user, message = provision_login_by_phone(
                    self.db, society_id=current_user.society_id,
                    phone=created.phone, full_name=created.full_name,
                    role_name="Resident",
                )
                created.user_id = user.id
                self.db.commit()
                self.db.refresh(created)
                warnings.insert(0, message)
            else:
                warnings.insert(0,
                    "No mobile number provided — a login account was not "
                    "created for this resident. Add a mobile number and "
                    "re-save to enable app login."
                )

        out = ResidentCreateOut.model_validate(created)
        out.family_member_count = self.repo.count_family_members(created.flat_id)
        out.warnings = warnings
        return out

    # ── Read ─────────────────────────────────────────────────────────────────

    def get_me(self, current_user: User) -> ResidentOut:
        resident = (
            self.db.query(Resident)
            .filter(Resident.user_id == current_user.id, Resident.is_active == True)  # noqa: E712
            .first()
        )
        if not resident:
            raise HTTPException(status_code=404, detail="No resident profile linked to this account")
        return self._enrich(resident)

    def get_or_404(self, id: UUID, current_user: User) -> ResidentOut:
        # get_any(), not get(): a moved-out resident (is_active=False) must
        # still be viewable — their detail page is exactly where occupancy
        # history is reviewed. Found live in M1.4-R Postgres E2E testing;
        # write access (update(), below) intentionally stays active-only.
        resident = self.repo.get_any(id, society_id=current_user.society_id)
        if not resident:
            raise HTTPException(status_code=404, detail="Resident not found")
        return self._enrich(resident)

    def list(
        self,
        current_user: User,
        flat_id: Optional[UUID] = None,
        resident_type: Optional[ResidentType] = None,
        is_active: Optional[bool] = True,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ResidentOut]:
        if flat_id is not None:
            # Confirm the flat itself is in-scope before filtering by it —
            # otherwise flat_id becomes an unscoped side-channel lookup.
            flat = self.flat_repo.get(flat_id, society_id=current_user.society_id)
            if not flat:
                raise HTTPException(status_code=404, detail="Flat not found")
        residents = self.repo.list_scoped(
            society_id=current_user.society_id, flat_id=flat_id,
            resident_type=resident_type, is_active=is_active, search=search,
            skip=skip, limit=limit,
        )
        return [self._enrich(r) for r in residents]

    # ── Update ───────────────────────────────────────────────────────────────

    def update(self, id: UUID, data: ResidentUpdate, current_user: User) -> ResidentOut:
        resident = self.repo.get(id, society_id=current_user.society_id)
        if not resident:
            raise HTTPException(status_code=404, detail="Resident not found")

        patch = data.model_dump(exclude_none=True)

        # Authoritative primary/type consistency check — merges the patch
        # against the resident's CURRENT row, since a PATCH may only touch
        # one of the two fields (e.g. flipping is_primary=true on an
        # existing FAMILY-typed row without resending resident_type).
        effective_is_primary = patch.get("is_primary", resident.is_primary)
        effective_type       = patch.get("resident_type", resident.resident_type)
        if effective_is_primary and effective_type not in _PRIMARY_ALLOWED_TYPES:
            raise HTTPException(
                status_code=422,
                detail="A primary resident must be OWNER or CO_OWNER",
            )
        if effective_is_primary and not resident.is_primary:
            # Newly becoming primary — check for a conflicting active primary.
            if self.repo.has_active_primary(resident.flat_id, exclude_id=resident.id):
                raise HTTPException(
                    status_code=409,
                    detail="This flat already has an active primary resident",
                )

        old_values = {k: getattr(resident, k) for k in patch}
        updated = self.repo.update(resident, patch)

        AuditService.log(
            db=self.db, action=AuditAction.UPDATE, module="resident",
            entity_id=str(updated.id), entity_type="Resident", user=current_user,
            old_values={k: (v.value if hasattr(v, "value") else v) for k, v in old_values.items()},
            new_values={k: (v.value if hasattr(v, "value") else v) for k, v in patch.items()},
        )
        return self._enrich(updated)
