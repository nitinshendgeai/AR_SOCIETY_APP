"""
Global exception handlers — registered in main.py.
Converts all known error types to standard ErrorResponse format.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
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


# Postgres "undefined table" / "undefined column": the code is newer than the
# database — a deploy whose migrations haven't run.
_SCHEMA_BEHIND_CODES = {"42P01", "42703"}


def schema_behind(exc: Exception) -> bool:
    if isinstance(exc, ProgrammingError):
        return getattr(exc.orig, "pgcode", None) in _SCHEMA_BEHIND_CODES
    if isinstance(exc, OperationalError):
        text = str(exc.orig).lower()
        return "no such table" in text or "no such column" in text
    return False


def error_response(exc: Exception) -> JSONResponse:
    """The JSON reply for an exception no route handled."""
    if schema_behind(exc):
        logger.error(f"Database schema is behind the code (run `alembic upgrade head`): {exc}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                message="The server's database hasn't been updated for this version of the app. "
                        "Ask the administrator to run the pending database update.",
                code="SCHEMA_OUTDATED",
            ).model_dump(mode="json"),
        )
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            message="An internal server error occurred.",
            code="INTERNAL_ERROR",
        ).model_dump(mode="json"),
    )


async def generic_exception_handler(request: Request, exc: Exception):
    return error_response(exc)
