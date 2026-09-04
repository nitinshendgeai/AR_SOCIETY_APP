from datetime import datetime, date
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.modules.staff.models.staff import (
    Staff, StaffDesignation, StaffShift, DutyAssignment,
    StaffAttendance, StaffTask, StaffLeave, StaffWorkLog,
    AttendanceStatus, TaskStatus, LeaveStatus, TASK_TRANSITIONS, StaffDepartment,
    ChecklistTemplate, ChecklistTemplateItem, DutyChecklistItem,
)
from app.modules.staff.schemas.staff import (
    StaffCreate, StaffUpdate, DesignationCreate, ShiftCreate,
    DutyCreate, DutyVerifyRequest, AttendanceCheckIn, AttendanceCheckOut,
    AttendanceManualEntry, AttendanceApprovalRequest, AttendanceCheckoutApprovalRequest,
    TaskCreate, TaskStatusUpdate, WorkLogCreate,
    LeaveCreate, LeaveApproveRequest, LeaveRejectRequest,
    ChecklistTemplateCreate, ChecklistTemplateUpdate,
    DutyChecklistItemCompleteRequest,
)
from app.modules.staff.repositories.staff_repo import (
    StaffRepository, StaffDesignationRepo, StaffShiftRepo,
    DutyRepository, AttendanceRepository, TaskRepository, LeaveRepository,
    ChecklistTemplateRepo,
)
from app.models.user import User, UserRole, UserStatus
from app.models.role import Role
from app.models.audit_log import AuditAction
from app.core.security import hash_password
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel

DEFAULT_STAFF_PASSWORD = "Staff@1234"

# Roles that bypass department restrictions
_MANAGER_ROLES_SVC = {
    "Manager", "Society Admin", "Platform Admin",
    "Committee Chairman", "Committee Secretary", "Committee Treasurer",
}

# Supervisor role → set of departments they can approve
_SUPERVISOR_DEPT_ACCESS: dict = {
    "Security Supervisor":     {"security"},
    "Housekeeping Supervisor": {"housekeeping", "gym", "gardening", "amenities"},
    "Technical Supervisor":    {"technical", "maintenance", "electrical", "plumbing"},
}

_DESIGNATION_TO_ROLE = {
    "Manager":                 "Manager",
    "Security Supervisor":     "Security Supervisor",
    "Security Guard":          "Security Staff",
    "Housekeeping Supervisor": "Housekeeping Supervisor",
    "Housekeeping Staff":      "Housekeeping Staff",
    "Technical Supervisor":    "Technical Supervisor",
    "Technical Staff":         "Technical Staff",
    "Maintenance Staff":       "Technical Staff",
    "Gym Trainer":             "Gym Trainer",
}

_DEPT_TO_ROLE = {
    "security":     "Security Staff",
    "housekeeping": "Housekeeping Staff",
    "technical":    "Technical Staff",
    "maintenance":  "Technical Staff",
    "electrical":   "Technical Staff",
    "plumbing":     "Technical Staff",
    "gardening":    "Housekeeping Staff",
    "amenities":    "Housekeeping Staff",
    "gym":          "Gym Trainer",
    "admin":        "Manager",
}


class StaffService:

    def __init__(self, db: Session):
        self.db          = db
        self.repo        = StaffRepository(db)
        self.desg_repo   = StaffDesignationRepo(db)
        self.shift_repo  = StaffShiftRepo(db)
        self.duty_repo   = DutyRepository(db)
        self.att_repo    = AttendanceRepository(db)
        self.task_repo   = TaskRepository(db)
        self.leave_repo  = LeaveRepository(db)
        self.checklist_repo = ChecklistTemplateRepo(db)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _staff_or_404(self, staff_id: UUID) -> Staff:
        s = self.repo.get(staff_id)
        if not s: raise HTTPException(status_code=404, detail="Staff not found")
        return s

    def _task_or_404(self, task_id: UUID) -> StaffTask:
        t = self.task_repo.get(task_id)
        if not t: raise HTTPException(status_code=404, detail="Task not found")
        return t

    def _audit(self, action, entity, entity_type, user, request=None, **kw):
        AuditService.log(db=self.db, action=action, module="staff",
                         entity_id=str(entity.id), entity_type=entity_type,
                         user=user, request=request, **kw)

    def _assert_self_or_supervisor(self, user: User, staff: Staff) -> None:
        """Attendance punch/read: a supervisor-or-above may act on any staff
        member (kiosk / on-behalf punching — the existing, tested behavior),
        but a plain staff member may only punch or view their own record.
        Without this, any authenticated staff-or-above user could check
        in/out or read the attendance history of an arbitrary staff_id."""
        role_names = {ur.role.name for ur in user.user_roles if ur.role}
        if role_names & _MANAGER_ROLES_SVC or role_names & set(_SUPERVISOR_DEPT_ACCESS.keys()):
            return
        if staff.user_id != user.id:
            raise HTTPException(status_code=403, detail="You can only manage your own attendance")

    def _check_dept_access(self, user: User, staff_department: str) -> None:
        """Raise 403 if a supervisor is not authorised to act on the given department.
        Managers/admins bypass this check entirely."""
        role_names = {ur.role.name for ur in user.user_roles if ur.role}
        if role_names & _MANAGER_ROLES_SVC:
            return
        for sup_role, allowed_depts in _SUPERVISOR_DEPT_ACCESS.items():
            if sup_role in role_names:
                if staff_department not in allowed_depts:
                    raise HTTPException(
                        status_code=403,
                        detail=f"{sup_role} cannot approve {staff_department} department attendance",
                    )
                return
        raise HTTPException(status_code=403, detail="Insufficient permissions to approve attendance")

    def _notify(self, user_id, title, body, type=NotificationType.INFO, module="staff", entity_id=None):
        if user_id:
            NotificationService.send(
                db=self.db, user_id=user_id, title=title, body=body,
                type=type, channel=NotificationChannel.IN_APP,
                module=module, entity_id=str(entity_id) if entity_id else None,
            )

    # ── Designations & Shifts ─────────────────────────────────────────────────

    def create_designation(self, data: DesignationCreate, user: User) -> StaffDesignation:
        d = StaffDesignation(**data.model_dump())
        return self.desg_repo.create(d)

    def list_designations(self, society_id: UUID) -> List[StaffDesignation]:
        return self.desg_repo.get_by_society(society_id)

    def create_shift(self, data: ShiftCreate, user: User) -> StaffShift:
        s = StaffShift(**data.model_dump())
        return self.shift_repo.create(s)

    def list_shifts(self, society_id: UUID) -> List[StaffShift]:
        return self.shift_repo.get_by_society(society_id)

    # ── Staff CRUD ────────────────────────────────────────────────────────────

    def create_staff(self, data: StaffCreate, user: User, request=None) -> Staff:
        code  = self.repo.next_employee_code(data.society_id)
        staff = Staff(**data.model_dump(), employee_code=code)
        self.repo.create(staff)  # commits + refreshes

        temp_pwd = None
        if data.email and not data.user_id:
            # Auto-create a login account for this staff member
            temp_pwd = DEFAULT_STAFF_PASSWORD
            new_user = User(
                society_id           = data.society_id,
                email                = data.email,
                full_name            = data.full_name,
                hashed_password      = hash_password(temp_pwd),
                status               = UserStatus.ACTIVE,
                must_change_password = True,
                terms_accepted       = False,
                setup_completed      = False,
            )
            self.db.add(new_user)
            self.db.flush()

            role_name = self._resolve_staff_role(staff)
            if role_name:
                role = self.db.query(Role).filter(Role.name == role_name).first()
                if role:
                    self.db.add(UserRole(user_id=new_user.id, role_id=role.id))

            staff.user_id = new_user.id
            self.db.commit()
            self.db.refresh(staff)

        self._audit(AuditAction.CREATE, staff, "Staff", user, request,
                    new_values={"employee_code": code, "name": data.full_name,
                                "dept": data.department.value, "user_created": temp_pwd is not None})

        if temp_pwd:
            staff.__dict__['temp_password'] = temp_pwd
        return staff

    def _resolve_staff_role(self, staff: Staff) -> Optional[str]:
        if staff.designation_id:
            desg = self.db.query(StaffDesignation).filter(
                StaffDesignation.id == staff.designation_id
            ).first()
            if desg and desg.name in _DESIGNATION_TO_ROLE:
                return _DESIGNATION_TO_ROLE[desg.name]
        return _DEPT_TO_ROLE.get(staff.department.value)

    def update_staff(self, staff_id: UUID, data: StaffUpdate, user: User, request=None) -> Staff:
        staff = self._staff_or_404(staff_id)
        updated = self.repo.update(staff, data.model_dump(exclude_none=True))
        self._audit(AuditAction.UPDATE, updated, "Staff", user, request)
        return updated

    def get_staff(self, staff_id: UUID) -> Staff:
        return self._staff_or_404(staff_id)

    def get_staff_by_user(self, user_id: UUID) -> Staff:
        staff = self.repo.get_by_user(user_id)
        if not staff:
            raise HTTPException(status_code=404, detail="No staff profile linked to this user")
        return staff

    def list_staff(self, society_id: UUID, skip=0, limit=50,
                   department: Optional[str] = None) -> List[Staff]:
        if department:
            from app.modules.staff.models.staff import StaffDepartment
            try:
                dept_enum = StaffDepartment(department)
                return self.repo.get_by_department(society_id, dept_enum)
            except ValueError:
                pass
        return self.repo.get_by_society(society_id, skip, limit)

    def list_by_department(self, society_id: UUID, dept) -> List[Staff]:
        return self.repo.get_by_department(society_id, dept)

    # ── Duty Assignment ───────────────────────────────────────────────────────

    def assign_duty(self, data: DutyCreate, assigner: User, request=None) -> DutyAssignment:
        staff = self._staff_or_404(data.staff_id)
        if data.checklist_template_id:
            template = self.checklist_repo.get(data.checklist_template_id)
            if not template:
                raise HTTPException(status_code=404, detail="Checklist template not found")

        duty = DutyAssignment(**data.model_dump(), assigned_by=assigner.id)
        self.db.add(duty)
        self.db.flush()

        # Snapshot the template's items onto this duty so later template
        # edits never retroactively change an already-assigned checklist.
        if data.checklist_template_id:
            for item in template.items:
                self.db.add(DutyChecklistItem(
                    duty_id=duty.id, template_item_id=item.id, sequence=item.sequence,
                    title=item.title, description=item.description, is_required=item.is_required,
                ))
            self.db.flush()

        self._audit(AuditAction.CREATE, duty, "DutyAssignment", assigner, request,
                    new_values={"staff": str(data.staff_id), "duty": data.duty_name, "date": str(data.duty_date)})
        # Notify staff if linked to user
        if staff.user_id:
            self._notify(staff.user_id, "Duty Assigned",
                f"You have been assigned: {data.duty_name} on {data.duty_date}",
                type=NotificationType.ALERT, entity_id=duty.id)
        self.db.commit()
        self.db.refresh(duty)
        return duty

    def complete_duty(self, duty_id: UUID, user: User) -> DutyAssignment:
        duty = self.duty_repo.get(duty_id)
        if not duty: raise HTTPException(status_code=404, detail="Duty not found")
        if duty.is_completed: raise HTTPException(status_code=409, detail="Duty already completed")
        incomplete_required = [
            i.title for i in duty.checklist_items if i.is_required and not i.is_completed
        ]
        if incomplete_required:
            raise HTTPException(
                status_code=409,
                detail=f"Complete all required checklist items first: {', '.join(incomplete_required)}",
            )
        duty.is_completed = True
        duty.completed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(duty)
        return duty

    # ── Duty Checklist ────────────────────────────────────────────────────────

    def get_duty_checklist(self, duty_id: UUID) -> List[DutyChecklistItem]:
        duty = self.duty_repo.get(duty_id)
        if not duty: raise HTTPException(status_code=404, detail="Duty not found")
        return duty.checklist_items

    def complete_checklist_item(
        self, duty_id: UUID, item_id: UUID, data: DutyChecklistItemCompleteRequest, user: User,
    ) -> DutyChecklistItem:
        duty = self.duty_repo.get(duty_id)
        if not duty: raise HTTPException(status_code=404, detail="Duty not found")

        item = next((i for i in duty.checklist_items if i.id == item_id), None)
        if not item:
            raise HTTPException(status_code=404, detail="Checklist item not found on this duty")

        item.is_completed = data.is_completed
        item.completed_at = datetime.utcnow() if data.is_completed else None
        if data.notes is not None:
            item.notes = data.notes
        self.db.commit()
        self.db.refresh(item)
        return item

    # ── Checklist Templates ───────────────────────────────────────────────────

    def create_checklist_template(self, data: ChecklistTemplateCreate, user: User) -> ChecklistTemplate:
        template = ChecklistTemplate(
            society_id=data.society_id, department=data.department,
            name=data.name, description=data.description, created_by=user.id,
        )
        self.db.add(template)
        self.db.flush()
        for idx, item in enumerate(data.items):
            self.db.add(ChecklistTemplateItem(
                template_id=template.id, sequence=item.sequence or idx,
                title=item.title, description=item.description, is_required=item.is_required,
            ))
        self.db.commit()
        self.db.refresh(template)
        return template

    def list_checklist_templates(self, society_id: UUID, department=None) -> List[ChecklistTemplate]:
        dept_enum = None
        if department:
            try:
                dept_enum = StaffDepartment(department)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Unknown department: {department}")
        return self.checklist_repo.get_by_society(society_id, dept_enum)

    def get_checklist_template(self, template_id: UUID) -> ChecklistTemplate:
        template = self.checklist_repo.get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Checklist template not found")
        return template

    def update_checklist_template(
        self, template_id: UUID, data: ChecklistTemplateUpdate, user: User,
    ) -> ChecklistTemplate:
        template = self.get_checklist_template(template_id)
        if data.name is not None:
            template.name = data.name
        if data.description is not None:
            template.description = data.description
        if data.department is not None:
            template.department = data.department
        if data.items is not None:
            for item in list(template.items):
                self.db.delete(item)
            self.db.flush()
            for idx, item in enumerate(data.items):
                self.db.add(ChecklistTemplateItem(
                    template_id=template.id, sequence=item.sequence or idx,
                    title=item.title, description=item.description, is_required=item.is_required,
                ))
        self.db.commit()
        self.db.refresh(template)
        return template

    def delete_checklist_template(self, template_id: UUID) -> None:
        template = self.get_checklist_template(template_id)
        self.checklist_repo.soft_delete(template)

    def verify_duty(self, duty_id: UUID, data: DutyVerifyRequest, verifier: User) -> DutyAssignment:
        duty = self.duty_repo.get(duty_id)
        if not duty: raise HTTPException(status_code=404, detail="Duty not found")
        if not duty.is_completed: raise HTTPException(status_code=409, detail="Duty not yet completed")
        duty.verified_by = verifier.id
        duty.verified_at = datetime.utcnow()
        if data.notes: duty.notes = data.notes
        self._audit(AuditAction.APPROVE, duty, "DutyAssignment", verifier)
        self.db.commit()
        self.db.refresh(duty)
        return duty

    def get_duties_by_date(self, society_id: UUID, duty_date: date) -> List[DutyAssignment]:
        return self.duty_repo.get_by_society_date(society_id, duty_date)

    def get_my_duties(self, staff_id: UUID) -> List[DutyAssignment]:
        return self.duty_repo.get_by_staff(staff_id)

    # ── Attendance ────────────────────────────────────────────────────────────

    def check_in(self, staff_id: UUID, data: AttendanceCheckIn,
                 user: User, request=None) -> StaffAttendance:
        staff = self._staff_or_404(staff_id)
        self._assert_self_or_supervisor(user, staff)
        today = date.today()
        existing = self.att_repo.get_today(staff_id, today)
        if existing:
            raise HTTPException(status_code=409,
                detail=f"Attendance already marked for today (status: {existing.status.value})")
        att = StaffAttendance(
            society_id=staff.society_id,
            staff_id=staff_id,
            attendance_date=today,
            status=AttendanceStatus.PRESENT,
            check_in_time=datetime.utcnow(),
            marked_by=user.id,
            notes=data.notes,
        )
        self.att_repo.create(att)
        self._audit(AuditAction.CREATE, att, "StaffAttendance", user, request,
                    new_values={"staff_id": str(staff_id), "date": str(today), "status": "present"})
        return att

    def check_out(self, staff_id: UUID, data: AttendanceCheckOut,
                  user: User, request=None) -> StaffAttendance:
        staff = self._staff_or_404(staff_id)
        self._assert_self_or_supervisor(user, staff)
        today = date.today()
        att = self.att_repo.get_today(staff_id, today)
        if not att:
            raise HTTPException(status_code=404, detail="No check-in found for today")
        if att.check_out_time:
            raise HTTPException(status_code=409, detail="Already checked out today")

        att.check_out_time = datetime.utcnow()
        # Compute working hours
        delta = att.check_out_time - att.check_in_time
        att.working_hours = round(delta.total_seconds() / 3600, 2)
        # Overtime: anything beyond 8h standard shift (payroll-ready)
        standard_hours = 8.0
        if att.working_hours > standard_hours:
            att.overtime_hours = round(att.working_hours - standard_hours, 2)
        if data.notes: att.notes = (att.notes or "") + f" | Checkout: {data.notes}"

        self.db.commit()
        self.db.refresh(att)
        self._audit(AuditAction.UPDATE, att, "StaffAttendance", user, request,
                    new_values={"working_hours": att.working_hours, "overtime_hours": att.overtime_hours})
        return att

    def manual_attendance(self, data: AttendanceManualEntry, user: User) -> StaffAttendance:
        existing = self.att_repo.get_today(data.staff_id, data.attendance_date)
        if existing:
            # Update existing
            existing.status = data.status
            if data.check_in_time:  existing.check_in_time  = data.check_in_time
            if data.check_out_time: existing.check_out_time = data.check_out_time
            existing.is_manual_entry = True
            existing.marked_by = user.id
            existing.notes = data.notes
            self.db.commit()
            self.db.refresh(existing)
            return existing
        att = StaffAttendance(**data.model_dump(), marked_by=user.id, is_manual_entry=True)
        return self.att_repo.create(att)

    def get_attendance(self, staff_id: UUID, user: User, skip=0, limit=50) -> List[StaffAttendance]:
        staff = self._staff_or_404(staff_id)
        self._assert_self_or_supervisor(user, staff)
        return self.att_repo.get_by_staff(staff_id, skip, limit)

    def get_daily_attendance(self, society_id: UUID, att_date: date) -> List[StaffAttendance]:
        return self.att_repo.get_by_society_date(society_id, att_date)

    def get_pending_attendance(self, society_id: UUID) -> List[StaffAttendance]:
        return self.att_repo.get_pending(society_id)

    def get_pending_attendance_for_supervisor(
        self, society_id: UUID, department: Optional[str] = None
    ) -> List[StaffAttendance]:
        return self.att_repo.get_pending_by_dept(society_id, department)

    def get_pending_checkout_approvals(
        self, society_id: UUID, department: Optional[str] = None
    ) -> List[StaffAttendance]:
        return self.att_repo.get_pending_checkout(society_id, department)

    def get_attendance_summary(self, society_id: UUID, att_date: date) -> dict:
        from datetime import timedelta
        records    = self.att_repo.get_by_society_date(society_id, att_date)
        staff_list = self.repo.get_by_society(society_id, skip=0, limit=500)
        staff_map  = {s.id: s for s in staff_list}
        total_staff = len(staff_list)

        present  = 0
        late     = 0
        pending_checkin  = 0
        pending_checkout = 0
        dept_map: dict = {}

        LATE_THRESHOLD_MINUTES = 30

        for r in records:
            if r.check_in_time is not None:
                present += 1
                # Late detection: compare check_in_time against assigned shift start
                st = staff_map.get(r.staff_id)
                if st and st.shift_id and st.shift:
                    shift_start = st.shift.start_time
                    # Build a datetime for today's shift start
                    from datetime import datetime as dt
                    shift_dt = dt.combine(att_date, shift_start)
                    # For overnight shifts the start on att_date is correct
                    if r.check_in_time > shift_dt + timedelta(minutes=LATE_THRESHOLD_MINUTES):
                        late += 1

            if not r.is_approved:
                pending_checkin += 1
            if r.check_out_time and not r.is_checkout_approved:
                pending_checkout += 1

            # dept breakdown
            st = staff_map.get(r.staff_id)
            dept = st.department.value if st else "unknown"
            if dept not in dept_map:
                dept_map[dept] = {"present": 0, "absent": 0, "late": 0}
            dept_map[dept]["present"] += 1
            if st and st.shift and r.check_in_time:
                pass  # late per dept could be added later

        absent = total_staff - present

        return {
            "date": str(att_date),
            "total_staff": total_staff,
            "present": present,
            "absent": absent,
            "late": late,
            "pending_checkin_approval": pending_checkin,
            "pending_checkout_approval": pending_checkout,
            "department_breakdown": dept_map,
        }

    def approve_attendance(self, attendance_id: UUID, data: AttendanceApprovalRequest,
                           user: User, request=None) -> StaffAttendance:
        attendance = self.att_repo.get(attendance_id)
        if not attendance:
            raise HTTPException(status_code=404, detail="Attendance record not found")
        if user.society_id and str(attendance.society_id) != str(user.society_id):
            raise HTTPException(status_code=403, detail="Cannot approve attendance from another society")
        staff = self.repo.get(attendance.staff_id)
        if staff:
            self._check_dept_access(user, staff.department.value)
        if attendance.is_approved:
            raise HTTPException(status_code=409, detail="Attendance record already approved")

        attendance.is_approved = True
        attendance.approved_by = user.id
        attendance.approved_at = datetime.utcnow()
        if data.notes:
            attendance.approval_notes = data.notes

        self._audit(AuditAction.APPROVE, attendance, "StaffAttendance", user, request,
                    new_values={"approval_status": "approved"})
        self.db.commit()
        self.db.refresh(attendance)
        return attendance

    def approve_checkout(self, attendance_id: UUID, data: AttendanceCheckoutApprovalRequest,
                         user: User, request=None) -> StaffAttendance:
        attendance = self.att_repo.get(attendance_id)
        if not attendance:
            raise HTTPException(status_code=404, detail="Attendance record not found")
        if user.society_id and str(attendance.society_id) != str(user.society_id):
            raise HTTPException(status_code=403, detail="Cannot approve attendance from another society")
        staff = self.repo.get(attendance.staff_id)
        if staff:
            self._check_dept_access(user, staff.department.value)
        if not attendance.check_out_time:
            raise HTTPException(status_code=409, detail="Staff has not checked out yet")
        if attendance.is_checkout_approved:
            raise HTTPException(status_code=409, detail="Checkout already approved")

        attendance.is_checkout_approved    = True
        attendance.checkout_approved_by    = user.id
        attendance.checkout_approved_at    = datetime.utcnow()
        if data.notes:
            attendance.checkout_approval_notes = data.notes

        self._audit(AuditAction.APPROVE, attendance, "StaffAttendance", user, request,
                    new_values={"checkout_approval_status": "approved"})
        self.db.commit()
        self.db.refresh(attendance)
        return attendance

    def reject_attendance(self, attendance_id: UUID, reason: Optional[str],
                          user: User, request=None) -> StaffAttendance:
        """Reject a pending punch-in. Deactivates the attendance record so staff
        can check in again. Stores rejection reason in approval_notes."""
        attendance = self.att_repo.get(attendance_id)
        if not attendance:
            raise HTTPException(status_code=404, detail="Attendance record not found")
        if user.society_id and str(attendance.society_id) != str(user.society_id):
            raise HTTPException(status_code=403, detail="Cannot reject attendance from another society")
        staff = self.repo.get(attendance.staff_id)
        if staff:
            self._check_dept_access(user, staff.department.value)
        if attendance.is_approved:
            raise HTTPException(status_code=409, detail="Attendance already approved — cannot reject")

        attendance.approval_notes = f"REJECTED by {user.email}: {reason or 'No reason given'}"
        attendance.is_active      = False
        self._audit(AuditAction.UPDATE, attendance, "StaffAttendance", user, request,
                    new_values={"approval_status": "rejected", "reason": reason})
        self.db.commit()
        self.db.refresh(attendance)
        return attendance

    def reject_checkout(self, attendance_id: UUID, reason: Optional[str],
                        user: User, request=None) -> StaffAttendance:
        """Reject a pending punch-out. Clears checkout fields so staff can
        re-check-out with a corrected timestamp."""
        attendance = self.att_repo.get(attendance_id)
        if not attendance:
            raise HTTPException(status_code=404, detail="Attendance record not found")
        if user.society_id and str(attendance.society_id) != str(user.society_id):
            raise HTTPException(status_code=403, detail="Cannot reject attendance from another society")
        staff = self.repo.get(attendance.staff_id)
        if staff:
            self._check_dept_access(user, staff.department.value)
        if not attendance.check_out_time:
            raise HTTPException(status_code=409, detail="No checkout recorded — nothing to reject")
        if attendance.is_checkout_approved:
            raise HTTPException(status_code=409, detail="Checkout already approved — cannot reject")

        attendance.checkout_approval_notes = f"REJECTED by {user.email}: {reason or 'No reason given'}"
        attendance.check_out_time          = None
        attendance.working_hours           = None
        attendance.overtime_hours          = None
        self._audit(AuditAction.UPDATE, attendance, "StaffAttendance", user, request,
                    new_values={"checkout_status": "rejected", "reason": reason})
        self.db.commit()
        self.db.refresh(attendance)
        return attendance

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def create_task(self, data: TaskCreate, assigner: User, request=None) -> StaffTask:
        staff = self._staff_or_404(data.staff_id)
        task = StaffTask(**data.model_dump(), assigned_by=assigner.id)
        self.db.add(task)
        self.db.flush()
        self._audit(AuditAction.CREATE, task, "StaffTask", assigner, request,
                    new_values={"title": data.title, "staff": str(data.staff_id)})
        if staff.user_id:
            self._notify(staff.user_id, "New Task Assigned",
                f"Task: {data.title}. Due: {data.due_date or 'ASAP'}",
                type=NotificationType.ALERT, entity_id=task.id)
        self.db.commit()
        self.db.refresh(task)
        return task

    def update_task_status(self, task_id: UUID, data: TaskStatusUpdate,
                           user: User, request=None) -> StaffTask:
        task = self._task_or_404(task_id)
        allowed = TASK_TRANSITIONS.get(task.status, set())
        if data.status not in allowed:
            raise HTTPException(status_code=409,
                detail=f"Cannot transition task from '{task.status.value}' to '{data.status.value}'")

        prev = task.status
        task.status = data.status
        now = datetime.utcnow()

        if data.status == TaskStatus.ACKNOWLEDGED: task.acknowledged_at = now
        elif data.status == TaskStatus.IN_PROGRESS: task.started_at = now
        elif data.status == TaskStatus.COMPLETED:
            task.completed_at = now
            if data.completion_notes: task.completion_notes = data.completion_notes
        elif data.status == TaskStatus.VERIFIED:
            task.verified_at = now
            task.verified_by = user.id

        self._audit(AuditAction.UPDATE, task, "StaffTask", user, request,
                    old_values={"status": prev.value}, new_values={"status": data.status.value})
        self.db.commit()
        self.db.refresh(task)
        return task

    def add_work_log(self, task_id: UUID, data: WorkLogCreate,
                     user: User, staff_id: UUID) -> StaffWorkLog:
        task  = self._task_or_404(task_id)
        staff = self._staff_or_404(staff_id)
        log = StaffWorkLog(
            society_id=staff.society_id, staff_id=staff_id, task_id=task_id,
            notes=data.notes, photos_url=data.photos_url, logged_at=datetime.utcnow(),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_my_tasks(self, staff_id: UUID, skip=0, limit=50) -> List[StaffTask]:
        return self.task_repo.get_by_staff(staff_id, skip, limit)

    def get_active_tasks(self, staff_id: UUID) -> List[StaffTask]:
        return self.task_repo.get_active_by_staff(staff_id)

    def get_society_tasks(self, society_id: UUID, skip=0, limit=50) -> List[StaffTask]:
        return self.task_repo.get_by_society(society_id, skip, limit)

    # ── Leave ─────────────────────────────────────────────────────────────────

    def apply_leave(self, data: LeaveCreate, staff_id: UUID, user: User) -> StaffLeave:
        role_names = {ur.role.name for ur in user.user_roles if ur.role}
        is_privileged = bool(role_names & _MANAGER_ROLES_SVC) or \
                        bool(role_names & set(_SUPERVISOR_DEPT_ACCESS.keys()))
        if not is_privileged:
            own_staff = self.repo.get_by_user(user.id)
            if not own_staff or str(own_staff.id) != str(staff_id):
                raise HTTPException(status_code=403,
                    detail="Staff can only apply leave for their own record")
        if self.leave_repo.has_conflict(staff_id, data.from_date, data.to_date):
            raise HTTPException(status_code=409,
                detail="A leave request already exists for this date range")
        total = (data.to_date - data.from_date).days + 1
        leave = StaffLeave(**data.model_dump(), staff_id=staff_id, total_days=total)
        return self.leave_repo.create(leave)

    def approve_leave(self, leave_id: UUID, data: LeaveApproveRequest,
                      approver: User, request=None) -> StaffLeave:
        leave = self.leave_repo.get(leave_id)
        if not leave: raise HTTPException(status_code=404, detail="Leave not found")
        if leave.status != LeaveStatus.PENDING:
            raise HTTPException(status_code=409, detail=f"Leave is already {leave.status.value}")
        leave.status      = LeaveStatus.APPROVED
        leave.approved_by = approver.id
        leave.approved_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(leave)
        self._audit(AuditAction.APPROVE, leave, "StaffLeave", approver, request)
        staff = self._staff_or_404(leave.staff_id)
        if staff.user_id:
            self._notify(staff.user_id, "Leave Approved",
                f"Your {leave.leave_type.value} leave from {leave.from_date} to {leave.to_date} has been approved.",
                entity_id=leave.id)
        return leave

    def reject_leave(self, leave_id: UUID, data: LeaveRejectRequest,
                     rejector: User, request=None) -> StaffLeave:
        leave = self.leave_repo.get(leave_id)
        if not leave: raise HTTPException(status_code=404, detail="Leave not found")
        if leave.status != LeaveStatus.PENDING:
            raise HTTPException(status_code=409, detail=f"Leave is already {leave.status.value}")
        leave.status           = LeaveStatus.REJECTED
        leave.rejection_reason = data.reason
        leave.approved_by      = rejector.id
        leave.approved_at      = datetime.utcnow()
        self.db.commit()
        self.db.refresh(leave)
        return leave

    def get_pending_leaves(self, society_id: UUID) -> List[StaffLeave]:
        return self.leave_repo.get_pending(society_id)

    def get_staff_leaves(self, staff_id: UUID, skip=0, limit=50) -> List[StaffLeave]:
        return self.leave_repo.get_by_staff(staff_id, skip, limit)

    def get_staff_leaves_checked(self, staff_id: UUID, skip: int, limit: int,
                                  user: User) -> List[StaffLeave]:
        role_names = {ur.role.name for ur in user.user_roles if ur.role}
        is_privileged = bool(role_names & _MANAGER_ROLES_SVC) or \
                        bool(role_names & set(_SUPERVISOR_DEPT_ACCESS.keys()))
        if not is_privileged:
            own_staff = self.repo.get_by_user(user.id)
            if not own_staff or str(own_staff.id) != str(staff_id):
                raise HTTPException(status_code=403,
                    detail="Staff can only view their own leave records")
        return self.leave_repo.get_by_staff(staff_id, skip, limit)

    # ── Complaint Assignment ───────────────────────────────────────────────────

    def _find_on_duty_staff_user(self, society_id: UUID, department: StaffDepartment) -> Optional[User]:
        """First staff member in the department who is currently checked in
        and not yet checked out today, with a linked login account."""
        today = date.today()
        return (
            self.db.query(User)
            .join(Staff, Staff.user_id == User.id)
            .join(StaffAttendance, StaffAttendance.staff_id == Staff.id)
            .filter(
                Staff.society_id == society_id,
                Staff.department == department,
                Staff.is_active == True,
                User.is_active == True,
                StaffAttendance.attendance_date == today,
                StaffAttendance.check_in_time.isnot(None),
                StaffAttendance.check_out_time.is_(None),
            )
            .order_by(StaffAttendance.check_in_time.asc())
            .first()
        )

    def assign_complaint_to_department(
        self, complaint_id: UUID, department: str, notes: Optional[str], user: User
    ) -> dict:
        from app.modules.complaint.models.complaint import Complaint, ComplaintStatus
        complaint = self.db.query(Complaint).filter(Complaint.id == complaint_id).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")
        try:
            dept_enum = StaffDepartment(department)
        except ValueError:
            valid_depts = {d.value for d in StaffDepartment}
            raise HTTPException(status_code=400, detail=f"department must be one of: {sorted(valid_depts)}")

        on_duty = self._find_on_duty_staff_user(complaint.society_id, dept_enum)

        complaint.assigned_department = department
        complaint.assigned_by = user.id
        complaint.assigned_at = datetime.utcnow()
        if on_duty:
            complaint.assigned_to = on_duty.id
            # Only move OPEN/REOPENED complaints into ASSIGNED — a complaint
            # already IN_PROGRESS/RESOLVED/etc. keeps its status; department
            # tagging + reassignment shouldn't regress a further-along complaint.
            if complaint.status in (ComplaintStatus.OPEN, ComplaintStatus.REOPENED, ComplaintStatus.ASSIGNED):
                complaint.status = ComplaintStatus.ASSIGNED
        if notes:
            complaint.resolution_notes = (complaint.resolution_notes or "") + f"\n[Dept Assignment] {notes}"
        self.db.commit()

        message = (
            f"Complaint assigned to on-duty {department} staff"
            if on_duty else
            f"Complaint tagged to {department} department — no one is currently on duty"
        )
        return {
            "complaint_id": str(complaint_id),
            "department": department,
            "assigned_by": str(user.id),
            "assigned_to": str(on_duty.id) if on_duty else None,
            "message": message,
        }

    def get_complaints_for_department(self, society_id: UUID, department: str) -> list:
        from app.modules.complaint.models.complaint import Complaint
        return self.db.query(Complaint).filter(
            Complaint.society_id == society_id,
            Complaint.assigned_department == department,
            Complaint.is_active == True,
        ).order_by(Complaint.created_at.desc()).all()
