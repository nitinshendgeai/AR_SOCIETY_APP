from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from typing import List

from app.models.wing import Wing
from app.repositories.wing_repo import WingRepository
from app.repositories.society_repo import SocietyRepository
from app.schemas.wing import WingCreate, WingUpdate


class WingService:
    def __init__(self, db: Session):
        self.repo         = WingRepository(db)
        self.society_repo = SocietyRepository(db)

    def create(self, data: WingCreate) -> Wing:
        society = self.society_repo.get(data.society_id)
        if not society:
            raise HTTPException(status_code=404, detail="Society not found")
        wing = Wing(**data.model_dump())
        return self.repo.create(wing)

    def get_or_404(self, id: UUID) -> Wing:
        obj = self.repo.get(id)
        if not obj:
            raise HTTPException(status_code=404, detail="Wing not found")
        return obj

    def list(self, skip: int = 0, limit: int = 50) -> List[Wing]:
        return self.repo.get_all(skip, limit)

    def list_by_society(self, society_id: UUID) -> List[Wing]:
        return self.repo.get_by_society(society_id)

    def update(self, id: UUID, data: WingUpdate) -> Wing:
        wing = self.get_or_404(id)
        return self.repo.update(wing, data.model_dump(exclude_none=True))

    def delete(self, id: UUID) -> None:
        wing = self.get_or_404(id)
        self.repo.soft_delete(wing)
