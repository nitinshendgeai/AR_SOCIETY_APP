import datetime as dt
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_manager_above
from app.db.session import get_db
from app.models.user import User
from app.modules.checklist.services.checklist_pdf import checklist_pdf
from app.modules.checklist.services.checklist_service import ChecklistService

router = APIRouter(prefix="/manager-checklist", tags=["Manager checklist"], dependencies=[Depends(require_manager_above)])


class CompleteIn(BaseModel):
    status: str = "done"                      # done | skipped
    done_on: Optional[dt.date] = None         # the day it was actually done (default today)
    note: Optional[str] = Field(default=None, max_length=1000)
    reference: Optional[str] = Field(default=None, max_length=120)
    valid_until: Optional[dt.date] = None     # a licence or certificate: the date it runs to


class ItemIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    detail: Optional[str] = Field(default=None, max_length=2000)
    category: str = "housekeeping"
    frequency: str = "daily"
    due_weekday: Optional[int] = Field(default=None, ge=0, le=6)
    due_day: Optional[int] = Field(default=None, ge=1, le=31)
    due_months: Optional[List[int]] = None
    lead_days: int = Field(default=0, ge=0, le=365)
    asset_category: Optional[str] = None
    staff_department: Optional[str] = None
    statutory: bool = False
    legal_basis: Optional[str] = Field(default=None, max_length=1000)
    link_key: Optional[str] = Field(default=None, max_length=30)


class ItemPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    detail: Optional[str] = Field(default=None, max_length=2000)
    category: Optional[str] = None
    frequency: Optional[str] = None
    due_weekday: Optional[int] = Field(default=None, ge=0, le=6)
    due_day: Optional[int] = Field(default=None, ge=1, le=31)
    due_months: Optional[List[int]] = None
    lead_days: Optional[int] = Field(default=None, ge=0, le=365)
    asset_category: Optional[str] = None
    staff_department: Optional[str] = None
    legal_basis: Optional[str] = Field(default=None, max_length=1000)
    link_key: Optional[str] = Field(default=None, max_length=30)
    is_enabled: Optional[bool] = None


class SignoffIn(BaseModel):
    remarks: Optional[str] = Field(default=None, max_length=1000)


@router.get("/society/{society_id}/today")
def today(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Today's checklist: the routine for this society's assets and staff, what needs attention now, and the
    statutory dates falling due."""
    return ChecklistService(db).today(society_id, user)


@router.get("/society/{society_id}/today.pdf")
def today_pdf(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The same checklist on paper, with a box to tick against each line and a signature at the foot."""
    svc = ChecklistService(db)
    data = svc.today(society_id, user)
    return Response(checklist_pdf(svc._society(society_id, user), data), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="Manager-Checklist-{data["as_of"]}.pdf"'})


@router.get("/society/{society_id}/compliance")
def compliance(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ChecklistService(db).compliance(society_id, user)


@router.get("/society/{society_id}/items")
def items(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ChecklistService(db).list_items(society_id, user)


@router.post("/society/{society_id}/items", status_code=201)
def create_item(society_id: UUID, data: ItemIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ChecklistService(db).create_item(society_id, user, data.model_dump())


@router.patch("/items/{item_id}")
def update_item(item_id: UUID, data: ItemPatch, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ChecklistService(db).update_item(item_id, user, data.model_dump(exclude_unset=True))


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ChecklistService(db).delete_item(item_id, user)


@router.post("/items/{item_id}/complete")
def complete(item_id: UUID, data: CompleteIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ChecklistService(db).complete(item_id, user, data.status, data.done_on, data.note, data.reference,
                                         data.valid_until)


@router.delete("/items/{item_id}/complete", status_code=204)
def undo(item_id: UUID, for_date: dt.date = Query(...), db: Session = Depends(get_db),
         user: User = Depends(get_current_user)):
    ChecklistService(db).undo(item_id, user, for_date)


@router.post("/society/{society_id}/signoff")
def signoff(society_id: UUID, data: SignoffIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ChecklistService(db).sign_off(society_id, user, data.remarks)


@router.get("/society/{society_id}/history")
def history(society_id: UUID, days: int = 30, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ChecklistService(db).history(society_id, user, days)
