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
    name:          Optional[str] = None
    address:       Optional[str] = None
    city:          Optional[str] = None
    state:         Optional[str] = None
    pincode:       Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    logo_url:      Optional[str] = None


class SocietyOut(TimestampSchema):
    name:          str
    address:       Optional[str]
    city:          Optional[str]
    state:         Optional[str]
    pincode:       Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    logo_url:      Optional[str]
