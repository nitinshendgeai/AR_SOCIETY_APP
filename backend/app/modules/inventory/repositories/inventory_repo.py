from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.modules.inventory.models.inventory import (
    InventoryCategory, InventoryItem, InventoryStock,
    InventoryTransaction, InventoryIssue, InventoryReturn,
    Asset, AssetMaintenance, AssetAMC, AssetUsageLog,
    IssueStatus, AssetStatus, MaintenanceStatus,
)
from app.repositories.base import BaseRepository


class InventoryCategoryRepo(BaseRepository[InventoryCategory]):
    def __init__(self, db): super().__init__(InventoryCategory, db)
    def get_by_society(self, sid: UUID) -> List[InventoryCategory]:
        return self.db.query(InventoryCategory).filter(InventoryCategory.society_id==sid, InventoryCategory.is_active==True).all()


class InventoryItemRepo(BaseRepository[InventoryItem]):
    def __init__(self, db): super().__init__(InventoryItem, db)

    def get_by_society(self, sid: UUID, skip=0, limit=50) -> List[InventoryItem]:
        return self.db.query(InventoryItem).filter(InventoryItem.society_id==sid, InventoryItem.is_active==True)\
            .offset(skip).limit(limit).all()

    def next_item_code(self, sid: UUID) -> str:
        count = self.db.query(InventoryItem).filter(InventoryItem.society_id==sid).count()
        return f"INV-{str(count+1).zfill(5)}"

    def get_low_stock(self, sid: UUID) -> List[InventoryItem]:
        """Items where current stock <= minimum_stock."""
        return self.db.query(InventoryItem).join(InventoryStock).filter(
            InventoryItem.society_id==sid,
            InventoryItem.is_active==True,
            InventoryStock.current_quantity <= InventoryItem.minimum_stock,
        ).all()


class InventoryStockRepo(BaseRepository[InventoryStock]):
    def __init__(self, db): super().__init__(InventoryStock, db)

    def get_by_item(self, item_id: UUID) -> Optional[InventoryStock]:
        return self.db.query(InventoryStock).filter(InventoryStock.item_id==item_id).first()

    def get_or_create(self, item_id: UUID, society_id: UUID) -> InventoryStock:
        s = self.get_by_item(item_id)
        if not s:
            s = InventoryStock(item_id=item_id, society_id=society_id, current_quantity=0)
            self.db.add(s)
            self.db.flush()
        return s


class InventoryTransactionRepo(BaseRepository[InventoryTransaction]):
    def __init__(self, db): super().__init__(InventoryTransaction, db)

    def get_by_item(self, item_id: UUID, skip=0, limit=50) -> List[InventoryTransaction]:
        return self.db.query(InventoryTransaction).filter(InventoryTransaction.item_id==item_id)\
            .order_by(InventoryTransaction.created_at.desc()).offset(skip).limit(limit).all()


class InventoryIssueRepo(BaseRepository[InventoryIssue]):
    def __init__(self, db): super().__init__(InventoryIssue, db)

    def get_active_by_item(self, item_id: UUID) -> List[InventoryIssue]:
        return self.db.query(InventoryIssue).filter(
            InventoryIssue.item_id==item_id,
            InventoryIssue.status==IssueStatus.ISSUED,
            InventoryIssue.is_active==True,
        ).all()

    def get_by_society(self, sid: UUID, skip=0, limit=50) -> List[InventoryIssue]:
        return self.db.query(InventoryIssue).filter(InventoryIssue.society_id==sid, InventoryIssue.is_active==True)\
            .order_by(InventoryIssue.created_at.desc()).offset(skip).limit(limit).all()


class AssetRepo(BaseRepository[Asset]):
    def __init__(self, db): super().__init__(Asset, db)

    def get_by_society(self, sid: UUID, skip=0, limit=50) -> List[Asset]:
        return self.db.query(Asset).filter(Asset.society_id==sid, Asset.is_active==True)\
            .offset(skip).limit(limit).all()

    def next_asset_code(self, sid: UUID) -> str:
        count = self.db.query(Asset).filter(Asset.society_id==sid).count()
        return f"AST-{str(count+1).zfill(4)}"

    def get_expiring_warranty(self, sid: UUID) -> List[Asset]:
        from datetime import date, timedelta
        in_30 = date.today() + timedelta(days=30)
        return self.db.query(Asset).filter(
            Asset.society_id==sid, Asset.warranty_expiry<=in_30,
            Asset.warranty_expiry>=date.today(), Asset.is_active==True,
        ).all()


class AssetMaintenanceRepo(BaseRepository[AssetMaintenance]):
    def __init__(self, db): super().__init__(AssetMaintenance, db)

    def get_by_asset(self, asset_id: UUID, skip=0, limit=20) -> List[AssetMaintenance]:
        return self.db.query(AssetMaintenance).filter(AssetMaintenance.asset_id==asset_id)\
            .order_by(AssetMaintenance.scheduled_date.desc()).offset(skip).limit(limit).all()

    def get_scheduled(self, sid: UUID) -> List[AssetMaintenance]:
        return self.db.query(AssetMaintenance).filter(
            AssetMaintenance.society_id==sid,
            AssetMaintenance.status==MaintenanceStatus.SCHEDULED,
            AssetMaintenance.is_active==True,
        ).all()


class AssetAMCRepo(BaseRepository[AssetAMC]):
    def __init__(self, db): super().__init__(AssetAMC, db)

    def get_by_asset(self, asset_id: UUID) -> List[AssetAMC]:
        return self.db.query(AssetAMC).filter(AssetAMC.asset_id==asset_id, AssetAMC.is_active==True).all()

    def get_expiring(self, sid: UUID) -> List[AssetAMC]:
        from datetime import date, timedelta
        in_30 = date.today() + timedelta(days=30)
        return self.db.query(AssetAMC).filter(
            AssetAMC.society_id==sid, AssetAMC.end_date<=in_30,
            AssetAMC.end_date>=date.today(), AssetAMC.is_active==True,
        ).all()
