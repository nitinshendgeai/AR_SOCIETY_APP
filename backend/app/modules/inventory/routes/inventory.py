from typing import List
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import (
    get_current_user, require_roles,
    require_admin_committee, require_manager_above, require_supervisor_above, require_any_staff,
)
from app.models.user import User
from app.modules.inventory.schemas.inventory import (
    CategoryCreate, CategoryOut, ItemCreate, ItemUpdate, ItemOut,
    StockInRequest, StockAdjustRequest, StockOut, TransactionOut,
    IssueCreate, IssueOut, ReturnCreate,
    AssetCreate, AssetUpdate, AssetOut, AssetAssignRequest,
    MaintenanceCreate, MaintenanceCompleteRequest, MaintenanceOut,
    AMCCreate, AMCOut, AssetSummaryOut, AssetHistoryOut,
)
from app.modules.inventory.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory & Asset Management"])

admin_or_committee = require_manager_above     # admin, committee and manager keep the stores and the asset register
staff_above        = require_supervisor_above
any_auth           = require_any_staff


# ── Categories ────────────────────────────────────────────────────────────────
@router.post("/categories", response_model=CategoryOut, status_code=201,
             dependencies=[Depends(admin_or_committee)])
def create_category(data: CategoryCreate, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    return InventoryService(db).create_category(data, user)

@router.get("/categories/{society_id}", response_model=List[CategoryOut],
            dependencies=[Depends(any_auth)])
def list_categories(society_id: UUID, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    return InventoryService(db).list_categories(society_id, user)


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

@router.get("/items/society/{society_id}/low-stock", response_model=List[ItemOut],
            dependencies=[Depends(admin_or_committee)])
def low_stock_items(society_id: UUID, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    return InventoryService(db).get_low_stock_items(society_id, user)

@router.get("/items/society/{society_id}", response_model=List[ItemOut],
            dependencies=[Depends(any_auth)])
def list_items(society_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
               q: Optional[str] = None, category: Optional[str] = None,
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return InventoryService(db).list_items(society_id, skip, limit, user, q=q, category=category)

@router.get("/items/{item_id}", response_model=ItemOut, dependencies=[Depends(any_auth)])
def get_item(item_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return InventoryService(db).get_item(item_id, user)


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
def get_stock(item_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return InventoryService(db).get_stock(item_id, user)

@router.get("/transactions/{item_id}", response_model=List[TransactionOut],
            dependencies=[Depends(any_auth)])
def get_transactions(item_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return InventoryService(db).get_transactions(item_id, skip, limit, user)


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
            dependencies=[Depends(any_auth)])
def list_issues(society_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return InventoryService(db).get_issues(society_id, skip, limit, user)


# ── Assets ────────────────────────────────────────────────────────────────────
@router.post("/assets", response_model=AssetOut, status_code=201)
def create_asset(data: AssetCreate, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(admin_or_committee)):
    return InventoryService(db).create_asset(data, user, request)

@router.get("/assets/summary/{society_id}", response_model=AssetSummaryOut,
            dependencies=[Depends(any_auth)])
def asset_summary(society_id: UUID, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    return InventoryService(db).asset_summary(society_id, user)

@router.get("/assets/society/{society_id}/expiring-warranty", response_model=List[AssetOut],
            dependencies=[Depends(admin_or_committee)])
def expiring_warranties(society_id: UUID, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    return InventoryService(db).get_expiring_warranties(society_id, user)

@router.get("/assets/society/{society_id}", response_model=List[AssetOut],
            dependencies=[Depends(any_auth)])
def list_assets(society_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
                q: Optional[str] = None, category: Optional[str] = None, status: Optional[str] = None,
                due: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """`due=true` lists assets whose service is overdue or falls within 30 days, soonest first."""
    return InventoryService(db).list_assets(society_id, skip, limit, user, q=q, category=category,
                                            status=status, due=due)

@router.patch("/assets/{asset_id}", response_model=AssetOut,
              dependencies=[Depends(admin_or_committee)])
def update_asset(asset_id: UUID, data: AssetUpdate, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    return InventoryService(db).update_asset(asset_id, data, user, request)

@router.get("/assets/{asset_id}/history", response_model=AssetHistoryOut,
            dependencies=[Depends(any_auth)])
def asset_history(asset_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Services, AMC, linked annual contracts and work orders, and the log, in one call."""
    return InventoryService(db).asset_history(asset_id, user)

@router.get("/assets/{asset_id}", response_model=AssetOut, dependencies=[Depends(any_auth)])
def get_asset(asset_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return InventoryService(db).get_asset(asset_id, user)

@router.post("/assets/{asset_id}/assign", response_model=AssetOut)
def assign_asset(asset_id: UUID, data: AssetAssignRequest, request: Request,
                 db: Session = Depends(get_db), user: User = Depends(admin_or_committee)):
    return InventoryService(db).assign_asset(asset_id, data, user, request)


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

@router.post("/maintenance/{maint_id}/cancel", response_model=MaintenanceOut)
def cancel_maintenance(maint_id: UUID, request: Request, db: Session = Depends(get_db),
                       user: User = Depends(admin_or_committee)):
    return InventoryService(db).cancel_maintenance(maint_id, user, request)

@router.get("/maintenance/asset/{asset_id}", response_model=List[MaintenanceOut],
            dependencies=[Depends(any_auth)])
def asset_maintenance_history(asset_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=200),
                               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return InventoryService(db).list_maintenance(asset_id, skip, limit, user)

@router.get("/maintenance/scheduled/{society_id}", response_model=List[MaintenanceOut],
            dependencies=[Depends(admin_or_committee)])
def scheduled_maintenance(society_id: UUID, db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    return InventoryService(db).get_scheduled_maintenance(society_id, user)


# ── AMC ───────────────────────────────────────────────────────────────────────
@router.post("/amc", response_model=AMCOut, status_code=201)
def add_amc(data: AMCCreate, request: Request, db: Session = Depends(get_db),
            user: User = Depends(admin_or_committee)):
    return InventoryService(db).add_amc(data, user, request)

@router.get("/amc/expiring/{society_id}", response_model=List[AMCOut],
            dependencies=[Depends(admin_or_committee)])
def expiring_amc(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return InventoryService(db).get_expiring_amc(society_id, user)

@router.get("/amc/asset/{asset_id}", response_model=List[AMCOut],
            dependencies=[Depends(admin_or_committee)])
def get_amc(asset_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return InventoryService(db).get_amc(asset_id, user)
