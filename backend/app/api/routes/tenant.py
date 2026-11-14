from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Literal, Optional
from uuid import UUID

from app.db.session import get_db
from app.schemas.tenant import (
    TenantCreate, TenantUpdate, TenantOut, TenantCreateOut, AgreementRenewalRequest,
)
from app.schemas.agreement import AgreementOut
from app.services.tenant_service import TenantService
from app.services.tenant_import import TenantImportRequest, TenantImportResult, import_tenants
from app.core.dependencies import require_admin_committee, require_manager_above, get_current_user
from app.core.privacy import TENANT_PRIVATE_FIELDS, hide_private
from app.models.user import User

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post("/", response_model=TenantCreateOut, status_code=201)
def create_tenant(data: TenantCreate, db: Session = Depends(get_db),
                   current_user: User = Depends(require_admin_committee)):
    return TenantService(db).create(data, current_user)


@router.post("/import", response_model=List[TenantImportResult])
def import_tenants_file(data: TenantImportRequest, db: Session = Depends(get_db),
                        current_user: User = Depends(require_admin_committee)):
    """Add tenants from a file: one row per let-out flat, with the agreement, the rent and the channel the agreement
    came through. A row for a tenant already in the flat is skipped; a bad row is reported and the rest go in.
    `dry_run` checks every row and writes nothing."""
    return import_tenants(db, data.rows, data.dry_run, current_user)


@router.get("/", response_model=List[TenantOut])
def list_tenants(
    flat_id: Optional[UUID] = None,
    wing_id: Optional[UUID] = None,
    is_active: Optional[bool] = True,
    moved_in: Optional[bool] = Query(None, description="true: living there now; false: no move-in date yet"),
    agreement: Optional[Literal["running", "expiring", "expired", "none"]] = Query(
        None, description="By the agreement's end date: running, expiring (within 30 days), expired, none on record"),
    police: Optional[Literal["pending", "submitted", "verified", "rejected"]] = None,
    kyc_verified: Optional[bool] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = TenantService(db).list(
        current_user, flat_id=flat_id, is_active=is_active, search=search, skip=skip, limit=limit,
        wing_id=wing_id, moved_in=moved_in, agreement=agreement, police=police, kyc_verified=kyc_verified,
    )
    return [hide_private(t, current_user, TENANT_PRIVATE_FIELDS) for t in rows]


@router.get("/count", response_model=dict)
def count_tenants(
    flat_id: Optional[UUID] = None,
    wing_id: Optional[UUID] = None,
    is_active: Optional[bool] = True,
    moved_in: Optional[bool] = Query(None, description="true: living there now; false: no move-in date yet"),
    agreement: Optional[Literal["running", "expiring", "expired", "none"]] = Query(
        None, description="By the agreement's end date: running, expiring (within 30 days), expired, none on record"),
    police: Optional[Literal["pending", "submitted", "verified", "rejected"]] = None,
    kyc_verified: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """How many tenants match the same filters as the list (no paging): {"count": n}."""
    return {"count": TenantService(db).count(
        current_user, flat_id=flat_id, is_active=is_active, search=search, wing_id=wing_id, moved_in=moved_in,
        agreement=agreement, police=police, kyc_verified=kyc_verified)}


_AGREEMENT_WORDS = {"running": "agreement running", "expiring": "agreement expiring in 30 days",
                    "expired": "agreement expired", "none": "no agreement end date"}
REPORT_MAX_ROWS = 5000


@router.get("/report.pdf")
def tenants_report_pdf(
    flat_id: Optional[UUID] = None,
    wing_id: Optional[UUID] = None,
    is_active: Optional[bool] = True,
    moved_in: Optional[bool] = Query(None, description="true: living there now; false: no move-in date yet"),
    agreement: Optional[Literal["running", "expiring", "expired", "none"]] = None,
    police: Optional[Literal["pending", "submitted", "verified", "rejected"]] = None,
    kyc_verified: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_above),
):
    """The printed Tenants report: every tenant the list would show for the same filters (no paging, up to
    5,000), as a PDF. Office roles only, because it carries phone numbers and rent."""
    from app.models.flat import Flat
    from app.models.society import Society
    from app.models.wing import Wing
    from app.modules.billing.services.bill_pdf import flat_label
    from app.services.tenant_report_pdf import render_tenants_pdf

    tenants = TenantService(db).list(
        current_user, flat_id=flat_id, is_active=is_active, search=search, skip=0, limit=REPORT_MAX_ROWS,
        wing_id=wing_id, moved_in=moved_in, agreement=agreement, police=police, kyc_verified=kyc_verified,
    )
    flats = {f.id: f for f in db.query(Flat).filter(Flat.id.in_({t.flat_id for t in tenants})).all()} if tenants else {}
    rows = [{
        "name": t.full_name, "flat": flat_label(flats.get(t.flat_id)), "phone": t.phone, "email": t.email,
        "rent": t.monthly_rent, "moved_in": t.move_in_date, "agreement_end": t.agreement_end_date,
        "police": t.police_verification_status.value if t.police_verification_status else None,
        "kyc": t.kyc_verified,
    } for t in tenants]
    rows.sort(key=lambda r: (r["flat"], r["name"].lower()))

    filters = ["current tenants" if is_active else ("former tenants" if is_active is False else "current and former")]
    if wing_id:
        wing = db.query(Wing).filter(Wing.id == wing_id, Wing.society_id == current_user.society_id).first()
        filters.append(f"wing {wing.name}" if wing else "one wing")
    if flat_id and flats.get(flat_id):
        filters.append(f"flat {flat_label(flats[flat_id])}")
    if moved_in is not None:
        filters.append("moved in" if moved_in else "not moved in yet")
    if agreement:
        filters.append(_AGREEMENT_WORDS[agreement])
    if police:
        filters.append(f"police verification {police}")
    if kyc_verified is not None:
        filters.append("KYC verified" if kyc_verified else "KYC not verified")
    if search and search.strip():
        filters.append(f'search "{search.strip()}"')

    society = db.query(Society).filter(Society.id == current_user.society_id).first()
    return Response(content=render_tenants_pdf(rows, filters, society), media_type="application/pdf",
                    headers={"Content-Disposition": "inline; filename=Tenants-Report.pdf"})


@router.get("/{tenant_id}", response_model=TenantOut)
def get_tenant(tenant_id: UUID, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    return hide_private(TenantService(db).get_or_404(tenant_id, current_user), current_user, TENANT_PRIVATE_FIELDS)


@router.patch("/{tenant_id}", response_model=TenantOut)
def update_tenant(tenant_id: UUID, data: TenantUpdate, db: Session = Depends(get_db),
                   current_user: User = Depends(require_admin_committee)):
    return TenantService(db).update(tenant_id, data, current_user)


@router.get("/{tenant_id}/agreements", response_model=List[AgreementOut])
def list_tenant_agreements(tenant_id: UUID, db: Session = Depends(get_db),
                            current_user: User = Depends(require_manager_above)):
    """Phase M1.4-R — full agreement history for a tenant (current +
    historical), newest start_date first. Read access mirrors get_tenant/
    list_tenants (any authenticated same-society member), not admin-gated."""
    return TenantService(db).list_agreements(tenant_id, current_user)


@router.post("/{tenant_id}/renew-agreement", response_model=AgreementOut, status_code=201)
def renew_agreement(tenant_id: UUID, data: AgreementRenewalRequest, db: Session = Depends(get_db),
                     current_user: User = Depends(require_admin_committee)):
    return TenantService(db).renew_agreement(
        tenant_id, data.start_date, data.end_date, current_user,
        monthly_rent=data.monthly_rent, security_deposit=data.security_deposit,
        document_url=data.document_url, channel=data.channel, channel_name=data.channel_name,
    )
