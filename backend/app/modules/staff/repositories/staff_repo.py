from typing import List, Optional
from uuid import UUID
from datetime import date, datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.modules.staff.models.staff import (
    Staff, StaffDesignation, StaffShift, DutyAssignment,
    StaffAttendance, StaffTask, StaffLeave, StaffWorkLog,
    AttendanceStatus, TaskStatus, LeaveStatus, StaffDepartment,
    ChecklistTemplate, ChecklistTemplateItem, DutyChecklistItem,
)
from app.repositories.base import BaseRepository


class StaffDesignationRepo(BaseRepository[StaffDesignation]):
    def __init__(self, db): super().__init__(StaffDesignation, db)
    def get_by_society(self, sid: UUID) -> List[StaffDesignation]:
        return self.db.query(StaffDesignation).filter(StaffDesignation.society_id==sid, StaffDesignation.is_active==True).all()


class StaffShiftRepo(BaseRepository[StaffShift]):
    def __init__(self, db): super().__init__(StaffShift, db)
    def get_by_society(self, sid: UUID) -> List[StaffShift]:
        return self.db.query(StaffShift).filter(StaffShift.society_id==sid, StaffShift.is_active==True).all()


class StaffRepository(BaseRepository[Staff]):
    def __init__(self, db): super().__init__(Staff, db)

    def get_by_society(self, sid: UUID, skip=0, limit=50) -> List[Staff]:
        return self.db.query(Staff).filter(Staff.society_id==sid, Staff.is_active==True)\
            .offset(skip).limit(limit).all()

    def get_by_department(self, sid: UUID, dept: StaffDepartment) -> List[Staff]:
        return self.db.query(Staff).filter(Staff.society_id==sid, Staff.department==dept, Staff.is_active==True).all()

    def next_employee_code(self, sid: UUID) -> str:
        """Codes are unique platform-wide: one more than the highest in use, so
        they can't repeat after a gap."""
        highest = 0
        for (code,) in self.db.query(Staff.employee_code):
            digits = code.rsplit("-", 1)[-1]
            if digits.isdigit():
                highest = max(highest, int(digits))
        return f"EMP-{str(highest+1).zfill(4)}"

    def get_by_user(self, user_id: UUID) -> Optional[Staff]:
        return self.db.query(Staff).filter(Staff.user_id==user_id, Staff.is_active==True).first()


class DutyRepository(BaseRepository[DutyAssignment]):
    def __init__(self, db): super().__init__(DutyAssignment, db)

    def get_by_staff(self, staff_id: UUID, duty_date: Optional[date]=None,
                     from_date: Optional[date]=None, to_date: Optional[date]=None) -> List[DutyAssignment]:
        q = self.db.query(DutyAssignment).filter(DutyAssignment.staff_id==staff_id, DutyAssignment.is_active==True)
        if duty_date: q = q.filter(DutyAssignment.duty_date==duty_date)
        if from_date: q = q.filter(DutyAssignment.duty_date>=from_date)
        if to_date: q = q.filter(DutyAssignment.duty_date<=to_date)
        return q.order_by(DutyAssignment.duty_date.desc()).all()

    def exists(self, staff_id: UUID, duty_date: date, duty_name: str) -> bool:
        return self.db.query(DutyAssignment.id).filter(
            DutyAssignment.staff_id==staff_id, DutyAssignment.duty_date==duty_date,
            func.lower(DutyAssignment.duty_name)==duty_name.lower(), DutyAssignment.is_active==True,
        ).first() is not None

    def for_sheet(self, sid: UUID, from_date: date, to_date: date, staff_id: Optional[UUID]=None,
                  department: Optional[StaffDepartment]=None) -> List[DutyAssignment]:
        """Duties of a society across a few days, optionally one staff member or department."""
        q = self.db.query(DutyAssignment).join(Staff, Staff.id==DutyAssignment.staff_id).filter(
            DutyAssignment.society_id==sid, DutyAssignment.is_active==True,
            DutyAssignment.duty_date>=from_date, DutyAssignment.duty_date<=to_date)
        if staff_id: q = q.filter(DutyAssignment.staff_id==staff_id)
        if department: q = q.filter(Staff.department==department)
        return q.order_by(DutyAssignment.duty_date, Staff.full_name,
                          DutyAssignment.start_time, DutyAssignment.duty_name).all()

    def get_by_society_date(self, sid: UUID, duty_date: date) -> List[DutyAssignment]:
        return self.db.query(DutyAssignment).filter(
            DutyAssignment.society_id==sid, DutyAssignment.duty_date==duty_date, DutyAssignment.is_active==True
        ).all()


class ChecklistTemplateRepo(BaseRepository[ChecklistTemplate]):
    def __init__(self, db): super().__init__(ChecklistTemplate, db)

    def get_by_society(self, sid: UUID, department: Optional[StaffDepartment] = None) -> List[ChecklistTemplate]:
        q = self.db.query(ChecklistTemplate).filter(
            ChecklistTemplate.society_id == sid, ChecklistTemplate.is_active == True)
        if department:
            q = q.filter(ChecklistTemplate.department == department)
        return q.order_by(ChecklistTemplate.name).all()


class AttendanceRepository(BaseRepository[StaffAttendance]):
    def __init__(self, db): super().__init__(StaffAttendance, db)

    def get_today(self, staff_id: UUID, today: date) -> Optional[StaffAttendance]:
        return self.db.query(StaffAttendance).filter(
            StaffAttendance.staff_id==staff_id,
            StaffAttendance.attendance_date==today,
            StaffAttendance.is_active==True,
        ).first()

    def get_by_staff(self, staff_id: UUID, skip=0, limit=50) -> List[StaffAttendance]:
        return self.db.query(StaffAttendance).filter(
            StaffAttendance.staff_id==staff_id, StaffAttendance.is_active==True
        ).order_by(StaffAttendance.attendance_date.desc()).offset(skip).limit(limit).all()

    def get_open(self, staff_id: UUID, since: datetime) -> Optional[StaffAttendance]:
        """The punch-in still waiting for its punch-out (a night shift's runs into the next day)."""
        return self.db.query(StaffAttendance).filter(
            StaffAttendance.staff_id==staff_id, StaffAttendance.is_active==True,
            StaffAttendance.check_in_time.isnot(None), StaffAttendance.check_out_time.is_(None),
            StaffAttendance.check_in_time>=since,
        ).order_by(StaffAttendance.check_in_time.desc()).first()

    def get_by_society_date(self, sid: UUID, att_date: date) -> List[StaffAttendance]:
        # A rejected punch is deactivated; it isn't attendance.
        return self.db.query(StaffAttendance).filter(
            StaffAttendance.society_id==sid, StaffAttendance.attendance_date==att_date,
            StaffAttendance.is_active==True,
        ).all()

    def get_pending(self, sid: UUID) -> List[StaffAttendance]:
        return self.db.query(StaffAttendance).filter(
            StaffAttendance.society_id==sid,
            StaffAttendance.is_active==True,
            StaffAttendance.is_approved==False,
        ).order_by(StaffAttendance.attendance_date.desc()).all()

    def get_pending_by_dept(self, sid: UUID, department: Optional[str] = None) -> List[StaffAttendance]:
        q = self.db.query(StaffAttendance).join(
            Staff, StaffAttendance.staff_id == Staff.id
        ).filter(
            StaffAttendance.society_id == sid,
            StaffAttendance.is_active == True,
            StaffAttendance.is_approved == False,
        )
        if department:
            q = q.filter(Staff.department == department)
        return q.order_by(StaffAttendance.attendance_date.desc()).all()

    def get_pending_checkout(self, sid: UUID, department: Optional[str] = None) -> List[StaffAttendance]:
        q = self.db.query(StaffAttendance).join(
            Staff, StaffAttendance.staff_id == Staff.id
        ).filter(
            StaffAttendance.society_id == sid,
            StaffAttendance.is_active == True,
            StaffAttendance.check_out_time.isnot(None),
            StaffAttendance.is_checkout_approved == False,
        )
        if department:
            q = q.filter(Staff.department == department)
        return q.order_by(StaffAttendance.attendance_date.desc()).all()


class TaskRepository(BaseRepository[StaffTask]):
    def __init__(self, db): super().__init__(StaffTask, db)

    def get_by_staff(self, staff_id: UUID, skip=0, limit=50) -> List[StaffTask]:
        return self.db.query(StaffTask).filter(
            StaffTask.staff_id==staff_id, StaffTask.is_active==True
        ).order_by(StaffTask.created_at.desc()).offset(skip).limit(limit).all()

    def get_active_by_staff(self, staff_id: UUID) -> List[StaffTask]:
        return self.db.query(StaffTask).filter(
            StaffTask.staff_id==staff_id,
            StaffTask.status.in_([TaskStatus.ASSIGNED, TaskStatus.ACKNOWLEDGED, TaskStatus.IN_PROGRESS]),
            StaffTask.is_active==True,
        ).all()

    def get_by_society(self, sid: UUID, skip=0, limit=50) -> List[StaffTask]:
        return self.db.query(StaffTask).filter(StaffTask.society_id==sid, StaffTask.is_active==True)\
            .order_by(StaffTask.created_at.desc()).offset(skip).limit(limit).all()


class LeaveRepository(BaseRepository[StaffLeave]):
    def __init__(self, db): super().__init__(StaffLeave, db)

    def get_by_staff(self, staff_id: UUID, skip=0, limit=50) -> List[StaffLeave]:
        return self.db.query(StaffLeave).filter(StaffLeave.staff_id==staff_id, StaffLeave.is_active==True)\
            .order_by(StaffLeave.from_date.desc()).offset(skip).limit(limit).all()

    def get_pending(self, sid: UUID) -> List[StaffLeave]:
        return self.db.query(StaffLeave).filter(
            StaffLeave.society_id==sid, StaffLeave.status==LeaveStatus.PENDING, StaffLeave.is_active==True
        ).all()

    def approved_on(self, staff_id: UUID, from_date: date, to_date: date) -> List[StaffLeave]:
        return self.db.query(StaffLeave).filter(
            StaffLeave.staff_id==staff_id, StaffLeave.status==LeaveStatus.APPROVED,
            StaffLeave.from_date<=to_date, StaffLeave.to_date>=from_date, StaffLeave.is_active==True,
        ).all()

    def has_conflict(self, staff_id: UUID, from_date: date, to_date: date) -> bool:
        return self.db.query(StaffLeave).filter(
            StaffLeave.staff_id==staff_id,
            StaffLeave.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
            StaffLeave.from_date<=to_date,
            StaffLeave.to_date>=from_date,
            StaffLeave.is_active==True,
        ).first() is not None
