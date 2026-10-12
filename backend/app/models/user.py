from sqlalchemy import Column, String, Boolean, Enum, ForeignKey, DateTime, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base, TimestampMixin
import uuid as _uuid


class UserStatus(str, enum.Enum):
    ACTIVE    = "active"
    INACTIVE  = "inactive"
    SUSPENDED = "suspended"
    PENDING   = "pending"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    # Tenant isolation: every non-superadmin user belongs to exactly one society.
    # NULL is permitted only for Platform Admin / superadmin accounts.
    society_id = Column(
        UUID(as_uuid=True),
        ForeignKey("societies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Not unique on their own: the same mobile number or email may belong to a person in more than one society
    # (one login row per society). Uniqueness is per society, among *active* users — see the indexes below.
    email          = Column(String(255), nullable=False, index=True)
    phone          = Column(String(20), nullable=True, index=True)
    full_name      = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    status         = Column(Enum(UserStatus, values_callable=lambda e: [x.value for x in e]), default=UserStatus.PENDING, nullable=False)
    profile_image  = Column(String(500), nullable=True)
    is_superadmin        = Column(Boolean, default=False, nullable=False)
    must_change_password = Column(Boolean, default=False, nullable=False)
    terms_accepted       = Column(Boolean, default=False, nullable=False)
    setup_completed      = Column(Boolean, default=False, nullable=False)
    last_login           = Column(DateTime, nullable=True)

    # Relationships
    society    = relationship("Society", foreign_keys=[society_id])
    user_roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    residents  = relationship("Resident", back_populates="user")
    tenants    = relationship("Tenant", back_populates="user")

    def __repr__(self):
        return f"<User id={self.id} email={self.email!r}>"


class UserRole(Base, TimestampMixin):
    __tablename__ = "user_roles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")

    def __repr__(self):
        return f"<UserRole user={self.user_id} role={self.role_id}>"


# A mobile number or email is unique within a society among active users (a disabled or removed user doesn't hold
# it). Platform admins belong to no society, so they are unique among themselves. Only active ones are checked.
_ACTIVE = "is_active AND status = 'active'"
Index("uq_users_society_email", User.society_id, User.email, unique=True,
      postgresql_where=text(f"society_id IS NOT NULL AND {_ACTIVE}"), sqlite_where=text(f"society_id IS NOT NULL AND {_ACTIVE}"))
Index("uq_users_society_phone", User.society_id, User.phone, unique=True,
      postgresql_where=text(f"society_id IS NOT NULL AND phone IS NOT NULL AND {_ACTIVE}"),
      sqlite_where=text(f"society_id IS NOT NULL AND phone IS NOT NULL AND {_ACTIVE}"))
Index("uq_users_platform_email", User.email, unique=True,
      postgresql_where=text(f"society_id IS NULL AND {_ACTIVE}"), sqlite_where=text(f"society_id IS NULL AND {_ACTIVE}"))
Index("uq_users_platform_phone", User.phone, unique=True,
      postgresql_where=text(f"society_id IS NULL AND phone IS NOT NULL AND {_ACTIVE}"),
      sqlite_where=text(f"society_id IS NULL AND phone IS NOT NULL AND {_ACTIVE}"))
