from typing import Optional
from app.schemas.common import OrmBase, TimestampSchema


class SocietyCreate(OrmBase):
    name:          str
    address:       Optional[str] = None
    city:          Optional[str] = None
    state:         Optional[str] = None
    pincode:       Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    logo_url:      Optional[str] = None


class SocietyUpdate(OrmBase):
    # Identity
    name:                    Optional[str] = None
    society_code:            Optional[str] = None
    address:                 Optional[str] = None
    city:                    Optional[str] = None
    state:                   Optional[str] = None
    pincode:                 Optional[str] = None
    country:                 Optional[str] = None
    timezone:                Optional[str] = None
    website:                 Optional[str] = None
    logo_url:                Optional[str] = None
    # Contact
    contact_email:           Optional[str] = None
    contact_phone:           Optional[str] = None
    contact_person_name:     Optional[str] = None
    emergency_contact_name:  Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    # Settings
    maintenance_day:         Optional[int]  = None
    late_fee_percent:        Optional[int]  = None
    allow_tenant_portal:     Optional[bool] = None
    require_visitor_approval: Optional[bool] = None


class SocietyOut(TimestampSchema):
    # Identity
    name:                    str
    society_code:            Optional[str]
    address:                 Optional[str]
    city:                    Optional[str]
    state:                   Optional[str]
    pincode:                 Optional[str]
    country:                 Optional[str]
    timezone:                Optional[str]
    website:                 Optional[str]
    logo_url:                Optional[str]
    # Contact
    contact_email:           Optional[str]
    contact_phone:           Optional[str]
    contact_person_name:     Optional[str]
    emergency_contact_name:  Optional[str]
    emergency_contact_phone: Optional[str]
    # Settings
    maintenance_day:          Optional[int]
    late_fee_percent:         Optional[int]
    allow_tenant_portal:      bool
    require_visitor_approval: bool
    # Trial & subscription (read-only)
    account_status:           Optional[str]
    is_trial:                 bool
    trial_start_date:         Optional[str]
    trial_end_date:           Optional[str]
    subscription_plan:        Optional[str]
    subscription_status:      Optional[str]
    # Limits
    allowed_users:            int
    allowed_flats:            int
    # Setup
    setup_completed:             bool
    setup_completion_percentage: int
