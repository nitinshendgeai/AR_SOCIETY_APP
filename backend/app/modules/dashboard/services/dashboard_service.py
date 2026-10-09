"""One call for the society dashboard: money, collection trend, occupancy and
what needs the office's attention. Everything is read from the existing
modules; nothing is stored here.

Each block is computed on its own and falls back to `None` (or an empty list)
if it fails, so one broken report never blanks the whole dashboard.
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Callable, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agreement_tracker import AgreementStatus, AgreementTracker
from app.models.flat import Flat, OccupancyStatus
from app.models.password_reset_request import PasswordResetRequest, PasswordResetStatus
from app.models.resident import Resident
from app.models.resident_edit_request import ResidentEditRequest, ResidentEditRequestStatus
from app.models.society import Society
from app.models.wing import Wing
from app.modules.accounts.services.accounts_service import AccountsService
from app.modules.accounts.services.recurring_expenses import RecurringExpenseService
from app.modules.amenity.models.amenity import AmenityBooking, BookingStatus
from app.modules.billing.models.billing import BillingCycle
from app.modules.billing.repositories.billing_repo import MaintenanceBillRepo
from app.modules.billing.routes.billing import _cycle_out
from app.modules.complaint.models.complaint import Complaint, ComplaintStatus
from app.modules.inventory.services.inventory_service import InventoryService
from app.modules.staff.models.staff import LeaveStatus, StaffAttendance, StaffLeave
from app.modules.vendor.models.vendor import VendorInvoice
from app.modules.visitor.models.visitor import Visitor, VisitorStatus
from app.utils.local_time import local_today, to_local, utc_naive, zone

logger = logging.getLogger(__name__)

ZERO = Decimal(0)
OPEN_COMPLAINTS = (ComplaintStatus.OPEN, ComplaintStatus.ASSIGNED,
                   ComplaintStatus.IN_PROGRESS, ComplaintStatus.REOPENED)


def _money(v) -> str:
    return str(Decimal(v or 0))


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _block(self, name: str, fn: Callable, default=None):
        try:
            return fn()
        except Exception:  # noqa: BLE001 - one block failing must not blank the page
            logger.exception("[dashboard] %s failed", name)
            self.db.rollback()
            return default

    def _flats(self, society_id: UUID):
        return (self.db.query(Flat).join(Wing, Flat.wing_id == Wing.id)
                .filter(Wing.society_id == society_id, Flat.is_active == True))

    # ── Blocks ───────────────────────────────────────────────────────────────

    def _collection(self, society_id: UUID) -> Optional[dict]:
        cycles = (self.db.query(BillingCycle)
                  .filter(BillingCycle.society_id == society_id, BillingCycle.is_active == True)
                  .order_by(BillingCycle.cycle_start.desc()).limit(6).all())
        if not cycles:
            return None
        rows = [_cycle_out(c) for c in cycles]            # newest first
        latest = rows[0]
        billed, collected = Decimal(latest["total_billed"]), Decimal(latest["total_collected"])
        return {
            "cycle_name": latest["name"],
            "due_date": latest["due_date"],
            "billed": _money(billed),
            "collected": _money(collected),
            "outstanding": latest["total_outstanding"],
            "percent": int((collected / billed * 100).to_integral_value()) if billed > 0 else 0,
            "bills": latest["bills_count"],
            "paid_bills": latest["paid_count"],
            "overdue_bills": latest["overdue_count"],
            "trend": [{"name": r["name"], "billed": r["total_billed"], "collected": r["total_collected"]}
                      for r in reversed(rows)],           # oldest first, for a chart
        }

    def _money_block(self, society_id: UUID) -> Optional[dict]:
        s = AccountsService(self.db).summary(society_id)
        return {
            "cash": _money(s["cash"]), "bank": _money(s["bank"]),
            "members_dues": _money(s["members_dues"]), "creditors": _money(s["creditors"]),
            "fy": s["fy"], "fy_income": _money(s["fy_income"]), "fy_expense": _money(s["fy_expense"]),
        }

    def _occupancy(self, society_id: UUID) -> dict:
        flats = self._flats(society_id).all()
        occupied = sum(1 for f in flats if f.occupancy_status not in (None, OccupancyStatus.VACANT))
        residents = (self.db.query(func.count(Resident.id))
                     .join(Flat, Resident.flat_id == Flat.id).join(Wing, Flat.wing_id == Wing.id)
                     .filter(Wing.society_id == society_id, Resident.is_active == True).scalar()) or 0
        return {"flats": len(flats), "occupied": occupied, "vacant": len(flats) - occupied,
                "residents": int(residents)}

    def _today(self, society_id: UUID, tz) -> dict:
        start = utc_naive(datetime.combine(local_today(tz), datetime.min.time(), tzinfo=tz))
        base = self.db.query(func.count(Visitor.id)).filter(Visitor.society_id == society_id)
        return {
            "visitors_today": int(base.filter(Visitor.created_at >= start).scalar() or 0),
            "visitors_inside": int(base.filter(Visitor.status == VisitorStatus.CHECKED_IN).scalar() or 0),
        }

    def _attention(self, society_id: UUID, today: date) -> list:
        db = self.db
        items = []

        def add(key: str, count: int, severity: str, **extra):
            if count:
                items.append({"key": key, "count": int(count), "severity": severity, **extra})

        # Money
        overdue = MaintenanceBillRepo(db).get_overdue(society_id)
        add("overdue_bills", len({b.flat_id for b in overdue}), "high",
            amount=_money(sum((b.outstanding for b in overdue), ZERO)))
        vendor_due = (db.query(VendorInvoice)
                      .filter(VendorInvoice.society_id == society_id, VendorInvoice.is_paid == False,
                              VendorInvoice.due_date != None, VendorInvoice.due_date < today).all())
        add("vendor_bills_overdue", len(vendor_due), "high",
            amount=_money(sum((v.total_amount - v.paid_amount for v in vendor_due), ZERO)))
        add("recurring_due", len(RecurringExpenseService(db).due(society_id)), "medium")

        # People
        in_30 = today + timedelta(days=30)
        agr = (db.query(AgreementTracker)
               .filter(AgreementTracker.society_id == society_id,
                       AgreementTracker.status == AgreementStatus.ACTIVE,
                       AgreementTracker.end_date <= in_30).all())
        add("agreements_expired", sum(1 for a in agr if a.end_date < today), "high")
        add("agreements_expiring", sum(1 for a in agr if a.end_date >= today), "medium")
        add("resident_changes", db.query(func.count(ResidentEditRequest.id)).filter(
            ResidentEditRequest.society_id == society_id,
            ResidentEditRequest.status == ResidentEditRequestStatus.PENDING).scalar(), "medium")
        add("password_resets", db.query(func.count(PasswordResetRequest.id)).filter(
            PasswordResetRequest.society_id == society_id,
            PasswordResetRequest.status == PasswordResetStatus.PENDING).scalar(), "medium")

        # Services
        now = datetime.utcnow()
        open_q = db.query(Complaint).filter(Complaint.society_id == society_id,
                                            Complaint.status.in_(OPEN_COMPLAINTS))
        add("complaints_old", open_q.filter(Complaint.created_at < now - timedelta(days=7)).count(), "high")
        add("complaints_open", open_q.count(), "info")
        add("amenity_requests", db.query(func.count(AmenityBooking.id)).filter(
            AmenityBooking.society_id == society_id,
            AmenityBooking.status == BookingStatus.PENDING).scalar(), "medium")

        # Staff
        add("punch_approvals", db.query(func.count(StaffAttendance.id)).filter(
            StaffAttendance.society_id == society_id, StaffAttendance.is_active == True,
            StaffAttendance.is_approved == False).scalar(), "medium")
        add("leave_requests", db.query(func.count(StaffLeave.id)).filter(
            StaffLeave.society_id == society_id, StaffLeave.is_active == True,
            StaffLeave.status == LeaveStatus.PENDING).scalar(), "medium")

        # Stores
        add("low_stock", len(InventoryService(db).get_low_stock_items(society_id)), "medium")

        order = {"high": 0, "medium": 1, "info": 2}
        items.sort(key=lambda i: (order[i["severity"]], -i["count"]))
        return items

    # ── Public ───────────────────────────────────────────────────────────────

    def society(self, society_id: UUID) -> dict:
        society = self.db.query(Society).filter(Society.id == society_id).first()
        tz = zone(getattr(society, "timezone", None))
        today = local_today(tz)
        return {
            "as_of": today.isoformat(),
            "collection": self._block("collection", lambda: self._collection(society_id)),
            "money": self._block("money", lambda: self._money_block(society_id)),
            "occupancy": self._block("occupancy", lambda: self._occupancy(society_id)),
            "today": self._block("today", lambda: self._today(society_id, tz)),
            "attention": self._block("attention", lambda: self._attention(society_id, today), []),
        }
