from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from typing import List

from app.models.floor import Floor
from app.models.flat import Flat
from app.models.user import User
from app.repositories.floor_repo import FloorRepository
from app.repositories.wing_repo import WingRepository
from app.schemas.floor import FloorCreate, FloorUpdate, FloorOut
from app.core.tenant_scope import assert_society_access


def _enrich(floor: Floor, db: Session) -> FloorOut:
    """Attach flat_count per floor."""
    out = FloorOut.model_validate(floor)
    out.flat_count = db.query(Flat).filter(
        Flat.wing_id == floor.wing_id,
        Flat.floor == floor.floor_number,
        Flat.is_active == True,
    ).count()
    return out


class FloorService:
    def __init__(self, db: Session):
        self.repo      = FloorRepository(db)
        self.wing_repo = WingRepository(db)

    def create(self, data: FloorCreate, current_user: User) -> FloorOut:
        # society_id is derived from the (tenant-scoped) parent wing, not
        # trusted from the request body — a caller-supplied society_id that
        # doesn't match the wing's real owner would otherwise let a floor be
        # silently attributed to the wrong society.
        wing = self.wing_repo.get(data.wing_id, society_id=current_user.society_id)
        if not wing:
            raise HTTPException(404, "Wing not found")
        self.repo.assert_unique_number(data.wing_id, data.floor_number)
        payload = data.model_dump()
        payload["society_id"] = wing.society_id
        floor = Floor(**payload)
        created = self.repo.create(floor)
        return _enrich(created, self.repo.db)

    def get_or_404(self, id: UUID, current_user: User) -> FloorOut:
        obj = self.repo.get(id, society_id=current_user.society_id)
        if not obj:
            raise HTTPException(404, "Floor not found")
        return _enrich(obj, self.repo.db)

    def list_by_wing(self, wing_id: UUID, current_user: User) -> List[FloorOut]:
        wing = self.wing_repo.get(wing_id, society_id=current_user.society_id)
        if not wing:
            raise HTTPException(404, "Wing not found")
        return [_enrich(f, self.repo.db) for f in self.repo.get_by_wing(wing_id)]

    def list_by_society(self, society_id: UUID, current_user: User) -> List[FloorOut]:
        assert_society_access(current_user, society_id)
        return [_enrich(f, self.repo.db) for f in self.repo.get_by_society(society_id)]

    def update(self, id: UUID, data: FloorUpdate, current_user: User) -> FloorOut:
        floor = self.repo.get(id, society_id=current_user.society_id)
        if not floor:
            raise HTTPException(404, "Floor not found")
        patch = data.model_dump(exclude_none=True)
        if "floor_number" in patch and patch["floor_number"] != floor.floor_number:
            self.repo.assert_unique_number(floor.wing_id, patch["floor_number"], exclude_id=id)
        updated = self.repo.update(floor, patch)
        return _enrich(updated, self.repo.db)

    def delete(self, id: UUID, current_user: User) -> None:
        floor = self.repo.get(id, society_id=current_user.society_id)
        if not floor:
            raise HTTPException(404, "Floor not found")
        self.repo.soft_delete(floor)
