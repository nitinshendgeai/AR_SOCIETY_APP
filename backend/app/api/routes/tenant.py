from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
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
    is_active: Optional[bool] = True,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = TenantService(db).list(
        current_user, flat_id=flat_id, is_active=is_active, search=search, skip=skip, limit=limit,
    )
    return [hide_private(t, current_user, TENANT_PRIVATE_FIELDS) for t in rows]


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
