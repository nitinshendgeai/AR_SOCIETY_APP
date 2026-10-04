import re
from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator
from app.schemas import validators as val
from typing import Optional, List, Literal
from uuid import UUID
from datetime import date, time, datetime
from app.schemas.common import OrmBase, TimestampSchema
from app.utils.local_time import DEFAULT_TZ, iso_utc, local_today, zone
from app.modules.staff.models.staff import (
    StaffDepartment, StaffStatus, AttendanceStatus,
    TaskStatus, LeaveType, LeaveStatus, ShiftType,
)


# ── Designation ───────────────────────────────────────────────────────────────
class DesignationCreate(OrmBase):
    society_id: UUID; name: str = Field(max_length=100); department: StaffDepartment
    description: Optional[str] = None

    _name = field_validator("name", mode="before")(val.line_max(100, required=True))
    _description = field_validator("description", mode="before")(val.note_max(500))

class DesignationOut(TimestampSchema):
    society_id: UUID; name: str; department: StaffDepartment; description: Optional[str]


# ── Shift ─────────────────────────────────────────────────────────────────────
class ShiftCreate(OrmBase):
    society_id: UUID; name: str = Field(max_length=100); shift_type: ShiftType = ShiftType.GENERAL
    start_time: time; end_time: time; is_overnight: bool = False

    _name = field_validator("name", mode="before")(val.line_max(100, required=True))

    @model_validator(mode="after")
    def _times(self):
        if self.end_time == self.start_time:
            raise ValueError("A shift can't start and end at the same time")
        if self.end_time < self.start_time and not self.is_overnight:
            raise ValueError("The shift ends before it starts — mark it overnight if it runs past midnight")
        return self

class ShiftOut(TimestampSchema):
    society_id: UUID; name: str; shift_type: ShiftType
    start_time: time; end_time: time; is_overnight: bool


# ── Staff ─────────────────────────────────────────────────────────────────────
class _StaffChecks(OrmBase):
    """What a staff form sends, checked the same way on create and edit."""
    _name = field_validator("full_name", mode="before", check_fields=False)(val.name)
    _mobile = field_validator("mobile", mode="before", check_fields=False)(val.mobile)
    _email = field_validator("email", mode="before", check_fields=False)(val.email)
    _emergency_name = field_validator("emergency_contact_name", mode="before", check_fields=False)(val.limited(255))
    _emergency_phone = field_validator("emergency_contact_phone", mode="before", check_fields=False)(val.contact_phone)
    _address = field_validator("address", mode="before", check_fields=False)(val.note_max(1000))
    _notes = field_validator("notes", mode="before", check_fields=False)(val.note_max(2000))
    _bank_name = field_validator("bank_name", mode="before", check_fields=False)(val.limited(100))
    _joining = field_validator("joining_date", check_fields=False)(val.sane_date)

    @field_validator("bank_account_number", mode="before", check_fields=False)
    @classmethod
    def _account(cls, v):
        v = val.text(v)
        if v is None:
            return None
        v = v.replace(" ", "").replace("-", "")
        if not re.fullmatch(r"[0-9A-Za-z]{5,34}", v):
            raise ValueError("Enter a valid bank account number")
        return v


class StaffCreate(_StaffChecks):
    society_id:       UUID
    full_name:        str = Field(max_length=255)
    mobile:           str
    email:            Optional[str]  = None
    department:       StaffDepartment
    designation_id:   Optional[UUID] = None
    shift_id:         Optional[UUID] = None
    joining_date:     Optional[date] = None
    emergency_contact_name:  Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    base_salary:      Optional[float] = Field(default=None, ge=0, le=10_000_000)
    user_id:          Optional[UUID] = None
    reporting_manager_id: Optional[UUID] = None
    address:          Optional[str] = None
    notes:            Optional[str] = None

class StaffUpdate(_StaffChecks):
    full_name:     Optional[str]            = Field(default=None, max_length=255)
    mobile:        Optional[str]            = None
    email:         Optional[str]            = None
    department:    Optional[StaffDepartment]= None
    designation_id:Optional[UUID]           = None
    shift_id:      Optional[UUID]           = None
    status:        Optional[StaffStatus]    = None
    joining_date:  Optional[date]           = None
    base_salary:   Optional[float]          = Field(default=None, ge=0, le=10_000_000)
    bank_account_number: Optional[str]      = None
    bank_name:     Optional[str]            = None
    reporting_manager_id: Optional[UUID]    = None
    address:       Optional[str]            = None
    notes:         Optional[str]            = None
    emergency_contact_name:  Optional[str]  = None
    emergency_contact_phone: Optional[str]  = None

class StaffOut(TimestampSchema):
    society_id:    UUID; employee_code: str; full_name: str; mobile: str
    email:         Optional[str]; department: StaffDepartment
    designation_id:Optional[UUID]; shift_id: Optional[UUID]
    status:        StaffStatus; joining_date: Optional[date]
    emergency_contact_name: Optional[str]; emergency_contact_phone: Optional[str] = None
    base_salary: Optional[float]
    reporting_manager_id: Optional[UUID] = None
    designation_name: Optional[str] = None
    reporting_manager_name: Optional[str] = None
    user_id:       Optional[UUID] = None
    temp_password: Optional[str] = None
    address:       Optional[str] = None
    notes:         Optional[str] = None
    photo_url:     Optional[str] = None


# ── Checklist Templates ───────────────────────────────────────────────────────
class ChecklistTemplateItemCreate(OrmBase):
    title: str = Field(max_length=255); description: Optional[str] = None
    is_required: bool = True; sequence: int = Field(default=0, ge=0, le=10_000)

    _title = field_validator("title", mode="before")(val.line_max(255, required=True))
    _description = field_validator("description", mode="before")(val.note_max(1000))

class ChecklistTemplateItemOut(TimestampSchema):
    template_id: UUID; sequence: int; title: str
    description: Optional[str]; is_required: bool

class ChecklistTemplateCreate(OrmBase):
    society_id:  UUID; department: StaffDepartment; name: str = Field(max_length=255)
    description: Optional[str] = None
    items:       List[ChecklistTemplateItemCreate] = Field(default=[], max_length=200)

    _name = field_validator("name", mode="before")(val.line_max(255, required=True))
    _description = field_validator("description", mode="before")(val.note_max(1000))

class ChecklistTemplateUpdate(OrmBase):
    name:        Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    department:  Optional[StaffDepartment] = None
    # When provided, replaces the template's entire item list.
    items:       Optional[List[ChecklistTemplateItemCreate]] = Field(default=None, max_length=200)

    _name = field_validator("name", mode="before")(val.line_max(255, required=True))
    _description = field_validator("description", mode="before")(val.note_max(1000))

class ChecklistTemplateOut(TimestampSchema):
    society_id:  UUID; department: StaffDepartment; name: str
    description: Optional[str]
    items:       List[ChecklistTemplateItemOut] = []


# ── Duty ──────────────────────────────────────────────────────────────────────
class DutyChecklistItemOut(TimestampSchema):
    duty_id: UUID; template_item_id: Optional[UUID]; sequence: int
    title: str; description: Optional[str]; is_required: bool
    is_completed: bool; completed_at: Optional[datetime]; notes: Optional[str]
    entered_from_paper: bool = False

class DutyChecklistItemCompleteRequest(OrmBase):
    is_completed: bool = True
    notes: Optional[str] = None

    _notes = field_validator("notes", mode="before")(val.note_max(1000))

class DutyCreate(OrmBase):
    staff_id:    UUID; society_id: UUID; duty_name: str = Field(max_length=255)
    description: Optional[str] = None; location: Optional[str] = Field(default=None, max_length=255)
    duty_date:   date; start_time: Optional[time] = None; end_time: Optional[time] = None
    shift_id:    Optional[UUID] = None; is_recurring: bool = False; notes: Optional[str] = None
    checklist_template_id: Optional[UUID] = None

    _name = field_validator("duty_name", mode="before")(val.line_max(255, required=True))
    _location = field_validator("location", mode="before")(val.line_max(255))
    _text = field_validator("description", "notes", mode="before")(val.note_max(2000))
    _date = field_validator("duty_date")(val.sane_date)

class DutyVerifyRequest(OrmBase):
    notes: Optional[str] = None

    _notes = field_validator("notes", mode="before")(val.note_max(1000))

class DutyOut(TimestampSchema):
    society_id: UUID; staff_id: UUID; duty_name: str; description: Optional[str]
    location: Optional[str]; duty_date: date; start_time: Optional[time]
    end_time: Optional[time]; is_completed: bool; completed_at: Optional[datetime]
    verified_by: Optional[UUID] = None; verified_at: Optional[datetime] = None
    is_recurring: bool; notes: Optional[str]
    checklist_template_id: Optional[UUID] = None
    series_id: Optional[UUID] = None
    completion_source: Optional[str] = None
    checklist_items: List[DutyChecklistItemOut] = []


class DutyPlanCreate(OrmBase):
    """One duty for several staff over a range of days: one duty per staff per day."""
    society_id:  UUID
    staff_ids:   List[UUID] = Field(min_length=1, max_length=50)
    duty_name:   str = Field(max_length=255)
    description: Optional[str] = None
    location:    Optional[str] = Field(default=None, max_length=255)
    from_date:   date
    to_date:     Optional[date] = None
    # 0 = Monday … 6 = Sunday; blank means every day in the range.
    weekdays:    Optional[List[int]] = None
    start_time:  Optional[time] = None
    end_time:    Optional[time] = None
    shift_id:    Optional[UUID] = None
    checklist_template_id: Optional[UUID] = None
    notes:       Optional[str] = None

    _name = field_validator("duty_name", mode="before")(val.line_max(255, required=True))
    _location = field_validator("location", mode="before")(val.line_max(255))
    _text = field_validator("description", "notes", mode="before")(val.note_max(2000))
    _dates = field_validator("from_date", "to_date")(val.sane_date)

    @field_validator("staff_ids")
    @classmethod
    def _unique_staff(cls, v):
        return list(dict.fromkeys(v))

    @field_validator("weekdays")
    @classmethod
    def _weekdays(cls, v):
        if not v:
            return None
        if any(not isinstance(d, int) or d < 0 or d > 6 for d in v):
            raise ValueError("Weekdays are 0 (Monday) to 6 (Sunday)")
        return sorted(set(v))

    @model_validator(mode="after")
    def _range(self):
        end = self.to_date or self.from_date
        if end < self.from_date:
            raise ValueError("The last day can't be before the first day")
        if (end - self.from_date).days > 61:
            raise ValueError("A plan can cover at most 62 days; make another plan for the rest")
        if self.start_time and self.end_time and self.start_time == self.end_time:
            raise ValueError("Start and end time can't be the same")
        return self


class DutyPlanSkip(OrmBase):
    staff_id: UUID; staff_name: str; duty_date: date; reason: str


class DutyPlanOut(OrmBase):
    series_id: Optional[UUID] = None
    created: int
    first_date: Optional[date] = None
    last_date: Optional[date] = None
    skipped: List[DutyPlanSkip] = []


class PaperItemEntry(OrmBase):
    item_id: UUID
    is_completed: bool = True
    notes: Optional[str] = None

    _notes = field_validator("notes", mode="before")(val.note_max(1000))


class PaperDutyEntry(OrmBase):
    duty_id: UUID
    items: List[PaperItemEntry] = Field(default=[], max_length=200)
    mark_complete: bool = False


class PaperSheetEntry(OrmBase):
    """What a supervisor read off a staff member's printed sheet for one day.
    Clock times are the society's own."""
    staff_id: UUID
    sheet_date: date
    attendance_status: Optional[AttendanceStatus] = None
    check_in: Optional[time] = None
    check_out: Optional[time] = None
    duties: List[PaperDutyEntry] = Field(default=[], max_length=50)
    notes: Optional[str] = None

    _notes = field_validator("notes", mode="before")(val.note_max(500))
    _date = field_validator("sheet_date")(val.sane_date)

    @model_validator(mode="after")
    def _times(self):
        if self.sheet_date > local_today(zone(DEFAULT_TZ)):
            raise ValueError("A sheet can't be entered for a future date")
        if self.check_out and not self.check_in:
            raise ValueError("Enter the in time as well as the out time")
        if self.attendance_status in (AttendanceStatus.ABSENT, AttendanceStatus.LEAVE,
                                      AttendanceStatus.OFF_DUTY) and (self.check_in or self.check_out):
            raise ValueError("A staff member marked absent, on leave or off duty has no in/out times")
        return self


class PaperSheetOut(OrmBase):
    attendance: Optional["AttendanceOut"] = None
    duties: List[DutyOut] = []


# ── Attendance ────────────────────────────────────────────────────────────────
class AttendanceCheckIn(OrmBase):
    notes: Optional[str] = None

    _notes = field_validator("notes", mode="before")(val.note_max(500))

class AttendanceCheckOut(OrmBase):
    notes: Optional[str] = None

    _notes = field_validator("notes", mode="before")(val.note_max(500))

class AttendanceManualEntry(OrmBase):
    staff_id:        UUID; society_id: UUID; attendance_date: date
    status:          AttendanceStatus
    check_in_time:   Optional[datetime] = None
    check_out_time:  Optional[datetime] = None
    notes:           Optional[str]      = None

    _notes = field_validator("notes", mode="before")(val.note_max(500))

    @model_validator(mode="after")
    def _times(self):
        if self.attendance_date > local_today(zone(DEFAULT_TZ)):
            raise ValueError("Attendance can't be recorded for a future date")
        if self.check_in_time and self.check_out_time and self.check_out_time <= self.check_in_time:
            raise ValueError("Check-out must be after check-in")
        return self

class AttendanceApprovalRequest(OrmBase):
    notes: Optional[str] = None

    _notes = field_validator("notes", mode="before")(val.note_max(500))

class AttendanceCheckoutApprovalRequest(OrmBase):
    notes: Optional[str] = None

    _notes = field_validator("notes", mode="before")(val.note_max(500))

class AttendanceRejectRequest(OrmBase):
    reason: Optional[str] = None

    _reason = field_validator("reason", mode="before")(val.note_max(500))

class AttendanceOut(TimestampSchema):
    society_id: UUID; staff_id: UUID; attendance_date: date; status: AttendanceStatus
    check_in_time: Optional[datetime]; check_out_time: Optional[datetime]
    working_hours: Optional[float]; overtime_hours: Optional[float]
    is_manual_entry: bool; is_approved: bool; approval_notes: Optional[str]
    approved_at: Optional[datetime]
    is_checkout_approved: bool = False
    checkout_approved_at: Optional[datetime] = None
    checkout_approval_notes: Optional[str] = None
    notes: Optional[str]
    staff_name: Optional[str] = None

    # Stored as naive UTC. Sent with an explicit Z so the app shows each viewer's
    # own clock instead of the UTC digits.
    @field_serializer("check_in_time", "check_out_time", "approved_at", "checkout_approved_at",
                      when_used="json")
    def _utc_text(self, v):
        return iso_utc(v)


PaperSheetOut.model_rebuild()


# ── Task ──────────────────────────────────────────────────────────────────────
class TaskCreate(OrmBase):
    society_id: UUID; staff_id: UUID; title: str = Field(max_length=255)
    description: Optional[str] = None; location: Optional[str] = Field(default=None, max_length=255)
    due_date: Optional[datetime] = None
    priority: Literal["low", "medium", "high", "urgent", "critical"] = "medium"
    complaint_id: Optional[UUID] = None; visitor_id: Optional[UUID] = None

    _title = field_validator("title", mode="before")(val.line_max(255, required=True))
    _location = field_validator("location", mode="before")(val.line_max(255))
    _description = field_validator("description", mode="before")(val.note_max(2000))

class TaskStatusUpdate(OrmBase):
    status: TaskStatus; completion_notes: Optional[str] = None

    _notes = field_validator("completion_notes", mode="before")(val.note_max(1000))

class WorkLogCreate(OrmBase):
    notes: str; photos_url: Optional[str] = Field(default=None, max_length=500)

    _notes = field_validator("notes", mode="before")(val.note_max(2000, required=True))

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

    _reason = field_validator("reason", mode="before")(val.note_max(1000))
    _dates = field_validator("from_date", "to_date")(val.sane_date)

    @field_validator("to_date")
    @classmethod
    def to_after_from(cls, v, info):
        if "from_date" in info.data and v < info.data["from_date"]:
            raise ValueError("to_date must be >= from_date")
        if "from_date" in info.data and (v - info.data["from_date"]).days > 365:
            raise ValueError("A leave can't be longer than a year")
        return v

class LeaveApproveRequest(OrmBase):
    notes: Optional[str] = None

    _notes = field_validator("notes", mode="before")(val.note_max(500))

class LeaveRejectRequest(OrmBase):
    reason: str

    _reason = field_validator("reason", mode="before")(val.note_max(500, required=True))

class LeaveOut(TimestampSchema):
    society_id: UUID; staff_id: UUID; leave_type: LeaveType
    from_date: date; to_date: date; total_days: int
    reason: Optional[str]; status: LeaveStatus
    approved_at: Optional[datetime]; rejection_reason: Optional[str]
