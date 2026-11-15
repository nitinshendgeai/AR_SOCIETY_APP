from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import _user_has_permission, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.modules.gym.services.gym_service import GymService

GYM_TRAINER = "Gym Trainer"


def require_gym_desk(user: User = Depends(get_current_user)) -> User:
    """The Gym Trainer keeps the book; the Manager, the Society Admin and the committee can see and keep it too."""
    names = {ur.role.name for ur in user.user_roles if ur.role}
    if GYM_TRAINER in names or _user_has_permission(user, "manager_above"):
        return user
    raise HTTPException(403, "The gym attendance book is kept by the Gym Trainer, the Manager and the committee")


router = APIRouter(prefix="/gym", tags=["Gym"], dependencies=[Depends(require_gym_desk)])


class CheckInIn(BaseModel):
    flat_id: UUID
    resident_ids: List[UUID] = Field(min_length=1, max_length=20)


class CheckOutIn(BaseModel):
    visit_ids: List[UUID] = Field(min_length=1, max_length=200)


@router.get("/flats/{flat_id}/members")
def flat_members(flat_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The members of one flat who may use the gym (the owners' side only), and who of them is inside now."""
    return GymService(db, user).members(flat_id)


@router.post("/check-in")
def check_in(data: CheckInIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return GymService(db, user).check_in(data.flat_id, data.resident_ids)


@router.post("/check-out")
def check_out(data: CheckOutIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return GymService(db, user).check_out(data.visit_ids)


@router.post("/check-out-all")
def check_out_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Closing time: everyone still inside (and anyone left open from an earlier day) is ticked out."""
    return GymService(db, user).check_out_all()


@router.get("/live")
def live(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Who is inside now, and how many came and left today."""
    return GymService(db, user).live()


@router.get("/report")
def report(period: str = Query("week", pattern="^(week|month)$"), on: Optional[date] = None,
           format: str = Query("json", pattern="^(json|pdf)$"),
           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The week (Monday to Sunday) or the calendar month that contains `on` (today by default): visits, who came and how
    often, and day by day. `format=pdf` is the printed report."""
    svc = GymService(db, user)
    data = svc.report(period, on)
    if format == "pdf":
        from app.models.society import Society
        from app.modules.gym.services.gym_report_pdf import render_gym_report_pdf
        society = db.query(Society).filter(Society.id == user.society_id).first()
        return Response(content=render_gym_report_pdf(data, society), media_type="application/pdf",
                        headers={"Content-Disposition": f"inline; filename=Gym-{period}-{data['from']}.pdf"})
    return data
