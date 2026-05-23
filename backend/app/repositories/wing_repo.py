from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
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
