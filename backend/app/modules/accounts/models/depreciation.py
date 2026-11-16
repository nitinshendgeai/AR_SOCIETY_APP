"""Depreciation setup for the society's fixed assets.

- DepreciationRule: for each asset category, how it is depreciated (reducing balance / straight line), the yearly
  rate, the life and residual value, and the fixed-asset ledger it belongs to. The first time a society opens the
  setup it is filled with starting values, which the society (and its auditor) then edits.
- AssetDepreciation: one asset's own setting where it differs from its category's — a method or rate of its own, a
  residual value, the date it was put to use and the date it stopped being used.

Nothing here posts to the books: the schedule is worked out from these settings and the asset register on demand.
"""
from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin

METHODS = ("wdv", "slm")
METHOD_LABELS = {"wdv": "Reducing balance (written down value)", "slm": "Straight line"}


class DepreciationRule(Base, TimestampMixin):
    __tablename__ = "depreciation_rules"
    __table_args__ = (UniqueConstraint("society_id", "asset_category", name="uq_dep_rule_society_category"),)

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_category = Column(String(30), nullable=False)
    method = Column(String(5), nullable=False, default="wdv", server_default="wdv")
    rate = Column(Numeric(7, 4), nullable=False, default=0, server_default="0")                # percent a year
    life_years = Column(Integer, nullable=True)                 # straight line with no rate: the rate is 100 / life
    salvage_percent = Column(Numeric(5, 2), nullable=False, default=0, server_default="0")    # residual value, % of cost
    ledger_system_key = Column(String(50), nullable=True)       # the fixed-asset ledger the category sits under
    notes = Column(String(300), nullable=True)


class AssetDepreciation(Base, TimestampMixin):
    __tablename__ = "asset_depreciation"
    __table_args__ = (UniqueConstraint("asset_id", name="uq_asset_depreciation_asset"),)

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    depreciate = Column(Boolean, nullable=False, default=True, server_default="true")   # false: never depreciated (land, say)
    method = Column(String(5), nullable=True)                   # empty: the category's
    rate = Column(Numeric(7, 4), nullable=True)
    life_years = Column(Integer, nullable=True)
    salvage_value = Column(Numeric(14, 2), nullable=True)       # empty: the category's % of cost
    start_on = Column(Date, nullable=True)                      # empty: the purchase date
    stop_on = Column(Date, nullable=True)                       # sold, scrapped or lost: depreciation runs up to this day
