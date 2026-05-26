"""
Payroll Readiness Models — architecture only, no calculations yet.

These tables capture the configuration and data structures needed
for a future payroll engine to plug into without schema changes.
"""
import enum
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, Date, Enum, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


class SalaryComponent(str, enum.Enum):
    BASIC           = "basic"
    HRA             = "hra"              # House Rent Allowance
    CONVEYANCE      = "conveyance"
    MEDICAL         = "medical"
    SPECIAL         = "special"
    OVERTIME        = "overtime"
    SHIFT_ALLOWANCE = "shift_allowance"
    PF_DEDUCTION    = "pf_deduction"
    ESI_DEDUCTION   = "esi_deduction"
    ADVANCE_RECOVERY= "advance_recovery"
    PENALTY         = "penalty"
    BONUS           = "bonus"


class PayrollCycle(str, enum.Enum):
    MONTHLY    = "monthly"
    WEEKLY     = "weekly"
    FORTNIGHTLY= "fortnightly"


class AttendanceCorrectionStatus(str, enum.Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ── StaffSalaryStructure ──────────────────────────────────────────────────────

class StaffSalaryStructure(Base, TimestampMixin):
    """
    Defines the salary breakdown for a staff member.
    Used by future payroll engine to compute monthly payslip.
    """
    __tablename__ = "staff_salary_structures"

    society_id      = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id        = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    effective_from  = Column(Date, nullable=False)
    effective_to    = Column(Date, nullable=True)    # null = current
    payroll_cycle   = Column(Enum(PayrollCycle), default=PayrollCycle.MONTHLY, nullable=False)

    # Gross components (stored as monthly amounts)
    basic_salary    = Column(Numeric(10, 2), nullable=False)
    hra             = Column(Numeric(10, 2), default=0, nullable=False)
    conveyance      = Column(Numeric(10, 2), default=0, nullable=False)
    medical         = Column(Numeric(10, 2), default=0, nullable=False)
    special_allowance = Column(Numeric(10, 2), default=0, nullable=False)
    shift_allowance = Column(Numeric(10, 2), default=0, nullable=False)

    # Deductions
    pf_employee_pct = Column(Float, default=12.0, nullable=False)   # % of basic
    esi_employee_pct= Column(Float, default=0.75, nullable=False)   # % of gross
    tds_monthly     = Column(Numeric(10, 2), default=0, nullable=False)

    # Overtime
    overtime_rate_per_hour = Column(Numeric(8, 2), nullable=True)  # if null, use basic/26/8

    # Working days config
    working_days_per_month = Column(Integer, default=26, nullable=False)
    paid_leaves_per_year   = Column(Integer, default=12, nullable=False)

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    society = relationship("Society")
    staff   = relationship("Staff")
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<SalaryStructure staff={self.staff_id} from={self.effective_from}>"


# ── AttendanceCorrection ──────────────────────────────────────────────────────

class AttendanceCorrection(Base, TimestampMixin):
    """
    Staff can request correction to their attendance record.
    Supervisor/Admin approves or rejects.
    """
    __tablename__ = "attendance_corrections"

    society_id        = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id          = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    attendance_id     = Column(UUID(as_uuid=True), ForeignKey("staff_attendance.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    correction_date   = Column(Date, nullable=False, index=True)
    original_status   = Column(String(50), nullable=True)
    requested_status  = Column(String(50), nullable=False)
    original_check_in = Column(String(20), nullable=True)   # stored as HH:MM
    requested_check_in= Column(String(20), nullable=True)
    original_check_out= Column(String(20), nullable=True)
    requested_check_out = Column(String(20), nullable=True)
    reason            = Column(Text, nullable=False)
    status            = Column(Enum(AttendanceCorrectionStatus),
                               default=AttendanceCorrectionStatus.PENDING, nullable=False, index=True)
    rejection_reason  = Column(Text, nullable=True)

    society    = relationship("Society")
    staff      = relationship("Staff")
    requester  = relationship("User", foreign_keys=[requested_by])
    approver   = relationship("User", foreign_keys=[approved_by])

    def __repr__(self):
        return f"<AttendanceCorrection staff={self.staff_id} date={self.correction_date} [{self.status}]>"


# ── MonthlyAttendanceSummary ──────────────────────────────────────────────────

class MonthlyAttendanceSummary(Base, TimestampMixin):
    """
    Pre-aggregated monthly attendance for payroll calculation.
    Generated at month end (by admin or future cron job).
    """
    __tablename__ = "monthly_attendance_summaries"

    society_id        = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id          = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    year              = Column(Integer, nullable=False, index=True)
    month             = Column(Integer, nullable=False, index=True)  # 1-12

    # Raw counts
    present_days      = Column(Integer, default=0, nullable=False)
    absent_days       = Column(Integer, default=0, nullable=False)
    half_day_count    = Column(Integer, default=0, nullable=False)
    leave_days        = Column(Integer, default=0, nullable=False)
    holiday_days      = Column(Integer, default=0, nullable=False)
    overtime_days     = Column(Integer, default=0, nullable=False)

    # Hours
    total_working_hours  = Column(Float, default=0.0, nullable=False)
    total_overtime_hours = Column(Float, default=0.0, nullable=False)

    # Late/early stats
    late_arrivals     = Column(Integer, default=0, nullable=False)
    early_departures  = Column(Integer, default=0, nullable=False)

    # Status
    is_finalized      = Column(Boolean, default=False, nullable=False)  # locked for payroll
    finalized_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    society   = relationship("Society")
    staff     = relationship("Staff")
    finalizer = relationship("User", foreign_keys=[finalized_by])

    def __repr__(self):
        return f"<MonthlyAttendance staff={self.staff_id} {self.year}-{self.month:02d}>"
