"""
Workload Analytics — operational visibility for Admin/Committee.
Aggregates staff task, attendance, and leave data for dashboards.
"""
from uuid import UUID
from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.core.dependencies import require_roles, require_admin_committee
from app.modules.staff.models.staff import (
    Staff, StaffTask, StaffAttendance, StaffLeave,
    TaskStatus, AttendanceStatus, LeaveStatus, StaffStatus,
)

router = APIRouter(prefix="/workload", tags=["Workload Analytics"])

admin_or_committee = require_admin_committee


@router.get("/society/{society_id}/summary",
            dependencies=[Depends(admin_or_committee)])
def society_workload_summary(society_id: UUID, db: Session = Depends(get_db)):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    total_staff  = db.query(func.count(Staff.id)).filter(Staff.society_id==society_id, Staff.status==StaffStatus.ACTIVE).scalar()
    present_today = db.query(func.count(StaffAttendance.id)).filter(
        StaffAttendance.society_id==society_id,
        StaffAttendance.attendance_date==today,
        StaffAttendance.status==AttendanceStatus.PRESENT,
    ).scalar()
    on_leave_today = db.query(func.count(StaffLeave.id)).filter(
        StaffLeave.society_id==society_id,
        StaffLeave.status==LeaveStatus.APPROVED,
        StaffLeave.from_date<=today,
        StaffLeave.to_date>=today,
    ).scalar()
    pending_tasks = db.query(func.count(StaffTask.id)).filter(
        StaffTask.society_id==society_id,
        StaffTask.status.in_([TaskStatus.ASSIGNED, TaskStatus.ACKNOWLEDGED]),
    ).scalar()
    in_progress_tasks = db.query(func.count(StaffTask.id)).filter(
        StaffTask.society_id==society_id,
        StaffTask.status==TaskStatus.IN_PROGRESS,
    ).scalar()
    completed_this_week = db.query(func.count(StaffTask.id)).filter(
        StaffTask.society_id==society_id,
        StaffTask.status.in_([TaskStatus.COMPLETED, TaskStatus.VERIFIED]),
        StaffTask.completed_at>=week_start,
    ).scalar()
    pending_leaves = db.query(func.count(StaffLeave.id)).filter(
        StaffLeave.society_id==society_id,
        StaffLeave.status==LeaveStatus.PENDING,
    ).scalar()

    return {
        "date": str(today),
        "staff": {
            "total_active": total_staff,
            "present_today": present_today,
            "absent_today": (total_staff or 0) - (present_today or 0) - (on_leave_today or 0),
            "on_leave_today": on_leave_today,
        },
        "tasks": {
            "pending": pending_tasks,
            "in_progress": in_progress_tasks,
            "completed_this_week": completed_this_week,
        },
        "leaves": {
            "pending_approvals": pending_leaves,
        },
    }


@router.get("/staff/{staff_id}/summary",
            dependencies=[Depends(admin_or_committee)])
def staff_workload_summary(staff_id: UUID, db: Session = Depends(get_db)):
    today      = date.today()
    month_start = today.replace(day=1)

    active_tasks = db.query(func.count(StaffTask.id)).filter(
        StaffTask.staff_id==staff_id,
        StaffTask.status.in_([TaskStatus.ASSIGNED, TaskStatus.ACKNOWLEDGED, TaskStatus.IN_PROGRESS]),
    ).scalar()
    completed_month = db.query(func.count(StaffTask.id)).filter(
        StaffTask.staff_id==staff_id,
        StaffTask.status.in_([TaskStatus.COMPLETED, TaskStatus.VERIFIED]),
        StaffTask.completed_at>=month_start,
    ).scalar()
    attendance_month = db.query(func.count(StaffAttendance.id)).filter(
        StaffAttendance.staff_id==staff_id,
        StaffAttendance.attendance_date>=month_start,
        StaffAttendance.status==AttendanceStatus.PRESENT,
    ).scalar()
    overtime_hours = db.query(func.sum(StaffAttendance.overtime_hours)).filter(
        StaffAttendance.staff_id==staff_id,
        StaffAttendance.attendance_date>=month_start,
    ).scalar() or 0.0

    return {
        "staff_id":   str(staff_id),
        "month":      str(month_start),
        "tasks": {
            "active":             active_tasks,
            "completed_this_month": completed_month,
        },
        "attendance": {
            "present_days_this_month": attendance_month,
            "overtime_hours_this_month": round(float(overtime_hours), 2),
        },
    }
