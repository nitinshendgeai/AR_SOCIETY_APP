from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException
from app.models.wing import Wing
from app.repositories.base import BaseRepository


class WingRepository(BaseRepository[Wing]):
    def __init__(self, db: Session):
        super().__init__(Wing, db)

    def get_by_society(self, society_id: UUID) -> List[Wing]:
        return self.db.query(Wing).filter(
            Wing.society_id == society_id,
            Wing.is_active == True,
        ).all()

    def assert_unique_name(self, society_id: UUID, name: str,
                           exclude_id: Optional[UUID] = None) -> None:
        q = self.db.query(Wing).filter(
            Wing.society_id == society_id,
            Wing.name == name,
            Wing.is_active == True,
        )
        if exclude_id:
            q = q.filter(Wing.id != exclude_id)
        if q.first():
            raise HTTPException(409, f"Wing name '{name}' already exists in this society")

    def assert_unique_code(self, society_id: UUID, code: str,
                           exclude_id: Optional[UUID] = None) -> None:
        if not code:
            return
        q = self.db.query(Wing).filter(
            Wing.society_id == society_id,
            Wing.code == code,
            Wing.is_active == True,
        )
        if exclude_id:
            q = q.filter(Wing.id != exclude_id)
        if q.first():
            raise HTTPException(409, f"Wing code '{code}' already exists in this society")
