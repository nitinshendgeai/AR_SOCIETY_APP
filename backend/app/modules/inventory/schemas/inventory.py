from pydantic import BaseModel, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from app.schemas.common import OrmBase, TimestampSchema
from app.modules.inventory.models.inventory import (
    ItemCategory, UnitType, TransactionType, IssueStatus,
    AssetCategory, AssetStatus, MaintenanceType, MaintenanceStatus,
)


# ── Category ──────────────────────────────────────────────────────────────────
class CategoryCreate(OrmBase):
    society_id: UUID; name: str; description: Optional[str] = None

class CategoryOut(TimestampSchema):
    society_id: UUID; name: str; description: Optional[str]


# ── Inventory Item ────────────────────────────────────────────────────────────
class ItemCreate(OrmBase):
    society_id: UUID; name: str; category: ItemCategory
    unit_type: UnitType = UnitType.PIECE
    description: Optional[str]    = None
    storage_location: Optional[str] = None
    minimum_stock: float           = 0
    unit_cost: Optional[Decimal]   = None
    vendor_name: Optional[str]     = None
    vendor_contact: Optional[str]  = None
    category_id: Optional[UUID]    = None
    remarks: Optional[str]         = None

class ItemUpdate(OrmBase):
    name: Optional[str]             = None
    description: Optional[str]      = None
    storage_location: Optional[str] = None
    minimum_stock: Optional[float]  = None
    unit_cost: Optional[Decimal]    = None
    vendor_name: Optional[str]      = None
    vendor_contact: Optional[str]   = None

class ItemOut(TimestampSchema):
    society_id: UUID; item_code: str; name: str; category: ItemCategory
    unit_type: UnitType; description: Optional[str]; storage_location: Optional[str]
    minimum_stock: float; unit_cost: Optional[Decimal]
    vendor_name: Optional[str]; current_stock: Optional[float] = None


# ── Stock operations ──────────────────────────────────────────────────────────
class StockInRequest(OrmBase):
    item_id:  UUID; quantity: float; unit_cost: Optional[Decimal] = None
    notes: Optional[str] = None; reference_id: Optional[str] = None

    @field_validator("quantity")
    @classmethod
    def qty_positive(cls, v):
        if v <= 0: raise ValueError("Quantity must be positive")
        return v

class StockAdjustRequest(OrmBase):
    item_id: UUID; new_quantity: float; notes: str

class TransactionOut(TimestampSchema):
    society_id: UUID; item_id: UUID; transaction_type: TransactionType
    quantity: float; quantity_before: float; quantity_after: float
    unit_cost: Optional[Decimal]; total_cost: Optional[Decimal]
    reference_id: Optional[str]; notes: Optional[str]

class StockOut(TimestampSchema):
    item_id: UUID; society_id: UUID
    current_quantity: float


# ── Issue / Return ────────────────────────────────────────────────────────────
class IssueCreate(OrmBase):
    society_id: UUID; item_id: UUID
    issued_to_user: Optional[UUID]  = None
    issued_to_staff: Optional[UUID] = None
    complaint_id: Optional[UUID]    = None
    task_id: Optional[UUID]         = None
    quantity_issued: float
    purpose: Optional[str]          = None
    expected_return_date: Optional[date] = None
    notes: Optional[str]            = None

    @field_validator("quantity_issued")
    @classmethod
    def qty_positive(cls, v):
        if v <= 0: raise ValueError("Quantity must be positive")
        return v

class ReturnCreate(OrmBase):
    issue_id: UUID; quantity: float
    condition: Optional[str] = None; notes: Optional[str] = None

class IssueOut(TimestampSchema):
    society_id: UUID; item_id: UUID; status: IssueStatus
    issued_to_user: Optional[UUID]; quantity_issued: float
    quantity_returned: float; purpose: Optional[str]
    expected_return_date: Optional[date]; actual_return_date: Optional[date]


# ── Asset ─────────────────────────────────────────────────────────────────────
class AssetCreate(OrmBase):
    society_id: UUID; name: str; asset_category: AssetCategory
    description: Optional[str]      = None
    location: Optional[str]         = None
    purchase_date: Optional[date]    = None
    purchase_cost: Optional[Decimal] = None
    vendor_name: Optional[str]       = None
    vendor_contact: Optional[str]    = None
    warranty_expiry: Optional[date]  = None
    expected_life_years: Optional[int] = None
    serial_number: Optional[str]     = None
    model_number: Optional[str]      = None
    invoice_number: Optional[str]    = None

class AssetUpdate(OrmBase):
    name: Optional[str]             = None
    description: Optional[str]      = None
    location: Optional[str]         = None
    status: Optional[AssetStatus]   = None
    warranty_expiry: Optional[date] = None

class AssetAssignRequest(OrmBase):
    assigned_to_user: Optional[UUID]  = None
    assigned_to_staff: Optional[UUID] = None
    notes: Optional[str]              = None

class AssetOut(TimestampSchema):
    society_id: UUID; asset_code: str; name: str; asset_category: AssetCategory
    description: Optional[str]; location: Optional[str]; status: AssetStatus
    purchase_date: Optional[date]; purchase_cost: Optional[Decimal]
    warranty_expiry: Optional[date]; serial_number: Optional[str]
    assigned_to_user: Optional[UUID]; assigned_at: Optional[datetime]


# ── Maintenance ───────────────────────────────────────────────────────────────
class MaintenanceCreate(OrmBase):
    asset_id: UUID; society_id: UUID
    maintenance_type: MaintenanceType
    scheduled_date: date
    vendor_name: Optional[str]    = None
    vendor_contact: Optional[str] = None
    description: Optional[str]    = None
    cost: Optional[Decimal]       = None

class MaintenanceCompleteRequest(OrmBase):
    findings: Optional[str]    = None
    cost: Optional[Decimal]    = None
    next_due_date: Optional[date] = None
    notes: Optional[str]       = None

class MaintenanceOut(TimestampSchema):
    asset_id: UUID; maintenance_type: MaintenanceType; status: MaintenanceStatus
    scheduled_date: date; completed_date: Optional[date]
    vendor_name: Optional[str]; cost: Optional[Decimal]
    findings: Optional[str]; next_due_date: Optional[date]


# ── AMC ───────────────────────────────────────────────────────────────────────
class AMCCreate(OrmBase):
    asset_id: UUID; society_id: UUID; vendor_name: str
    start_date: date; end_date: date
    vendor_contact: Optional[str]    = None
    contract_number: Optional[str]   = None
    annual_cost: Optional[Decimal]   = None
    coverage: Optional[str]          = None
    is_comprehensive: bool           = False
    auto_renew: bool                 = False
    document_url: Optional[str]      = None

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v, info):
        if "start_date" in info.data and v <= info.data["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v

class AMCOut(TimestampSchema):
    asset_id: UUID; vendor_name: str; contract_number: Optional[str]
    start_date: date; end_date: date; annual_cost: Optional[Decimal]
    coverage: Optional[str]; is_comprehensive: bool; auto_renew: bool
