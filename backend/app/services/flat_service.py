from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from typing import List

from app.models.flat import Flat
from app.repositories.flat_repo import FlatRepository
from app.repositories.wing_repo import WingRepository
from app.schemas.flat import FlatCreate, FlatUpdate


class FlatService:
    def __init__(self, db: Session):
        self.repo      = FlatRepository(db)
        self.wing_repo = WingRepository(db)

    def create(self, data: FlatCreate) -> Flat:
        wing = self.wing_repo.get(data.wing_id)
        if not wing:
            raise HTTPException(status_code=404, detail="Wing not found")
        flat = Flat(**data.model_dump())
        return self.repo.create(flat)

    def get_or_404(self, id: UUID) -> Flat:
        obj = self.repo.get(id)
        if not obj:
            raise HTTPException(status_code=404, detail="Flat not found")
        return obj

    def list(self, skip: int = 0, limit: int = 50) -> List[Flat]:
        return self.repo.get_all(skip, limit)

    def list_by_wing(self, wing_id: UUID) -> List[Flat]:
        return self.repo.get_by_wing(wing_id)

    def update(self, id: UUID, data: FlatUpdate) -> Flat:
        flat = self.get_or_404(id)
        return self.repo.update(flat, data.model_dump(exclude_none=True))

    def delete(self, id: UUID) -> None:
        flat = self.get_or_404(id)
        self.repo.soft_delete(flat)
