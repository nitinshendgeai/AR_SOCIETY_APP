from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User
from app.modules.inventory.schemas.inventory import (
    CategoryCreate, CategoryOut, ItemCreate, ItemUpdate, ItemOut,
    StockInRequest, StockAdjustRequest, StockOut, TransactionOut,
    IssueCreate, IssueOut, ReturnCreate,
    AssetCreate, AssetUpdate, AssetOut, AssetAssignRequest,
    MaintenanceCreate, MaintenanceCompleteRequest, MaintenanceOut,
    AMCCreate, AMCOut,
)
from app.modules.inventory.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory & Asset Management"])

admin_or_committee = require_roles("Admin", "Committee")
staff_above        = require_roles("Admin", "Committee", "Staff")
any_auth           = require_roles("Admin", "Committee", "Staff", "Security")


# ── Categories ────────────────────────────────────────────────────────────────
@router.post("/categories", response_model=CategoryOut, status_code=201,
             dependencies=[Depends(admin_or_committee)])
def create_category(data: CategoryCreate, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    return InventoryService(db).create_category(data, user)

@router.get("/categories/{society_id}", response_model=List[CategoryOut],
            dependencies=[Depends(any_auth)])
def list_categories(society_id: UUID, db: Session = Depends(get_db)):
    return InventoryService(db).list_categories(society_id)


# ── Inventory Items ───────────────────────────────────────────────────────────
@router.post("/items", response_model=ItemOut, status_code=201)
def create_item(data: ItemCreate, request: Request, db: Session = Depends(get_db),
                user: User = Depends(admin_or_committee)):
    return InventoryService(db).create_item(data, user, request)

@router.patch("/items/{item_id}", response_model=ItemOut,
              dependencies=[Depends(admin_or_committee)])
def update_item(item_id: UUID, data: ItemUpdate, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    return InventoryService(db).update_item(item_id, data, user)

@router.get("/items/{item_id}", response_model=ItemOut, dependencies=[Depends(any_auth)])
def get_item(item_id: UUID, db: Session = Depends(get_db)):
    return InventoryService(db).get_item(item_id)

@router.get("/items/society/{society_id}", response_model=List[ItemOut],
            dependencies=[Depends(any_auth)])
def list_items(society_id: UUID, skip: int = 0, limit: int = 50,
               db: Session = Depends(get_db)):
    return InventoryService(db).list_items(society_id, skip, limit)

@router.get("/items/society/{society_id}/low-stock", response_model=List[ItemOut],
            dependencies=[Depends(admin_or_committee)])
def low_stock_items(society_id: UUID, db: Session = Depends(get_db)):
    return InventoryService(db).get_low_stock_items(society_id)


# ── Stock operations ──────────────────────────────────────────────────────────
@router.post("/stock/in", response_model=StockOut)
def stock_in(data: StockInRequest, request: Request, db: Session = Depends(get_db),
             user: User = Depends(admin_or_committee)):
    return InventoryService(db).stock_in(data, user, request)

@router.post("/stock/adjust", response_model=StockOut,
             dependencies=[Depends(admin_or_committee)])
def stock_adjust(data: StockAdjustRequest, request: Request,
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return InventoryService(db).stock_adjust(data, user, request)

@router.get("/stock/{item_id}", response_model=StockOut, dependencies=[Depends(any_auth)])
def get_stock(item_id: UUID, db: Session = Depends(get_db)):
    return InventoryService(db).get_stock(item_id)

@router.get("/transactions/{item_id}", response_model=List[TransactionOut],
            dependencies=[Depends(admin_or_committee)])
def get_transactions(item_id: UUID, skip: int = 0, limit: int = 50,
                     db: Session = Depends(get_db)):
    return InventoryService(db).get_transactions(item_id, skip, limit)


# ── Issue / Return ────────────────────────────────────────────────────────────
@router.post("/issues", response_model=IssueOut, status_code=201)
def issue_item(data: IssueCreate, request: Request, db: Session = Depends(get_db),
               user: User = Depends(staff_above)):
    return InventoryService(db).issue_item(data, user, request)

@router.post("/returns", response_model=IssueOut)
def return_item(data: ReturnCreate, request: Request, db: Session = Depends(get_db),
                user: User = Depends(staff_above)):
    return InventoryService(db).return_item(data, user, request)

@router.get("/issues/society/{society_id}", response_model=List[IssueOut],
            dependencies=[Depends(admin_or_committee)])
def list_issues(society_id: UUID, skip: int = 0, limit: int = 50,
                db: Session = Depends(get_db)):
    return InventoryService(db).get_issues(society_id, skip, limit)


# ── Assets ────────────────────────────────────────────────────────────────────
@router.post("/assets", response_model=AssetOut, status_code=201)
def create_asset(data: AssetCreate, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(admin_or_committee)):
    return InventoryService(db).create_asset(data, user, request)

@router.patch("/assets/{asset_id}", response_model=AssetOut,
              dependencies=[Depends(admin_or_committee)])
def update_asset(asset_id: UUID, data: AssetUpdate, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    return InventoryService(db).update_asset(asset_id, data, user)

@router.get("/assets/{asset_id}", response_model=AssetOut, dependencies=[Depends(any_auth)])
def get_asset(asset_id: UUID, db: Session = Depends(get_db)):
    return InventoryService(db).get_asset(asset_id)

@router.get("/assets/society/{society_id}", response_model=List[AssetOut],
            dependencies=[Depends(any_auth)])
def list_assets(society_id: UUID, skip: int = 0, limit: int = 50,
                db: Session = Depends(get_db)):
    return InventoryService(db).list_assets(society_id, skip, limit)

@router.post("/assets/{asset_id}/assign", response_model=AssetOut)
def assign_asset(asset_id: UUID, data: AssetAssignRequest, request: Request,
                 db: Session = Depends(get_db), user: User = Depends(admin_or_committee)):
    return InventoryService(db).assign_asset(asset_id, data, user, request)

@router.get("/assets/society/{society_id}/expiring-warranty", response_model=List[AssetOut],
            dependencies=[Depends(admin_or_committee)])
def expiring_warranties(society_id: UUID, db: Session = Depends(get_db)):
    return InventoryService(db).get_expiring_warranties(society_id)


# ── Maintenance ───────────────────────────────────────────────────────────────
@router.post("/maintenance", response_model=MaintenanceOut, status_code=201)
def schedule_maintenance(data: MaintenanceCreate, request: Request,
                         db: Session = Depends(get_db),
                         user: User = Depends(admin_or_committee)):
    return InventoryService(db).schedule_maintenance(data, user, request)

@router.post("/maintenance/{maint_id}/complete", response_model=MaintenanceOut)
def complete_maintenance(maint_id: UUID, data: MaintenanceCompleteRequest,
                         request: Request, db: Session = Depends(get_db),
                         user: User = Depends(admin_or_committee)):
    return InventoryService(db).complete_maintenance(maint_id, data, user, request)

@router.get("/maintenance/asset/{asset_id}", response_model=List[MaintenanceOut],
            dependencies=[Depends(any_auth)])
def asset_maintenance_history(asset_id: UUID, skip: int = 0, limit: int = 20,
                               db: Session = Depends(get_db)):
    return InventoryService(db).list_maintenance(asset_id, skip, limit)

@router.get("/maintenance/scheduled/{society_id}", response_model=List[MaintenanceOut],
            dependencies=[Depends(admin_or_committee)])
def scheduled_maintenance(society_id: UUID, db: Session = Depends(get_db)):
    return InventoryService(db).get_scheduled_maintenance(society_id)


# ── AMC ───────────────────────────────────────────────────────────────────────
@router.post("/amc", response_model=AMCOut, status_code=201)
def add_amc(data: AMCCreate, request: Request, db: Session = Depends(get_db),
            user: User = Depends(admin_or_committee)):
    return InventoryService(db).add_amc(data, user, request)

@router.get("/amc/asset/{asset_id}", response_model=List[AMCOut],
            dependencies=[Depends(admin_or_committee)])
def get_amc(asset_id: UUID, db: Session = Depends(get_db)):
    return InventoryService(db).get_amc(asset_id)

@router.get("/amc/expiring/{society_id}", response_model=List[AMCOut],
            dependencies=[Depends(admin_or_committee)])
def expiring_amc(society_id: UUID, db: Session = Depends(get_db)):
    return InventoryService(db).get_expiring_amc(society_id)
