from sqlalchemy.orm import Session
from typing import Optional
from app.models.user import User, UserRole
from app.models.role import Role
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session):
        super().__init__(User, db)

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_phone(self, phone: str) -> Optional[User]:
        return self.db.query(User).filter(User.phone == phone).first()

    def assign_role(self, user: User, role_name: str) -> None:
        role = self.db.query(Role).filter(Role.name == role_name).first()
        if not role:
            role = Role(name=role_name)
            self.db.add(role)
            self.db.flush()

        existing = self.db.query(UserRole).filter(
            UserRole.user_id == user.id,
            UserRole.role_id == role.id,
        ).first()
        if not existing:
            self.db.add(UserRole(user_id=user.id, role_id=role.id))
            self.db.commit()

    def get_roles(self, user: User) -> list:
        return [ur.role.name for ur in user.user_roles if ur.role]

    def remove_role(self, user: User, role_name: str) -> None:
        role = self.db.query(Role).filter(Role.name == role_name).first()
        if not role:
            return
        ur = self.db.query(UserRole).filter(
            UserRole.user_id == user.id,
            UserRole.role_id == role.id,
        ).first()
        if ur:
            self.db.delete(ur)
            self.db.commit()
