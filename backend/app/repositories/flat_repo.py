from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException
from app.models.flat import Flat
from app.models.wing import Wing
from app.repositories.base import BaseRepository


class FlatRepository(BaseRepository[Flat]):
    def __init__(self, db: Session):
        super().__init__(Flat, db)

    def get_by_wing(self, wing_id: UUID) -> List[Flat]:
        return self.db.query(Flat).filter(
            Flat.wing_id == wing_id,
            Flat.is_active == True,
        ).order_by(Flat.flat_number).all()

    def get_by_society(self, society_id: UUID) -> List[Flat]:
        return (
            self.db.query(Flat)
            .join(Wing, Flat.wing_id == Wing.id)
            .filter(Wing.society_id == society_id, Flat.is_active == True)
            .order_by(Wing.name, Flat.flat_number)
            .all()
        )

    def assert_unique_flat_number(self, wing_id: UUID, flat_number: str,
                                   exclude_id: Optional[UUID] = None) -> None:
        q = self.db.query(Flat).filter(
            Flat.wing_id == wing_id,
            Flat.flat_number == flat_number,
            Flat.is_active == True,
        )
        if exclude_id:
            q = q.filter(Flat.id != exclude_id)
        if q.first():
            raise HTTPException(
                409, f"Flat '{flat_number}' already exists in this wing"
            )
