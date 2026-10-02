from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from typing import List, Optional

from app.models.society import Society
from app.repositories.society_repo import SocietyRepository
from app.schemas.society import SocietyCreate, SocietyUpdate


class SocietyService:
    def __init__(self, db: Session):
        self.repo = SocietyRepository(db)

    def create(self, data: SocietyCreate) -> Society:
        if self.repo.get_by_name(data.name):
            raise HTTPException(status_code=400, detail="Society name already exists")
        society = Society(**data.model_dump())
        return self.repo.create(society)

    def get_or_404(self, id: UUID, caller_society_id: Optional[UUID] = None) -> Society:
        """Fetch a society by id. When caller_society_id is provided (a
        society-scoped caller, not a platform admin), the id must match it —
        otherwise a Society Admin/Committee member of one society could
        read/target another society purely by knowing its UUID."""
        if caller_society_id is not None and caller_society_id != id:
            raise HTTPException(status_code=403, detail="Access denied to this society")
        obj = self.repo.get(id)
        if not obj:
            raise HTTPException(status_code=404, detail="Society not found")
        return obj

    def list(self, skip: int = 0, limit: int = 50) -> List[Society]:
        return self.repo.get_all(skip, limit)

    def update(self, id: UUID, data: SocietyUpdate, caller_society_id: Optional[UUID] = None) -> Society:
        society = self.get_or_404(id, caller_society_id)
        patch = data.model_dump(exclude_none=True)
        # Names and codes are unique across societies
        if "name" in patch and patch["name"].lower() != society.name.lower():
            other = self.repo.get_by_name(patch["name"])
            if other and other.id != society.id:
                raise HTTPException(status_code=409, detail="Another society already uses this name")
        if patch.get("society_code") and patch["society_code"] != society.society_code:
            taken = self.repo.db.query(Society).filter(
                Society.society_code == patch["society_code"], Society.id != society.id).first()
            if taken:
                raise HTTPException(status_code=409, detail="Another society already uses this code")
        return self.repo.update(society, patch)

    def delete(self, id: UUID, caller_society_id: Optional[UUID] = None) -> None:
        society = self.get_or_404(id, caller_society_id)
        self.repo.soft_delete(society)
