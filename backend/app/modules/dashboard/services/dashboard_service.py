"""One call for the society dashboard: money, collection trend, occupancy and
what needs the office's attention. Everything is read from the existing
modules; nothing is stored here.

Each block is computed on its own and falls back to `None` (or an empty list)
if it fails, so one broken report never blanks the whole dashboard. A block that
failed is named in the response's `errors` list, so the app can say "could not
load" instead of showing the fallback as if it were a real empty result.
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
from app.modules.billing.routes.billing import _cycle_out
from app.modules.billing.services.defaulters import MemberDues, months_before
from app.modules.complaint.models.complaint import OPEN_STATUSES, Complaint
from app.modules.inventory.services.inventory_service import InventoryService
from app.modules.staff.models.staff import LeaveStatus, Staff, StaffAttendance, StaffLeave
from app.modules.vendor.models.vendor import VendorInvoice
from app.modules.visitor.models.visitor import Visitor, VisitorStatus
from app.utils.local_time import local_today, to_local, utc_naive, zone

logger = logging.getLogger(__name__)

ZERO = Decimal(0)
# A flat is a defaulter when part of its dues has been outstanding longer than this many months after the due date.
# It is the Defaulters screen's own default, so the dashboard and that screen show the same flats.
DEFAULT_MONTHS = 3


def _money(v) -> str:
    return str(Decimal(v or 0))


# The optional service each "needs attention" item belongs to (items not listed are core).
ATTENTION_SERVICE = {
    "vendor_bills_overdue": "vendors", "recurring_due": "accounts",
    "complaints_old": "complaints", "complaints_open": "complaints", "amenity_requests": "amenities",
    "punch_approvals": "staff", "leave_requests": "staff", "low_stock": "inventory",
}


class DashboardService:
    def __init__(self, db: Session):
        self.db = db
        self.errors: list = []      # names of the blocks that failed in this call
        self._dues_cache: dict = {}

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _block(self, name: str, fn: Callable, default=None):
        try:
            return fn()
        except Exception:  # noqa: BLE001 - one block failing must not blank the page
            logger.exception("[dashboard] %s failed", name)
            self.db.rollback()
            self.errors.append(name)
            return default

    def _member_dues(self, society_id: UUID, today: date) -> list:
        """Every flat with dues, once per call: the money card and the defaulters row both read it."""
        key = (society_id, today)
        if key not in self._dues_cache:
            self._dues_cache[key] = MemberDues(self.db).flats(society_id, today)
        return self._dues_cache[key]

    def _flats(self, society_id: UUID):
        return (self.db.query(Flat).join(Wing, Flat.wing_id == Wing.id)
                .filter(Wing.society_id == society_id, Flat.is_active == True))

    # ── Blocks ───────────────────────────────────────────────────────────────

    def _collection(self, society_id: UUID, today: date) -> Optional[dict]:
        cycles = (self.db.query(BillingCycle)
                  .filter(BillingCycle.society_id == society_id, BillingCycle.is_active == True)
                  .order_by(BillingCycle.cycle_start.desc()).limit(6).all())
        if not cycles:
            return None
        rows = [_cycle_out(c, today) for c in cycles]     # newest first
        latest = rows[0]
        billed, collected = Decimal(latest["total_billed"]), Decimal(latest["total_collected"])
        return {
            "cycle_name": latest["name"],
            "due_date": latest["due_date"],
            "billed": _money(billed),
            "collected": _money(collected),
            "outstanding": latest["total_outstanding"],
            # Whole percent, rounded down: 99.6% collected must not read "100%" while money is still outstanding.
            "percent": (100 if collected >= billed else int(collected / billed * 100)) if billed > 0 else 0,
            "bills": latest["bills_count"],
            "paid_bills": latest["paid_count"],
            "overdue_bills": latest["overdue_count"],
            "trend": [{"name": r["name"], "billed": r["total_billed"], "collected": r["total_collected"]}
                      for r in reversed(rows)],           # oldest first, for a chart
        }

    def _money_block(self, society_id: UUID, today: date) -> Optional[dict]:
        s = AccountsService(self.db).summary(society_id)
        # What members owe is worked out from their unpaid bills, less money paid on account - the very figure the
        # Defaulters screen (and the outstanding report) total up, which is where this card leads. The books' own
        # Members' Dues balance is on the Accounts screen.
        dues = sum((fd.total for fd in self._member_dues(society_id, today)), ZERO)
        return {
            "cash": _money(s["cash"]), "bank": _money(s["bank"]),
            "members_dues": _money(dues), "creditors": _money(s["creditors"]),
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

    def _staff(self, society_id: UUID) -> dict:
        """Active staff, all of them (the staff list screen pages its rows, so counting its first page would stop at 50)."""
        n = (self.db.query(func.count(Staff.id))
             .filter(Staff.society_id == society_id, Staff.is_active == True).scalar())  # noqa: E712
        return {"active": int(n or 0)}

    def _gate_today(self, society_id: UUID, tz) -> dict:
        """What the gate needs: visitors logged today, how many were let in today, and who is inside now."""
        start = utc_naive(datetime.combine(local_today(tz), datetime.min.time(), tzinfo=tz))
        base = self.db.query(func.count(Visitor.id)).filter(Visitor.society_id == society_id)
        return {
            "visitors_today": int(base.filter(Visitor.created_at >= start).scalar() or 0),
            "checked_in_today": int(base.filter(Visitor.checked_in_at >= start).scalar() or 0),
            "visitors_inside": int(base.filter(Visitor.status == VisitorStatus.CHECKED_IN).scalar() or 0),
        }

    def _attention(self, society_id: UUID, today: date) -> list:
        db = self.db
        items = []

        def add(key: str, count: int, severity: str, **extra):
            if count:
                items.append({"key": key, "count": int(count), "severity": severity, **extra})

        # Money
        # Defaulters: the flats the Defaulters screen lists by default (dues outstanding over DEFAULT_MONTHS months
        # after the due date) and what they owe in all - its own "Defaulters" card, figure for figure.
        cutoff = months_before(today, DEFAULT_MONTHS)
        defaulters = [fd for fd in self._member_dues(society_id, today) if fd.overdue_beyond(cutoff) > 0]
        add("overdue_bills", len(defaulters), "high",
            amount=_money(sum((fd.total for fd in defaulters), ZERO)), months=DEFAULT_MONTHS)
        vendor_due = (db.query(VendorInvoice)
                      .filter(VendorInvoice.society_id == society_id, VendorInvoice.is_paid == False,
                              VendorInvoice.is_active == True,
                              VendorInvoice.due_date != None, VendorInvoice.due_date < today).all())
        add("vendor_bills_overdue", len(vendor_due), "high",
            amount=_money(sum((v.total_amount - (v.tds_amount or 0) - v.paid_amount for v in vendor_due), ZERO)))
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
        open_q = db.query(Complaint).filter(Complaint.society_id == society_id, Complaint.is_active == True,  # noqa: E712
                                            Complaint.status.in_(OPEN_STATUSES))
        add("complaints_old", open_q.filter(Complaint.created_at < now - timedelta(days=7)).count(), "high")
        add("complaints_open", open_q.count(), "info")
        add("amenity_requests", db.query(func.count(AmenityBooking.id)).filter(
            AmenityBooking.society_id == society_id,
            AmenityBooking.status == BookingStatus.PENDING).scalar(), "medium")

        # Staff
        # Punch-ins and punch-outs waiting for approval: both lists on the Approvals screen.
        punches = db.query(func.count(StaffAttendance.id)).filter(
            StaffAttendance.society_id == society_id, StaffAttendance.is_active == True,  # noqa: E712
            StaffAttendance.is_approved == False).scalar() or 0  # noqa: E712
        punches += db.query(func.count(StaffAttendance.id)).filter(
            StaffAttendance.society_id == society_id, StaffAttendance.is_active == True,  # noqa: E712
            StaffAttendance.check_out_time.isnot(None),
            StaffAttendance.is_checkout_approved == False).scalar() or 0  # noqa: E712
        add("punch_approvals", punches, "medium")
        add("leave_requests", db.query(func.count(StaffLeave.id)).filter(
            StaffLeave.society_id == society_id, StaffLeave.is_active == True,
            StaffLeave.status == LeaveStatus.PENDING).scalar(), "medium")

        # Stores
        add("low_stock", len(InventoryService(db).get_low_stock_items(society_id)), "medium")

        # Nothing is raised about a service the platform owner has switched off for this society.
        from app.core.services_catalog import off_services
        off = off_services(db, society_id)
        items = [i for i in items if ATTENTION_SERVICE.get(i["key"]) not in off]
        order = {"high": 0, "medium": 1, "info": 2}
        items.sort(key=lambda i: (order[i["severity"]], -i["count"]))
        return items

    # ── Public ───────────────────────────────────────────────────────────────

    def attention(self, society_id: UUID, today: date) -> list:
        """What needs the office's attention today, most urgent first (the same list the dashboard shows)."""
        return self._attention(society_id, today)

    def security(self, society_id: UUID) -> dict:
        """The gate's own summary (security roles): today's visitor figures only, nothing about money or people."""
        from app.core.services_catalog import off_services
        off = off_services(self.db, society_id)
        society = self.db.query(Society).filter(Society.id == society_id).first()
        tz = zone(getattr(society, "timezone", None))
        body = {
            "as_of": local_today(tz).isoformat(),
            "today": None if "visitors" in off else self._block("today", lambda: self._gate_today(society_id, tz)),
        }
        body["errors"] = list(self.errors)
        return body

    def society(self, society_id: UUID) -> dict:
        from app.core.services_catalog import off_services
        off = off_services(self.db, society_id)
        society = self.db.query(Society).filter(Society.id == society_id).first()
        tz = zone(getattr(society, "timezone", None))
        today = local_today(tz)
        body = {
            "as_of": today.isoformat(),
            "collection": self._block("collection", lambda: self._collection(society_id, today)),
            "money": None if "accounts" in off else self._block("money", lambda: self._money_block(society_id, today)),
            "occupancy": self._block("occupancy", lambda: self._occupancy(society_id)),
            "today": None if "visitors" in off else self._block("today", lambda: self._today(society_id, tz)),
            "staff": None if "staff" in off else self._block("staff", lambda: self._staff(society_id)),
            "attention": self._block("attention", lambda: self._attention(society_id, today), []),
        }
        body["errors"] = list(self.errors)      # [] when every block loaded
        return body
