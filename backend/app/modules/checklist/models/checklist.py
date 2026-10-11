"""The society manager's daily checklist: the routine and statutory items a manager works through, what has been
done against them, and the end-of-day sign-off."""
from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin

CATEGORIES = ("security", "housekeeping", "technical", "assets", "staff", "accounts", "residents", "safety",
              "compliance")
CATEGORY_LABELS = {
    "security": "Security & gate", "housekeeping": "Housekeeping & garden", "technical": "Water, power & technical",
    "assets": "Assets & equipment", "staff": "Staff", "accounts": "Accounts & money",
    "residents": "Residents & services", "safety": "Safety", "compliance": "Statutory & compliance",
}
# daily: every day · weekly: on `due_weekday` · monthly: on `due_day` of every month · on_dates: on `due_day` of
# the months in `due_months` · licence: renewed by the date a licence or certificate runs to (`valid_until`).
FREQUENCIES = ("daily", "weekly", "monthly", "on_dates", "licence")
FREQUENCY_LABELS = {"daily": "Every day", "weekly": "Every week", "monthly": "Every month",
                    "on_dates": "On fixed dates", "licence": "When the licence or certificate runs out"}
LOG_STATUSES = ("done", "skipped")


class ChecklistItem(Base, TimestampMixin):
    """One thing the manager does: a standard item from the built-in list (carries a `code`, a society can switch
    it off or reword it) or one the society added."""
    __tablename__ = "manager_checklist_items"
    __table_args__ = (UniqueConstraint("society_id", "code", name="uq_checklist_society_code"),)

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(60), nullable=True)
    title = Column(String(200), nullable=False)
    detail = Column(Text, nullable=True)
    category = Column(String(20), nullable=False, default="housekeeping")
    frequency = Column(String(10), nullable=False, default="daily")
    due_weekday = Column(Integer, nullable=True)          # 0 Monday … 6 Sunday
    due_day = Column(Integer, nullable=True)              # day of the month; 31 means the last day
    due_months = Column(String(40), nullable=True)        # "1,7": the months of an on_dates item
    lead_days = Column(Integer, nullable=False, default=0)    # show this many days before it falls due
    # Applies only when the society has an active asset of this kind / active staff in this department ("any": any).
    asset_category = Column(String(30), nullable=True)
    staff_department = Column(String(30), nullable=True)
    statutory = Column(Boolean, nullable=False, default=False)
    legal_basis = Column(Text, nullable=True)
    jurisdiction = Column(String(20), nullable=True)      # central | maharashtra | None for the society's own
    link_key = Column(String(30), nullable=True)          # the app screen that does the work
    is_enabled = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=100)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ChecklistLog(Base, TimestampMixin):
    """An item done (or skipped as not applicable) for one occurrence — `for_date` is the date it fell due."""
    __tablename__ = "manager_checklist_logs"
    __table_args__ = (UniqueConstraint("item_id", "for_date", name="uq_checklist_log_item_date"),)

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(UUID(as_uuid=True), ForeignKey("manager_checklist_items.id", ondelete="CASCADE"), nullable=False,
                     index=True)
    for_date = Column(Date, nullable=False, index=True)
    status = Column(String(10), nullable=False, default="done")
    done_on = Column(Date, nullable=False)                # the day it was actually done
    note = Column(Text, nullable=True)
    reference = Column(String(120), nullable=True)        # certificate, receipt or challan number
    valid_until = Column(Date, nullable=True)             # a licence or certificate, as renewed
    done_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ChecklistSignoff(Base, TimestampMixin):
    """The manager closing the day: what was done, what was left, and a word on it."""
    __tablename__ = "manager_checklist_signoffs"
    __table_args__ = (UniqueConstraint("society_id", "for_date", name="uq_checklist_signoff_day"),)

    society_id = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    for_date = Column(Date, nullable=False, index=True)
    signed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    remarks = Column(Text, nullable=True)
    routine_total = Column(Integer, nullable=False, default=0)
    routine_done = Column(Integer, nullable=False, default=0)
    live_open = Column(Integer, nullable=False, default=0)
