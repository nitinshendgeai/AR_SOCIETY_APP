from typing import List, Optional
from uuid import UUID
from datetime import date
from sqlalchemy.orm import Session
from app.modules.staff.models.staff import (
    Staff, StaffDesignation, StaffShift, DutyAssignment,
    StaffAttendance, StaffTask, StaffLeave, StaffWorkLog,
    AttendanceStatus, TaskStatus, LeaveStatus, StaffDepartment,
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
        count = self.db.query(Staff).filter(Staff.society_id==sid).count()
        return f"EMP-{str(count+1).zfill(4)}"

    def get_by_user(self, user_id: UUID) -> Optional[Staff]:
        return self.db.query(Staff).filter(Staff.user_id==user_id, Staff.is_active==True).first()


class DutyRepository(BaseRepository[DutyAssignment]):
    def __init__(self, db): super().__init__(DutyAssignment, db)

    def get_by_staff(self, staff_id: UUID, duty_date: Optional[date]=None) -> List[DutyAssignment]:
        q = self.db.query(DutyAssignment).filter(DutyAssignment.staff_id==staff_id, DutyAssignment.is_active==True)
        if duty_date: q = q.filter(DutyAssignment.duty_date==duty_date)
        return q.order_by(DutyAssignment.duty_date.desc()).all()

    def get_by_society_date(self, sid: UUID, duty_date: date) -> List[DutyAssignment]:
        return self.db.query(DutyAssignment).filter(
            DutyAssignment.society_id==sid, DutyAssignment.duty_date==duty_date, DutyAssignment.is_active==True
        ).all()


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

    def get_by_society_date(self, sid: UUID, att_date: date) -> List[StaffAttendance]:
        return self.db.query(StaffAttendance).filter(
            StaffAttendance.society_id==sid, StaffAttendance.attendance_date==att_date
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

    def has_conflict(self, staff_id: UUID, from_date: date, to_date: date) -> bool:
        return self.db.query(StaffLeave).filter(
            StaffLeave.staff_id==staff_id,
            StaffLeave.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
            StaffLeave.from_date<=to_date,
            StaffLeave.to_date>=from_date,
            StaffLeave.is_active==True,
        ).first() is not None
