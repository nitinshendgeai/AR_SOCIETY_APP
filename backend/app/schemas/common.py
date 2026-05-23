from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Any, Generic, List, Optional, TypeVar

T = TypeVar("T")


class OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampSchema(OrmBase):
    id:         UUID
    created_at: datetime
    updated_at: datetime
    is_active:  bool


# ── Standard API response envelopes ──────────────────────────────────────────

class SuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str  = "OK"
    data:    Optional[T] = None

    @classmethod
    def of(cls, data: T, message: str = "OK") -> "SuccessResponse[T]":
        return cls(data=data, message=message)


class ErrorDetail(BaseModel):
    field:   Optional[str] = None
    message: str


class ErrorResponse(BaseModel):
    success: bool          = False
    message: str
    errors:  List[ErrorDetail] = []
    code:    Optional[str] = None


class PaginatedResponse(BaseModel, Generic[T]):
    success: bool    = True
    items:   List[T]
    total:   int
    page:    int
    size:    int
    pages:   int

    @classmethod
    def build(cls, items: List[T], total: int, page: int, size: int) -> "PaginatedResponse[T]":
        import math
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=max(1, math.ceil(total / size)) if size else 1,
        )
