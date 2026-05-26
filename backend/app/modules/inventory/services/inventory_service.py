from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.modules.inventory.models.inventory import (
    InventoryCategory, InventoryItem, InventoryStock, InventoryTransaction,
    InventoryIssue, InventoryReturn, Asset, AssetMaintenance, AssetAMC, AssetUsageLog,
    TransactionType, IssueStatus, AssetStatus, MaintenanceStatus,
)
from app.modules.inventory.schemas.inventory import (
    CategoryCreate, ItemCreate, ItemUpdate, StockInRequest, StockAdjustRequest,
    IssueCreate, ReturnCreate, AssetCreate, AssetUpdate, AssetAssignRequest,
    MaintenanceCreate, MaintenanceCompleteRequest, AMCCreate,
)
from app.modules.inventory.repositories.inventory_repo import (
    InventoryCategoryRepo, InventoryItemRepo, InventoryStockRepo,
    InventoryTransactionRepo, InventoryIssueRepo,
    AssetRepo, AssetMaintenanceRepo, AssetAMCRepo,
)
from app.models.user import User
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel


class InventoryService:

    def __init__(self, db: Session):
        self.db        = db
        self.cat_repo  = InventoryCategoryRepo(db)
        self.item_repo = InventoryItemRepo(db)
        self.stock_repo= InventoryStockRepo(db)
        self.txn_repo  = InventoryTransactionRepo(db)
        self.issue_repo= InventoryIssueRepo(db)
        self.asset_repo= AssetRepo(db)
        self.maint_repo= AssetMaintenanceRepo(db)
        self.amc_repo  = AssetAMCRepo(db)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _item_or_404(self, item_id: UUID) -> InventoryItem:
        i = self.item_repo.get(item_id)
        if not i: raise HTTPException(status_code=404, detail="Inventory item not found")
        return i

    def _asset_or_404(self, asset_id: UUID) -> Asset:
        a = self.asset_repo.get(asset_id)
        if not a: raise HTTPException(status_code=404, detail="Asset not found")
        return a

    def _audit(self, action, entity, entity_type, user, request=None, **kw):
        AuditService.log(db=self.db, action=action, module="inventory",
                         entity_id=str(entity.id), entity_type=entity_type,
                         user=user, request=request, **kw)

    def _record_txn(self, item: InventoryItem, stock: InventoryStock,
                    txn_type: TransactionType, qty: float,
                    user: User, notes=None, ref=None, unit_cost=None) -> InventoryTransaction:
        qty_before = stock.current_quantity
        if txn_type in (TransactionType.STOCK_OUT, TransactionType.CONSUMPTION,
                        TransactionType.TRANSFER, TransactionType.ISSUE_TXN if hasattr(TransactionType, 'ISSUE_TXN') else None):
            qty_after = qty_before - qty
        else:
            qty_after = qty_before + qty

        total = float(unit_cost) * qty if unit_cost else None
        txn = InventoryTransaction(
            society_id=item.society_id, item_id=item.id,
            transaction_type=txn_type, quantity=qty,
            quantity_before=qty_before, quantity_after=qty_after,
            unit_cost=unit_cost, total_cost=total,
            reference_id=ref, notes=notes, performed_by=user.id,
        )
        self.db.add(txn)
        stock.current_quantity = qty_after
        stock.last_updated_by  = user.id
        return txn

    def _check_low_stock(self, item: InventoryItem, stock: InventoryStock, user: User):
        if stock.current_quantity <= item.minimum_stock and user:
            NotificationService.send(
                db=self.db, user_id=user.id,
                title="Low Stock Alert",
                body=f"{item.name} ({item.item_code}) is below minimum stock. Current: {stock.current_quantity} {item.unit_type.value}",
                type=NotificationType.WARNING, channel=NotificationChannel.IN_APP,
                module="inventory", entity_id=str(item.id),
            )

    # ── Category ──────────────────────────────────────────────────────────────

    def create_category(self, data: CategoryCreate, user: User) -> InventoryCategory:
        c = InventoryCategory(**data.model_dump())
        return self.cat_repo.create(c)

    def list_categories(self, society_id: UUID) -> List[InventoryCategory]:
        return self.cat_repo.get_by_society(society_id)

    # ── Inventory Items ───────────────────────────────────────────────────────

    def create_item(self, data: ItemCreate, user: User, request=None) -> InventoryItem:
        code = self.item_repo.next_item_code(data.society_id)
        item = InventoryItem(**data.model_dump(), item_code=code)
        self.item_repo.create(item)
        # Initialize stock record
        self.stock_repo.get_or_create(item.id, data.society_id)
        self._audit(AuditAction.CREATE, item, "InventoryItem", user, request,
                    new_values={"code": code, "name": data.name})
        return item

    def update_item(self, item_id: UUID, data: ItemUpdate, user: User) -> InventoryItem:
        item = self._item_or_404(item_id)
        return self.item_repo.update(item, data.model_dump(exclude_none=True))

    def get_item(self, item_id: UUID) -> InventoryItem:
        return self._item_or_404(item_id)

    def list_items(self, society_id: UUID, skip=0, limit=50) -> List[InventoryItem]:
        return self.item_repo.get_by_society(society_id, skip, limit)

    def get_low_stock_items(self, society_id: UUID) -> List[InventoryItem]:
        return self.item_repo.get_low_stock(society_id)

    # ── Stock operations ──────────────────────────────────────────────────────

    def stock_in(self, data: StockInRequest, user: User, request=None) -> InventoryStock:
        item  = self._item_or_404(data.item_id)
        stock = self.stock_repo.get_or_create(item.id, item.society_id)
        self._record_txn(item, stock, TransactionType.STOCK_IN, data.quantity, user,
                         notes=data.notes, ref=data.reference_id, unit_cost=data.unit_cost)
        self._audit(AuditAction.UPDATE, item, "InventoryItem", user, request,
                    new_values={"action": "stock_in", "qty": data.quantity,
                                "new_total": stock.current_quantity})
        self.db.commit()
        self.db.refresh(stock)
        return stock

    def stock_adjust(self, data: StockAdjustRequest, user: User, request=None) -> InventoryStock:
        item  = self._item_or_404(data.item_id)
        stock = self.stock_repo.get_or_create(item.id, item.society_id)
        diff  = data.new_quantity - stock.current_quantity
        txn_type = TransactionType.ADJUSTMENT
        # Record as ADJUSTMENT — quantity is the diff (positive or negative)
        qty_before = stock.current_quantity
        txn = InventoryTransaction(
            society_id=item.society_id, item_id=item.id,
            transaction_type=txn_type, quantity=abs(diff),
            quantity_before=qty_before, quantity_after=data.new_quantity,
            notes=data.notes, performed_by=user.id,
        )
        self.db.add(txn)
        stock.current_quantity = data.new_quantity
        stock.last_updated_by  = user.id
        self._check_low_stock(item, stock, user)
        self.db.commit()
        self.db.refresh(stock)
        return stock

    def get_stock(self, item_id: UUID) -> InventoryStock:
        s = self.stock_repo.get_by_item(item_id)
        if not s: raise HTTPException(status_code=404, detail="Stock record not found")
        return s

    def get_transactions(self, item_id: UUID, skip=0, limit=50) -> List[InventoryTransaction]:
        return self.txn_repo.get_by_item(item_id, skip, limit)

    # ── Issue / Return ────────────────────────────────────────────────────────

    def issue_item(self, data: IssueCreate, user: User, request=None) -> InventoryIssue:
        item  = self._item_or_404(data.item_id)
        stock = self.stock_repo.get_or_create(item.id, item.society_id)

        if stock.current_quantity < data.quantity_issued:
            raise HTTPException(status_code=409,
                detail=f"Insufficient stock. Available: {stock.current_quantity} {item.unit_type.value}, Requested: {data.quantity_issued}")

        # Deduct stock
        self._record_txn(item, stock, TransactionType.STOCK_OUT, data.quantity_issued, user,
                         notes=data.purpose, ref=str(data.issued_to_user or data.issued_to_staff or ""))

        issue = InventoryIssue(**data.model_dump(), issued_by=user.id)
        self.db.add(issue)
        self.db.flush()

        self._check_low_stock(item, stock, user)
        self._audit(AuditAction.UPDATE, item, "InventoryItem", user, request,
                    new_values={"action": "issued", "qty": data.quantity_issued})
        self.db.commit()
        self.db.refresh(issue)
        return issue

    def return_item(self, data: ReturnCreate, user: User, request=None) -> InventoryIssue:
        issue = self.issue_repo.get(data.issue_id)
        if not issue: raise HTTPException(status_code=404, detail="Issue record not found")
        if issue.status == IssueStatus.RETURNED:
            raise HTTPException(status_code=409, detail="Item already fully returned")

        remaining_to_return = issue.quantity_issued - issue.quantity_returned
        if data.quantity > remaining_to_return:
            raise HTTPException(status_code=409,
                detail=f"Cannot return {data.quantity}. Max returnable: {remaining_to_return}")

        item  = self._item_or_404(issue.item_id)
        stock = self.stock_repo.get_or_create(item.id, item.society_id)
        self._record_txn(item, stock, TransactionType.RETURN, data.quantity, user, notes=data.notes)

        ret = InventoryReturn(
            issue_id=issue.id, society_id=issue.society_id,
            quantity=data.quantity, condition=data.condition,
            returned_by=user.id, received_by=user.id, notes=data.notes,
        )
        self.db.add(ret)

        issue.quantity_returned += data.quantity
        issue.actual_return_date = date.today()
        if issue.quantity_returned >= issue.quantity_issued:
            issue.status = IssueStatus.RETURNED
        else:
            issue.status = IssueStatus.PARTIALLY_RETURNED

        self._audit(AuditAction.UPDATE, item, "InventoryItem", user, request,
                    new_values={"action": "returned", "qty": data.quantity})
        self.db.commit()
        self.db.refresh(issue)
        return issue

    def get_issues(self, society_id: UUID, skip=0, limit=50) -> List[InventoryIssue]:
        return self.issue_repo.get_by_society(society_id, skip, limit)

    # ── Asset CRUD ────────────────────────────────────────────────────────────

    def create_asset(self, data: AssetCreate, user: User, request=None) -> Asset:
        code  = self.asset_repo.next_asset_code(data.society_id)
        asset = Asset(**data.model_dump(), asset_code=code)
        self.asset_repo.create(asset)
        # Initial usage log
        log = AssetUsageLog(asset_id=asset.id, society_id=asset.society_id,
                            logged_by=user.id, action="REGISTERED",
                            notes=f"Asset registered by {user.email}")
        self.db.add(log)
        self._audit(AuditAction.CREATE, asset, "Asset", user, request,
                    new_values={"code": code, "name": data.name, "category": data.asset_category.value})
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def update_asset(self, asset_id: UUID, data: AssetUpdate, user: User) -> Asset:
        asset = self._asset_or_404(asset_id)
        return self.asset_repo.update(asset, data.model_dump(exclude_none=True))

    def get_asset(self, asset_id: UUID) -> Asset:
        return self._asset_or_404(asset_id)

    def list_assets(self, society_id: UUID, skip=0, limit=50) -> List[Asset]:
        return self.asset_repo.get_by_society(society_id, skip, limit)

    def assign_asset(self, asset_id: UUID, data: AssetAssignRequest,
                     user: User, request=None) -> Asset:
        asset = self._asset_or_404(asset_id)
        asset.assigned_to_user  = data.assigned_to_user
        asset.assigned_to_staff = data.assigned_to_staff
        asset.assigned_at = datetime.utcnow()
        log = AssetUsageLog(asset_id=asset.id, society_id=asset.society_id,
                            logged_by=user.id, action="ASSIGNED",
                            notes=data.notes or f"Assigned by {user.email}")
        self.db.add(log)
        self._audit(AuditAction.UPDATE, asset, "Asset", user, request,
                    new_values={"action": "assigned", "to": str(data.assigned_to_user or data.assigned_to_staff)})
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def get_expiring_warranties(self, society_id: UUID) -> List[Asset]:
        return self.asset_repo.get_expiring_warranty(society_id)

    # ── Maintenance ───────────────────────────────────────────────────────────

    def schedule_maintenance(self, data: MaintenanceCreate,
                              user: User, request=None) -> AssetMaintenance:
        asset = self._asset_or_404(data.asset_id)
        maint = AssetMaintenance(**data.model_dump(), performed_by=user.id)
        self.db.add(maint)
        self.db.flush()
        self._audit(AuditAction.CREATE, maint, "AssetMaintenance", user, request,
                    new_values={"type": data.maintenance_type.value, "date": str(data.scheduled_date)})
        self.db.commit()
        self.db.refresh(maint)
        return maint

    def complete_maintenance(self, maint_id: UUID,
                              data: MaintenanceCompleteRequest,
                              user: User, request=None) -> AssetMaintenance:
        maint = self.maint_repo.get(maint_id)
        if not maint: raise HTTPException(status_code=404, detail="Maintenance record not found")
        if maint.status == MaintenanceStatus.COMPLETED:
            raise HTTPException(status_code=409, detail="Maintenance already completed")

        maint.status         = MaintenanceStatus.COMPLETED
        maint.completed_date = date.today()
        maint.findings       = data.findings
        maint.next_due_date  = data.next_due_date
        if data.cost: maint.cost = data.cost

        # Log on asset
        log = AssetUsageLog(asset_id=maint.asset_id, society_id=maint.society_id,
                            logged_by=user.id, action="MAINTENANCE_COMPLETED",
                            notes=data.findings, cost=data.cost)
        self.db.add(log)
        self._audit(AuditAction.UPDATE, maint, "AssetMaintenance", user, request,
                    new_values={"status": "completed", "date": str(date.today())})
        self.db.commit()
        self.db.refresh(maint)
        return maint

    def list_maintenance(self, asset_id: UUID, skip=0, limit=20) -> List[AssetMaintenance]:
        return self.maint_repo.get_by_asset(asset_id, skip, limit)

    def get_scheduled_maintenance(self, society_id: UUID) -> List[AssetMaintenance]:
        return self.maint_repo.get_scheduled(society_id)

    # ── AMC ───────────────────────────────────────────────────────────────────

    def add_amc(self, data: AMCCreate, user: User, request=None) -> AssetAMC:
        self._asset_or_404(data.asset_id)
        amc = AssetAMC(**data.model_dump())
        self.db.add(amc)
        self._audit(AuditAction.CREATE, amc, "AssetAMC", user, request,
                    new_values={"vendor": data.vendor_name, "end": str(data.end_date)})
        self.db.commit()
        self.db.refresh(amc)
        return amc

    def get_amc(self, asset_id: UUID) -> List[AssetAMC]:
        return self.amc_repo.get_by_asset(asset_id)

    def get_expiring_amc(self, society_id: UUID) -> List[AssetAMC]:
        return self.amc_repo.get_expiring(society_id)
