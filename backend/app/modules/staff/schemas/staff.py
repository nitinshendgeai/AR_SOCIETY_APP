from pydantic import BaseModel, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import date, time, datetime
from app.schemas.common import OrmBase, TimestampSchema
from app.modules.staff.models.staff import (
    StaffDepartment, StaffStatus, AttendanceStatus,
    TaskStatus, LeaveType, LeaveStatus, ShiftType,
)


# ── Designation ───────────────────────────────────────────────────────────────
class DesignationCreate(OrmBase):
    society_id: UUID; name: str; department: StaffDepartment; description: Optional[str] = None

class DesignationOut(TimestampSchema):
    society_id: UUID; name: str; department: StaffDepartment; description: Optional[str]


# ── Shift ─────────────────────────────────────────────────────────────────────
class ShiftCreate(OrmBase):
    society_id: UUID; name: str; shift_type: ShiftType = ShiftType.GENERAL
    start_time: time; end_time: time; is_overnight: bool = False

class ShiftOut(TimestampSchema):
    society_id: UUID; name: str; shift_type: ShiftType
    start_time: time; end_time: time; is_overnight: bool


# ── Staff ─────────────────────────────────────────────────────────────────────
class StaffCreate(OrmBase):
    society_id:       UUID
    full_name:        str
    mobile:           str
    email:            Optional[str]  = None
    department:       StaffDepartment
    designation_id:   Optional[UUID] = None
    shift_id:         Optional[UUID] = None
    joining_date:     Optional[date] = None
    emergency_contact_name:  Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    base_salary:      Optional[float] = None
    user_id:          Optional[UUID] = None

class StaffUpdate(OrmBase):
    full_name:     Optional[str]            = None
    mobile:        Optional[str]            = None
    department:    Optional[StaffDepartment]= None
    designation_id:Optional[UUID]           = None
    shift_id:      Optional[UUID]           = None
    status:        Optional[StaffStatus]    = None
    base_salary:   Optional[float]          = None
    bank_account_number: Optional[str]      = None
    bank_name:     Optional[str]            = None

class StaffOut(TimestampSchema):
    society_id:    UUID; employee_code: str; full_name: str; mobile: str
    email:         Optional[str]; department: StaffDepartment
    designation_id:Optional[UUID]; shift_id: Optional[UUID]
    status:        StaffStatus; joining_date: Optional[date]
    emergency_contact_name: Optional[str]; base_salary: Optional[float]


# ── Duty ──────────────────────────────────────────────────────────────────────
class DutyCreate(OrmBase):
    staff_id:    UUID; society_id: UUID; duty_name: str
    description: Optional[str] = None; location: Optional[str] = None
    duty_date:   date; start_time: Optional[time] = None; end_time: Optional[time] = None
    shift_id:    Optional[UUID] = None; is_recurring: bool = False; notes: Optional[str] = None

class DutyVerifyRequest(OrmBase):
    notes: Optional[str] = None

class DutyOut(TimestampSchema):
    society_id: UUID; staff_id: UUID; duty_name: str; description: Optional[str]
    location: Optional[str]; duty_date: date; start_time: Optional[time]
    end_time: Optional[time]; is_completed: bool; completed_at: Optional[datetime]
    is_recurring: bool; notes: Optional[str]


# ── Attendance ────────────────────────────────────────────────────────────────
class AttendanceCheckIn(OrmBase):
    notes: Optional[str] = None

class AttendanceCheckOut(OrmBase):
    notes: Optional[str] = None

class AttendanceManualEntry(OrmBase):
    staff_id:        UUID; society_id: UUID; attendance_date: date
    status:          AttendanceStatus
    check_in_time:   Optional[datetime] = None
    check_out_time:  Optional[datetime] = None
    notes:           Optional[str]      = None

class AttendanceApprovalRequest(OrmBase):
    notes: Optional[str] = None

class AttendanceOut(TimestampSchema):
    society_id: UUID; staff_id: UUID; attendance_date: date; status: AttendanceStatus
    check_in_time: Optional[datetime]; check_out_time: Optional[datetime]
    working_hours: Optional[float]; overtime_hours: Optional[float]
    is_manual_entry: bool; is_approved: bool; approval_notes: Optional[str]
    approved_at: Optional[datetime]; notes: Optional[str]


# ── Task ──────────────────────────────────────────────────────────────────────
class TaskCreate(OrmBase):
    society_id: UUID; staff_id: UUID; title: str
    description: Optional[str] = None; location: Optional[str] = None
    due_date: Optional[datetime] = None; priority: str = "medium"
    complaint_id: Optional[UUID] = None; visitor_id: Optional[UUID] = None

class TaskStatusUpdate(OrmBase):
    status: TaskStatus; completion_notes: Optional[str] = None

class WorkLogCreate(OrmBase):
    notes: str; photos_url: Optional[str] = None

class TaskOut(TimestampSchema):
    society_id: UUID; staff_id: UUID; title: str; description: Optional[str]
    location: Optional[str]; due_date: Optional[datetime]; status: TaskStatus
    priority: str; acknowledged_at: Optional[datetime]; started_at: Optional[datetime]
    completed_at: Optional[datetime]; verified_at: Optional[datetime]
    completion_notes: Optional[str]


# ── Leave ─────────────────────────────────────────────────────────────────────
class LeaveCreate(OrmBase):
    society_id: UUID; leave_type: LeaveType
    from_date: date; to_date: date; reason: Optional[str] = None

    @field_validator("to_date")
    @classmethod
    def to_after_from(cls, v, info):
        if "from_date" in info.data and v < info.data["from_date"]:
            raise ValueError("to_date must be >= from_date")
        return v

class LeaveApproveRequest(OrmBase):
    notes: Optional[str] = None

class LeaveRejectRequest(OrmBase):
    reason: str

class LeaveOut(TimestampSchema):
    society_id: UUID; staff_id: UUID; leave_type: LeaveType
    from_date: date; to_date: date; total_days: int
    reason: Optional[str]; status: LeaveStatus
    approved_at: Optional[datetime]; rejection_reason: Optional[str]
