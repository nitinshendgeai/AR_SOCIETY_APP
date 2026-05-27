"""
SocietySetupService — automated onboarding workflow.

On society creation:
  1. Create default roles (idempotent)
  2. Create default admin user with temporary password
  3. Create default operational users (security, staff)
  4. Log all setup events in audit

Designed to run in a single transaction — rollback on any failure.
"""
import secrets
import string
from typing import Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.society import Society
from app.models.role import Role
from app.models.user import User, UserRole, UserStatus
from app.models.audit_log import AuditAction
from app.core.security import hash_password
from app.services.audit_service import AuditService


# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_ROLES = [
    ("Super Admin",    "Full system access"),
    ("Society Admin",  "Society-level administration"),
    ("Committee",      "Committee member access"),
    ("Security",       "Gate and security operations"),
    ("Staff",          "General staff operations"),
    ("Resident",       "Resident access"),
]


def _generate_temp_password(length: int = 12) -> str:
    """Generate a secure temporary password."""
    alphabet = string.ascii_letters + string.digits + "@#$!"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        # Ensure complexity: uppercase, lowercase, digit, special
        if (any(c.isupper() for c in pwd) and any(c.islower() for c in pwd)
                and any(c.isdigit() for c in pwd)
                and any(c in "@#$!" for c in pwd)):
            return pwd


class SocietySetupService:

    def __init__(self, db: Session):
        self.db = db

    def initialize_society(self, society: Society, created_by_user: User = None) -> dict:
        """
        Run full initialization for a newly created society.
        Returns: {roles, users, temp_credentials}
        """
        try:
            roles      = self._create_default_roles(society)
            users, creds = self._create_default_users(society, roles)
            self._audit_setup(society, created_by_user, len(roles), len(users))
            self.db.commit()
            return {
                "society_id":    str(society.id),
                "society_code":  society.society_code,
                "roles_created": [r.name for r in roles],
                "users_created": len(users),
                "credentials":   creds,
                "message":       "Society initialized successfully",
            }
        except Exception as e:
            self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Society initialization failed: {str(e)}")

    def _create_default_roles(self, society: Society) -> list:
        """Create roles globally (idempotent) — roles are shared across societies."""
        created = []
        for name, description in DEFAULT_ROLES:
            r = self.db.query(Role).filter(Role.name == name).first()
            if not r:
                r = Role(name=name, description=description)
                self.db.add(r)
                self.db.flush()
            created.append(r)
        return created

    def _create_default_users(self, society: Society,
                               roles: list) -> Tuple[list, list]:
        """
        Create default operational users for the society.
        Returns (users list, credentials list)
        """
        code = (society.society_code or "soc").lower()
        role_map = {r.name: r for r in roles}

        default_users = [
            {
                "email":     f"admin@{code}.arsociety.com",
                "full_name": f"{society.name} Admin",
                "role":      "Society Admin",
                "phone":     None,
            },
            {
                "email":     f"security@{code}.arsociety.com",
                "full_name": f"{society.name} Security",
                "role":      "Security",
                "phone":     None,
            },
            {
                "email":     f"staff@{code}.arsociety.com",
                "full_name": f"{society.name} Staff",
                "role":      "Staff",
                "phone":     None,
            },
        ]

        created_users = []
        credentials   = []

        for udata in default_users:
            existing = self.db.query(User).filter(User.email == udata["email"]).first()
            if existing:
                continue  # idempotent

            temp_pwd = _generate_temp_password()
            user = User(
                email=udata["email"],
                full_name=udata["full_name"],
                phone=udata["phone"],
                hashed_password=hash_password(temp_pwd),
                status=UserStatus.ACTIVE,
                must_change_password=True,  # force password change on first login
            )
            self.db.add(user)
            self.db.flush()

            # Assign role
            role = role_map.get(udata["role"])
            if role:
                self.db.add(UserRole(user_id=user.id, role_id=role.id))

            created_users.append(user)
            credentials.append({
                "email":    udata["email"],
                "role":     udata["role"],
                "password": temp_pwd,   # returned only at creation time
            })

        return created_users, credentials

    def _audit_setup(self, society: Society, user: User, role_count: int, user_count: int):
        AuditService.log(
            db=self.db, action=AuditAction.CREATE, module="society_setup",
            entity_id=str(society.id), entity_type="Society",
            user=user,
            new_values={
                "event":        "society_initialized",
                "society":      society.name,
                "roles_created": role_count,
                "users_created": user_count,
            },
        )
