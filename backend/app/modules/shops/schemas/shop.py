import re
from datetime import date
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import OrmBase, TimestampSchema
from app.schemas.floor import MAX_FLOOR, MIN_FLOOR
from app.utils.unit_fields import clean_possession_date, clean_ref

Occupancy = Literal["owner_run", "rented", "vacant"]
_PHONE = re.compile(r"^\+?\d{7,15}$")


def _text(v):
    if v is None:
        return None
    v = " ".join(str(v).split())
    return v or None


def _phone(v):
    v = _text(v)
    if v is None:
        return None
    digits = re.sub(r"[\s\-()]", "", v)
    if not _PHONE.match(digits):
        raise ValueError("Enter a valid phone number")
    return digits


class _ShopFields(OrmBase):
    floor:           Optional[int] = Field(default=None, ge=MIN_FLOOR, le=MAX_FLOOR)
    location:        Optional[str] = Field(default=None, max_length=120)
    area_sqft:       Optional[float] = Field(default=None, gt=0, le=1_000_000)
    business_name:   Optional[str] = Field(default=None, max_length=150)
    owner_phone:     Optional[str] = None
    owner_email:     Optional[str] = Field(default=None, max_length=255)
    occupancy:       Optional[Occupancy] = None
    tenant_name:     Optional[str] = Field(default=None, max_length=255)
    tenant_phone:    Optional[str] = None
    possession_date: Optional[date] = None
    electric_meter_no:    Optional[str] = Field(default=None, max_length=40)
    electric_consumer_no: Optional[str] = Field(default=None, max_length=40)
    remarks:         Optional[str] = None

    _t = field_validator("location", "business_name", "tenant_name", "remarks", "owner_email")(_text)
    _p = field_validator("owner_phone", "tenant_phone")(_phone)
    _d = field_validator("possession_date")(clean_possession_date)
    _m = field_validator("electric_meter_no", "electric_consumer_no")(clean_ref)


class ShopCreate(_ShopFields):
    society_id:  Optional[UUID] = None
    shop_number: str = Field(max_length=30)
    owner_name:  str = Field(max_length=255)

    @field_validator("shop_number", "owner_name", mode="before")
    @classmethod
    def _required(cls, v):
        v = _text(v)
        if not v:
            raise ValueError("Cannot be blank")
        return v


class ShopUpdate(_ShopFields):
    """Only fields sent change; send null (or "") to clear an optional one."""
    shop_number: Optional[str] = Field(default=None, max_length=30)
    owner_name:  Optional[str] = Field(default=None, max_length=255)

    @field_validator("shop_number", "owner_name", mode="before")
    @classmethod
    def _required(cls, v):
        if v is None:
            return None
        v = _text(v)
        if not v:
            raise ValueError("Cannot be blank")
        return v


class ShopOut(TimestampSchema):
    society_id:  UUID
    shop_number: str
    floor:       Optional[int]
    location:    Optional[str]
    area_sqft:   Optional[float]
    business_name: Optional[str]
    owner_name:  str
    owner_phone: Optional[str]
    owner_email: Optional[str]
    occupancy:   str
    tenant_name: Optional[str]
    tenant_phone: Optional[str]
    possession_date: Optional[date]
    electric_meter_no: Optional[str]
    electric_consumer_no: Optional[str]
    remarks:     Optional[str]


class ShopImportRow(BaseModel):
    """One line of the file. Everything arrives as text (or null); the service reads it the way a person typed it."""
    line:            Optional[int] = None
    shop_number:     Optional[str] = None
    owner_name:      Optional[str] = None
    owner_phone:     Optional[str] = None
    owner_email:     Optional[str] = None
    floor:           Optional[str] = None
    location:        Optional[str] = None
    area_sqft:       Optional[str] = None
    business_name:   Optional[str] = None
    occupancy:       Optional[str] = None
    tenant_name:     Optional[str] = None
    tenant_phone:    Optional[str] = None
    possession_date: Optional[str] = None          # ISO date; the app converts dd/mm/yyyy before sending
    electric_meter_no:    Optional[str] = None
    electric_consumer_no: Optional[str] = None
    remarks:         Optional[str] = None


class ShopImportRequest(BaseModel):
    society_id: Optional[UUID] = None
    rows: List[ShopImportRow] = Field(max_length=2000)
    dry_run: bool = False


class ShopImportResult(BaseModel):
    line: Optional[int]
    shop_number: Optional[str]
    status: Literal["created", "updated", "error"]
    message: Optional[str] = None
