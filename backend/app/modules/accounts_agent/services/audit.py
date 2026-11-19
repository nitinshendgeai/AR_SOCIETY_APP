"""Append-only audit trail of agent and reviewer actions. Never logs amounts or narrations in application logs; the
trail itself stores ids, statuses and short reasons."""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.accounts_agent.models.agent import AgentAuditLog


def record(db: Session, society_id: UUID, action: str, entity_type: str, entity_id=None,
           actor_id: Optional[UUID] = None, details: Optional[dict] = None) -> AgentAuditLog:
    row = AgentAuditLog(society_id=society_id, actor_id=actor_id, action=action, entity_type=entity_type,
                        entity_id=str(entity_id) if entity_id else None, details=details)
    db.add(row)
    return row
