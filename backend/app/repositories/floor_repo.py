from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException
from app.models.floor import Floor
from app.repositories.base import BaseRepository


class FloorRepository(BaseRepository[Floor]):
    def __init__(self, db: Session):
        super().__init__(Floor, db)

    def get_by_wing(self, wing_id: UUID) -> List[Floor]:
        return (
            self.db.query(Floor)
            .filter(Floor.wing_id == wing_id, Floor.is_active == True)
            .order_by(Floor.floor_number)
            .all()
        )

    def get_by_society(self, society_id: UUID) -> List[Floor]:
        return (
            self.db.query(Floor)
            .filter(Floor.society_id == society_id, Floor.is_active == True)
            .order_by(Floor.floor_number)
            .all()
        )

    def assert_unique_number(self, wing_id: UUID, floor_number: int,
                              exclude_id: Optional[UUID] = None) -> None:
        q = self.db.query(Floor).filter(
            Floor.wing_id == wing_id,
            Floor.floor_number == floor_number,
            Floor.is_active == True,
        )
        if exclude_id:
            q = q.filter(Floor.id != exclude_id)
        if q.first():
            raise HTTPException(
                409,
                f"Floor {floor_number} already exists in this wing",
            )
