"""
AuditService — reusable across all ERP modules.

Usage:
    AuditService.log(
        db=db,
        action=AuditAction.CREATE,
        module="society",
        entity_id=str(society.id),
        entity_type="Society",
        new_values={"name": society.name},
        user=current_user,
        request=request,
    )
"""
import enum
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Any
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import Request

from app.models.audit_log import AuditLog, AuditAction
from app.models.user import User

logger = logging.getLogger(__name__)


def _jsonable(value: Any) -> Any:
    """Audit values hold whatever the caller had to hand — dates, amounts,
    ids, enums — and are stored as JSON."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, enum.Enum):
        return _jsonable(value.value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    return value


class AuditService:

    @staticmethod
    def log(
        db:          Session,
        action:      AuditAction,
        module:      str,
        entity_id:   Optional[str]  = None,
        entity_type: Optional[str]  = None,
        old_values:  Optional[dict] = None,
        new_values:  Optional[dict] = None,
        notes:       Optional[str]  = None,
        user:        Optional[User] = None,
        request:     Optional[Any]  = None,   # FastAPI Request
    ) -> Optional[AuditLog]:
        """Create an audit log entry. Never raises — logs errors silently."""
        try:
            entry = AuditLog(
                user_id     = user.id    if user else None,
                user_email  = user.email if user else None,
                action      = action,
                module      = module,
                entity_id   = str(entity_id) if entity_id else None,
                entity_type = entity_type,
                old_values  = _jsonable(old_values),
                new_values  = _jsonable(new_values),
                notes       = notes,
                ip_address  = AuditService._get_ip(request),
                user_agent  = AuditService._get_ua(request),
            )
            db.add(entry)
            db.commit()
            return entry
        except Exception as e:
            logger.error(f"[audit] Failed to write audit log: {e}")
            db.rollback()
            return None

    @staticmethod
    def _get_ip(request: Optional[Any]) -> Optional[str]:
        if not request:
            return None
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return getattr(request.client, "host", None)

    @staticmethod
    def _get_ua(request: Optional[Any]) -> Optional[str]:
        if not request:
            return None
        return request.headers.get("User-Agent", "")[:500]
