from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin_committee, require_any_member
from app.db.session import get_db
from app.models.flat import Flat
from app.models.society import Society
from app.models.user import User
from app.modules.certificates.models.certificates import CERTIFICATE_KINDS
from app.modules.certificates.services.certificate_pdf import generate_certificate_pdf
from app.modules.certificates.services.certificate_pdf_deva import generate_deva_certificate_pdf, supported
from app.modules.certificates.services.certificate_service import CertificateService
from fastapi import HTTPException

router = APIRouter(prefix="/certificates", tags=["Certificates"])


class CertificateIn(BaseModel):
    kind: str
    purpose: Optional[str] = Field(default=None, max_length=1000)
    party_name: Optional[str] = Field(default=None, max_length=200)
    flat_id: Optional[UUID] = None             # the office asking on a member's behalf
    applicant_name: Optional[str] = Field(default=None, max_length=200)


class DecisionIn(BaseModel):
    approve: bool
    note: Optional[str] = Field(default=None, max_length=1000)
    override_dues: bool = False


@router.get("/kinds", dependencies=[Depends(require_any_member)])
def kinds():
    return [{"kind": k, "title": v[0], "needs_clear_dues": v[2]} for k, v in CERTIFICATE_KINDS.items()]


@router.post("/society/{society_id}", status_code=201, dependencies=[Depends(require_any_member)])
def request_certificate(society_id: UUID, data: CertificateIn, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    svc = CertificateService(db)
    return svc.out(svc.create(society_id, data.model_dump(), user))


@router.get("/society/{society_id}", dependencies=[Depends(require_any_member)])
def list_certificates(society_id: UUID, status: Optional[str] = None, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    svc = CertificateService(db)
    return [svc.out(r) for r in svc.list(society_id, user, status)]


@router.get("/{request_id}", dependencies=[Depends(require_any_member)])
def get_certificate(request_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = CertificateService(db)
    return svc.out(svc.get(request_id, user))


@router.post("/{request_id}/decision", dependencies=[Depends(require_admin_committee)])
def decide(request_id: UUID, data: DecisionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = CertificateService(db)
    return svc.out(svc.decide(request_id, user, data.approve, data.note, data.override_dues))


@router.post("/{request_id}/cancel", dependencies=[Depends(require_any_member)])
def cancel(request_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = CertificateService(db)
    return svc.out(svc.cancel(request_id, user))


@router.get("/{request_id}/pdf", dependencies=[Depends(require_any_member)])
def certificate_pdf(request_id: UUID, lang: str = "en", db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """The certificate as a PDF: lang=en (default), hi (Hindi) or mr (Marathi)."""
    if lang != "en" and not supported(lang):
        raise HTTPException(422, "Language must be en, hi or mr")
    req = CertificateService(db).get(request_id, user)
    if req.status != "approved":
        raise HTTPException(409, "The certificate can be downloaded only once the request is approved")
    society = db.query(Society).filter(Society.id == req.society_id).first()
    flat = db.query(Flat).filter(Flat.id == req.flat_id).first()
    name = (req.certificate_no or "certificate").replace("/", "-")
    pdf = (generate_deva_certificate_pdf(req, society, flat, lang) if supported(lang)
           else generate_certificate_pdf(req, society, flat))
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={name}{'' if lang == 'en' else '-' + lang}.pdf"})
