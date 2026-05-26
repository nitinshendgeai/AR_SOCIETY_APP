from typing import List
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User
from app.services.occupancy_service import OccupancyService
from app.schemas.common import OrmBase, TimestampSchema
from app.models.occupancy_log import OccupancyEventType
from app.models.agreement_tracker import AgreementStatus

router = APIRouter(prefix="/occupancy", tags=["Occupancy & Agreement Tracking"])

committee_or_admin = require_roles("Admin", "Committee")
any_member         = require_roles("Admin", "Committee", "Resident")


class MoveInRequest(OrmBase):
    flat_id: UUID; resident_id: UUID; move_in_date: date

class MoveOutRequest(OrmBase):
    flat_id: UUID; resident_id: UUID; move_out_date: date

class TenantMoveInRequest(OrmBase):
    flat_id: UUID; tenant_id: UUID; move_in_date: date; create_agreement: bool = True

class TenantMoveOutRequest(OrmBase):
    flat_id: UUID; tenant_id: UUID; move_out_date: date


class OccupancyLogOut(TimestampSchema):
    flat_id: UUID; event_type: OccupancyEventType; event_date: date
    resident_id: Optional[UUID]; tenant_id: Optional[UUID]; notes: Optional[str]


class AgreementOut(TimestampSchema):
    flat_id: UUID; tenant_id: UUID; start_date: date; end_date: date
    status: AgreementStatus; monthly_rent: Optional[float]
    alert_sent_30: bool; alert_sent_7: bool


@router.post("/resident/move-in", dependencies=[Depends(committee_or_admin)])
def resident_move_in(data: MoveInRequest, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    return OccupancyService(db).resident_move_in(data.flat_id, data.resident_id, data.move_in_date, user)


@router.post("/resident/move-out", dependencies=[Depends(committee_or_admin)])
def resident_move_out(data: MoveOutRequest, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    return OccupancyService(db).resident_move_out(data.flat_id, data.resident_id, data.move_out_date, user)


@router.post("/tenant/move-in", dependencies=[Depends(committee_or_admin)])
def tenant_move_in(data: TenantMoveInRequest, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return OccupancyService(db).tenant_move_in(data.flat_id, data.tenant_id,
                                                data.move_in_date, user, data.create_agreement)


@router.post("/tenant/move-out", dependencies=[Depends(committee_or_admin)])
def tenant_move_out(data: TenantMoveOutRequest, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    return OccupancyService(db).tenant_move_out(data.flat_id, data.tenant_id, data.move_out_date, user)


@router.get("/flat/{flat_id}/history", response_model=List[OccupancyLogOut],
            dependencies=[Depends(any_member)])
def flat_history(flat_id: UUID, db: Session = Depends(get_db)):
    return OccupancyService(db).get_flat_history(flat_id)


@router.get("/agreements/expiring/{society_id}", response_model=List[AgreementOut],
            dependencies=[Depends(committee_or_admin)])
def expiring_agreements(society_id: UUID,
                        days: int = Query(30, description="Look-ahead days"),
                        db: Session = Depends(get_db)):
    return OccupancyService(db).get_expiring_agreements(society_id, days)
