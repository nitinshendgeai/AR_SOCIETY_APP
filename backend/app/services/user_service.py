import secrets
import string
from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from typing import List

from app.models.user import User, UserStatus
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserUpdate, AdminUserCreate
from app.core.security import hash_password


def _generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.isupper() for c in pwd)
                and any(c.islower() for c in pwd)
                and any(c.isdigit() for c in pwd)):
            return pwd


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

    def create(self, data: AdminUserCreate) -> tuple[User, str]:
        """Create user with a generated temp password. Returns (user, plain_password)."""
        if self.repo.get_by_email(data.email):
            raise HTTPException(status_code=409, detail="Email already registered")
        temp_pwd = _generate_temp_password()
        user = User(
            email=data.email,
            full_name=data.full_name,
            phone=data.phone,
            hashed_password=hash_password(temp_pwd),
            status=UserStatus.ACTIVE,
            must_change_password=data.must_change_password,
            terms_accepted=False,
            setup_completed=False,
        )
        self.repo.db.add(user)
        self.repo.db.flush()
        if data.role_name:
            self.repo.assign_role(user, data.role_name)
        else:
            self.repo.db.commit()
        return user, temp_pwd

    def update(self, id: UUID, data: UserUpdate) -> User:
        user = self.get_or_404(id)
        return self.repo.update(user, data.model_dump(exclude_none=True))

    def assign_role(self, user_id: UUID, role_name: str) -> User:
        user = self.get_or_404(user_id)
        self.repo.assign_role(user, role_name)
        return user

    def remove_role(self, user_id: UUID, role_name: str) -> User:
        user = self.get_or_404(user_id)
        self.repo.remove_role(user, role_name)
        return user

    def reset_password(self, user_id: UUID) -> tuple[User, str]:
        """Reset to a new temp password. Returns (user, plain_password)."""
        user = self.get_or_404(user_id)
        temp_pwd = _generate_temp_password()
        user.hashed_password = hash_password(temp_pwd)
        user.must_change_password = True
        self.repo.db.commit()
        return user, temp_pwd

    def delete(self, id: UUID) -> None:
        user = self.get_or_404(id)
        self.repo.soft_delete(user)
