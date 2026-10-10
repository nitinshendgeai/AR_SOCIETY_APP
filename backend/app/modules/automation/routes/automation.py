from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin_committee
from app.core.tenant_scope import assert_society_access
from app.db.session import get_db
from app.models.user import User
from app.modules.automation.services.automation_service import AutomationService, JOB_BY_KEY

router = APIRouter(prefix="/automation", tags=["Automation"])


class AutomationUpdate(BaseModel):
    dues_reminders: Optional[bool] = None
    reminder_every_days: Optional[int] = Field(default=None, ge=1, le=90)
    reminder_min_months: Optional[int] = Field(default=None, ge=0, le=24)
    agreement_alerts: Optional[bool] = None
    asset_alerts: Optional[bool] = None
    billing_nudge: Optional[bool] = None
    visitor_expiry: Optional[bool] = None


class RunRequest(BaseModel):
    job: str


@router.get("/{society_id}", dependencies=[Depends(require_admin_committee)])
def get_automation(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    return AutomationService(db).overview(society_id)


@router.put("/{society_id}", dependencies=[Depends(require_admin_committee)])
def update_automation(society_id: UUID, data: AutomationUpdate, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    assert_society_access(user, society_id)
    svc = AutomationService(db)
    svc.update_settings(society_id, data.model_dump(exclude_unset=True))
    return svc.overview(society_id)


@router.post("/{society_id}/run", dependencies=[Depends(require_admin_committee)])
def run_now(society_id: UUID, data: RunRequest, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    """Run one task now, whatever its schedule. Recorded as a manual run."""
    assert_society_access(user, society_id)
    if data.job not in JOB_BY_KEY:
        raise HTTPException(422, "Unknown task")
    run = AutomationService(db).run_job(society_id, data.job, manual=True)
    if run is None:
        raise HTTPException(409, "This task is already running")
    return {"status": run.status, "summary": run.summary}
