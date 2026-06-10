from typing import List, Optional
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal

from app.db.session import get_db
from app.core.dependencies import (
    get_current_user, require_roles,
    require_admin_committee, require_supervisor_above, require_admin,
)
from app.models.user import User
from app.modules.staff.services.payroll_service import PayrollService
from app.modules.staff.models.payroll_readiness import (
    AttendanceCorrectionStatus, PayrollCycle,
)
from app.schemas.common import OrmBase, TimestampSchema
from typing import Optional

router = APIRouter(prefix="/payroll", tags=["Payroll Readiness"])

admin_only         = require_admin
committee_or_admin = require_admin_committee
supervisor_above   = require_supervisor_above


# ── Salary Structure ──────────────────────────────────────────────────────────
class SalaryStructureCreate(OrmBase):
    society_id: UUID; staff_id: UUID; effective_from: date
    payroll_cycle: PayrollCycle = PayrollCycle.MONTHLY
    basic_salary: Decimal; hra: Decimal = Decimal(0)
    conveyance: Decimal = Decimal(0); medical: Decimal = Decimal(0)
    special_allowance: Decimal = Decimal(0); shift_allowance: Decimal = Decimal(0)
    pf_employee_pct: float = 12.0; esi_employee_pct: float = 0.75
    tds_monthly: Decimal = Decimal(0)
    overtime_rate_per_hour: Optional[Decimal] = None
    working_days_per_month: int = 26; paid_leaves_per_year: int = 12


class SalaryStructureOut(TimestampSchema):
    society_id: UUID; staff_id: UUID; effective_from: date
    effective_to: Optional[date]; payroll_cycle: PayrollCycle
    basic_salary: Decimal; hra: Decimal; conveyance: Decimal
    medical: Decimal; special_allowance: Decimal; shift_allowance: Decimal
    pf_employee_pct: float; esi_employee_pct: float; tds_monthly: Decimal
    working_days_per_month: int


@router.post("/salary-structure", response_model=SalaryStructureOut, status_code=201,
             dependencies=[Depends(admin_only)])
def set_salary_structure(data: SalaryStructureCreate, db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    return PayrollService(db).set_salary_structure(data.model_dump(), user)


@router.get("/salary-structure/{staff_id}", response_model=Optional[SalaryStructureOut],
            dependencies=[Depends(committee_or_admin)])
def get_salary_structure(staff_id: UUID, db: Session = Depends(get_db)):
    result = PayrollService(db).get_salary_structure(staff_id)
    if not result: raise HTTPException(status_code=404, detail="No salary structure found")
    return result


# ── Attendance Correction ─────────────────────────────────────────────────────
class CorrectionRequest(OrmBase):
    society_id: UUID; staff_id: UUID; attendance_id: UUID
    correction_date: date; reason: str
    requested_status: Optional[str]  = None
    requested_check_in: Optional[str]  = None
    requested_check_out: Optional[str] = None


class CorrectionOut(TimestampSchema):
    society_id: UUID; staff_id: UUID; correction_date: date
    requested_status: Optional[str]; reason: str
    status: AttendanceCorrectionStatus; rejection_reason: Optional[str]


class RejectCorrectionRequest(OrmBase):
    reason: str


@router.post("/attendance-correction", response_model=CorrectionOut, status_code=201)
def request_correction(data: CorrectionRequest, db: Session = Depends(get_db),
                        user: User = Depends(supervisor_above)):
    return PayrollService(db).request_correction(data.model_dump(), user)


@router.post("/attendance-correction/{correction_id}/approve", response_model=CorrectionOut)
def approve_correction(correction_id: UUID, db: Session = Depends(get_db),
                        user: User = Depends(committee_or_admin)):
    return PayrollService(db).approve_correction(correction_id, user)


@router.post("/attendance-correction/{correction_id}/reject", response_model=CorrectionOut)
def reject_correction(correction_id: UUID, data: RejectCorrectionRequest,
                       db: Session = Depends(get_db),
                       user: User = Depends(committee_or_admin)):
    return PayrollService(db).reject_correction(correction_id, data.reason, user)


@router.get("/attendance-correction/society/{society_id}", response_model=List[CorrectionOut],
            dependencies=[Depends(committee_or_admin)])
def list_corrections(society_id: UUID, status: Optional[str] = None,
                     db: Session = Depends(get_db)):
    return PayrollService(db).list_corrections(society_id, status)


# ── Monthly Attendance Summary ────────────────────────────────────────────────
class MonthlySummaryOut(TimestampSchema):
    society_id: UUID; staff_id: UUID; year: int; month: int
    present_days: int; absent_days: int; half_day_count: int
    leave_days: int; overtime_days: int
    total_working_hours: float; total_overtime_hours: float
    late_arrivals: int; is_finalized: bool


@router.post("/monthly-summary/{society_id}/{staff_id}/{year}/{month}",
             response_model=MonthlySummaryOut, dependencies=[Depends(committee_or_admin)])
def aggregate_monthly(society_id: UUID, staff_id: UUID, year: int, month: int,
                       db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    return PayrollService(db).aggregate_monthly_attendance(society_id, staff_id, year, month, user)


@router.post("/monthly-summary/{summary_id}/finalize",
             response_model=MonthlySummaryOut, dependencies=[Depends(admin_only)])
def finalize_monthly(summary_id: UUID, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    return PayrollService(db).finalize_monthly_attendance(summary_id, user)


@router.get("/monthly-summary/{staff_id}/{year}/{month}",
            response_model=Optional[MonthlySummaryOut],
            dependencies=[Depends(committee_or_admin)])
def get_monthly_summary(staff_id: UUID, year: int, month: int, db: Session = Depends(get_db)):
    result = PayrollService(db).get_monthly_summary(staff_id, year, month)
    if not result: raise HTTPException(status_code=404, detail="Summary not found")
    return result
