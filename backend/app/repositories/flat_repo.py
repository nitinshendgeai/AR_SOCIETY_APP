from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from app.models.flat import Flat
from app.repositories.base import BaseRepository


class FlatRepository(BaseRepository[Flat]):
    def __init__(self, db: Session):
        super().__init__(Flat, db)

    def get_by_wing(self, wing_id: UUID) -> List[Flat]:
        return self.db.query(Flat).filter(
            Flat.wing_id == wing_id,
            Flat.is_active == True,
        ).all()
