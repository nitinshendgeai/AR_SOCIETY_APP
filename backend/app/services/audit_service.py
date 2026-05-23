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
import logging
from typing import Optional, Any
from sqlalchemy.orm import Session
from fastapi import Request

from app.models.audit_log import AuditLog, AuditAction
from app.models.user import User

logger = logging.getLogger(__name__)


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
                old_values  = old_values,
                new_values  = new_values,
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
