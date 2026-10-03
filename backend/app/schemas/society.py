import re
from datetime import date
from typing import Optional
from pydantic import Field, field_validator
from app.schemas.common import OrmBase, TimestampSchema
from app.schemas.validators import name, phone, text

_PAN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_GSTIN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_PINCODE = re.compile(r"^[0-9]{6}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


_text = text
_name = name
_phone = phone


def _pan(v):
    v = _text(v)
    if v is None:
        return None
    v = v.replace(" ", "").upper()
    if not _PAN.match(v):
        raise ValueError("PAN must look like ABCDE1234F")
    return v


def _gstin(v):
    v = _text(v)
    if v is None:
        return None
    v = v.replace(" ", "").upper()
    if not _GSTIN.match(v):
        raise ValueError("GSTIN must be 15 characters, like 27AAAAA0000A1Z5")
    return v


def _pincode(v):
    v = _text(v)
    if v is None:
        return None
    v = v.replace(" ", "")
    if not _PINCODE.match(v):
        raise ValueError("Pincode must be 6 digits")
    return v


def _email(v):
    v = _text(v)
    if v is None:
        return None
    if not _EMAIL.match(v):
        raise ValueError("Enter a valid email address")
    return v.lower()


class SocietyCreate(OrmBase):
    name:          str = Field(max_length=255)
    address:       Optional[str] = None
    city:          Optional[str] = Field(default=None, max_length=100)
    state:         Optional[str] = Field(default=None, max_length=100)
    pincode:       Optional[str] = None
    contact_email: Optional[str] = Field(default=None, max_length=255)
    contact_phone: Optional[str] = None
    logo_url:      Optional[str] = Field(default=None, max_length=500)

    _name = field_validator("name", mode="before")(_name)
    _pincode = field_validator("pincode", mode="before")(_pincode)
    _email = field_validator("contact_email", mode="before")(_email)
    _phone = field_validator("contact_phone", mode="before")(_phone)


class SocietyUpdate(OrmBase):
    # Identity
    name:                    Optional[str] = Field(default=None, max_length=255)
    society_code:            Optional[str] = Field(default=None, max_length=20)
    address:                 Optional[str] = None
    city:                    Optional[str] = Field(default=None, max_length=100)
    state:                   Optional[str] = Field(default=None, max_length=100)
    pincode:                 Optional[str] = None
    country:                 Optional[str] = Field(default=None, max_length=50)
    timezone:                Optional[str] = Field(default=None, max_length=50)
    website:                 Optional[str] = Field(default=None, max_length=255)
    logo_url:                Optional[str] = Field(default=None, max_length=500)
    # Legal
    registration_number:     Optional[str] = Field(default=None, max_length=100)
    gst_number:              Optional[str] = None
    pan_number:              Optional[str] = None
    # Contact
    contact_email:           Optional[str] = Field(default=None, max_length=255)
    contact_phone:           Optional[str] = None
    contact_person_name:     Optional[str] = Field(default=None, max_length=255)
    emergency_contact_name:  Optional[str] = Field(default=None, max_length=255)
    emergency_contact_phone: Optional[str] = None
    # Settings
    maintenance_day:          Optional[int]  = Field(default=None, ge=1, le=28)    # the bill day, safe in every month
    late_fee_percent:         Optional[int]  = Field(default=None, ge=0, le=100)
    allow_tenant_portal:      Optional[bool] = None
    require_visitor_approval: Optional[bool] = None

    _name = field_validator("name", mode="before")(_name)
    _pincode = field_validator("pincode", mode="before")(_pincode)
    _gst = field_validator("gst_number", mode="before")(_gstin)
    _pan = field_validator("pan_number", mode="before")(_pan)
    _email = field_validator("contact_email", mode="before")(_email)
    _phone = field_validator("contact_phone", "emergency_contact_phone", mode="before")(_phone)


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
    # Legal
    registration_number:     Optional[str]
    gst_number:              Optional[str]
    pan_number:              Optional[str]
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
    trial_start_date:         Optional[date]
    trial_end_date:           Optional[date]
    subscription_plan:        Optional[str]
    subscription_status:      Optional[str]
    # Limits
    allowed_users:            int
    allowed_flats:            int
    # Setup
    setup_completed:             bool
    setup_completion_percentage: int
