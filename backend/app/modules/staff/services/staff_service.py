from datetime import datetime, date
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.modules.staff.models.staff import (
    Staff, StaffDesignation, StaffShift, DutyAssignment,
    StaffAttendance, StaffTask, StaffLeave, StaffWorkLog,
    AttendanceStatus, TaskStatus, LeaveStatus, TASK_TRANSITIONS,
)
from app.modules.staff.schemas.staff import (
    StaffCreate, StaffUpdate, DesignationCreate, ShiftCreate,
    DutyCreate, DutyVerifyRequest, AttendanceCheckIn, AttendanceCheckOut,
    AttendanceManualEntry, AttendanceApprovalRequest, TaskCreate, TaskStatusUpdate, WorkLogCreate,
    LeaveCreate, LeaveApproveRequest, LeaveRejectRequest,
)
from app.modules.staff.repositories.staff_repo import (
    StaffRepository, StaffDesignationRepo, StaffShiftRepo,
    DutyRepository, AttendanceRepository, TaskRepository, LeaveRepository,
)
from app.models.user import User
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel


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
        self.repo.create(staff)
        self._audit(AuditAction.CREATE, staff, "Staff", user, request,
                    new_values={"employee_code": code, "name": data.full_name, "dept": data.department.value})
        return staff

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

    def list_staff(self, society_id: UUID, skip=0, limit=50) -> List[Staff]:
        return self.repo.get_by_society(society_id, skip, limit)

    def list_by_department(self, society_id: UUID, dept) -> List[Staff]:
        return self.repo.get_by_department(society_id, dept)

    # ── Duty Assignment ───────────────────────────────────────────────────────

    def assign_duty(self, data: DutyCreate, assigner: User, request=None) -> DutyAssignment:
        staff = self._staff_or_404(data.staff_id)
        duty = DutyAssignment(**data.model_dump(), assigned_by=assigner.id)
        self.db.add(duty)
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
        duty.is_completed = True
        duty.completed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(duty)
        return duty

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
        today = date.today()
        existing = self.att_repo.get_today(staff_id, today)
        if existing:
            raise HTTPException(status_code=409,
                detail=f"Attendance already marked for today (status: {existing.status.value})")
        att = StaffAttendance(
            society_id=self._staff_or_404(staff_id).society_id,
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

    def get_attendance(self, staff_id: UUID, skip=0, limit=50) -> List[StaffAttendance]:
        return self.att_repo.get_by_staff(staff_id, skip, limit)

    def get_daily_attendance(self, society_id: UUID, att_date: date) -> List[StaffAttendance]:
        return self.att_repo.get_by_society_date(society_id, att_date)

    def get_pending_attendance(self, society_id: UUID) -> List[StaffAttendance]:
        return self.att_repo.get_pending(society_id)

    def approve_attendance(self, attendance_id: UUID, data: AttendanceApprovalRequest,
                           user: User, request=None) -> StaffAttendance:
        attendance = self.att_repo.get(attendance_id)
        if not attendance:
            raise HTTPException(status_code=404, detail="Attendance record not found")
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
