"""
Reusable response helpers for all route handlers.
Use these instead of returning raw dicts or models directly.
"""
from typing import Any, Optional, Type, TypeVar
from fastapi.responses import JSONResponse
from app.schemas.common import SuccessResponse, ErrorResponse, ErrorDetail

T = TypeVar("T")


def success(data: Any = None, message: str = "OK", status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=SuccessResponse(data=data, message=message).model_dump(mode="json"),
    )


def created(data: Any = None, message: str = "Created") -> JSONResponse:
    return success(data=data, message=message, status_code=201)


def error(message: str, status_code: int = 400, code: str = None, errors: list = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            message=message,
            code=code,
            errors=[ErrorDetail(**e) if isinstance(e, dict) else e for e in (errors or [])],
        ).model_dump(mode="json"),
    )


def not_found(entity: str = "Resource") -> JSONResponse:
    return error(f"{entity} not found", status_code=404, code="NOT_FOUND")


def forbidden(message: str = "Access denied") -> JSONResponse:
    return error(message, status_code=403, code="FORBIDDEN")


def unauthorized(message: str = "Authentication required") -> JSONResponse:
    return error(message, status_code=401, code="UNAUTHORIZED")
