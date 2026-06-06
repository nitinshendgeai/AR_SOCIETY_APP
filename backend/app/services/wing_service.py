from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from typing import List

from app.models.wing import Wing
from app.repositories.wing_repo import WingRepository
from app.repositories.society_repo import SocietyRepository
from app.schemas.wing import WingCreate, WingUpdate, WingOut


def _enrich(wing: Wing) -> WingOut:
    """Attach computed stats to a WingOut instance."""
    out = WingOut.model_validate(wing)
    active_flats  = [f for f in wing.flats  if f.is_active]
    active_floors = [f for f in wing.floors if f.is_active] if hasattr(wing, 'floors') else []
    out.flat_count  = len(active_flats)
    out.floor_count = len(active_floors)
    return out


class WingService:
    def __init__(self, db: Session):
        self.repo         = WingRepository(db)
        self.society_repo = SocietyRepository(db)

    def create(self, data: WingCreate) -> WingOut:
        society = self.society_repo.get(data.society_id)
        if not society:
            raise HTTPException(status_code=404, detail="Society not found")
        self.repo.assert_unique_name(data.society_id, data.name)
        if data.code:
            self.repo.assert_unique_code(data.society_id, data.code)
        wing = Wing(**data.model_dump())
        created = self.repo.create(wing)
        return _enrich(created)

    def get_or_404(self, id: UUID) -> WingOut:
        obj = self.repo.get(id)
        if not obj:
            raise HTTPException(status_code=404, detail="Wing not found")
        return _enrich(obj)

    def list(self, skip: int = 0, limit: int = 50) -> List[WingOut]:
        return [_enrich(w) for w in self.repo.get_all(skip, limit)]

    def list_by_society(self, society_id: UUID) -> List[WingOut]:
        return [_enrich(w) for w in self.repo.get_by_society(society_id)]

    def update(self, id: UUID, data: WingUpdate) -> WingOut:
        wing = self.repo.get(id)
        if not wing:
            raise HTTPException(status_code=404, detail="Wing not found")
        patch = data.model_dump(exclude_none=True)
        if "name" in patch and patch["name"] != wing.name:
            self.repo.assert_unique_name(wing.society_id, patch["name"], exclude_id=id)
        if "code" in patch and patch["code"] != wing.code:
            self.repo.assert_unique_code(wing.society_id, patch["code"], exclude_id=id)
        return _enrich(self.repo.update(wing, patch))

    def toggle_active(self, id: UUID, activate: bool) -> WingOut:
        wing = self.repo.get(id)
        if not wing:
            raise HTTPException(status_code=404, detail="Wing not found")
        wing.is_active = activate
        self.repo.db.commit()
        self.repo.db.refresh(wing)
        return _enrich(wing)

    def delete(self, id: UUID) -> None:
        wing = self.repo.get(id)
        if not wing:
            raise HTTPException(status_code=404, detail="Wing not found")
        self.repo.soft_delete(wing)
