from typing import List, Optional
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Path, Request, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import (
    get_current_user, require_roles,
    require_manager_above,
    require_supervisor_above, require_any_staff, require_any_member,
)
from app.models.user import User
from app.core.tenant_scope import assert_society_access, resolve_create_society_id
from app.modules.staff.schemas.staff import (
    StaffCreate, StaffUpdate, StaffOut, DesignationCreate, DesignationOut,
    ShiftCreate, ShiftOut, DutyCreate, DutyOut, DutyVerifyRequest,
    DutyPlanCreate, DutyPlanOut, DutyCancelOut, PaperSheetEntry, PaperSheetOut,
    AttendanceCheckIn, AttendanceCheckOut, AttendanceManualEntry,
    AttendanceApprovalRequest, AttendanceCheckoutApprovalRequest,
    AttendanceRejectRequest, AttendanceOut,
    TaskCreate, TaskOut, TaskStatusUpdate, WorkLogCreate,
    LeaveCreate, LeaveOut, LeaveApproveRequest, LeaveRejectRequest,
    ChecklistTemplateCreate, ChecklistTemplateUpdate, ChecklistTemplateOut,
    DutyChecklistItemOut, DutyChecklistItemCompleteRequest,
)
from app.modules.staff.models.staff import StaffDepartment
from app.modules.staff.services.staff_service import StaffService

router = APIRouter(prefix="/staff", tags=["Staff Operations"])

# The staff module (master, designations, shifts, attendance, leaves, roster,
# checklist templates) is run by the society's Manager as well as the
# committee; supervisors keep their department-scoped access below.
supervisor_above   = require_supervisor_above
any_auth           = require_any_member
any_staff          = require_any_staff
manager_or_above   = require_manager_above

# Roles that can see all departments (managers and above)
_MANAGER_ROLES = {
    "Manager", "Society Admin", "Platform Admin",
    "Committee Chairman", "Committee Secretary", "Committee Treasurer",
}


def _resolve_dept(user: User, requested_dept: Optional[str], db: Session) -> Optional[str]:
    """
    Managers/admins: pass through the requested_dept (or None = all depts).
    Supervisors: always restrict to their own staff.department, ignoring requested_dept.
    """
    role_names = {ur.role.name for ur in user.user_roles if ur.role}
    if role_names & _MANAGER_ROLES:
        return requested_dept
    # Supervisor — look up their staff record
    from app.modules.staff.repositories.staff_repo import StaffRepository
    staff = StaffRepository(db).get_by_user(user.id)
    return staff.department.value if staff else requested_dept


# ── Designations ──────────────────────────────────────────────────────────────
@router.post("/designations", response_model=DesignationOut, status_code=201,
             dependencies=[Depends(manager_or_above)])
def create_designation(data: DesignationCreate, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    return StaffService(db).create_designation(data, user)

@router.get("/designations/{society_id}", response_model=List[DesignationOut])
def list_designations(society_id: UUID, db: Session = Depends(get_db),
                      user: User = Depends(manager_or_above)):
    assert_society_access(user, society_id)
    return StaffService(db).list_designations(society_id)


# ── Shifts ────────────────────────────────────────────────────────────────────
@router.post("/shifts", response_model=ShiftOut, status_code=201,
             dependencies=[Depends(manager_or_above)])
def create_shift(data: ShiftCreate, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    return StaffService(db).create_shift(data, user)

@router.get("/shifts/{society_id}", response_model=List[ShiftOut])
def list_shifts(society_id: UUID, db: Session = Depends(get_db),
                user: User = Depends(manager_or_above)):
    assert_society_access(user, society_id)
    return StaffService(db).list_shifts(society_id)


# ── Staff CRUD ────────────────────────────────────────────────────────────────
@router.post("/", response_model=StaffOut, status_code=201,
             dependencies=[Depends(manager_or_above)])
def create_staff(data: StaffCreate, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    return StaffService(db).create_staff(data, user, request)

@router.patch("/{staff_id}", response_model=StaffOut,
              dependencies=[Depends(manager_or_above)])
def update_staff(staff_id: UUID, data: StaffUpdate, request: Request,
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return StaffService(db).update_staff(staff_id, data, user, request)

@router.get("/{staff_id}", response_model=StaffOut)
def get_staff(staff_id: UUID, db: Session = Depends(get_db),
              user: User = Depends(supervisor_above)):
    return StaffService(db).get_staff(staff_id, user)

@router.get("/by-user/{user_id}", response_model=StaffOut)
def get_staff_by_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(any_auth),
):
    """Return the Staff record linked to a given user_id.
    Callers may only look up their own record unless they are admin/committee/manager.
    """
    role_names = {ur.role.name for ur in current_user.user_roles if ur.role}
    is_privileged = bool(role_names & _MANAGER_ROLES) or \
                    bool(role_names & {"Committee Chairman", "Committee Secretary", "Committee Treasurer", "Society Admin", "Platform Admin"})
    if not is_privileged and str(current_user.id) != str(user_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="You can only fetch your own staff record")
    return StaffService(db).get_staff_by_user(user_id)

@router.get("/society/{society_id}", response_model=List[StaffOut])
def list_staff(
    society_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    department: Optional[str] = Query(None, description="Filter by department (security/housekeeping/technical/gym/admin)"),
    db: Session = Depends(get_db),
    user: User = Depends(supervisor_above),
):
    assert_society_access(user, society_id)
    effective_dept = _resolve_dept(user, department, db)
    return StaffService(db).list_staff(society_id, skip, limit, effective_dept)

@router.get("/society/{society_id}/department/{department}", response_model=List[StaffOut])
def list_by_department(society_id: UUID, department: StaffDepartment,
                       db: Session = Depends(get_db), user: User = Depends(manager_or_above)):
    assert_society_access(user, society_id)
    return StaffService(db).list_by_department(society_id, department)


# ── Duties ────────────────────────────────────────────────────────────────────
@router.post("/duties", response_model=DutyOut, status_code=201)
def assign_duty(data: DutyCreate, request: Request, db: Session = Depends(get_db),
                user: User = Depends(supervisor_above)):
    return StaffService(db).assign_duty(data, user, request)

@router.post("/duties/plan", response_model=DutyPlanOut, status_code=201)
def assign_duty_plan(data: DutyPlanCreate, request: Request, db: Session = Depends(get_db),
                     user: User = Depends(supervisor_above)):
    """One duty for several staff over a range of days (every day or chosen weekdays)."""
    return StaffService(db).assign_duty_plan(data, user, request)

@router.post("/duties/series/{series_id}/cancel", response_model=DutyCancelOut)
def cancel_duty_series(series_id: UUID,
                       from_date: Optional[date] = Query(None, description="First day to cancel; today by default"),
                       staff_id: Optional[UUID] = Query(None, description="Only this staff member's; everyone in the plan if blank"),
                       request: Request = None, db: Session = Depends(get_db),
                       user: User = Depends(supervisor_above)):
    """Cancel the rest of a duty plan (duties nobody has started)."""
    return StaffService(db).cancel_duty_series(series_id, from_date, user, request, staff_id)

@router.post("/duties/{duty_id}/cancel", response_model=DutyCancelOut)
def cancel_duty(duty_id: UUID, request: Request, db: Session = Depends(get_db),
                user: User = Depends(supervisor_above)):
    """Cancel one duty that nobody has started."""
    return StaffService(db).cancel_duty(duty_id, user, request)

@router.post("/duties/{duty_id}/complete", response_model=DutyOut)
def complete_duty(duty_id: UUID, db: Session = Depends(get_db),
                  user: User = Depends(any_staff)):
    return StaffService(db).complete_duty(duty_id, user)

@router.post("/duties/{duty_id}/verify", response_model=DutyOut)
def verify_duty(duty_id: UUID, data: DutyVerifyRequest, db: Session = Depends(get_db),
                user: User = Depends(supervisor_above)):
    return StaffService(db).verify_duty(duty_id, data, user)

@router.get("/duties/society/{society_id}", response_model=List[DutyOut])
def duties_by_date(society_id: UUID,
                   duty_date: date = Query(..., description="YYYY-MM-DD"),
                   db: Session = Depends(get_db), user: User = Depends(supervisor_above)):
    assert_society_access(user, society_id)
    return StaffService(db).get_duties_by_date(society_id, duty_date)

@router.get("/duties/me/{staff_id}", response_model=List[DutyOut])
def my_duties(staff_id: UUID,
              from_date: Optional[date] = Query(None, description="First day to include"),
              to_date: Optional[date] = Query(None, description="Last day to include"),
              db: Session = Depends(get_db), user: User = Depends(any_staff)):
    return StaffService(db).get_my_duties(staff_id, user, from_date, to_date)


# ── Printable duty sheets and paper entry ─────────────────────────────────────
def _pdf(content: bytes, filename: str) -> Response:
    return Response(content=content, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={filename}"})

def _sheet_name(first: date, last: date) -> str:
    return f"duty-sheet-{first}.pdf" if first == last else f"duty-sheets-{first}-to-{last}.pdf"

@router.get("/duties/sheet/society/{society_id}")
def duty_sheets(society_id: UUID,
                duty_date: date = Query(..., description="YYYY-MM-DD"),
                to_date: Optional[date] = Query(None, description="Last day, up to 7 days in all"),
                department: Optional[str] = Query(None),
                db: Session = Depends(get_db), user: User = Depends(supervisor_above)):
    """The printable duty sheets (one page per staff member per day). A supervisor gets
    their own department's."""
    from app.modules.staff.services.duty_sheet_pdf import render_duty_sheets
    assert_society_access(user, society_id)
    svc = StaffService(db)
    pages = svc.duty_sheet_pages(society_id, duty_date, to_date or duty_date,
                                 department=_resolve_dept(user, department, db))
    return _pdf(render_duty_sheets(svc.society_for_print(society_id), svc.zone_for(society_id), pages),
                _sheet_name(duty_date, to_date or duty_date))

@router.get("/duties/sheet/staff/{staff_id}")
def duty_sheet_for_staff(staff_id: UUID,
                         duty_date: date = Query(..., description="YYYY-MM-DD"),
                         to_date: Optional[date] = Query(None),
                         db: Session = Depends(get_db), user: User = Depends(any_staff)):
    """One staff member's printable sheet(s); they can print their own."""
    from app.modules.staff.services.duty_sheet_pdf import render_duty_sheets
    svc = StaffService(db)
    pages = svc.duty_sheet_pages_for_staff(staff_id, duty_date, to_date or duty_date, user)
    society_id = pages[0]["staff"].society_id
    return _pdf(render_duty_sheets(svc.society_for_print(society_id), svc.zone_for(society_id), pages),
                _sheet_name(duty_date, to_date or duty_date))

@router.post("/sheets/entry", response_model=PaperSheetOut)
def enter_paper_sheet(data: PaperSheetEntry, request: Request, db: Session = Depends(get_db),
                      user: User = Depends(supervisor_above)):
    """A supervisor records a filled-in printed sheet: checklist ticks, completed duties
    and the in/out times."""
    return StaffService(db).record_paper_sheet(data, user, request)


# ── Duty Checklist ────────────────────────────────────────────────────────────
@router.get("/duties/{duty_id}/checklist", response_model=List[DutyChecklistItemOut])
def get_duty_checklist(duty_id: UUID, db: Session = Depends(get_db), user: User = Depends(any_staff)):
    return StaffService(db).get_duty_checklist(duty_id, user)

@router.post("/duties/{duty_id}/checklist/{item_id}/complete", response_model=DutyChecklistItemOut)
def complete_checklist_item(duty_id: UUID, item_id: UUID, data: DutyChecklistItemCompleteRequest,
                            db: Session = Depends(get_db), user: User = Depends(any_staff)):
    return StaffService(db).complete_checklist_item(duty_id, item_id, data, user)


# ── Checklist Templates ───────────────────────────────────────────────────────
@router.get("/checklist-templates/{template_id}/sheet")
def checklist_template_sheet(template_id: UUID, db: Session = Depends(get_db),
                             user: User = Depends(supervisor_above)):
    """The checklist as a blank printable sheet (name, date and times left to fill in)."""
    from app.modules.staff.services.duty_sheet_pdf import render_blank_template_sheet
    svc = StaffService(db)
    template = svc.get_checklist_template(template_id, user)
    return _pdf(render_blank_template_sheet(svc.society_for_print(template.society_id),
                                            svc.zone_for(template.society_id), template),
                f"checklist-{template.name.lower().replace(' ', '-')[:40]}.pdf")

@router.post("/checklist-templates", response_model=ChecklistTemplateOut, status_code=201,
             dependencies=[Depends(manager_or_above)])
def create_checklist_template(data: ChecklistTemplateCreate, db: Session = Depends(get_db),
                              user: User = Depends(get_current_user)):
    return StaffService(db).create_checklist_template(data, user)

@router.get("/checklist-templates/society/{society_id}", response_model=List[ChecklistTemplateOut])
def list_checklist_templates(society_id: UUID,
                             department: Optional[str] = Query(None, description="Filter by department"),
                             db: Session = Depends(get_db), user: User = Depends(supervisor_above)):
    assert_society_access(user, society_id)
    return StaffService(db).list_checklist_templates(society_id, department)

@router.get("/checklist-templates/{template_id}", response_model=ChecklistTemplateOut)
def get_checklist_template(template_id: UUID, db: Session = Depends(get_db),
                           user: User = Depends(supervisor_above)):
    return StaffService(db).get_checklist_template(template_id, user)

@router.patch("/checklist-templates/{template_id}", response_model=ChecklistTemplateOut,
              dependencies=[Depends(manager_or_above)])
def update_checklist_template(template_id: UUID, data: ChecklistTemplateUpdate,
                              db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return StaffService(db).update_checklist_template(template_id, data, user)

@router.delete("/checklist-templates/{template_id}", status_code=204)
def delete_checklist_template(template_id: UUID, db: Session = Depends(get_db),
                              user: User = Depends(manager_or_above)):
    StaffService(db).delete_checklist_template(template_id, user)


# ── Attendance ────────────────────────────────────────────────────────────────
@router.post("/attendance/{staff_id}/checkin", response_model=AttendanceOut)
def check_in(staff_id: UUID, data: AttendanceCheckIn, request: Request,
             db: Session = Depends(get_db), user: User = Depends(any_staff)):
    return StaffService(db).check_in(staff_id, data, user, request)

@router.post("/attendance/{staff_id}/checkout", response_model=AttendanceOut)
def check_out(staff_id: UUID, data: AttendanceCheckOut, request: Request,
              db: Session = Depends(get_db), user: User = Depends(any_staff)):
    return StaffService(db).check_out(staff_id, data, user, request)

@router.post("/attendance/manual", response_model=AttendanceOut,
             dependencies=[Depends(manager_or_above)])
def manual_attendance(data: AttendanceManualEntry, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    return StaffService(db).manual_attendance(data, user)

@router.get("/attendance/{staff_id}", response_model=List[AttendanceOut])
def get_attendance(staff_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500),
                   db: Session = Depends(get_db), user: User = Depends(any_staff)):
    return StaffService(db).get_attendance(staff_id, user, skip, limit)

@router.get("/attendance/daily/{society_id}", response_model=List[AttendanceOut])
def daily_attendance(society_id: UUID,
                     att_date: date = Query(..., description="YYYY-MM-DD"),
                     db: Session = Depends(get_db), user: User = Depends(manager_or_above)):
    assert_society_access(user, society_id)
    return StaffService(db).get_daily_attendance(society_id, att_date)

@router.get("/attendance/pending/{society_id}", response_model=List[AttendanceOut])
def pending_attendance(society_id: UUID, db: Session = Depends(get_db),
                       user: User = Depends(manager_or_above)):
    assert_society_access(user, society_id)
    return StaffService(db).get_pending_attendance(society_id)

@router.post("/attendance/{attendance_id}/approve", response_model=AttendanceOut)
def approve_attendance(attendance_id: UUID, data: AttendanceApprovalRequest,
                      db: Session = Depends(get_db),
                      user: User = Depends(supervisor_above)):
    return StaffService(db).approve_attendance(attendance_id, data, user)

@router.post("/attendance/{attendance_id}/approve-checkout", response_model=AttendanceOut)
def approve_checkout(attendance_id: UUID, data: AttendanceCheckoutApprovalRequest,
                     db: Session = Depends(get_db),
                     user: User = Depends(supervisor_above)):
    """Approve the punch-out for a staff attendance record."""
    return StaffService(db).approve_checkout(attendance_id, data, user)

@router.post("/attendance/{attendance_id}/reject", response_model=AttendanceOut)
def reject_attendance(attendance_id: UUID, data: AttendanceRejectRequest,
                      request: Request, db: Session = Depends(get_db),
                      user: User = Depends(supervisor_above)):
    """Reject a pending punch-in. Deactivates the record; staff must re-check-in."""
    return StaffService(db).reject_attendance(attendance_id, data.reason, user, request)

@router.post("/attendance/{attendance_id}/reject-checkout", response_model=AttendanceOut)
def reject_checkout(attendance_id: UUID, data: AttendanceRejectRequest,
                    request: Request, db: Session = Depends(get_db),
                    user: User = Depends(supervisor_above)):
    """Reject a pending punch-out. Clears checkout fields; staff must re-check-out."""
    return StaffService(db).reject_checkout(attendance_id, data.reason, user, request)

@router.get("/attendance/pending/supervisor/{society_id}", response_model=List[AttendanceOut])
def supervisor_pending_attendance(
    society_id: UUID,
    department: Optional[str] = Query(None, description="Filter by department (security/housekeeping/technical/gym)"),
    db: Session = Depends(get_db),
    user: User = Depends(supervisor_above),
):
    """
    Returns pending punch-in approvals.
    Managers/admins see all (or filter by requested dept).
    Supervisors are automatically restricted to their own department.
    """
    assert_society_access(user, society_id)
    effective_dept = _resolve_dept(user, department, db)
    return StaffService(db).get_pending_attendance_for_supervisor(society_id, effective_dept)

@router.get("/attendance/pending-checkout/{society_id}", response_model=List[AttendanceOut])
def pending_checkout_approvals(
    society_id: UUID,
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(supervisor_above),
):
    """Returns attendance records with completed checkout awaiting checkout approval.
    Supervisors are automatically restricted to their own department.
    """
    assert_society_access(user, society_id)
    effective_dept = _resolve_dept(user, department, db)
    return StaffService(db).get_pending_checkout_approvals(society_id, effective_dept)

@router.get("/society/{society_id}/summary", response_model=dict)
def attendance_summary(
    society_id: UUID,
    att_date: date = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    user: User = Depends(supervisor_above),
):
    """Department-wise attendance summary for manager/supervisor dashboard.
    Supervisors see their own department only; managers see all.
    """
    assert_society_access(user, society_id)
    return StaffService(db).get_attendance_summary(society_id, att_date, StaffService.supervised_departments(user))


# ── Tasks ─────────────────────────────────────────────────────────────────────
@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(data: TaskCreate, request: Request, db: Session = Depends(get_db),
                user: User = Depends(manager_or_above)):
    return StaffService(db).create_task(data, user, request)

@router.post("/tasks/{task_id}/status", response_model=TaskOut)
def update_task(task_id: UUID, data: TaskStatusUpdate, request: Request,
                db: Session = Depends(get_db), user: User = Depends(any_staff)):
    return StaffService(db).update_task_status(task_id, data, user, request)

@router.post("/tasks/{task_id}/worklog", response_model=TaskOut, status_code=201)
def add_worklog(task_id: UUID, staff_id: UUID, data: WorkLogCreate,
                db: Session = Depends(get_db), user: User = Depends(supervisor_above)):
    StaffService(db).add_work_log(task_id, data, user, staff_id)
    return StaffService(db).get_active_tasks(staff_id, user)

@router.get("/tasks/staff/{staff_id}", response_model=List[TaskOut])
def staff_tasks(staff_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500),
                db: Session = Depends(get_db), user: User = Depends(supervisor_above)):
    return StaffService(db).get_my_tasks(staff_id, skip, limit, user)

@router.get("/tasks/staff/{staff_id}/active", response_model=List[TaskOut])
def active_tasks(staff_id: UUID, db: Session = Depends(get_db), user: User = Depends(supervisor_above)):
    return StaffService(db).get_active_tasks(staff_id, user)

@router.get("/tasks/society/{society_id}", response_model=List[TaskOut])
def society_tasks(society_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500),
                  db: Session = Depends(get_db), user: User = Depends(manager_or_above)):
    assert_society_access(user, society_id)
    return StaffService(db).get_society_tasks(society_id, skip, limit)


# ── Leave ─────────────────────────────────────────────────────────────────────
@router.post("/leaves/{staff_id}", response_model=LeaveOut, status_code=201)
def apply_leave(staff_id: UUID, data: LeaveCreate, db: Session = Depends(get_db),
                user: User = Depends(any_staff)):
    return StaffService(db).apply_leave(data, staff_id, user)

@router.post("/leaves/{leave_id}/approve", response_model=LeaveOut)
def approve_leave(leave_id: UUID, data: LeaveApproveRequest, request: Request,
                  db: Session = Depends(get_db), user: User = Depends(manager_or_above)):
    return StaffService(db).approve_leave(leave_id, data, user, request)

@router.post("/leaves/{leave_id}/reject", response_model=LeaveOut)
def reject_leave(leave_id: UUID, data: LeaveRejectRequest, request: Request,
                 db: Session = Depends(get_db), user: User = Depends(manager_or_above)):
    return StaffService(db).reject_leave(leave_id, data, user, request)

@router.get("/leaves/pending/{society_id}", response_model=List[LeaveOut])
def pending_leaves(society_id: UUID, db: Session = Depends(get_db),
                   user: User = Depends(manager_or_above)):
    assert_society_access(user, society_id)
    return StaffService(db).get_pending_leaves(society_id)

@router.get("/leaves/staff/{staff_id}", response_model=List[LeaveOut])
def staff_leaves(staff_id: UUID, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500),
                 db: Session = Depends(get_db),
                 user: User = Depends(any_staff)):
    return StaffService(db).get_staff_leaves_checked(staff_id, skip, limit, user)


# ── Complaint Assignment to Staff Department ──────────────────────────────────

from pydantic import BaseModel as _BM

class ComplaintDeptAssign(_BM):
    complaint_id: UUID
    department: str   # security | housekeeping | technical
    notes: Optional[str] = None

class ComplaintDeptAssignOut(_BM):
    complaint_id: str
    department: str
    assigned_by: str
    assigned_to: Optional[str] = None
    message: str

@router.post("/complaints/assign-department", response_model=ComplaintDeptAssignOut)
def assign_complaint_to_department(
    data: ComplaintDeptAssign,
    db: Session = Depends(get_db),
    user: User = Depends(manager_or_above),
):
    """Manager assigns a complaint to a staff department (security/housekeeping/technical)."""
    return StaffService(db).assign_complaint_to_department(data.complaint_id, data.department, data.notes, user)

@router.get("/complaints/department/{society_id}", response_model=list)
def complaints_by_department(
    society_id: UUID,
    department: str = Query(..., description="security|housekeeping|technical"),
    db: Session = Depends(get_db),
    user: User = Depends(supervisor_above),
):
    """Lists complaints assigned to a specific department."""
    assert_society_access(user, society_id)
    return StaffService(db).get_complaints_for_department(society_id, department)


# ── Roster ────────────────────────────────────────────────────────────────────
from app.modules.staff.models.staff import StaffRoster, StaffLeaveBalance, RosterStatus, Staff
from app.schemas.common import OrmBase, TimestampSchema as TS2
from pydantic import BaseModel as BM2, model_validator

class RosterCreate(OrmBase):
    society_id: UUID; staff_id: UUID; shift_id: Optional[UUID] = None
    week_start: date; week_end: date
    monday: bool = True; tuesday: bool = True; wednesday: bool = True
    thursday: bool = True; friday: bool = True; saturday: bool = True; sunday: bool = False
    is_holiday_week: bool = False; notes: Optional[str] = None

    @model_validator(mode="after")
    def _week(self):
        if self.week_end < self.week_start:
            raise ValueError("week_end must not be before week_start")
        if (self.week_end - self.week_start).days > 6:
            raise ValueError("A roster covers at most a week")
        return self

class RosterOut(TS2):
    society_id: UUID; staff_id: UUID; shift_id: Optional[UUID]
    week_start: date; week_end: date; roster_status: RosterStatus
    monday: bool; tuesday: bool; wednesday: bool
    thursday: bool; friday: bool; saturday: bool; sunday: bool

@router.post("/roster", response_model=RosterOut, status_code=201,
             dependencies=[Depends(manager_or_above)])
def create_roster(data: RosterCreate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    society_id = resolve_create_society_id(user, data.society_id)
    staff = db.query(Staff).filter(Staff.id == data.staff_id).first()
    if not staff or staff.society_id != society_id:
        raise HTTPException(status_code=422, detail="That staff member is not in this society")
    payload = data.model_dump()
    payload["society_id"] = society_id
    roster = StaffRoster(**payload, created_by=user.id)
    db.add(roster); db.commit(); db.refresh(roster); return roster

@router.patch("/roster/{roster_id}/publish", response_model=RosterOut)
def publish_roster(roster_id: UUID, db: Session = Depends(get_db),
                   user: User = Depends(manager_or_above)):
    r = db.query(StaffRoster).filter(StaffRoster.id==roster_id).first()
    if not r or (user.society_id is not None and r.society_id != user.society_id):
        raise HTTPException(status_code=404, detail="Roster not found")
    r.roster_status = RosterStatus.PUBLISHED
    db.commit(); db.refresh(r); return r

@router.get("/roster/society/{society_id}", response_model=List[RosterOut])
def list_rosters(society_id: UUID, db: Session = Depends(get_db), user: User = Depends(manager_or_above)):
    assert_society_access(user, society_id)
    return db.query(StaffRoster).filter(StaffRoster.society_id==society_id, StaffRoster.is_active==True)\
        .order_by(StaffRoster.week_start.desc()).limit(20).all()


# ── Leave Balance ─────────────────────────────────────────────────────────────
class LeaveBalanceOut(TS2):
    staff_id: UUID; year: int
    casual_total: float; sick_total: float; earned_total: float
    casual_used: float; sick_used: float; earned_used: float

@router.get("/leave-balance/{staff_id}/{year}", response_model=LeaveBalanceOut)
def get_leave_balance(staff_id: UUID, year: int = Path(..., ge=2000, le=2100), db: Session = Depends(get_db),
                      user: User = Depends(supervisor_above)):
    staff_obj = db.query(Staff).filter(Staff.id == staff_id).first()
    if not staff_obj or (user.society_id is not None and staff_obj.society_id != user.society_id):
        raise HTTPException(status_code=404, detail="Staff not found")
    lb = db.query(StaffLeaveBalance).filter(
        StaffLeaveBalance.staff_id==staff_id, StaffLeaveBalance.year==year
    ).first()
    if not lb:
        # Auto-create default balance
        lb = StaffLeaveBalance(
            society_id=staff_obj.society_id,
            staff_id=staff_id, year=year,
        )
        db.add(lb); db.commit(); db.refresh(lb)
    return lb
