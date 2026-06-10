"""
Staff Operations Models — workforce ERP architecture.

Workflows:
  Attendance: CHECK_IN → CHECKED_IN → CHECK_OUT
  Task: ASSIGNED → ACKNOWLEDGED → IN_PROGRESS → COMPLETED → VERIFIED
  Leave: PENDING → APPROVED | REJECTED
"""
import enum
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean,
    DateTime, Date, Time, Enum, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin


# ── Enums ─────────────────────────────────────────────────────────────────────

class StaffDepartment(str, enum.Enum):
    SECURITY     = "security"
    HOUSEKEEPING = "housekeeping"
    TECHNICAL    = "technical"
    GYM          = "gym"
    ADMIN        = "admin"
    MAINTENANCE  = "maintenance"
    ELECTRICAL   = "electrical"
    PLUMBING     = "plumbing"
    GARDENING    = "gardening"
    AMENITIES    = "amenities"


class StaffStatus(str, enum.Enum):
    ACTIVE      = "active"
    INACTIVE    = "inactive"
    ON_LEAVE    = "on_leave"
    TERMINATED  = "terminated"
    PROBATION   = "probation"


class AttendanceStatus(str, enum.Enum):
    PRESENT   = "present"
    ABSENT    = "absent"
    HALF_DAY  = "half_day"
    LEAVE     = "leave"
    OVERTIME  = "overtime"
    OFF_DUTY  = "off_duty"


class TaskStatus(str, enum.Enum):
    ASSIGNED    = "assigned"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    VERIFIED    = "verified"
    CANCELLED   = "cancelled"


class LeaveType(str, enum.Enum):
    CASUAL    = "casual"
    SICK      = "sick"
    EARNED    = "earned"
    EMERGENCY = "emergency"
    UNPAID    = "unpaid"


class LeaveStatus(str, enum.Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ShiftType(str, enum.Enum):
    MORNING   = "morning"   # 06:00-14:00
    AFTERNOON = "afternoon" # 14:00-22:00
    NIGHT     = "night"     # 22:00-06:00
    GENERAL   = "general"   # 09:00-18:00
    CUSTOM    = "custom"


# ── FSM Transitions ───────────────────────────────────────────────────────────
TASK_TRANSITIONS: dict = {
    TaskStatus.ASSIGNED:     {TaskStatus.ACKNOWLEDGED, TaskStatus.CANCELLED},
    TaskStatus.ACKNOWLEDGED: {TaskStatus.IN_PROGRESS,  TaskStatus.CANCELLED},
    TaskStatus.IN_PROGRESS:  {TaskStatus.COMPLETED,    TaskStatus.CANCELLED},
    TaskStatus.COMPLETED:    {TaskStatus.VERIFIED},
    TaskStatus.VERIFIED:     set(),
    TaskStatus.CANCELLED:    set(),
}


# ── StaffDesignation ──────────────────────────────────────────────────────────

class StaffDesignation(Base, TimestampMixin):
    __tablename__ = "staff_designations"

    society_id  = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    name        = Column(String(100), nullable=False)
    department  = Column(Enum(StaffDepartment, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    description = Column(Text, nullable=True)

    society = relationship("Society")
    staff   = relationship("Staff", back_populates="designation_rel")


# ── StaffShift ────────────────────────────────────────────────────────────────

class StaffShift(Base, TimestampMixin):
    __tablename__ = "staff_shifts"

    society_id  = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    name        = Column(String(100), nullable=False)
    shift_type  = Column(Enum(ShiftType, values_callable=lambda e: [x.value for x in e]), default=ShiftType.GENERAL, nullable=False)
    start_time  = Column(Time, nullable=False)
    end_time    = Column(Time, nullable=False)
    is_overnight = Column(Boolean, default=False, nullable=False)

    society   = relationship("Society")
    staff     = relationship("Staff", back_populates="shift")
    duties    = relationship("DutyAssignment", back_populates="shift")


# ── Staff ─────────────────────────────────────────────────────────────────────

class Staff(Base, TimestampMixin):
    __tablename__ = "staff"

    society_id        = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id           = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Identity
    employee_code     = Column(String(20), nullable=False, unique=True, index=True)
    full_name         = Column(String(255), nullable=False)
    mobile            = Column(String(20), nullable=False, index=True)
    email             = Column(String(255), nullable=True)
    photo_url         = Column(String(500), nullable=True)

    # Employment
    department        = Column(Enum(StaffDepartment, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    designation_id    = Column(UUID(as_uuid=True), ForeignKey("staff_designations.id", ondelete="SET NULL"), nullable=True)
    shift_id          = Column(UUID(as_uuid=True), ForeignKey("staff_shifts.id", ondelete="SET NULL"), nullable=True)
    status            = Column(Enum(StaffStatus, values_callable=lambda e: [x.value for x in e]), default=StaffStatus.PROBATION, nullable=False, index=True)
    joining_date      = Column(Date, nullable=True)
    termination_date  = Column(Date, nullable=True)

    # Reporting hierarchy
    reporting_manager_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Emergency contact
    emergency_contact_name  = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)

    # Payroll readiness
    bank_account_number = Column(String(50), nullable=True)
    bank_name           = Column(String(100), nullable=True)
    base_salary         = Column(Float, nullable=True)
    pf_number           = Column(String(50), nullable=True)

    # Relationships
    society             = relationship("Society")
    user                = relationship("User", foreign_keys=[user_id])
    reporting_manager   = relationship("User", foreign_keys=[reporting_manager_id])
    designation_rel     = relationship("StaffDesignation", back_populates="staff")
    shift           = relationship("StaffShift", back_populates="staff")
    attendance      = relationship("StaffAttendance", back_populates="staff", cascade="all, delete-orphan")
    duties          = relationship("DutyAssignment", back_populates="staff", cascade="all, delete-orphan")
    tasks           = relationship("StaffTask", back_populates="assigned_staff", cascade="all, delete-orphan")
    leaves          = relationship("StaffLeave", back_populates="staff", cascade="all, delete-orphan")
    work_logs       = relationship("StaffWorkLog", back_populates="staff", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Staff {self.employee_code} {self.full_name}>"


# ── DutyAssignment ────────────────────────────────────────────────────────────

class DutyAssignment(Base, TimestampMixin):
    __tablename__ = "duty_assignments"

    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id     = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    shift_id     = Column(UUID(as_uuid=True), ForeignKey("staff_shifts.id", ondelete="SET NULL"), nullable=True)
    assigned_by  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    duty_name    = Column(String(255), nullable=False)
    description  = Column(Text, nullable=True)
    location     = Column(String(255), nullable=True)
    duty_date    = Column(Date, nullable=False, index=True)
    start_time   = Column(Time, nullable=True)
    end_time     = Column(Time, nullable=True)
    is_recurring = Column(Boolean, default=False, nullable=False)
    is_completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    verified_by  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at  = Column(DateTime, nullable=True)
    notes        = Column(Text, nullable=True)

    society  = relationship("Society")
    staff    = relationship("Staff", back_populates="duties")
    shift    = relationship("StaffShift", back_populates="duties")
    assigner = relationship("User", foreign_keys=[assigned_by])
    verifier = relationship("User", foreign_keys=[verified_by])


# ── StaffAttendance ───────────────────────────────────────────────────────────

class StaffAttendance(Base, TimestampMixin):
    __tablename__ = "staff_attendance"

    society_id       = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id         = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    attendance_date  = Column(Date, nullable=False, index=True)
    status           = Column(Enum(AttendanceStatus, values_callable=lambda e: [x.value for x in e]), default=AttendanceStatus.PRESENT, nullable=False, index=True)

    check_in_time    = Column(DateTime, nullable=True)
    check_out_time   = Column(DateTime, nullable=True)
    working_hours    = Column(Float, nullable=True)     # computed on checkout
    overtime_hours   = Column(Float, nullable=True)     # payroll-ready
    is_manual_entry  = Column(Boolean, default=False)   # admin override flag
    # Punch-in approval
    is_approved      = Column(Boolean, default=False, nullable=False, index=True)
    approved_by      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at      = Column(DateTime, nullable=True)
    approval_notes   = Column(Text, nullable=True)
    # Punch-out approval
    is_checkout_approved    = Column(Boolean, default=False, nullable=False)
    checkout_approved_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    checkout_approved_at    = Column(DateTime, nullable=True)
    checkout_approval_notes = Column(Text, nullable=True)

    marked_by        = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes            = Column(Text, nullable=True)

    society          = relationship("Society")
    staff            = relationship("Staff", back_populates="attendance")
    marker           = relationship("User", foreign_keys=[marked_by])
    approver         = relationship("User", foreign_keys=[approved_by])
    checkout_approver = relationship("User", foreign_keys=[checkout_approved_by])

    def __repr__(self):
        return f"<Attendance staff={self.staff_id} date={self.attendance_date} {self.status}>"


# ── StaffTask ─────────────────────────────────────────────────────────────────

class StaffTask(Base, TimestampMixin):
    __tablename__ = "staff_tasks"

    society_id    = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id      = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_by   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Link to complaint/visitor if applicable
    complaint_id  = Column(UUID(as_uuid=True), nullable=True)
    visitor_id    = Column(UUID(as_uuid=True), nullable=True)

    title         = Column(String(255), nullable=False)
    description   = Column(Text, nullable=True)
    location      = Column(String(255), nullable=True)
    due_date      = Column(DateTime, nullable=True)
    status        = Column(Enum(TaskStatus, values_callable=lambda e: [x.value for x in e]), default=TaskStatus.ASSIGNED, nullable=False, index=True)

    acknowledged_at = Column(DateTime, nullable=True)
    started_at      = Column(DateTime, nullable=True)
    completed_at    = Column(DateTime, nullable=True)
    verified_at     = Column(DateTime, nullable=True)
    completion_notes = Column(Text, nullable=True)
    priority        = Column(String(20), default="medium", nullable=False)

    society          = relationship("Society")
    assigned_staff   = relationship("Staff", back_populates="tasks")
    assigner         = relationship("User", foreign_keys=[assigned_by])
    verifier_user    = relationship("User", foreign_keys=[verified_by])
    work_logs        = relationship("StaffWorkLog", back_populates="task", cascade="all, delete-orphan")


# ── StaffLeave ────────────────────────────────────────────────────────────────

class StaffLeave(Base, TimestampMixin):
    __tablename__ = "staff_leaves"

    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id     = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    approved_by  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    leave_type   = Column(Enum(LeaveType, values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    from_date    = Column(Date, nullable=False)
    to_date      = Column(Date, nullable=False)
    total_days   = Column(Integer, nullable=False)
    reason       = Column(Text, nullable=True)
    status       = Column(Enum(LeaveStatus, values_callable=lambda e: [x.value for x in e]), default=LeaveStatus.PENDING, nullable=False, index=True)
    approved_at  = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    society  = relationship("Society")
    staff    = relationship("Staff", back_populates="leaves")
    approver = relationship("User", foreign_keys=[approved_by])


# ── StaffWorkLog ──────────────────────────────────────────────────────────────

class StaffWorkLog(Base, TimestampMixin):
    """Append-only log of work progress updates."""
    __tablename__ = "staff_work_logs"

    society_id  = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id    = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id     = Column(UUID(as_uuid=True), ForeignKey("staff_tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    notes       = Column(Text, nullable=False)
    logged_at   = Column(DateTime, nullable=False)
    photos_url  = Column(Text, nullable=True)   # JSON array of photo URLs

    society = relationship("Society")
    staff   = relationship("Staff", back_populates="work_logs")
    task    = relationship("StaffTask", back_populates="work_logs")


# ── StaffRoster (Weekly duty roster) ─────────────────────────────────────────

class RosterStatus(str, enum.Enum):
    DRAFT     = "draft"
    PUBLISHED = "published"
    ARCHIVED  = "archived"


class StaffRoster(Base, TimestampMixin):
    """Weekly/periodic shift roster for a society."""
    __tablename__ = "staff_rosters"

    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id     = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    shift_id     = Column(UUID(as_uuid=True), ForeignKey("staff_shifts.id", ondelete="SET NULL"), nullable=True)
    created_by   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    week_start   = Column(Date, nullable=False, index=True)
    week_end     = Column(Date, nullable=False)
    roster_status = Column(Enum(RosterStatus, values_callable=lambda e: [x.value for x in e]), default=RosterStatus.DRAFT, nullable=False)

    monday    = Column(Boolean, default=True)
    tuesday   = Column(Boolean, default=True)
    wednesday = Column(Boolean, default=True)
    thursday  = Column(Boolean, default=True)
    friday    = Column(Boolean, default=True)
    saturday  = Column(Boolean, default=True)
    sunday    = Column(Boolean, default=False)
    is_holiday_week = Column(Boolean, default=False)
    notes     = Column(Text, nullable=True)

    society = relationship("Society")
    staff   = relationship("Staff")
    shift   = relationship("StaffShift")
    creator = relationship("User", foreign_keys=[created_by])


# ── StaffLeaveBalance (leave quota tracking) ──────────────────────────────────

class StaffLeaveBalance(Base, TimestampMixin):
    """Annual leave quota and consumed balance per staff per year."""
    __tablename__ = "staff_leave_balances"

    society_id   = Column(UUID(as_uuid=True), ForeignKey("societies.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_id     = Column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    year         = Column(Integer, nullable=False, index=True)   # e.g. 2026
    casual_total    = Column(Float, default=12.0, nullable=False)
    sick_total      = Column(Float, default=12.0, nullable=False)
    earned_total    = Column(Float, default=15.0, nullable=False)
    casual_used     = Column(Float, default=0.0, nullable=False)
    sick_used       = Column(Float, default=0.0, nullable=False)
    earned_used     = Column(Float, default=0.0, nullable=False)

    society = relationship("Society")
    staff   = relationship("Staff")
