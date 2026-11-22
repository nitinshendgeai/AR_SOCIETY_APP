from datetime import date
from typing import Literal, Optional
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas import validators as val
from app.schemas.common import OrmBase

FamilyRelation = Literal["spouse", "child", "parent", "sibling", "other"]


class TenantFamilyCreate(OrmBase):
    full_name:     str = Field(min_length=1, max_length=255)
    relation:      Optional[FamilyRelation] = None
    phone:         Optional[str] = None
    date_of_birth: Optional[date] = None

    _name = field_validator("full_name", mode="before")(val.name)
    _phone = field_validator("phone", mode="before")(val.mobile)
    _dob = field_validator("date_of_birth")(val.birth_date)


class TenantFamilyOut(OrmBase):
    id:            UUID
    tenant_id:     UUID
    full_name:     str
    relation:      Optional[str] = None
    phone:         Optional[str] = None
    date_of_birth: Optional[date] = None
