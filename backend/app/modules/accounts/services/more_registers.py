"""More registers a society keeps, in one shared shape so the app and the printout draw them all the same way.

- the rental register: every flat and shop that is let out, with the tenant, agreement, rent and deposit, and how long
  the agreement still has to run;
- the receipts register: every payment received from members, what it was set off against, and any advance left;
- the staff attendance register: a month's grid of present, absent, half-day and leave for each staff member.

Each is read-only. A register is {title, subtitle, columns, rows, totals, statuses, uses_period, uses_month} where
`columns` say what to draw (key, label, whether it is a number, its width on paper, whether a phone shows it) and every
row is a dict of display strings keyed by column. Adding a register is one more method here and one more line in
REGISTERS; the app screen and the PDF need nothing.
"""
import calendar
import csv
import io
import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.agreement_tracker import AgreementStatus, AgreementTracker
from app.models.flat import Flat
from app.models.tenant import Tenant
from app.models.wing import Wing
from app.modules.accounts.services.accounts_service import money
from app.modules.billing.models.billing import OnlinePaymentSubmission, ReconciliationStatus
from app.modules.billing.services.allocations import allocated, payment_counts, unapplied
from app.modules.billing.services.bill_pdf import flat_label, member_name
from app.modules.shops.models.shop import Shop
from app.modules.staff.models.staff import AttendanceStatus, LeaveStatus, Staff, StaffAttendance, StaffLeave, StaffStatus

ZERO = Decimal("0.00")
EXPIRING_DAYS = 60
MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _amt(v) -> str:
    return str(money(v))


def _col(key: str, label: str, width: float = 0, right: bool = False, phone: bool = False) -> dict:
    return {"key": key, "label": label, "width": width, "right": right, "phone": phone}


def _fmt_date(d: Optional[date]) -> str:
    return d.strftime("%d-%m-%Y") if d else ""


def _words(value: str) -> str:
    return value.replace("_", " ").capitalize()


class MoreRegistersService:
    def __init__(self, db: Session):
        self.db = db

    # ── Rental register ───────────────────────────────────────────────────────

    RENTAL_STATUSES = [(None, "All"), ("active", "Running"), ("expiring", f"Expiring in {EXPIRING_DAYS} days"),
                       ("expired", "Expired"), ("no_agreement", "No agreement dates"), ("past", "Past tenants")]

    def rental_register(self, society_id: UUID, status: Optional[str] = None, q: Optional[str] = None) -> dict:
        today = date.today()
        tenants = (self.db.query(Tenant).join(Flat, Tenant.flat_id == Flat.id).join(Wing, Flat.wing_id == Wing.id)
                   .options(joinedload(Tenant.flat).joinedload(Flat.wing),
                            joinedload(Tenant.flat).selectinload(Flat.residents))
                   .filter(Wing.society_id == society_id).order_by(Wing.name, Flat.flat_number).all())
        trackers: Dict[UUID, AgreementTracker] = {}
        for a in (self.db.query(AgreementTracker).filter(AgreementTracker.society_id == society_id,
                                                         AgreementTracker.is_active == True)  # noqa: E712
                  .order_by(AgreementTracker.start_date).all()):
            trackers[a.tenant_id] = a                      # the latest agreement of each tenant wins
        rows: List[dict] = []
        for t in tenants:
            past = (not t.is_active) or t.move_out_date is not None
            tr = trackers.get(t.id)
            start = (tr.start_date if tr else None) or t.agreement_start_date or t.lease_start_date
            end = (tr.end_date if tr else None) or t.agreement_end_date or t.lease_end_date
            rent = (tr.monthly_rent if tr and tr.monthly_rent is not None else t.monthly_rent)
            deposit = (tr.security_deposit if tr and tr.security_deposit is not None else t.security_deposit)
            state = ("past" if past else "no_agreement" if end is None else "expired" if end < today
                     else "expiring" if (end - today).days <= EXPIRING_DAYS else "active")
            rows.append(self._rental_row(
                kind="Flat", unit=flat_label(t.flat), owner=member_name(t.flat), tenant=t.full_name, mobile=t.phone,
                agreement_no=(tr.agreement_number if tr else None) or "", start=start, end=end, today=today,
                rent=rent, deposit=deposit, how=self._channel(tr.channel if tr else t.agreement_channel,
                                                              tr.channel_name if tr else t.agreement_channel_name),
                police=_words(t.police_verification_status.value) if t.police_verification_status else "",
                state=state))
        for s in (self.db.query(Shop).filter(Shop.society_id == society_id, Shop.is_active == True,  # noqa: E712
                                              Shop.occupancy == "rented").order_by(Shop.shop_number).all()):
            rows.append(self._rental_row(
                kind="Shop", unit=f"Shop {s.shop_number}", owner=s.owner_name, tenant=s.tenant_name or "",
                mobile=s.tenant_phone, agreement_no="", start=None, end=None, today=today, rent=None, deposit=None,
                how="", police="", state="no_agreement"))
        # Past tenants (moved out) are listed only when asked for; every other view is of the tenancies running now
        shown = [r for r in rows if r["_state"] == status] if status else [r for r in rows if r["_state"] != "past"]
        needle = (q or "").strip().lower()
        if needle:
            shown = [r for r in shown if needle in f"{r['unit']} {r['owner']} {r['tenant']} {r['mobile']}".lower()]
        live = [r for r in shown if r["_state"] != "past"]
        totals_rent = sum((r["_money_rent"] for r in live), ZERO)
        totals_deposit = sum((r["_money_dep"] for r in live), ZERO)
        for r in shown:
            for private in ("_state", "_money_rent", "_money_dep"):
                r.pop(private)
        return {
            "kind": "rental", "title": "Rental Register",
            "subtitle": f"Flats and shops let out, as on {_fmt_date(today)}",
            "columns": [
                _col("kind", "Type", 12), _col("unit", "Unit", 22, phone=True), _col("owner", "Owner", 0),
                _col("tenant", "Tenant", 0, phone=True), _col("mobile", "Mobile", 24),
                _col("agreement_no", "Agreement No.", 24), _col("start", "From", 19), _col("end", "To", 19, phone=True),
                _col("days_left", "Days left", 15, True), _col("rent", "Rent / month Rs.", 24, True, phone=True),
                _col("deposit", "Deposit Rs.", 22, True), _col("how", "Arranged by", 24),
                _col("police", "Police verif.", 20), _col("status", "Status", 21, phone=True)],
            "rows": shown,
            "totals": [{"label": "Tenancies", "value": str(len(live))},
                       {"label": "Rent per month Rs.", "value": _amt(totals_rent)},
                       {"label": "Deposits held Rs.", "value": _amt(totals_deposit)},
                       {"label": f"Expiring in {EXPIRING_DAYS} days", "value": str(sum(r["status"] == "Expiring" for r in live))},
                       {"label": "Expired", "value": str(sum(r["status"] == "Expired" for r in live))}],
            "statuses": [{"value": v, "label": l} for v, l in self.RENTAL_STATUSES],
            "uses_period": False, "uses_month": False,
        }

    @staticmethod
    def _channel(channel: Optional[str], name: Optional[str]) -> str:
        if not channel:
            return ""
        label = {"direct": "Direct", "agent": "Agent", "online_app": "Online app"}.get(channel, _words(channel))
        return f"{label} ({name})" if name else label

    @staticmethod
    def _rental_row(*, kind, unit, owner, tenant, mobile, agreement_no, start, end, today, rent, deposit, how, police,
                    state) -> dict:
        labels = {"active": "Running", "expiring": "Expiring", "expired": "Expired", "no_agreement": "No dates",
                  "past": "Moved out"}
        days = "" if end is None or state == "past" else str((end - today).days)
        r = {"kind": kind, "unit": unit, "owner": owner or "", "tenant": tenant or "", "mobile": mobile or "",
             "agreement_no": agreement_no, "start": _fmt_date(start), "end": _fmt_date(end), "days_left": days,
             "rent": _amt(rent) if rent is not None else "", "deposit": _amt(deposit) if deposit is not None else "",
             "how": how, "police": police, "status": labels[state]}
        r["_state"] = state
        r["_money_rent"] = Decimal(rent) if rent is not None else ZERO
        r["_money_dep"] = Decimal(deposit) if deposit is not None else ZERO
        return r

    # ── Receipts register ─────────────────────────────────────────────────────

    RECEIPT_STATUSES = [(None, "All"), ("pending", "Pending review"), ("reconciled", "Reconciled"),
                        ("rejected", "Rejected")]

    def receipts_register(self, society_id: UUID, date_from: Optional[date] = None, date_to: Optional[date] = None,
                          status: Optional[str] = None, q: Optional[str] = None) -> dict:
        query = (self.db.query(OnlinePaymentSubmission)
                 .options(joinedload(OnlinePaymentSubmission.flat).joinedload(Flat.wing),
                          joinedload(OnlinePaymentSubmission.flat).selectinload(Flat.residents),
                          selectinload(OnlinePaymentSubmission.allocations),
                          joinedload(OnlinePaymentSubmission.recorder))
                 .filter(OnlinePaymentSubmission.society_id == society_id,
                         OnlinePaymentSubmission.is_active == True))                                  # noqa: E712
        if date_from:
            query = query.filter(OnlinePaymentSubmission.payment_date >= date_from)
        if date_to:
            query = query.filter(OnlinePaymentSubmission.payment_date <= date_to)
        if status:
            query = query.filter(OnlinePaymentSubmission.status == ReconciliationStatus(status))
        payments = query.order_by(OnlinePaymentSubmission.payment_date, OnlinePaymentSubmission.receipt_number).all()
        rows, received, applied, advance, pending = [], ZERO, ZERO, ZERO, 0
        needle = (q or "").strip().lower()
        for p in payments:
            label, member = flat_label(p.flat), member_name(p.flat)
            ref = p.transaction_ref or ""
            if needle and needle not in f"{p.receipt_number} {label} {member} {ref}".lower():
                continue
            bills = ", ".join(a.bill.invoice_number for a in p.allocations if a.is_live and a.bill is not None)
            counts = payment_counts(p)
            if counts:
                received += money(p.amount)
                applied += allocated(p)
                advance += unapplied(p)
            if p.status == ReconciliationStatus.PENDING:
                pending += 1
            rows.append({
                "date": _fmt_date(p.payment_date), "receipt_no": p.receipt_number, "flat": label, "member": member,
                "purpose": _words(p.purpose.value), "mode": _words(p.payment_mode.value), "reference": ref,
                "amount": _amt(p.amount), "applied_to": bills, "advance": _amt(unapplied(p)) if unapplied(p) else "",
                "status": _words(p.status.value), "recorded_by": p.recorder.full_name if p.recorder else ""})
        return {
            "kind": "receipts", "title": "Receipts Register", "subtitle": "Payments received from members",
            "columns": [
                _col("date", "Date", 19, phone=True), _col("receipt_no", "Receipt No.", 26, phone=True),
                _col("flat", "Flat", 17, phone=True), _col("member", "Member", 0), _col("purpose", "For", 20),
                _col("mode", "Mode", 21), _col("reference", "Reference", 28), _col("amount", "Amount Rs.", 24, True, True),
                _col("applied_to", "Set off against", 0), _col("advance", "Advance Rs.", 22, True),
                _col("status", "Status", 20, phone=True), _col("recorded_by", "Recorded by", 28)],
            "rows": rows,
            "totals": [{"label": "Receipts", "value": str(len(rows))}, {"label": "Received Rs.", "value": _amt(received)},
                       {"label": "Set off against bills Rs.", "value": _amt(applied)},
                       {"label": "Held as advance Rs.", "value": _amt(advance)},
                       {"label": "Pending review", "value": str(pending)}],
            "statuses": [{"value": v, "label": l} for v, l in self.RECEIPT_STATUSES],
            "uses_period": True, "uses_month": False,
        }

    # ── Staff attendance register ─────────────────────────────────────────────

    MARKS = {AttendanceStatus.PRESENT: "P", AttendanceStatus.ABSENT: "A", AttendanceStatus.HALF_DAY: "H",
             AttendanceStatus.LEAVE: "L", AttendanceStatus.OVERTIME: "OT", AttendanceStatus.OFF_DUTY: "WO"}

    def attendance_register(self, society_id: UUID, month: Optional[str] = None, department: Optional[str] = None,
                            q: Optional[str] = None) -> dict:
        today = date.today()
        if month is None:
            month = f"{today.year}-{today.month:02d}"
        if not MONTH.match(month):
            raise ValueError("The month must look like 2026-11")
        year, mon = int(month[:4]), int(month[5:])
        days = calendar.monthrange(year, mon)[1]
        first, last = date(year, mon, 1), date(year, mon, days)

        staff_q = (self.db.query(Staff).options(joinedload(Staff.designation_rel))
                   .filter(Staff.society_id == society_id, Staff.is_active == True))                  # noqa: E712
        marks = (self.db.query(StaffAttendance)
                 .filter(StaffAttendance.society_id == society_id, StaffAttendance.attendance_date >= first,
                         StaffAttendance.attendance_date <= last).all())
        by_staff: Dict[UUID, Dict[int, StaffAttendance]] = {}
        for m in marks:
            by_staff.setdefault(m.staff_id, {})[m.attendance_date.day] = m
        leaves = (self.db.query(StaffLeave).filter(StaffLeave.society_id == society_id,
                                                    StaffLeave.status == LeaveStatus.APPROVED,
                                                    StaffLeave.from_date <= last, StaffLeave.to_date >= first).all())
        leave_days: Dict[UUID, set] = {}
        for lv in leaves:
            d = max(lv.from_date, first)
            while d <= min(lv.to_date, last):
                leave_days.setdefault(lv.staff_id, set()).add(d.day)
                d += timedelta(days=1)

        needle = (q or "").strip().lower()
        rows, tot_p, tot_a, tot_l, departments = [], 0, 0, 0, {}
        for s in sorted(staff_q.all(), key=lambda x: (x.department.value, x.full_name.lower())):   # by department name
            # Someone who has left appears only in a month they were marked in; a new joiner only from their start
            departed = s.status in (StaffStatus.INACTIVE, StaffStatus.TERMINATED) and s.id not in by_staff
            if departed or (s.joining_date and s.joining_date > last):
                continue
            departments[s.department.value] = _words(s.department.value)
            if department and s.department.value != department:
                continue
            if needle and needle not in f"{s.full_name} {s.employee_code}".lower():
                continue
            mine = by_staff.get(s.id, {})
            present = half = absent = leave = 0
            hours = overtime = 0.0
            row = {"code": s.employee_code, "name": s.full_name, "department": _words(s.department.value)}
            for d in range(1, days + 1):
                m, mark = mine.get(d), ""
                if m is not None:
                    mark = self.MARKS[m.status]
                    present += m.status in (AttendanceStatus.PRESENT, AttendanceStatus.OVERTIME)
                    half += m.status == AttendanceStatus.HALF_DAY
                    absent += m.status == AttendanceStatus.ABSENT
                    leave += m.status == AttendanceStatus.LEAVE
                    hours += m.working_hours or 0
                    overtime += m.overtime_hours or 0
                elif d in leave_days.get(s.id, ()):
                    mark, leave = "L", leave + 1                       # an approved leave with no mark of its own
                row[f"d{d}"] = mark
            row.update({"present": str(present), "half": str(half), "leave": str(leave), "absent": str(absent),
                        "hours": f"{hours:.1f}" if hours else "", "overtime": f"{overtime:.1f}" if overtime else ""})
            tot_p, tot_a, tot_l = tot_p + present, tot_a + absent, tot_l + leave
            rows.append(row)
        day_cols = [_col(f"d{d}", str(d), 5.2) for d in range(1, days + 1)]
        return {
            "kind": "attendance", "title": "Staff Attendance Register",
            "subtitle": f"For {calendar.month_name[mon]} {year}  ·  P present, A absent, H half day, L leave, "
                        f"OT overtime, WO off duty",
            "columns": [_col("code", "Code", 13), _col("name", "Name", 36, phone=True),
                        _col("department", "Department", 0), *day_cols,
                        _col("present", "Pres.", 9, True, True), _col("half", "Half", 8, True),
                        _col("leave", "Leave", 9, True, True), _col("absent", "Abs.", 8, True, True),
                        _col("hours", "Hours", 11, True, True), _col("overtime", "OT hrs", 11, True)],
            "rows": rows,
            "totals": [{"label": "Staff", "value": str(len(rows))}, {"label": "Present days", "value": str(tot_p)},
                       {"label": "Absent days", "value": str(tot_a)}, {"label": "Leave days", "value": str(tot_l)}],
            "statuses": [{"value": None, "label": "All"}] + [{"value": k, "label": v} for k, v in sorted(departments.items())],
            "uses_period": False, "uses_month": True, "month": month,
        }


def register_to_csv(reg: dict) -> str:
    """The register as a spreadsheet: the column headings, then each row."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([c["label"] for c in reg["columns"]])
    for r in reg["rows"]:
        w.writerow([r.get(c["key"], "") for c in reg["columns"]])
    w.writerow([])
    for t in reg["totals"]:
        w.writerow([t["label"], t["value"]])
    return buf.getvalue()


REGISTERS: Dict[str, str] = {"rental": "rental_register", "receipts": "receipts_register",
                             "attendance": "attendance_register"}
