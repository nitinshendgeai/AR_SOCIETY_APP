import enum
from sqlalchemy import Column, String, Text, Boolean, Integer, Date, Enum
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class AccountStatus(str, enum.Enum):
    TRIAL     = "TRIAL"
    ACTIVE    = "ACTIVE"
    EXPIRED   = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"


ACCOUNT_STATUS_TRANSITIONS: dict = {
    AccountStatus.TRIAL:     {AccountStatus.ACTIVE, AccountStatus.EXPIRED, AccountStatus.SUSPENDED},
    AccountStatus.ACTIVE:    {AccountStatus.SUSPENDED, AccountStatus.CANCELLED, AccountStatus.EXPIRED},
    AccountStatus.EXPIRED:   {AccountStatus.ACTIVE, AccountStatus.SUSPENDED},
    AccountStatus.SUSPENDED: {AccountStatus.ACTIVE, AccountStatus.CANCELLED},
    AccountStatus.CANCELLED: set(),
}


class Society(Base, TimestampMixin):
    __tablename__ = "societies"

    # Identity
    society_code  = Column(String(20), nullable=True, unique=True, index=True)
    name          = Column(String(255), nullable=False, unique=True, index=True)
    address       = Column(Text, nullable=True)
    city          = Column(String(100), nullable=True)
    state         = Column(String(100), nullable=True)
    pincode       = Column(String(20), nullable=True)
    country       = Column(String(50), default="India", nullable=True)

    # Operational
    timezone    = Column(String(50), default="Asia/Kolkata", nullable=False)
    total_wings = Column(Integer, nullable=True)
    total_flats = Column(Integer, nullable=True)

    # Contact
    contact_email               = Column(String(255), nullable=True)
    contact_phone               = Column(String(20), nullable=True)
    contact_person_name         = Column(String(255), nullable=True)
    emergency_contact_name      = Column(String(255), nullable=True)
    emergency_contact_phone     = Column(String(20), nullable=True)
    logo_url                    = Column(String(500), nullable=True)
    website                     = Column(String(255), nullable=True)

    # Settings
    maintenance_day          = Column(Integer, nullable=True)
    late_fee_percent         = Column(Integer, nullable=True)
    allow_tenant_portal      = Column(Boolean, default=True, nullable=False)
    require_visitor_approval = Column(Boolean, default=True, nullable=False)

    # Trial & Subscription
    account_status   = Column(Enum(AccountStatus), default=AccountStatus.TRIAL, nullable=False)
    is_trial         = Column(Boolean, default=True, nullable=False)
    trial_start_date = Column(Date, nullable=True)
    trial_end_date   = Column(Date, nullable=True)

    # Subscription (null until upgraded)
    subscription_plan        = Column(String(50), nullable=True)
    subscription_status      = Column(String(50), nullable=True)
    subscription_start_date  = Column(Date, nullable=True)
    subscription_expiry_date = Column(Date, nullable=True)

    # Usage limits
    allowed_users      = Column(Integer, default=50, nullable=False)
    allowed_flats      = Column(Integer, default=100, nullable=False)
    allowed_storage_mb = Column(Integer, default=1024, nullable=False)

    # Setup wizard progress
    setup_completed             = Column(Boolean, default=False, nullable=False)
    setup_completion_percentage = Column(Integer, default=0, nullable=False)

    # Relationships
    wings = relationship("Wing", back_populates="society", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Society {self.society_code or self.name}>"
