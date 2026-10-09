from pydantic import BaseModel, field_validator, computed_field
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
    society_id: Optional[UUID] = None       # a society user's own society is used
    name: str; description: Optional[str] = None

class CategoryOut(TimestampSchema):
    society_id: UUID; name: str; description: Optional[str]


# ── Inventory Item ────────────────────────────────────────────────────────────
class ItemCreate(OrmBase):
    society_id: Optional[UUID] = None       # a society user's own society is used
    name: str; category: ItemCategory
    unit_type: UnitType = UnitType.PIECE
    description: Optional[str]    = None
    storage_location: Optional[str] = None
    minimum_stock: float           = 0
    unit_cost: Optional[Decimal]   = None
    vendor_name: Optional[str]     = None
    vendor_contact: Optional[str]  = None
    category_id: Optional[UUID]    = None
    remarks: Optional[str]         = None

    @field_validator("name")
    @classmethod
    def name_required(cls, v):
        if not (v or "").strip(): raise ValueError("Give the item a name")
        return v.strip()

    @field_validator("minimum_stock")
    @classmethod
    def minimum_not_negative(cls, v):
        if v < 0: raise ValueError("The minimum can't be negative")
        return v

    @field_validator("unit_cost")
    @classmethod
    def cost_not_negative(cls, v):
        if v is not None and v < 0: raise ValueError("A cost can't be negative")
        return v

class ItemUpdate(OrmBase):
    name: Optional[str]             = None
    category: Optional[ItemCategory] = None
    is_active: Optional[bool]       = None       # false: retired, no longer listed or issued
    description: Optional[str]      = None
    storage_location: Optional[str] = None
    minimum_stock: Optional[float]  = None
    unit_cost: Optional[Decimal]    = None
    vendor_name: Optional[str]      = None
    vendor_contact: Optional[str]   = None

    @field_validator("minimum_stock")
    @classmethod
    def minimum_not_negative(cls, v):
        if v is not None and v < 0: raise ValueError("The minimum can't be negative")
        return v

    @field_validator("unit_cost")
    @classmethod
    def cost_not_negative(cls, v):
        if v is not None and v < 0: raise ValueError("A cost can't be negative")
        return v

class ItemOut(TimestampSchema):
    society_id: UUID; item_code: str; name: str; category: ItemCategory
    unit_type: UnitType; description: Optional[str]; storage_location: Optional[str]
    minimum_stock: float; unit_cost: Optional[Decimal]
    vendor_name: Optional[str]; vendor_contact: Optional[str] = None
    current_stock: Optional[float] = None

    @computed_field
    @property
    def is_low_stock(self) -> bool:
        return (self.current_stock or 0) <= (self.minimum_stock or 0)


# ── Stock operations ──────────────────────────────────────────────────────────
class StockInRequest(OrmBase):
    item_id:  UUID; quantity: float; unit_cost: Optional[Decimal] = None
    notes: Optional[str] = None; reference_id: Optional[str] = None

    @field_validator("unit_cost")
    @classmethod
    def cost_not_negative(cls, v):
        if v is not None and v < 0: raise ValueError("A cost can't be negative")
        return v

    @field_validator("quantity")
    @classmethod
    def qty_positive(cls, v):
        if v <= 0: raise ValueError("Quantity must be positive")
        return v

class StockAdjustRequest(OrmBase):
    item_id: UUID; new_quantity: float; notes: str

    @field_validator("notes")
    @classmethod
    def reason_required(cls, v):
        if not (v or "").strip(): raise ValueError("Say why the count changed")
        return v.strip()

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
    society_id: Optional[UUID] = None       # ignored: an issue belongs to its item's society
    item_id: UUID
    issued_to_user: Optional[UUID]  = None
    issued_to_staff: Optional[UUID] = None
    complaint_id: Optional[UUID]    = None
    task_id: Optional[UUID]         = None
    quantity_issued: float
    purpose: Optional[str]          = None
    expected_return_date: Optional[date] = None
    consumed: bool                  = False     # used up (cleaning supplies…): not expected back
    notes: Optional[str]            = None

    @field_validator("quantity_issued")
    @classmethod
    def qty_positive(cls, v):
        if v <= 0: raise ValueError("Quantity must be positive")
        return v

class ReturnCreate(OrmBase):
    issue_id: UUID; quantity: float
    condition: Optional[str] = None; notes: Optional[str] = None

    @field_validator("quantity")
    @classmethod
    def qty_positive(cls, v):
        if v <= 0: raise ValueError("Quantity must be positive")
        return v

class IssueOut(TimestampSchema):
    society_id: UUID; item_id: UUID; status: IssueStatus
    issued_to_user: Optional[UUID]; quantity_issued: float
    quantity_returned: float; purpose: Optional[str]
    expected_return_date: Optional[date]; actual_return_date: Optional[date]


# ── Asset ─────────────────────────────────────────────────────────────────────
class AssetCreate(OrmBase):
    society_id: Optional[UUID] = None       # a society user's own society is used; only a platform admin names one
    name: str; asset_category: AssetCategory
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
    service_interval_months: Optional[int] = None
    last_serviced_on: Optional[date] = None
    next_service_due: Optional[date] = None

    @field_validator("name")
    @classmethod
    def name_required(cls, v):
        v = (v or "").strip()
        if not v: raise ValueError("Name is required")
        return v

    @field_validator("purchase_cost")
    @classmethod
    def cost_not_negative(cls, v):
        if v is not None and v < 0: raise ValueError("Cost can't be negative")
        return v

    @field_validator("service_interval_months")
    @classmethod
    def interval_sane(cls, v):
        if v is not None and not (1 <= v <= 120): raise ValueError("Service interval must be 1 to 120 months")
        return v

    @field_validator("expected_life_years")
    @classmethod
    def life_sane(cls, v):
        if v is not None and not (1 <= v <= 100): raise ValueError("Expected life must be 1 to 100 years")
        return v

class AssetUpdate(OrmBase):
    """Only fields sent are changed; send null to clear an optional one."""
    name: Optional[str]                  = None
    asset_category: Optional[AssetCategory] = None
    description: Optional[str]           = None
    location: Optional[str]              = None
    status: Optional[AssetStatus]        = None
    purchase_date: Optional[date]        = None
    purchase_cost: Optional[Decimal]     = None
    vendor_name: Optional[str]           = None
    vendor_contact: Optional[str]        = None
    invoice_number: Optional[str]        = None
    warranty_expiry: Optional[date]      = None
    expected_life_years: Optional[int]   = None
    serial_number: Optional[str]         = None
    model_number: Optional[str]          = None
    service_interval_months: Optional[int] = None
    last_serviced_on: Optional[date]     = None
    next_service_due: Optional[date]     = None

    @field_validator("purchase_cost")
    @classmethod
    def cost_not_negative(cls, v):
        if v is not None and v < 0: raise ValueError("Cost can't be negative")
        return v

    @field_validator("service_interval_months")
    @classmethod
    def interval_sane(cls, v):
        if v is not None and not (1 <= v <= 120): raise ValueError("Service interval must be 1 to 120 months")
        return v

class AssetAssignRequest(OrmBase):
    assigned_to_user: Optional[UUID]  = None
    assigned_to_staff: Optional[UUID] = None
    notes: Optional[str]              = None

WARRANTY_SOON_DAYS = 30
SERVICE_SOON_DAYS  = 30

class AssetOut(TimestampSchema):
    society_id: UUID; asset_code: str; name: str; asset_category: AssetCategory
    description: Optional[str]; location: Optional[str]; status: AssetStatus
    purchase_date: Optional[date]; purchase_cost: Optional[Decimal]
    vendor_name: Optional[str] = None; vendor_contact: Optional[str] = None
    invoice_number: Optional[str] = None
    warranty_expiry: Optional[date]; serial_number: Optional[str]
    model_number: Optional[str] = None; expected_life_years: Optional[int] = None
    service_interval_months: Optional[int] = None
    last_serviced_on: Optional[date] = None; next_service_due: Optional[date] = None
    assigned_to_user: Optional[UUID]; assigned_at: Optional[datetime]

    @computed_field
    @property
    def warranty_status(self) -> str:
        """none / active / expiring (within 30 days) / expired"""
        if not self.warranty_expiry: return "none"
        days = (self.warranty_expiry - date.today()).days
        return "expired" if days < 0 else "expiring" if days <= WARRANTY_SOON_DAYS else "active"

    @computed_field
    @property
    def service_status(self) -> str:
        """none (no schedule) / ok / due_soon (within 30 days) / overdue. A retired asset needs no service."""
        if self.status in (AssetStatus.RETIRED, AssetStatus.DISPOSED, AssetStatus.LOST): return "none"
        if not self.next_service_due: return "none"
        days = (self.next_service_due - date.today()).days
        return "overdue" if days < 0 else "due_soon" if days <= SERVICE_SOON_DAYS else "ok"

    @computed_field
    @property
    def days_to_service(self) -> Optional[int]:
        return (self.next_service_due - date.today()).days if self.next_service_due else None


class AssetSummaryOut(OrmBase):
    total: int
    active: int
    under_maintenance: int
    retired: int
    total_purchase_cost: Decimal
    warranty_expiring: int
    warranty_expired: int
    service_overdue: int
    service_due_soon: int
    amc_expiring: int
    by_category: dict


# ── Maintenance ───────────────────────────────────────────────────────────────
class MaintenanceCreate(OrmBase):
    asset_id: UUID
    society_id: Optional[UUID] = None       # ignored: a service always belongs to its asset's society
    maintenance_type: MaintenanceType
    scheduled_date: date
    vendor_name: Optional[str]    = None
    vendor_contact: Optional[str] = None
    description: Optional[str]    = None
    cost: Optional[Decimal]       = None

    @field_validator("cost")
    @classmethod
    def cost_not_negative(cls, v):
        if v is not None and v < 0: raise ValueError("Cost can't be negative")
        return v

class MaintenanceCompleteRequest(OrmBase):
    completed_date: Optional[date] = None     # defaults to today; can't be in the future
    findings: Optional[str]    = None
    cost: Optional[Decimal]    = None
    next_due_date: Optional[date] = None      # else worked out from the asset's service interval
    vendor_name: Optional[str] = None
    notes: Optional[str]       = None

    @field_validator("cost")
    @classmethod
    def cost_not_negative(cls, v):
        if v is not None and v < 0: raise ValueError("Cost can't be negative")
        return v

class MaintenanceOut(TimestampSchema):
    asset_id: UUID; society_id: UUID; maintenance_type: MaintenanceType; status: MaintenanceStatus
    scheduled_date: date; completed_date: Optional[date]
    vendor_name: Optional[str]; vendor_contact: Optional[str] = None
    cost: Optional[Decimal]; description: Optional[str] = None
    findings: Optional[str]; next_due_date: Optional[date]


# ── AMC ───────────────────────────────────────────────────────────────────────
class AMCCreate(OrmBase):
    asset_id: UUID; vendor_name: str
    society_id: Optional[UUID]       = None   # ignored: taken from the asset
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
    asset_id: UUID; society_id: UUID; vendor_name: str; vendor_contact: Optional[str] = None
    contract_number: Optional[str]
    start_date: date; end_date: date; annual_cost: Optional[Decimal]
    coverage: Optional[str]; is_comprehensive: bool; auto_renew: bool


# ── History ───────────────────────────────────────────────────────────────────
class UsageLogOut(TimestampSchema):
    action: str; notes: Optional[str]; cost: Optional[Decimal]

class LinkedContractOut(OrmBase):
    id: UUID; contract_number: str; contract_name: str; status: str
    start_date: date; end_date: date; annual_value: Optional[Decimal]

class LinkedWorkOrderOut(OrmBase):
    id: UUID; wo_number: str; title: str; status: str; estimated_cost: Optional[Decimal]

class AssetHistoryOut(OrmBase):
    asset: AssetOut
    maintenance: List[MaintenanceOut]
    amc: List[AMCOut]
    contracts: List[LinkedContractOut]      # annual contracts from Vendors & Work that cover this asset
    work_orders: List[LinkedWorkOrderOut]   # work orders raised for this asset
    log: List[UsageLogOut]
    total_service_cost: Decimal             # completed services
