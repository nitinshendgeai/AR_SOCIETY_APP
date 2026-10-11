"""What needs the manager's attention today, read straight from the society's own records.

Nothing is stored: each line is a count taken now, so it clears by itself once the work is done. The items depend on
what the society has: asset checks come from the assets register, staff checks from the staff and duty records.
Every block fails on its own (it is logged and left out) so one broken report never blanks the checklist.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.accounts.models.accounts import Voucher
from app.modules.certificates.models.certificates import CertificateRequest
from app.modules.dashboard.services.dashboard_service import DashboardService
from app.modules.gate.models.gate import Parcel
from app.modules.inventory.models.inventory import (Asset, AssetAMC, AssetMaintenance, AssetStatus, MaintenanceStatus)
from app.modules.staff.models.staff import (AttendanceStatus, DutyAssignment, LeaveStatus, Staff, StaffAttendance,
                                            StaffLeave, StaffStatus)
from app.modules.vendor.models.vendor import AMCContract, ContractStatus, WorkOrder, WorkOrderStatus
from app.utils.local_time import to_local

logger = logging.getLogger(__name__)

LIVE_ASSET_STATUSES = (AssetStatus.ACTIVE, AssetStatus.UNDER_MAINTENANCE)
ACTIVE_STAFF = (StaffStatus.ACTIVE, StaffStatus.PROBATION, StaffStatus.ON_LEAVE)

# The dashboard's own "needs attention" keys, as checklist lines: (category, link, title for a count).
_FROM_DASHBOARD: Dict[str, tuple] = {
    "overdue_bills": ("accounts", "defaulters", "{n} flat(s) have overdue maintenance bills"),
    "vendor_bills_overdue": ("accounts", "vendors", "{n} vendor bill(s) are past their due date"),
    "recurring_due": ("accounts", "recurring", "{n} recurring expense(s) are due to be booked"),
    "agreements_expired": ("residents", "tenants", "{n} rent agreement(s) have expired"),
    "agreements_expiring": ("residents", "tenants", "{n} rent agreement(s) expire within 30 days"),
    "resident_changes": ("residents", "pending_changes", "{n} resident change request(s) await review"),
    "password_resets": ("residents", "password_resets", "{n} password reset request(s) await action"),
    "complaints_old": ("residents", "complaints", "{n} complaint(s) have been open for over a week"),
    "complaints_open": ("residents", "complaints", "{n} complaint(s) are open"),
    "amenity_requests": ("residents", "amenities", "{n} amenity booking request(s) await approval"),
    "punch_approvals": ("staff", "staff_approvals", "{n} staff check-in/out punch(es) await approval"),
    "leave_requests": ("staff", "staff_approvals", "{n} staff leave request(s) await a decision"),
    "low_stock": ("assets", "inventory", "{n} store item(s) are at or below the minimum stock"),
}


def _names(rows, attr: str = "name", limit: int = 3) -> str:
    names = [getattr(r, attr) for r in rows[:limit]]
    more = len(rows) - len(names)
    return ", ".join(names) + (f" and {more} more" if more > 0 else "")


class LiveItems:
    def __init__(self, db: Session):
        self.db = db

    def _safe(self, name: str, fn: Callable[[], List[dict]]) -> List[dict]:
        try:
            return fn()
        except Exception:  # noqa: BLE001 - one block failing must not blank the checklist
            logger.exception("[checklist] live block %s failed", name)
            self.db.rollback()
            return []

    @staticmethod
    def _line(key: str, category: str, link: str, severity: str, title: str, count: int, detail: str = "") -> dict:
        return {"key": key, "category": category, "link_key": link, "severity": severity, "title": title,
                "count": int(count), "detail": detail or None}

    # ── Assets ──────────────────────────────────────────────────────────────────────────────────────────────────
    def assets(self, society_id: UUID, today: date) -> List[dict]:
        db, out = self.db, []
        base = db.query(Asset).filter(Asset.society_id == society_id, Asset.is_active == True,  # noqa: E712
                                      Asset.status.in_(LIVE_ASSET_STATUSES))
        overdue = base.filter(Asset.next_service_due != None, Asset.next_service_due < today).all()  # noqa: E711
        if overdue:
            out.append(self._line("assets_service_overdue", "assets", "assets", "high",
                                  f"{len(overdue)} asset(s) are overdue for service", len(overdue), _names(overdue)))
        soon = base.filter(Asset.next_service_due >= today, Asset.next_service_due <= today + timedelta(days=7)).all()
        if soon:
            out.append(self._line("assets_service_soon", "assets", "assets", "medium",
                                  f"{len(soon)} asset(s) fall due for service this week", len(soon), _names(soon)))
        down = base.filter(Asset.status == AssetStatus.UNDER_MAINTENANCE).all()
        if down:
            out.append(self._line("assets_down", "assets", "assets", "medium",
                                  f"{len(down)} asset(s) are out of use for maintenance", len(down), _names(down)))
        warranty = base.filter(Asset.warranty_expiry != None, Asset.warranty_expiry >= today,  # noqa: E711
                               Asset.warranty_expiry <= today + timedelta(days=30)).all()
        if warranty:
            out.append(self._line("warranty_expiring", "assets", "assets", "info",
                                  f"{len(warranty)} asset warranty(ies) end within 30 days — claim any fault now",
                                  len(warranty), _names(warranty)))
        # AMCs: ended with no later cover, or ending within 30 days.
        amcs = (db.query(AssetAMC).join(Asset, AssetAMC.asset_id == Asset.id)
                .filter(AssetAMC.society_id == society_id, AssetAMC.is_active == True,  # noqa: E712
                        Asset.is_active == True, Asset.status.in_(LIVE_ASSET_STATUSES)).all())  # noqa: E712
        latest: Dict[UUID, AssetAMC] = {}
        for a in amcs:
            if a.asset_id not in latest or a.end_date > latest[a.asset_id].end_date:
                latest[a.asset_id] = a
        lapsed = [a for a in latest.values() if a.end_date < today]
        ending = [a for a in latest.values() if today <= a.end_date <= today + timedelta(days=30)]
        if lapsed:
            out.append(self._line("amc_lapsed", "assets", "assets", "high",
                                  f"{len(lapsed)} asset(s) have no AMC cover — it ended", len(lapsed),
                                  _names([a.asset for a in lapsed if a.asset])))
        if ending:
            out.append(self._line("amc_ending", "assets", "assets", "medium",
                                  f"{len(ending)} AMC(s) end within 30 days — renew", len(ending),
                                  _names([a.asset for a in ending if a.asset])))
        sched = (db.query(func.count(AssetMaintenance.id))
                 .filter(AssetMaintenance.society_id == society_id, AssetMaintenance.is_active == True,  # noqa: E712
                         AssetMaintenance.status.in_((MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS)),
                         AssetMaintenance.scheduled_date <= today).scalar() or 0)
        if sched:
            out.append(self._line("maintenance_due", "assets", "assets", "medium",
                                  f"{sched} scheduled maintenance job(s) are due or running", sched))
        contracts = (db.query(AMCContract).filter(AMCContract.society_id == society_id,
                                                  AMCContract.is_active == True,  # noqa: E712
                                                  AMCContract.status == ContractStatus.ACTIVE,
                                                  AMCContract.end_date >= today,
                                                  AMCContract.end_date <= today + timedelta(days=30)).all())
        if contracts:
            out.append(self._line("contracts_ending", "assets", "vendors", "medium",
                                  f"{len(contracts)} vendor contract(s) end within 30 days — renew or re-tender",
                                  len(contracts), _names(contracts, "contract_name")))
        late = (db.query(WorkOrder).filter(WorkOrder.society_id == society_id, WorkOrder.is_active == True,  # noqa: E712
                                           WorkOrder.status.in_((WorkOrderStatus.SANCTIONED, WorkOrderStatus.ISSUED)),
                                           WorkOrder.due_date != None, WorkOrder.due_date < today).all())  # noqa: E711
        if late:
            out.append(self._line("work_orders_late", "assets", "vendors", "high",
                                  f"{len(late)} work order(s) are past their completion date", len(late)))
        return out

    # ── Staff ───────────────────────────────────────────────────────────────────────────────────────────────────
    def staff(self, society_id: UUID, today: date, tz) -> List[dict]:
        db, out = self.db, []
        now_local = datetime.now(tz)
        # Staff with a duty today whose shift has started but who have not checked in.
        duties = (db.query(DutyAssignment).filter(DutyAssignment.society_id == society_id,
                                                  DutyAssignment.is_active == True,  # noqa: E712
                                                  DutyAssignment.duty_date == today).all())
        started = [d for d in duties if d.start_time is None or d.start_time <= now_local.time()]
        in_ids = {r[0] for r in db.query(StaffAttendance.staff_id).filter(
            StaffAttendance.society_id == society_id, StaffAttendance.attendance_date == today,
            StaffAttendance.is_active == True, StaffAttendance.check_in_time != None).all()}  # noqa: E712,E711
        missing = {}
        for d in started:
            if d.staff_id not in in_ids and d.staff is not None and d.staff.status in ACTIVE_STAFF:
                missing[d.staff_id] = d.staff
        if missing:
            out.append(self._line("staff_not_in", "staff", "staff", "high",
                                  f"{len(missing)} staff member(s) on duty today have not checked in", len(missing),
                                  _names(list(missing.values()), "full_name")))
        # Approved leave covering today.
        on_leave = (db.query(StaffLeave).filter(StaffLeave.society_id == society_id, StaffLeave.is_active == True,  # noqa: E712
                                                StaffLeave.status == LeaveStatus.APPROVED,
                                                StaffLeave.from_date <= today, StaffLeave.to_date >= today).all())
        if on_leave:
            out.append(self._line("staff_on_leave", "staff", "staff", "info",
                                  f"{len(on_leave)} staff member(s) are on approved leave today — cover their posts",
                                  len(on_leave), _names([l.staff for l in on_leave if l.staff], "full_name")))
        # Duties from the last week left open.
        open_old = (db.query(func.count(DutyAssignment.id))
                    .filter(DutyAssignment.society_id == society_id, DutyAssignment.is_active == True,  # noqa: E712
                            DutyAssignment.is_completed == False,  # noqa: E712
                            DutyAssignment.duty_date < today,
                            DutyAssignment.duty_date >= today - timedelta(days=7)).scalar() or 0)
        if open_old:
            out.append(self._line("duties_open", "staff", "staff", "medium",
                                  f"{open_old} duty(ies) from the last 7 days were not completed", open_old))
        # Staff with no duty today, where the society plans duties at all.
        if duties or db.query(DutyAssignment.id).filter(
                DutyAssignment.society_id == society_id,
                DutyAssignment.duty_date >= today - timedelta(days=7)).first():
            have = {d.staff_id for d in duties}
            leave_ids = {l.staff_id for l in on_leave}
            staff = db.query(Staff).filter(Staff.society_id == society_id, Staff.is_active == True,  # noqa: E712
                                           Staff.status.in_((StaffStatus.ACTIVE, StaffStatus.PROBATION))).all()
            idle = [s for s in staff if s.id not in have and s.id not in leave_ids]
            if idle:
                out.append(self._line("staff_no_duty", "staff", "staff", "medium",
                                      f"{len(idle)} staff member(s) have no duty assigned today", len(idle),
                                      _names(idle, "full_name")))
        return out

    # ── The rest of the society ─────────────────────────────────────────────────────────────────────────────────
    def society(self, society_id: UUID, today: date) -> List[dict]:
        db, out = self.db, []
        for item in DashboardService(db).attention(society_id, today):
            spec = _FROM_DASHBOARD.get(item["key"])
            if spec:
                category, link, title = spec
                detail = None
                if item.get("amount"):
                    detail = f"₹{item['amount']}"
                out.append(self._line(item["key"], category, link, item["severity"],
                                      title.format(n=item["count"]), item["count"], detail or ""))
        pending = (db.query(func.count(Voucher.id)).filter(Voucher.society_id == society_id,
                                                           Voucher.is_active == True,  # noqa: E712
                                                           Voucher.approval_status == "pending").scalar() or 0)
        if pending:
            out.append(self._line("vouchers_pending", "accounts", "approvals", "high",
                                  f"{pending} payment/journal voucher(s) await approval — they are not in the books "
                                  f"until approved", pending))
        certs = (db.query(func.count(CertificateRequest.id)).filter(CertificateRequest.society_id == society_id,
                                                                   CertificateRequest.is_active == True,  # noqa: E712
                                                                   CertificateRequest.status == "pending").scalar() or 0)
        if certs:
            out.append(self._line("certificates_pending", "residents", "certificates", "medium",
                                  f"{certs} NOC / certificate request(s) await a decision", certs))
        cutoff = datetime.utcnow() - timedelta(days=2)
        parcels = (db.query(func.count(Parcel.id)).filter(Parcel.society_id == society_id,
                                                          Parcel.is_active == True,  # noqa: E712
                                                          Parcel.status == "at_gate",
                                                          Parcel.received_at < cutoff).scalar() or 0)
        if parcels:
            out.append(self._line("parcels_waiting", "security", "parcels", "info",
                                  f"{parcels} parcel(s) have waited at the gate for over 2 days", parcels))
        return out

    # ── Everything ──────────────────────────────────────────────────────────────────────────────────────────────
    def all(self, society_id: UUID, today: date, tz) -> List[dict]:
        lines = (self._safe("assets", lambda: self.assets(society_id, today))
                 + self._safe("staff", lambda: self.staff(society_id, today, tz))
                 + self._safe("society", lambda: self.society(society_id, today)))
        seen, merged = set(), []
        for l in lines:
            if l["key"] not in seen:
                seen.add(l["key"])
                merged.append(l)
        order = {"high": 0, "medium": 1, "info": 2}
        merged.sort(key=lambda l: (order.get(l["severity"], 3), -l["count"]))
        return merged
