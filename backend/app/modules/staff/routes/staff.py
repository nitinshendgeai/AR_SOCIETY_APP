from typing import List, Optional
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User
from app.modules.staff.schemas.staff import (
    StaffCreate, StaffUpdate, StaffOut, DesignationCreate, DesignationOut,
    ShiftCreate, ShiftOut, DutyCreate, DutyOut, DutyVerifyRequest,
    AttendanceCheckIn, AttendanceCheckOut, AttendanceManualEntry, AttendanceOut,
    TaskCreate, TaskOut, TaskStatusUpdate, WorkLogCreate,
    LeaveCreate, LeaveOut, LeaveApproveRequest, LeaveRejectRequest,
)
from app.modules.staff.models.staff import StaffDepartment
from app.modules.staff.services.staff_service import StaffService

router = APIRouter(prefix="/staff", tags=["Staff Operations"])

admin_or_committee = require_roles("Admin", "Committee")
supervisor_above   = require_roles("Admin", "Committee", "Staff")
any_auth           = require_roles("Admin", "Committee", "Staff", "Resident", "Security")


# ── Designations ──────────────────────────────────────────────────────────────
@router.post("/designations", response_model=DesignationOut, status_code=201,
             dependencies=[Depends(admin_or_committee)])
def create_designation(data: DesignationCreate, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    return StaffService(db).create_designation(data, user)

@router.get("/designations/{society_id}", response_model=List[DesignationOut],
            dependencies=[Depends(admin_or_committee)])
def list_designations(society_id: UUID, db: Session = Depends(get_db)):
    return StaffService(db).list_designations(society_id)


# ── Shifts ────────────────────────────────────────────────────────────────────
@router.post("/shifts", response_model=ShiftOut, status_code=201,
             dependencies=[Depends(admin_or_committee)])
def create_shift(data: ShiftCreate, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    return StaffService(db).create_shift(data, user)

@router.get("/shifts/{society_id}", response_model=List[ShiftOut],
            dependencies=[Depends(admin_or_committee)])
def list_shifts(society_id: UUID, db: Session = Depends(get_db)):
    return StaffService(db).list_shifts(society_id)


# ── Staff CRUD ────────────────────────────────────────────────────────────────
@router.post("/", response_model=StaffOut, status_code=201,
             dependencies=[Depends(admin_or_committee)])
def create_staff(data: StaffCreate, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    return StaffService(db).create_staff(data, user, request)

@router.patch("/{staff_id}", response_model=StaffOut,
              dependencies=[Depends(admin_or_committee)])
def update_staff(staff_id: UUID, data: StaffUpdate, request: Request,
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return StaffService(db).update_staff(staff_id, data, user, request)

@router.get("/{staff_id}", response_model=StaffOut,
            dependencies=[Depends(admin_or_committee)])
def get_staff(staff_id: UUID, db: Session = Depends(get_db)):
    return StaffService(db).get_staff(staff_id)

@router.get("/society/{society_id}", response_model=List[StaffOut],
            dependencies=[Depends(admin_or_committee)])
def list_staff(society_id: UUID, skip: int = 0, limit: int = 50,
               db: Session = Depends(get_db)):
    return StaffService(db).list_staff(society_id, skip, limit)

@router.get("/society/{society_id}/department/{department}", response_model=List[StaffOut],
            dependencies=[Depends(admin_or_committee)])
def list_by_department(society_id: UUID, department: StaffDepartment,
                       db: Session = Depends(get_db)):
    return StaffService(db).list_by_department(society_id, department)


# ── Duties ────────────────────────────────────────────────────────────────────
@router.post("/duties", response_model=DutyOut, status_code=201)
def assign_duty(data: DutyCreate, request: Request, db: Session = Depends(get_db),
                user: User = Depends(admin_or_committee)):
    return StaffService(db).assign_duty(data, user, request)

@router.post("/duties/{duty_id}/complete", response_model=DutyOut)
def complete_duty(duty_id: UUID, db: Session = Depends(get_db),
                  user: User = Depends(supervisor_above)):
    return StaffService(db).complete_duty(duty_id, user)

@router.post("/duties/{duty_id}/verify", response_model=DutyOut)
def verify_duty(duty_id: UUID, data: DutyVerifyRequest, db: Session = Depends(get_db),
                user: User = Depends(admin_or_committee)):
    return StaffService(db).verify_duty(duty_id, data, user)

@router.get("/duties/society/{society_id}", response_model=List[DutyOut],
            dependencies=[Depends(admin_or_committee)])
def duties_by_date(society_id: UUID,
                   duty_date: date = Query(..., description="YYYY-MM-DD"),
                   db: Session = Depends(get_db)):
    return StaffService(db).get_duties_by_date(society_id, duty_date)

@router.get("/duties/me/{staff_id}", response_model=List[DutyOut],
            dependencies=[Depends(supervisor_above)])
def my_duties(staff_id: UUID, db: Session = Depends(get_db)):
    return StaffService(db).get_my_duties(staff_id)


# ── Attendance ────────────────────────────────────────────────────────────────
@router.post("/attendance/{staff_id}/checkin", response_model=AttendanceOut)
def check_in(staff_id: UUID, data: AttendanceCheckIn, request: Request,
             db: Session = Depends(get_db), user: User = Depends(supervisor_above)):
    return StaffService(db).check_in(staff_id, data, user, request)

@router.post("/attendance/{staff_id}/checkout", response_model=AttendanceOut)
def check_out(staff_id: UUID, data: AttendanceCheckOut, request: Request,
              db: Session = Depends(get_db), user: User = Depends(supervisor_above)):
    return StaffService(db).check_out(staff_id, data, user, request)

@router.post("/attendance/manual", response_model=AttendanceOut,
             dependencies=[Depends(admin_or_committee)])
def manual_attendance(data: AttendanceManualEntry, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    return StaffService(db).manual_attendance(data, user)

@router.get("/attendance/{staff_id}", response_model=List[AttendanceOut],
            dependencies=[Depends(admin_or_committee)])
def get_attendance(staff_id: UUID, skip: int = 0, limit: int = 50,
                   db: Session = Depends(get_db)):
    return StaffService(db).get_attendance(staff_id, skip, limit)

@router.get("/attendance/daily/{society_id}", response_model=List[AttendanceOut],
            dependencies=[Depends(admin_or_committee)])
def daily_attendance(society_id: UUID,
                     att_date: date = Query(..., description="YYYY-MM-DD"),
                     db: Session = Depends(get_db)):
    return StaffService(db).get_daily_attendance(society_id, att_date)


# ── Tasks ─────────────────────────────────────────────────────────────────────
@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(data: TaskCreate, request: Request, db: Session = Depends(get_db),
                user: User = Depends(admin_or_committee)):
    return StaffService(db).create_task(data, user, request)

@router.post("/tasks/{task_id}/status", response_model=TaskOut)
def update_task(task_id: UUID, data: TaskStatusUpdate, request: Request,
                db: Session = Depends(get_db), user: User = Depends(supervisor_above)):
    return StaffService(db).update_task_status(task_id, data, user, request)

@router.post("/tasks/{task_id}/worklog", response_model=TaskOut, status_code=201)
def add_worklog(task_id: UUID, staff_id: UUID, data: WorkLogCreate,
                db: Session = Depends(get_db), user: User = Depends(supervisor_above)):
    StaffService(db).add_work_log(task_id, data, user, staff_id)
    return StaffService(db).get_active_tasks(staff_id)

@router.get("/tasks/staff/{staff_id}", response_model=List[TaskOut],
            dependencies=[Depends(supervisor_above)])
def staff_tasks(staff_id: UUID, skip: int = 0, limit: int = 50,
                db: Session = Depends(get_db)):
    return StaffService(db).get_my_tasks(staff_id, skip, limit)

@router.get("/tasks/staff/{staff_id}/active", response_model=List[TaskOut],
            dependencies=[Depends(supervisor_above)])
def active_tasks(staff_id: UUID, db: Session = Depends(get_db)):
    return StaffService(db).get_active_tasks(staff_id)

@router.get("/tasks/society/{society_id}", response_model=List[TaskOut],
            dependencies=[Depends(admin_or_committee)])
def society_tasks(society_id: UUID, skip: int = 0, limit: int = 50,
                  db: Session = Depends(get_db)):
    return StaffService(db).get_society_tasks(society_id, skip, limit)


# ── Leave ─────────────────────────────────────────────────────────────────────
@router.post("/leaves/{staff_id}", response_model=LeaveOut, status_code=201)
def apply_leave(staff_id: UUID, data: LeaveCreate, db: Session = Depends(get_db),
                user: User = Depends(supervisor_above)):
    return StaffService(db).apply_leave(data, staff_id, user)

@router.post("/leaves/{leave_id}/approve", response_model=LeaveOut)
def approve_leave(leave_id: UUID, data: LeaveApproveRequest, request: Request,
                  db: Session = Depends(get_db), user: User = Depends(admin_or_committee)):
    return StaffService(db).approve_leave(leave_id, data, user, request)

@router.post("/leaves/{leave_id}/reject", response_model=LeaveOut)
def reject_leave(leave_id: UUID, data: LeaveRejectRequest, request: Request,
                 db: Session = Depends(get_db), user: User = Depends(admin_or_committee)):
    return StaffService(db).reject_leave(leave_id, data, user, request)

@router.get("/leaves/pending/{society_id}", response_model=List[LeaveOut],
            dependencies=[Depends(admin_or_committee)])
def pending_leaves(society_id: UUID, db: Session = Depends(get_db)):
    return StaffService(db).get_pending_leaves(society_id)

@router.get("/leaves/staff/{staff_id}", response_model=List[LeaveOut],
            dependencies=[Depends(supervisor_above)])
def staff_leaves(staff_id: UUID, skip: int = 0, limit: int = 50,
                 db: Session = Depends(get_db)):
    return StaffService(db).get_staff_leaves(staff_id, skip, limit)


# ── Roster ────────────────────────────────────────────────────────────────────
from app.modules.staff.models.staff import StaffRoster, StaffLeaveBalance, RosterStatus
from app.schemas.common import OrmBase, TimestampSchema as TS2
from pydantic import BaseModel as BM2

class RosterCreate(OrmBase):
    society_id: UUID; staff_id: UUID; shift_id: Optional[UUID] = None
    week_start: date; week_end: date
    monday: bool = True; tuesday: bool = True; wednesday: bool = True
    thursday: bool = True; friday: bool = True; saturday: bool = True; sunday: bool = False
    is_holiday_week: bool = False; notes: Optional[str] = None

class RosterOut(TS2):
    society_id: UUID; staff_id: UUID; shift_id: Optional[UUID]
    week_start: date; week_end: date; roster_status: RosterStatus
    monday: bool; tuesday: bool; wednesday: bool
    thursday: bool; friday: bool; saturday: bool; sunday: bool

@router.post("/roster", response_model=RosterOut, status_code=201,
             dependencies=[Depends(admin_or_committee)])
def create_roster(data: RosterCreate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    roster = StaffRoster(**data.model_dump(), created_by=user.id)
    db.add(roster); db.commit(); db.refresh(roster); return roster

@router.patch("/roster/{roster_id}/publish", response_model=RosterOut,
              dependencies=[Depends(admin_or_committee)])
def publish_roster(roster_id: UUID, db: Session = Depends(get_db)):
    r = db.query(StaffRoster).filter(StaffRoster.id==roster_id).first()
    if not r: raise HTTPException(status_code=404, detail="Roster not found")
    r.roster_status = RosterStatus.PUBLISHED
    db.commit(); db.refresh(r); return r

@router.get("/roster/society/{society_id}", response_model=List[RosterOut],
            dependencies=[Depends(admin_or_committee)])
def list_rosters(society_id: UUID, db: Session = Depends(get_db)):
    return db.query(StaffRoster).filter(StaffRoster.society_id==society_id, StaffRoster.is_active==True)\
        .order_by(StaffRoster.week_start.desc()).limit(20).all()


# ── Leave Balance ─────────────────────────────────────────────────────────────
class LeaveBalanceOut(TS2):
    staff_id: UUID; year: int
    casual_total: float; sick_total: float; earned_total: float
    casual_used: float; sick_used: float; earned_used: float

@router.get("/leave-balance/{staff_id}/{year}", response_model=LeaveBalanceOut,
            dependencies=[Depends(supervisor_above)])
def get_leave_balance(staff_id: UUID, year: int, db: Session = Depends(get_db)):
    lb = db.query(StaffLeaveBalance).filter(
        StaffLeaveBalance.staff_id==staff_id, StaffLeaveBalance.year==year
    ).first()
    if not lb:
        # Auto-create default balance
        lb = StaffLeaveBalance(
            society_id=db.query(Staff).filter(Staff.id==staff_id).first().society_id,
            staff_id=staff_id, year=year,
        )
        db.add(lb); db.commit(); db.refresh(lb)
    return lb
