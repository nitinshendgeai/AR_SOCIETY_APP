from typing import Optional
from uuid import UUID
from app.schemas.common import OrmBase, TimestampSchema


class WingCreate(OrmBase):
    name:         str
    code:         Optional[str] = None
    total_floors: Optional[int] = None
    society_id:   UUID


class WingUpdate(OrmBase):
    name:         Optional[str] = None
    code:         Optional[str] = None
    total_floors: Optional[int] = None


class WingOut(TimestampSchema):
    name:         str
    code:         Optional[str]
    total_floors: Optional[int]
    society_id:   UUID
