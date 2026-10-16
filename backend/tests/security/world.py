"""Shared two-society world for the Phase 1 security tests.

Society A and society B each have an admin, a manager, a resident and a wing/flat; B also has staff, a salary
structure, attendance and a pending correction, so cross-society calls have real records to (fail to) reach.
Platform admins are what the app creates with `create_platform_admin`: no society and `is_superadmin`.
"""
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from tests.conftest import link_staff_login, make_flat, make_society, make_user, make_wing

API = "/api/v1"


def scoped_user(db, email, role, society):
    """A login of `society` with the given role (the shape every real login has)."""
    u = make_user(db, email, role=role)
    u["user"].society_id = society.id
    db.commit()
    return u


def platform_admin(db, email="platform@duxos.test"):
    u = make_user(db, email, role="Platform Admin")
    u["user"].is_superadmin = True
    db.commit()
    return u


def make_staff(db, society_id, name, department="security"):
    from app.modules.staff.models.staff import Staff, StaffDepartment, StaffStatus
    staff = Staff(
        society_id=society_id, employee_code=f"EMP-{abs(hash((name, str(society_id)))) % 1000000}",
        full_name=name, mobile=f"9{abs(hash((name, 'm'))) % 999999999:09d}",
        department=StaffDepartment(department), status=StaffStatus.ACTIVE,
    )
    db.add(staff); db.commit(); db.refresh(staff)
    return staff


def make_attendance(db, society_id, staff_id):
    from app.modules.staff.models.staff import AttendanceStatus, StaffAttendance
    att = StaffAttendance(
        society_id=society_id, staff_id=staff_id, attendance_date=date.today(), status=AttendanceStatus.PRESENT,
        check_in_time=datetime.utcnow() - timedelta(hours=8), check_out_time=datetime.utcnow(),
    )
    db.add(att); db.commit(); db.refresh(att)
    return att


def correction_body(society_id, staff_id, attendance_id):
    return {
        "society_id": str(society_id), "staff_id": str(staff_id), "attendance_id": str(attendance_id),
        "correction_date": str(date.today()), "requested_status": "half_day",
        "reason": "Forgot to punch out on time, actually left early.",
    }


def salary_body(society_id, staff_id, basic=15000):
    return {"society_id": str(society_id), "staff_id": str(staff_id), "effective_from": "2026-01-01",
            "basic_salary": basic}


@pytest.fixture
def world(client, db):
    A = make_society(db, "Security Society A")
    B = make_society(db, "Security Society B")
    wing_a, wing_b = make_wing(db, A.id, "A Wing"), make_wing(db, B.id, "B Wing")
    flat_a, flat_b = make_flat(db, wing_a.id, "A-101"), make_flat(db, wing_b.id, "B-101")

    w = SimpleNamespace(A=A, B=B, flat_a=flat_a, flat_b=flat_b)
    w.admin_a = scoped_user(db, "admin@a.sec", "Society Admin", A)
    w.manager_a = scoped_user(db, "manager@a.sec", "Manager", A)
    w.resident_a = scoped_user(db, "resident@a.sec", "Resident", A)
    w.security_a = scoped_user(db, "security@a.sec", "Security Staff", A)
    w.supervisor_a = scoped_user(db, "super@a.sec", "Housekeeping Supervisor", A)
    w.committee_a = scoped_user(db, "committee@a.sec", "Committee Member", A)
    w.admin_b = scoped_user(db, "admin@b.sec", "Society Admin", B)
    w.manager_b = scoped_user(db, "manager@b.sec", "Manager", B)
    w.resident_b = scoped_user(db, "resident@b.sec", "Resident", B)
    w.platform = platform_admin(db)

    # society A: a guard with a login, and a colleague
    w.staff_a = make_staff(db, A.id, "Guard A One")
    w.staff_a2 = make_staff(db, A.id, "Guard A Two")
    link_staff_login(db, w.staff_a.id, w.security_a)
    w.att_a = make_attendance(db, A.id, w.staff_a.id)
    w.att_a2 = make_attendance(db, A.id, w.staff_a2.id)

    # society B: a guard with a login, a salary, attendance and a pending correction
    w.staff_b = make_staff(db, B.id, "Guard B One")
    w.staff_b_login = scoped_user(db, "guard@b.sec", "Security Staff", B)
    link_staff_login(db, w.staff_b.id, w.staff_b_login)
    w.att_b = make_attendance(db, B.id, w.staff_b.id)
    h = w.admin_b["headers"]
    assert client.post(f"{API}/payroll/salary-structure", json=salary_body(B.id, w.staff_b.id), headers=h).status_code == 201
    r = client.post(f"{API}/payroll/attendance-correction", json=correction_body(B.id, w.staff_b.id, w.att_b.id), headers=h)
    assert r.status_code == 201, r.text
    w.correction_b = r.json()["id"]
    r = client.post(f"{API}/payroll/monthly-summary/{B.id}/{w.staff_b.id}/2026/9", headers=h)
    assert r.status_code == 200, r.text
    w.summary_b = r.json()["id"]
    return w
