from typing import Generic, TypeVar, Type, Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db    = db

    def get(self, id) -> Optional[ModelType]:
        """Get by UUID — handles both UUID objects and string forms (SQLite compat)."""
        try:
            result = self.db.query(self.model).filter(
                self.model.id == id, self.model.is_active == True,
            ).first()
            if result:
                return result
        except Exception:
            pass
        # Fallback: string comparison for SQLite
        try:
            result = self.db.query(self.model).filter(
                self.model.id == str(id), self.model.is_active == True,
            ).first()
            return result
        except Exception:
            return None

    def get_including_inactive(self, id) -> Optional[ModelType]:
        try:
            return self.db.query(self.model).filter(self.model.id == id).first()
        except Exception:
            return self.db.query(self.model).filter(
                self.model.id == str(id)
            ).first()

    def get_all(self, skip: int = 0, limit: int = 50) -> List[ModelType]:
        return self.db.query(self.model).filter(
            self.model.is_active == True
        ).offset(skip).limit(limit).all()

    def create(self, obj: ModelType) -> ModelType:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, obj: ModelType, data: dict) -> ModelType:
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def soft_delete(self, obj: ModelType) -> ModelType:
        obj.is_active = False
        self.db.commit()
        self.db.refresh(obj)
        return obj
