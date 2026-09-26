import re
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models.user import User, UserRole
from app.models.role import Role
from app.repositories.base import BaseRepository


def login_mobile(value: str) -> str:
    """A typed Indian mobile number as the 10 digits accounts store:
    "+91 98765-43210", "919876543210" and "09876543210" → "9876543210"."""
    digits = re.sub(r"[\s\-()]", "", value)
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits


class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session):
        super().__init__(User, db)

    # ── Tenant-scoped queries ─────────────────────────────────────────────────

    def get_all(                                # type: ignore[override]
        self,
        society_id,
        skip: int = 0,
        limit: int = 100,
    ) -> List[User]:
        """Return active users for the caller's society, or all users for global admins."""
        q = self.db.query(User).filter(User.is_active == True)
        if society_id is not None:
            q = q.filter(User.society_id == society_id)
        return (
            q.order_by(User.full_name)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get(self, id, society_id=None) -> Optional[User]:           # type: ignore[override]
        """Fetch user by ID, optionally verifying they belong to society_id."""
        import uuid as _uuid
        try:
            uid = _uuid.UUID(str(id))
        except (ValueError, AttributeError):
            uid = id

        q = self.db.query(User).filter(User.id == uid, User.is_active == True)
        if society_id is not None:
            q = q.filter(User.society_id == society_id)
        return q.first()

    # ── Lookup helpers (global — used for auth / uniqueness) ──────────────────

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_phone(self, phone: str) -> Optional[User]:
        return self.db.query(User).filter(User.phone == phone).first()

    def get_by_email_or_phone(self, identifier: str) -> Optional[User]:
        """Login lookup: residents/tenants sign in with their mobile number,
        admin/committee/staff accounts sign in with email — accept either in
        the same field rather than making the client classify it first.

        Forgiving about how it's typed, like the login form's validation:
        emails match regardless of case (phone keyboards capitalise the first
        letter), and a mobile number may carry spaces, dashes, +91/91/0 —
        it's compared as the 10 digits it's stored as."""
        identifier = identifier.strip()
        if "@" in identifier:
            return self.db.query(User).filter(
                func.lower(User.email) == identifier.lower()
            ).first()
        return self.db.query(User).filter(
            or_(User.phone == identifier, User.phone == login_mobile(identifier))
        ).first()

    # ── Role management ───────────────────────────────────────────────────────

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
