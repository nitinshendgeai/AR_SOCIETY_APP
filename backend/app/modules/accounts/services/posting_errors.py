from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.accounts.models.posting_errors import AccountingPostingError, POSTING_ERROR_STATUSES


class AccountingPostingErrorService:
    """First-class exception queue for operational-to-GL posting failures."""

    def __init__(self, db: Session):
        self.db = db

    def record(self, society_id: UUID, source_type: str, source_id: UUID,
               operation: str, exc: Exception, *, voucher_id: Optional[UUID] = None) -> AccountingPostingError:
        now = datetime.utcnow()
        row = self.db.query(AccountingPostingError).filter(
            AccountingPostingError.society_id == society_id,
            AccountingPostingError.source_type == source_type,
            AccountingPostingError.source_id == source_id,
            AccountingPostingError.operation == operation,
        ).first()
        if row:
            row.last_failed_at = now
            row.retry_count = (row.retry_count or 0) + 1
            row.error_message = str(exc)[:10000]
            row.status = "OPEN"
            if voucher_id:
                row.last_voucher_id = voucher_id
        else:
            row = AccountingPostingError(
                society_id=society_id,
                source_type=source_type,
                source_id=source_id,
                operation=operation,
                error_code=type(exc).__name__,
                error_message=str(exc)[:10000],
                first_failed_at=now,
                last_failed_at=now,
                retry_count=1,
                status="OPEN",
                last_voucher_id=voucher_id,
            )
            self.db.add(row)
        self.db.flush()
        return row

    def resolve(self, society_id: UUID, source_type: str, source_id: UUID,
                operation: str, user_id: Optional[UUID] = None, note: str = "Posting succeeded") -> None:
        row = self.db.query(AccountingPostingError).filter(
            AccountingPostingError.society_id == society_id,
            AccountingPostingError.source_type == source_type,
            AccountingPostingError.source_id == source_id,
            AccountingPostingError.operation == operation,
            AccountingPostingError.status.in_(("OPEN", "RETRYING")),
        ).first()
        if row:
            row.status = "RESOLVED"
            row.resolved_at = datetime.utcnow()
            row.resolved_by = user_id
            row.resolution_note = note
            self.db.flush()

    def list(self, society_id: UUID, status: Optional[str] = None, limit: int = 100):
        q = self.db.query(AccountingPostingError).filter(
            AccountingPostingError.society_id == society_id
        )
        if status:
            status = status.upper()
            if status not in POSTING_ERROR_STATUSES:
                raise ValueError("Invalid posting error status")
            q = q.filter(AccountingPostingError.status == status)
        return q.order_by(AccountingPostingError.last_failed_at.desc()).limit(limit).all()
