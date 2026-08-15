from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from typing import List, Optional

from app.models.flat import Flat
from app.models.user import User
from app.repositories.flat_repo import FlatRepository
from app.repositories.wing_repo import WingRepository
from app.schemas.flat import FlatCreate, FlatUpdate, FlatOut
from app.core.tenant_scope import assert_society_access


def _enrich(flat: Flat) -> FlatOut:
    out = FlatOut.model_validate(flat)
    if hasattr(flat, 'wing') and flat.wing:
        out.wing_name = flat.wing.name
    return out


class FlatService:
    def __init__(self, db: Session):
        self.repo      = FlatRepository(db)
        self.wing_repo = WingRepository(db)

    def create(self, data: FlatCreate, current_user: User) -> FlatOut:
        # Flat has no society_id of its own — scoping is entirely a function
        # of whether the target wing belongs to the caller's own society.
        wing = self.wing_repo.get(data.wing_id, society_id=current_user.society_id)
        if not wing:
            raise HTTPException(status_code=404, detail="Wing not found")
        self.repo.assert_unique_flat_number(data.wing_id, data.flat_number)
        flat = Flat(**data.model_dump())
        return _enrich(self.repo.create(flat))

    def get_or_404(self, id: UUID, current_user: User) -> FlatOut:
        obj = self.repo.get(id, society_id=current_user.society_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Flat not found")
        return _enrich(obj)

    def list(self, current_user: User, skip: int = 0, limit: int = 50) -> List[FlatOut]:
        return [_enrich(f) for f in self.repo.get_all(skip, limit, society_id=current_user.society_id)]

    def list_by_wing(self, wing_id: UUID, current_user: User) -> List[FlatOut]:
        wing = self.wing_repo.get(wing_id, society_id=current_user.society_id)
        if not wing:
            raise HTTPException(status_code=404, detail="Wing not found")
        return [_enrich(f) for f in self.repo.get_by_wing(wing_id)]

    def list_by_society(self, society_id: UUID, current_user: User) -> List[FlatOut]:
        assert_society_access(current_user, society_id)
        return [_enrich(f) for f in self.repo.get_by_society(society_id)]

    def update(self, id: UUID, data: FlatUpdate, current_user: User) -> FlatOut:
        flat = self.repo.get(id, society_id=current_user.society_id)
        if not flat:
            raise HTTPException(status_code=404, detail="Flat not found")
        patch = data.model_dump(exclude_none=True)
        if "flat_number" in patch and patch["flat_number"] != flat.flat_number:
            self.repo.assert_unique_flat_number(
                flat.wing_id, patch["flat_number"], exclude_id=id
            )
        return _enrich(self.repo.update(flat, patch))

    def delete(self, id: UUID, current_user: User) -> None:
        flat = self.repo.get(id, society_id=current_user.society_id)
        if not flat:
            raise HTTPException(status_code=404, detail="Flat not found")
        self.repo.soft_delete(flat)
