"""
Inventory & Asset Management Models — operational ERP architecture.

Stock workflow:  STOCK_IN → ISSUED → RETURNED/CONSUMED
Asset workflow:  REGISTERED → ASSIGNED → MAINTENANCE → AMC_TRACKED → RETIRED
"""
import enum
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean,
    DateTime, Date, Enum, ForeignKey, Numeric
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


# ── Enums ─────────────────────────────────────────────────────────────────────

class ItemCategory(str, enum.Enum):
    CLEANING     = "cleaning"
    ELECTRICAL   = "electrical"
    PLUMBING     = "plumbing"
    SAFETY       = "safety"
    TOOLS        = "tools"
    UNIFORMS     = "uniforms"
    STATIONERY   = "stationery"
    HOUSEKEEPING = "housekeeping"
    GARDENING    = "gardening"
    OTHER        = "other"


class UnitType(str, enum.Enum):
    PIECE   = "piece"
    KG      = "kg"
    LITRE   = "litre"
    METER   = "meter"
    BOX     = "box"
    PACK    = "pack"
    ROLL    = "roll"
    SET     = "set"
    PAIR    = "pair"


class TransactionType(str, enum.Enum):
    STOCK_IN    = "stock_in"
    STOCK_OUT   = "stock_out"
    TRANSFER    = "transfer"
    RETURN      = "return"
    ADJUSTMENT  = "adjustment"
    CONSUMPTION = "consumption"


class IssueStatus(str, enum.Enum):
    ISSUED    = "issued"
    PARTIALLY_RETURNED = "partially_returned"
    RETURNED  = "returned"
    CONSUMED  = "consumed"


class AssetCategory(str, enum.Enum):
    LIFT        = "lift"
    CCTV        = "cctv"
    PUMP        = "pump"
    GENERATOR   = "generator"
    BIOMETRIC   = "biometric"
    FIRE_SAFETY = "fire_safety"
    ELECTRICAL  = "electrical"
    HVAC        = "hvac"
    VEHICLE     = "vehicle"
    FURNITURE   = "furniture"
    IT_EQUIPMENT = "it_equipment"
    OTHER       = "other"


class AssetStatus(str, enum.Enum):
    ACTIVE      = "active"
    UNDER_MAINTENANCE = "under_maintenance"
    RETIRED     = "retired"
    DISPOSED    = "disposed"
    LOST        = "lost"


class MaintenanceType(str, enum.Enum):
    PREVENTIVE  = "preventive"
    CORRECTIVE  = "corrective"
    EMERGENCY   = "emergency"
    AMC_SERVICE = "amc_service"


class MaintenanceStatus(str, enum.Enum):
    SCHEDULED  = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED  = "completed"
    CANCELLED  = "cancelled"


# ── InventoryCategory ─────────────────────────────────────────────────────────

class InventoryCategory(Base, TimestampMixin):
    __tablename__ = "inventory_categories"

    society_id  = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    name        = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    society = relationship("Society")
    items   = relationship("InventoryItem", back_populates="category_rel")


# ── InventoryItem ─────────────────────────────────────────────────────────────

class InventoryItem(Base, TimestampMixin):
    __tablename__ = "inventory_items"

    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id    = Column(UUID(as_uuid=True), ForeignKey("inventory_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    item_code      = Column(String(30), nullable=False, unique=True, index=True)
    name           = Column(String(255), nullable=False)
    description    = Column(Text, nullable=True)
    category       = Column(Enum(ItemCategory, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    unit_type      = Column(Enum(UnitType, values_callable=lambda e: [x.value for x in e]), default=UnitType.PIECE, nullable=False)
    storage_location = Column(String(255), nullable=True)
    minimum_stock  = Column(Float, default=0, nullable=False)   # alert threshold
    unit_cost      = Column(Numeric(10, 2), nullable=True)      # finance-ready
    image_url      = Column(String(500), nullable=True)
    vendor_name    = Column(String(255), nullable=True)
    vendor_contact = Column(String(100), nullable=True)
    remarks        = Column(Text, nullable=True)

    society      = relationship("Society")
    category_rel = relationship("InventoryCategory", back_populates="items")
    stock        = relationship("InventoryStock", back_populates="item", uselist=False, cascade="all, delete-orphan")
    transactions = relationship("InventoryTransaction", back_populates="item", cascade="all, delete-orphan")
    issues       = relationship("InventoryIssue", back_populates="item", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<InventoryItem {self.item_code} {self.name}>"


# ── InventoryStock (current stock level) ─────────────────────────────────────

class InventoryStock(Base, TimestampMixin):
    __tablename__ = "inventory_stock"

    item_id         = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    society_id      = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    current_quantity = Column(Float, default=0, nullable=False)
    last_updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    item    = relationship("InventoryItem", back_populates="stock")
    society = relationship("Society")

    def __repr__(self):
        return f"<Stock item={self.item_id} qty={self.current_quantity}>"


# ── InventoryTransaction (immutable ledger) ───────────────────────────────────

class InventoryTransaction(Base, TimestampMixin):
    __tablename__ = "inventory_transactions"

    society_id       = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id          = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_type = Column(Enum(TransactionType, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    quantity         = Column(Float, nullable=False)
    quantity_before  = Column(Float, nullable=False)   # stock snapshot for audit
    quantity_after   = Column(Float, nullable=False)
    unit_cost        = Column(Numeric(10, 2), nullable=True)
    total_cost       = Column(Numeric(12, 2), nullable=True)
    reference_id     = Column(String(100), nullable=True)  # issue/return/PO ref
    notes            = Column(Text, nullable=True)
    performed_by     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    society  = relationship("Society")
    item     = relationship("InventoryItem", back_populates="transactions")
    performer = relationship("User", foreign_keys=[performed_by])


# ── InventoryIssue ────────────────────────────────────────────────────────────

class InventoryIssue(Base, TimestampMixin):
    __tablename__ = "inventory_issues"

    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id        = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True)
    issued_to_user = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    issued_to_staff = Column(UUID(as_uuid=True), nullable=True)   # staff_id ref
    issued_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    complaint_id   = Column(UUID(as_uuid=True), nullable=True)   # linked complaint
    task_id        = Column(UUID(as_uuid=True), nullable=True)   # linked task

    quantity_issued   = Column(Float, nullable=False)
    quantity_returned = Column(Float, default=0, nullable=False)
    status            = Column(Enum(IssueStatus, values_callable=lambda e: [x.value for x in e]), default=IssueStatus.ISSUED, nullable=False, index=True)
    purpose           = Column(Text, nullable=True)
    expected_return_date = Column(Date, nullable=True)
    actual_return_date   = Column(Date, nullable=True)
    notes             = Column(Text, nullable=True)

    society      = relationship("Society")
    item         = relationship("InventoryItem", back_populates="issues")
    issued_to    = relationship("User", foreign_keys=[issued_to_user])
    issuer       = relationship("User", foreign_keys=[issued_by])
    returns      = relationship("InventoryReturn", back_populates="issue", cascade="all, delete-orphan")


# ── InventoryReturn ───────────────────────────────────────────────────────────

class InventoryReturn(Base, TimestampMixin):
    __tablename__ = "inventory_returns"

    issue_id       = Column(UUID(as_uuid=True), ForeignKey("inventory_issues.id", ondelete="CASCADE"), nullable=False, index=True)
    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity       = Column(Float, nullable=False)
    condition      = Column(String(50), nullable=True)   # good / damaged / lost
    returned_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    received_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes          = Column(Text, nullable=True)

    issue       = relationship("InventoryIssue", back_populates="returns")
    society     = relationship("Society")
    returner    = relationship("User", foreign_keys=[returned_by])
    receiver    = relationship("User", foreign_keys=[received_by])


# ── Asset ─────────────────────────────────────────────────────────────────────

class Asset(Base, TimestampMixin):
    __tablename__ = "assets"

    society_id       = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_code       = Column(String(30), nullable=False, unique=True, index=True)
    name             = Column(String(255), nullable=False)
    asset_category   = Column(Enum(AssetCategory, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    description      = Column(Text, nullable=True)
    location         = Column(String(255), nullable=True)
    status           = Column(Enum(AssetStatus, values_callable=lambda e: [x.value for x in e]), default=AssetStatus.ACTIVE, nullable=False, index=True)

    # Procurement
    purchase_date    = Column(Date, nullable=True)
    purchase_cost    = Column(Numeric(12, 2), nullable=True)
    vendor_name      = Column(String(255), nullable=True)
    vendor_contact   = Column(String(100), nullable=True)
    invoice_number   = Column(String(100), nullable=True)

    # Warranty / lifecycle
    warranty_expiry  = Column(Date, nullable=True)
    expected_life_years = Column(Integer, nullable=True)  # depreciation-ready
    serial_number    = Column(String(100), nullable=True, index=True)
    model_number     = Column(String(100), nullable=True)
    image_url        = Column(String(500), nullable=True)

    # Assignment
    assigned_to_staff = Column(UUID(as_uuid=True), nullable=True)
    assigned_to_user  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at       = Column(DateTime, nullable=True)

    society      = relationship("Society")
    assigned_user = relationship("User", foreign_keys=[assigned_to_user])
    maintenance  = relationship("AssetMaintenance", back_populates="asset", cascade="all, delete-orphan")
    amc          = relationship("AssetAMC",         back_populates="asset", cascade="all, delete-orphan")
    usage_logs   = relationship("AssetUsageLog",    back_populates="asset", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Asset {self.asset_code} {self.name} [{self.status}]>"


# ── AssetMaintenance ──────────────────────────────────────────────────────────

class AssetMaintenance(Base, TimestampMixin):
    __tablename__ = "asset_maintenance"

    asset_id          = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    society_id        = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    maintenance_type  = Column(Enum(MaintenanceType, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    status            = Column(Enum(MaintenanceStatus, values_callable=lambda e: [x.value for x in e]), default=MaintenanceStatus.SCHEDULED, nullable=False, index=True)
    scheduled_date    = Column(Date, nullable=False)
    completed_date    = Column(Date, nullable=True)
    vendor_name       = Column(String(255), nullable=True)
    vendor_contact    = Column(String(100), nullable=True)
    cost              = Column(Numeric(10, 2), nullable=True)
    description       = Column(Text, nullable=True)
    findings          = Column(Text, nullable=True)
    next_due_date     = Column(Date, nullable=True)
    performed_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    asset    = relationship("Asset", back_populates="maintenance")
    society  = relationship("Society")
    performer = relationship("User", foreign_keys=[performed_by])


# ── AssetAMC (Annual Maintenance Contract) ────────────────────────────────────

class AssetAMC(Base, TimestampMixin):
    __tablename__ = "asset_amc"

    asset_id       = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    society_id     = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_name    = Column(String(255), nullable=False)
    vendor_contact = Column(String(100), nullable=True)
    contract_number = Column(String(100), nullable=True)
    start_date     = Column(Date, nullable=False)
    end_date       = Column(Date, nullable=False, index=True)
    annual_cost    = Column(Numeric(10, 2), nullable=True)
    coverage       = Column(Text, nullable=True)   # what's covered
    is_comprehensive = Column(Boolean, default=False, nullable=False)
    auto_renew     = Column(Boolean, default=False, nullable=False)
    document_url   = Column(String(500), nullable=True)

    asset   = relationship("Asset", back_populates="amc")
    society = relationship("Society")


# ── AssetUsageLog ─────────────────────────────────────────────────────────────

class AssetUsageLog(Base, TimestampMixin):
    __tablename__ = "asset_usage_logs"

    asset_id     = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    logged_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action       = Column(String(100), nullable=False)  # ASSIGNED, SERVICED, REPAIRED, RETIRED
    notes        = Column(Text, nullable=True)
    cost         = Column(Numeric(10, 2), nullable=True)

    asset   = relationship("Asset", back_populates="usage_logs")
    society = relationship("Society")
    logger  = relationship("User", foreign_keys=[logged_by])
