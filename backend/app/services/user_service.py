from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from typing import List

from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserUpdate


class UserService:
    def __init__(self, db: Session):
        self.repo = UserRepository(db)

    def get_or_404(self, id: UUID) -> User:
        obj = self.repo.get(id)
        if not obj:
            raise HTTPException(status_code=404, detail="User not found")
        return obj

    def list(self, skip: int = 0, limit: int = 50) -> List[User]:
        return self.repo.get_all(skip, limit)

    def update(self, id: UUID, data: UserUpdate) -> User:
        user = self.get_or_404(id)
        return self.repo.update(user, data.model_dump(exclude_none=True))

    def assign_role(self, user_id: UUID, role_name: str) -> User:
        user = self.get_or_404(user_id)
        self.repo.assign_role(user, role_name)
        return user

    def delete(self, id: UUID) -> None:
        user = self.get_or_404(id)
        self.repo.soft_delete(user)
