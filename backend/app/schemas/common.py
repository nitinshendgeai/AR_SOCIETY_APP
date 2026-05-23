from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Generic, List, Optional, TypeVar

T = TypeVar("T")


class OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampSchema(OrmBase):
    id:         UUID
    created_at: datetime
    updated_at: datetime
    is_active:  bool


class PaginatedResponse(BaseModel, Generic[T]):
    items:   List[T]
    total:   int
    page:    int
    size:    int
    pages:   int
