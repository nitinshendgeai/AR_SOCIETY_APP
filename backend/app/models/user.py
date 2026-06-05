from sqlalchemy import Column, String, Boolean, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base, TimestampMixin


class UserStatus(str, enum.Enum):
    ACTIVE    = "active"
    INACTIVE  = "inactive"
    SUSPENDED = "suspended"
    PENDING   = "pending"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    email          = Column(String(255), nullable=False, unique=True, index=True)
    phone          = Column(String(20), nullable=True, unique=True, index=True)
    full_name      = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    status         = Column(Enum(UserStatus), default=UserStatus.PENDING, nullable=False)
    profile_image  = Column(String(500), nullable=True)
    is_superadmin        = Column(Boolean, default=False, nullable=False)
    must_change_password = Column(Boolean, default=False, nullable=False)
    terms_accepted       = Column(Boolean, default=False, nullable=False)
    setup_completed      = Column(Boolean, default=False, nullable=False)

    # Relationships
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
