from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin_committee, require_security
from app.core.tenant_scope import assert_society_access
from app.db.session import get_db
from app.models.user import User
from app.modules.dashboard.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/society/{society_id}", dependencies=[Depends(require_admin_committee)])
def society_dashboard(society_id: UUID, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """What the office needs at a glance: money, collection trend, occupancy and
    the items waiting on someone. Admin and committee only; own society only."""
    assert_society_access(user, society_id)
    return DashboardService(db).society(society_id)


@router.get("/security/{society_id}", dependencies=[Depends(require_security)])
def security_dashboard(society_id: UUID, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """The gate at a glance: visitors logged today, let in today, and inside now. Same roles as the visitor log
    (admin, committee, manager, security supervisor and staff); own society only. Counts only - no visitor details."""
    assert_society_access(user, society_id)
    return DashboardService(db).security(society_id)
