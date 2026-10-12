import re
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_
from app.models.society import AccountStatus, Society
from app.models.user import User, UserRole, UserStatus
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

    # Scope for the duplicate checks: any active society (the default), the platform (None), or one society.
    ANY = object()

    def _active_users(self, scope=ANY):
        """Users that count when checking whether a mobile number or email is taken: active users (not disabled or
        removed) of an active society (not suspended, closed or removed). A person in a disabled society or a
        disabled user doesn't hold their number or email, so someone else may use it."""
        q = (self.db.query(User).outerjoin(Society, Society.id == User.society_id)
             .filter(User.is_active == True, User.status == UserStatus.ACTIVE))  # noqa: E712
        if scope is UserRepository.ANY:
            q = q.filter(or_(User.society_id.is_(None), and_(
                Society.is_active == True,  # noqa: E712
                Society.account_status.notin_([AccountStatus.SUSPENDED, AccountStatus.CANCELLED]))))
        elif scope is None:
            q = q.filter(User.society_id.is_(None))
        else:
            q = q.filter(User.society_id == scope)
        return q

    def get_by_email(self, email: str, society_id=ANY) -> Optional[User]:
        """The active user with this email (in `society_id`, or in any active society)."""
        return self._active_users(society_id).filter(func.lower(User.email) == email.strip().lower()).first()

    def get_by_phone(self, phone: str, society_id=ANY) -> Optional[User]:
        """The active user with this mobile number (in `society_id`, or in any active society)."""
        digits = login_mobile(phone)
        return self._active_users(society_id).filter(or_(User.phone == phone, User.phone == digits)).first()

    def candidates(self, identifier: str) -> List[User]:
        """Every login this email or mobile number could be: one per society the person belongs to, oldest first.
        Includes disabled users and societies (the caller decides which can be signed in to and says why not)."""
        identifier = identifier.strip()
        q = self.db.query(User).filter(User.is_active == True)  # noqa: E712
        if "@" in identifier:
            q = q.filter(func.lower(User.email) == identifier.lower())
        else:
            q = q.filter(or_(User.phone == identifier, User.phone == login_mobile(identifier)))
        return q.order_by(User.created_at, User.id).all()

    def get_by_email_or_phone(self, identifier: str) -> Optional[User]:
        """The first login for this email or mobile number (see `candidates`)."""
        found = self.candidates(identifier)
        return found[0] if found else None

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
