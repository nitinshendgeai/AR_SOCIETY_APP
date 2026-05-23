from sqlalchemy.orm import Session
from typing import Optional
from app.models.society import Society
from app.repositories.base import BaseRepository


class SocietyRepository(BaseRepository[Society]):
    def __init__(self, db: Session):
        super().__init__(Society, db)

    def get_by_name(self, name: str) -> Optional[Society]:
        return self.db.query(Society).filter(Society.name == name).first()
