"""
PayrollService — readiness layer only. No calculations yet.

Provides:
- salary structure CRUD
- attendance correction workflow
- monthly attendance aggregation (triggered manually or by future cron)
"""
from datetime import date
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.modules.staff.models.payroll_readiness import (
    StaffSalaryStructure, AttendanceCorrection, MonthlyAttendanceSummary,
    AttendanceCorrectionStatus,
)
from app.modules.staff.models.staff import StaffAttendance, AttendanceStatus
from app.models.user import User
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel


class PayrollService:

    def __init__(self, db: Session):
        self.db = db

    # ── Salary Structure ──────────────────────────────────────────────────────

    def set_salary_structure(self, data: dict, user: User) -> StaffSalaryStructure:
        # Expire any current active structure
        existing = self.db.query(StaffSalaryStructure).filter(
            StaffSalaryStructure.staff_id      == data["staff_id"],
            StaffSalaryStructure.effective_to  == None,
            StaffSalaryStructure.is_active     == True,
        ).first()
        if existing:
            existing.effective_to = date.today()
            self.db.flush()

        struct = StaffSalaryStructure(**data, created_by=user.id)
        self.db.add(struct)
        self.db.flush()
        AuditService.log(db=self.db, action=AuditAction.CREATE, module="payroll",
                         entity_id=str(struct.id), entity_type="StaffSalaryStructure", user=user,
                         new_values={"staff_id": str(data["staff_id"]),
                                     "basic": str(data.get("basic_salary", 0))})
        self.db.commit()
        self.db.refresh(struct)
        return struct

    def get_salary_structure(self, staff_id: UUID) -> Optional[StaffSalaryStructure]:
        return self.db.query(StaffSalaryStructure).filter(
            StaffSalaryStructure.staff_id     == staff_id,
            StaffSalaryStructure.effective_to == None,
            StaffSalaryStructure.is_active    == True,
        ).first()

    # ── Attendance Correction ─────────────────────────────────────────────────

    def request_correction(self, data: dict, requester: User) -> AttendanceCorrection:
        correction = AttendanceCorrection(**data, requested_by=requester.id)
        self.db.add(correction)
        self.db.commit()
        self.db.refresh(correction)
        return correction

    def approve_correction(self, correction_id: UUID, approver: User) -> AttendanceCorrection:
        c = self.db.query(AttendanceCorrection).filter(AttendanceCorrection.id == correction_id).first()
        if not c: raise HTTPException(status_code=404, detail="Correction request not found")
        if c.status != AttendanceCorrectionStatus.PENDING:
            raise HTTPException(status_code=409, detail=f"Correction already {c.status.value}")

        c.status      = AttendanceCorrectionStatus.APPROVED
        c.approved_by = approver.id

        # Apply correction to attendance record
        att = self.db.query(StaffAttendance).filter(StaffAttendance.id == c.attendance_id).first()
        if att:
            if c.requested_status: att.status = c.requested_status
            att.is_manual_entry = True
            att.marked_by = approver.id

        # Notify staff if linked to user
        from app.modules.staff.models.staff import Staff
        staff = self.db.query(Staff).filter(Staff.id == c.staff_id).first()
        if staff and staff.user_id:
            NotificationService.send(
                db=self.db, user_id=staff.user_id,
                title="Attendance Correction Approved",
                body=f"Your attendance correction for {c.correction_date} has been approved.",
                type=NotificationType.INFO, channel=NotificationChannel.IN_APP,
                module="attendance", entity_id=str(c.id),
            )

        self.db.commit()
        self.db.refresh(c)
        return c

    def reject_correction(self, correction_id: UUID, reason: str, rejector: User) -> AttendanceCorrection:
        c = self.db.query(AttendanceCorrection).filter(AttendanceCorrection.id == correction_id).first()
        if not c: raise HTTPException(status_code=404, detail="Correction request not found")
        if c.status != AttendanceCorrectionStatus.PENDING:
            raise HTTPException(status_code=409, detail=f"Correction already {c.status.value}")
        c.status           = AttendanceCorrectionStatus.REJECTED
        c.approved_by      = rejector.id
        c.rejection_reason = reason
        self.db.commit()
        self.db.refresh(c)
        return c

    def list_corrections(self, society_id: UUID, status: Optional[str] = None) -> list:
        q = self.db.query(AttendanceCorrection).filter(AttendanceCorrection.society_id == society_id)
        if status: q = q.filter(AttendanceCorrection.status == status)
        return q.order_by(AttendanceCorrection.correction_date.desc()).limit(100).all()

    # ── Monthly Attendance Aggregation ────────────────────────────────────────

    def aggregate_monthly_attendance(self, society_id: UUID, staff_id: UUID,
                                      year: int, month: int,
                                      user: User) -> MonthlyAttendanceSummary:
        """
        Aggregate attendance records for a staff member for a given month.
        Creates or updates the MonthlyAttendanceSummary record.
        """
        from datetime import date as dt
        import calendar

        # Check if already finalized
        existing = self.db.query(MonthlyAttendanceSummary).filter(
            MonthlyAttendanceSummary.staff_id == staff_id,
            MonthlyAttendanceSummary.year     == year,
            MonthlyAttendanceSummary.month    == month,
        ).first()
        if existing and existing.is_finalized:
            raise HTTPException(status_code=409,
                detail="Monthly attendance already finalized and locked for payroll")

        # Date range for the month
        _, days_in_month = calendar.monthrange(year, month)
        start = dt(year, month, 1)
        end   = dt(year, month, days_in_month)

        records = self.db.query(StaffAttendance).filter(
            StaffAttendance.staff_id        == staff_id,
            StaffAttendance.attendance_date >= start,
            StaffAttendance.attendance_date <= end,
        ).all()

        # Count by status
        counts = {s: 0 for s in AttendanceStatus}
        total_hours = 0.0
        overtime_hours = 0.0
        late_arrivals = 0

        for r in records:
            counts[r.status] = counts.get(r.status, 0) + 1
            if r.working_hours:  total_hours    += r.working_hours
            if r.overtime_hours: overtime_hours += r.overtime_hours
            # Late arrival: check_in after 09:30 for general shift
            if r.check_in_time and r.check_in_time.time().hour >= 9 and r.check_in_time.time().minute > 30:
                late_arrivals += 1

        summary_data = {
            "society_id":          society_id,
            "staff_id":            staff_id,
            "year":                year,
            "month":               month,
            "present_days":        counts.get(AttendanceStatus.PRESENT, 0) + counts.get(AttendanceStatus.OVERTIME, 0),
            "absent_days":         counts.get(AttendanceStatus.ABSENT, 0),
            "half_day_count":      counts.get(AttendanceStatus.HALF_DAY, 0),
            "leave_days":          counts.get(AttendanceStatus.LEAVE, 0),
            "overtime_days":       counts.get(AttendanceStatus.OVERTIME, 0),
            "total_working_hours": round(total_hours, 2),
            "total_overtime_hours":round(overtime_hours, 2),
            "late_arrivals":       late_arrivals,
        }

        if existing:
            for k, v in summary_data.items(): setattr(existing, k, v)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        summary = MonthlyAttendanceSummary(**summary_data)
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)
        return summary

    def finalize_monthly_attendance(self, summary_id: UUID, user: User) -> MonthlyAttendanceSummary:
        s = self.db.query(MonthlyAttendanceSummary).filter(MonthlyAttendanceSummary.id == summary_id).first()
        if not s: raise HTTPException(status_code=404, detail="Summary not found")
        if s.is_finalized: raise HTTPException(status_code=409, detail="Already finalized")
        s.is_finalized  = True
        s.finalized_by  = user.id
        self.db.commit()
        self.db.refresh(s)
        return s

    def get_monthly_summary(self, staff_id: UUID, year: int, month: int) -> Optional[MonthlyAttendanceSummary]:
        return self.db.query(MonthlyAttendanceSummary).filter(
            MonthlyAttendanceSummary.staff_id == staff_id,
            MonthlyAttendanceSummary.year     == year,
            MonthlyAttendanceSummary.month    == month,
        ).first()
