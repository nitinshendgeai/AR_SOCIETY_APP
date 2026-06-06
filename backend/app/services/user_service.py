import secrets
import string
from typing import List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

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

    # ── Tenant-scoped operations ──────────────────────────────────────────────

    def get_or_404(self, id: UUID, society_id) -> User:
        """Fetch user by ID, restricted to the calling admin's society."""
        obj = self.repo.get(id, society_id=society_id)
        if not obj:
            raise HTTPException(status_code=404, detail="User not found")
        return obj

    def list(self, society_id, skip: int = 0, limit: int = 100) -> List[User]:
        """Return all active users belonging to society_id."""
        return self.repo.get_all(society_id=society_id, skip=skip, limit=limit)

    def create(self, data: AdminUserCreate, society_id) -> tuple[User, str]:
        """Create a user in the caller's society. Returns (user, plain_temp_password)."""
        if self.repo.get_by_email(data.email):
            raise HTTPException(status_code=409, detail="Email already registered")
        temp_pwd = _generate_temp_password()
        user = User(
            society_id           = society_id,
            email                = data.email,
            full_name            = data.full_name,
            phone                = data.phone,
            hashed_password      = hash_password(temp_pwd),
            status               = UserStatus.ACTIVE,
            must_change_password = data.must_change_password,
            terms_accepted       = False,
            setup_completed      = False,
        )
        self.repo.db.add(user)
        self.repo.db.flush()
        if data.role_name:
            self.repo.assign_role(user, data.role_name)
        else:
            self.repo.db.commit()
        return user, temp_pwd

    def update(self, id: UUID, data: UserUpdate, society_id) -> User:
        user = self.get_or_404(id, society_id)
        return self.repo.update(user, data.model_dump(exclude_none=True))

    def assign_role(self, user_id: UUID, role_name: str, society_id) -> User:
        user = self.get_or_404(user_id, society_id)
        self.repo.assign_role(user, role_name)
        return user

    def remove_role(self, user_id: UUID, role_name: str, society_id) -> User:
        user = self.get_or_404(user_id, society_id)
        self.repo.remove_role(user, role_name)
        return user

    def reset_password(self, user_id: UUID, society_id) -> tuple[User, str]:
        """Reset to a new temp password within the caller's society."""
        user = self.get_or_404(user_id, society_id)
        temp_pwd = _generate_temp_password()
        user.hashed_password      = hash_password(temp_pwd)
        user.must_change_password = True
        self.repo.db.commit()
        return user, temp_pwd

    def delete(self, id: UUID, society_id) -> None:
        user = self.get_or_404(id, society_id)
        self.repo.soft_delete(user)
