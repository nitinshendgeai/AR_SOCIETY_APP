import datetime as dt
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin_committee, require_any_member, require_security
from app.db.session import get_db
from app.models.society import Society
from app.models.user import User
from app.modules.gate.services.gate_service import GateService
from app.modules.gate.services.pass_pdf import generate_pass_pdf

router = APIRouter(prefix="/gate", tags=["Gate"])

member = Depends(require_any_member)
gate = Depends(require_security)
office = Depends(require_admin_committee)


# ── Parcels ───────────────────────────────────────────────────────────────────

class ParcelIn(BaseModel):
    flat_id: UUID
    courier: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=255)
    recipient_name: Optional[str] = Field(default=None, max_length=120)


class HandOverIn(BaseModel):
    collected_by_name: Optional[str] = Field(default=None, max_length=120)


class ReturnIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)


@router.post("/parcels/society/{society_id}", status_code=201, dependencies=[gate])
def log_parcel(society_id: UUID, data: ParcelIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = GateService(db)
    return svc.parcel_out(svc.log_parcel(society_id, data.model_dump(), user))


@router.get("/parcels/society/{society_id}", dependencies=[member])
def list_parcels(society_id: UUID, status: Optional[str] = None, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    svc = GateService(db)
    return [svc.parcel_out(p) for p in svc.list_parcels(society_id, user, status)]


@router.post("/parcels/{parcel_id}/collect", dependencies=[member])
def collect_parcel(parcel_id: UUID, data: HandOverIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    svc = GateService(db)
    return svc.parcel_out(svc.hand_over(parcel_id, user, data.collected_by_name))


@router.post("/parcels/{parcel_id}/return", dependencies=[gate])
def return_parcel(parcel_id: UUID, data: ReturnIn, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    svc = GateService(db)
    return svc.parcel_out(svc.return_parcel(parcel_id, user, data.note))


# ── Domestic help ─────────────────────────────────────────────────────────────

class HelpIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    mobile: str = Field(min_length=7, max_length=20)
    kind: str = "maid"
    id_proof: Optional[str] = Field(default=None, max_length=120)
    flat_ids: Optional[List[UUID]] = None
    police_verified: bool = False
    valid_until: Optional[dt.date] = None


class ApproveIn(BaseModel):
    valid_until: Optional[dt.date] = None
    police_verified: Optional[bool] = None


class StatusIn(BaseModel):
    status: str
    note: Optional[str] = Field(default=None, max_length=500)


class RenewIn(BaseModel):
    valid_until: Optional[dt.date] = None


@router.post("/help/society/{society_id}", status_code=201, dependencies=[member])
def register_help(society_id: UUID, data: HelpIn, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    svc = GateService(db)
    return svc.help_out(svc.register_help(society_id, data.model_dump(), user))


@router.get("/help/society/{society_id}", dependencies=[member])
def list_help(society_id: UUID, status: Optional[str] = None, q: Optional[str] = None, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    svc = GateService(db)
    return [svc.help_out(h) for h in svc.list_help(society_id, user, status, q)]


@router.get("/help/society/{society_id}/inside", dependencies=[gate])
def help_inside(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = GateService(db)
    return [svc.help_out(h) for h in svc.inside(society_id, user)]


@router.post("/help/{help_id}/approve", dependencies=[office])
def approve_help(help_id: UUID, data: ApproveIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = GateService(db)
    return svc.help_out(svc.approve_help(help_id, user, data.valid_until, data.police_verified))


@router.post("/help/{help_id}/status", dependencies=[office])
def set_help_status(help_id: UUID, data: StatusIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    svc = GateService(db)
    return svc.help_out(svc.set_help_status(help_id, user, data.status, data.note))


@router.post("/help/{help_id}/renew", dependencies=[office])
def renew_help(help_id: UUID, data: RenewIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = GateService(db)
    return svc.help_out(svc.renew_help(help_id, user, data.valid_until))


@router.delete("/help/{help_id}/flats/{flat_id}", dependencies=[member])
def remove_flat(help_id: UUID, flat_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = GateService(db)
    return svc.help_out(svc.remove_flat(help_id, flat_id, user))


@router.post("/help/{help_id}/scan", dependencies=[gate])
def scan(help_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return GateService(db).gate_scan(help_id, user)


@router.get("/help/{help_id}/entries", dependencies=[member])
def entries(help_id: UUID, days: int = 30, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [{"in_at": e.in_at, "out_at": e.out_at}
            for e in GateService(db).entries(help_id, user, max(1, min(days, 365)))]


@router.get("/help/{help_id}/pass", dependencies=[member])
def pass_pdf(help_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = GateService(db)
    h = svc._help(help_id, user)
    if h.status != "active" or not h.pass_no:
        raise HTTPException(409, "A pass is printed only once it is approved")
    society = db.query(Society).filter(Society.id == h.society_id).first()
    labels = [x["label"] for x in svc.help_out(h)["flats"]]
    return Response(content=generate_pass_pdf(h, society, labels), media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={h.pass_no}.pdf"})
