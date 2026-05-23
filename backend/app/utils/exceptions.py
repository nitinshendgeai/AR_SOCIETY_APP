"""
Global exception handlers — registered in main.py.
Converts all known error types to standard ErrorResponse format.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from app.schemas.common import ErrorResponse, ErrorDetail
import logging

logger = logging.getLogger(__name__)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        field = ".".join(str(l) for l in err.get("loc", []) if l != "body")
        errors.append(ErrorDetail(field=field or None, message=err["msg"]))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            message="Validation failed",
            code="VALIDATION_ERROR",
            errors=errors,
        ).model_dump(mode="json"),
    )


async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.error(f"DB IntegrityError: {exc}")
    msg = "A record with this data already exists."
    if "unique" in str(exc.orig).lower():
        msg = "Duplicate entry — this value already exists."
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=ErrorResponse(message=msg, code="CONFLICT").model_dump(mode="json"),
    )


async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            message="An internal server error occurred.",
            code="INTERNAL_ERROR",
        ).model_dump(mode="json"),
    )
