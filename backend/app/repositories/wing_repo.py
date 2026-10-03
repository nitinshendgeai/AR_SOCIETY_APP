from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException
from app.models.wing import Wing
from app.repositories.base import BaseRepository
from app.utils.natural_sort import natural_sort_key


class WingRepository(BaseRepository[Wing]):
    def __init__(self, db: Session):
        super().__init__(Wing, db)

    def get_by_society(self, society_id: UUID, include_inactive: bool = False) -> List[Wing]:
        """The society's wings in natural order ("Tower 2" before "Tower 10").
        Deactivated wings only with `include_inactive`; deleted ones never."""
        q = self.db.query(Wing).filter(Wing.society_id == society_id, Wing.deleted_at.is_(None))
        if not include_inactive:
            q = q.filter(Wing.is_active == True)
        return sorted(q.all(), key=lambda w: natural_sort_key(w.name))

    def get_kept(self, id, society_id=None) -> Optional[Wing]:
        """A wing that exists — active or deactivated, not deleted."""
        q = self.db.query(Wing).filter(Wing.id == id, Wing.deleted_at.is_(None))
        if society_id is not None:
            q = q.filter(Wing.society_id == society_id)
        return q.first()

    def assert_unique_name(self, society_id: UUID, name: str,
                           exclude_id: Optional[UUID] = None) -> None:
        q = self.db.query(Wing).filter(
            Wing.society_id == society_id,
            func.lower(Wing.name) == name.lower(),
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
            func.upper(Wing.code) == code.upper(),
            Wing.is_active == True,
        )
        if exclude_id:
            q = q.filter(Wing.id != exclude_id)
        if q.first():
            raise HTTPException(409, f"Wing code '{code}' already exists in this society")
