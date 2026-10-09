from datetime import datetime

from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from typing import List

from app.models.wing import Wing
from app.models.user import User
from app.repositories.wing_repo import WingRepository
from app.repositories.society_repo import SocietyRepository
from app.schemas.wing import WingCreate, WingUpdate, WingOut
from app.core.tenant_scope import assert_society_access, resolve_create_society_id


def _enrich(wing: Wing) -> WingOut:
    """Attach computed stats to a WingOut instance."""
    out = WingOut.model_validate(wing)
    active_flats  = [f for f in wing.flats  if f.is_active]
    active_floors = [f for f in wing.floors if f.is_active] if hasattr(wing, 'floors') else []
    out.flat_count  = len(active_flats)
    out.floor_count = len(active_floors)
    return out


from app.utils.auto_code import short_code


class WingService:
    def __init__(self, db: Session):
        self.repo         = WingRepository(db)
        self.society_repo = SocietyRepository(db)

    def create(self, data: WingCreate, current_user: User) -> WingOut:
        society_id = resolve_create_society_id(current_user, data.society_id)
        society = self.society_repo.get(society_id)
        if not society:
            raise HTTPException(status_code=404, detail="Society not found")
        self.repo.assert_unique_name(society_id, data.name)
        if data.code:
            self.repo.assert_unique_code(society_id, data.code)
        payload = data.model_dump()
        if not (payload.get("code") or "").strip():
            # No code given: the app makes one from the name ("A Wing" -> "A").
            taken = [w.code for w in self.repo.get_by_society(society_id, True)]
            payload["code"] = short_code(data.name, taken)
        payload["society_id"] = society_id
        wing = Wing(**payload)
        created = self.repo.create(wing)
        return _enrich(created)

    def get_or_404(self, id: UUID, current_user: User) -> WingOut:
        obj = self.repo.get_kept(id, society_id=current_user.society_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Wing not found")
        return _enrich(obj)

    def list(self, current_user: User, skip: int = 0, limit: int = 50) -> List[WingOut]:
        return [_enrich(w) for w in self.repo.get_all(skip, limit, society_id=current_user.society_id)]

    def list_by_society(self, society_id: UUID, current_user: User,
                        include_inactive: bool = False) -> List[WingOut]:
        assert_society_access(current_user, society_id)
        return [_enrich(w) for w in self.repo.get_by_society(society_id, include_inactive)]

    def update(self, id: UUID, data: WingUpdate, current_user: User) -> WingOut:
        wing = self.repo.get_kept(id, society_id=current_user.society_id)
        if not wing:
            raise HTTPException(status_code=404, detail="Wing not found")
        patch = data.model_dump(exclude_none=True)
        if "name" in patch and patch["name"] != wing.name:
            self.repo.assert_unique_name(wing.society_id, patch["name"], exclude_id=id)
        if "code" in patch and patch["code"] != wing.code:
            self.repo.assert_unique_code(wing.society_id, patch["code"], exclude_id=id)
        return _enrich(self.repo.update(wing, patch))

    def toggle_active(self, id: UUID, activate: bool, current_user: User) -> WingOut:
        # A deactivated wing is still there to be found (and switched on again)
        wing = self.repo.get_kept(id, society_id=current_user.society_id)
        if not wing:
            raise HTTPException(status_code=404, detail="Wing not found")
        if activate and not wing.is_active:
            # Its name or code may have been taken while it was switched off
            self.repo.assert_unique_name(wing.society_id, wing.name, exclude_id=id)
            if wing.code:
                self.repo.assert_unique_code(wing.society_id, wing.code, exclude_id=id)
        wing.is_active = activate
        self.repo.db.commit()
        self.repo.db.refresh(wing)
        return _enrich(wing)

    def delete(self, id: UUID, current_user: User) -> None:
        """Remove a wing that has no flats left; its (empty) floors go with
        it. A wing with flats is refused — they hold residents and dues."""
        wing = self.repo.get_kept(id, society_id=current_user.society_id)
        if not wing:
            raise HTTPException(status_code=404, detail="Wing not found")
        flats = [f for f in wing.flats if f.is_active]
        if flats:
            raise HTTPException(
                409, f"Wing '{wing.name}' still has {len(flats)} flat{'s' if len(flats) != 1 else ''}. "
                     f"Delete or move them first.")
        for floor in wing.floors:
            floor.is_active = False
        wing.deleted_at = datetime.utcnow()
        self.repo.soft_delete(wing)
