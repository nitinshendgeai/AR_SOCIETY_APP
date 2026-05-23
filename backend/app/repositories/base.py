from typing import Generic, List, Optional, Type, TypeVar
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db    = db

    def get(self, id: UUID) -> Optional[ModelType]:
        return self.db.query(self.model).filter(
            self.model.id == id,
            self.model.is_active == True,
        ).first()

    def get_all(self, skip: int = 0, limit: int = 50) -> List[ModelType]:
        return self.db.query(self.model).filter(
            self.model.is_active == True
        ).offset(skip).limit(limit).all()

    def count(self) -> int:
        return self.db.query(self.model).filter(self.model.is_active == True).count()

    def create(self, obj: ModelType) -> ModelType:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, obj: ModelType, data: dict) -> ModelType:
        for field, value in data.items():
            if value is not None:
                setattr(obj, field, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def soft_delete(self, obj: ModelType) -> ModelType:
        obj.is_active = False
        self.db.commit()
        return obj

    def hard_delete(self, obj: ModelType) -> None:
        self.db.delete(obj)
        self.db.commit()
