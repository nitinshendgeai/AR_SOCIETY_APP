from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin_committee
from app.db.session import get_db
from app.models.user import User
from app.modules.shops.schemas.shop import (
    ShopCreate, ShopImportRequest, ShopImportResult, ShopOut, ShopUpdate,
)
from app.modules.shops.services.shop_service import ShopService

router = APIRouter(prefix="/shops", tags=["Shops"])

# The shop master (owners, possession dates, meters) is the committee's record.
committee_or_admin = require_admin_committee


@router.post("/", response_model=ShopOut, status_code=201, dependencies=[Depends(committee_or_admin)])
def create_shop(data: ShopCreate, request: Request, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    return ShopService(db).create(data, user, request)


@router.post("/import", response_model=List[ShopImportResult], dependencies=[Depends(committee_or_admin)])
def import_shops(data: ShopImportRequest, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """Add shops from a file, or fill in the ones that exist. `dry_run` checks every row and writes nothing."""
    return ShopService(db).import_rows(data.society_id, data.rows, data.dry_run, user, request)


@router.get("/society/{society_id}", response_model=List[ShopOut], dependencies=[Depends(committee_or_admin)])
def list_shops(society_id: UUID, q: Optional[str] = None, occupancy: Optional[str] = Query(None),
               include_inactive: bool = False, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    return ShopService(db).list(society_id, user, q, occupancy, include_inactive)


@router.get("/{shop_id}", response_model=ShopOut, dependencies=[Depends(committee_or_admin)])
def get_shop(shop_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ShopService(db).get(shop_id, user)


@router.patch("/{shop_id}", response_model=ShopOut, dependencies=[Depends(committee_or_admin)])
def update_shop(shop_id: UUID, data: ShopUpdate, request: Request, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    return ShopService(db).update(shop_id, data, user, request)


@router.delete("/{shop_id}", status_code=204, dependencies=[Depends(committee_or_admin)])
def delete_shop(shop_id: UUID, request: Request, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    ShopService(db).delete(shop_id, user, request)
