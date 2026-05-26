"""Staff attendance workflow tests — edge cases and validation."""
import pytest
from datetime import date
from tests.conftest import make_user, make_society


def _make_staff(db, society_id, name="Guard One"):
    from app.modules.staff.models.staff import Staff, StaffDepartment, StaffStatus
    staff = Staff(
        society_id=society_id, employee_code=f"EMP-{name[:3].upper()}",
        full_name=name, mobile=f"9{hash(name) % 999999999:09d}",
        department=StaffDepartment.SECURITY, status=StaffStatus.ACTIVE,
    )
    db.add(staff); db.commit(); db.refresh(staff)
    return staff


def test_checkin_success(client, db):
    admin   = make_user(db, "adm@att.com", role="Admin")
    society = make_society(db, "Attendance Society")
    staff   = _make_staff(db, society.id)
    r = client.post(f"/api/v1/staff/attendance/{staff.id}/checkin",
                    json={"notes": "On time"}, headers=admin["headers"])
    assert r.status_code == 200
    assert r.json()["status"] == "present"


def test_duplicate_checkin_prevented(client, db):
    admin   = make_user(db, "adm2@att.com", role="Admin")
    society = make_society(db, "Attendance Society 2")
    staff   = _make_staff(db, society.id, "Guard Two")
    client.post(f"/api/v1/staff/attendance/{staff.id}/checkin",
                json={}, headers=admin["headers"])
    r2 = client.post(f"/api/v1/staff/attendance/{staff.id}/checkin",
                     json={}, headers=admin["headers"])
    assert r2.status_code == 409
    assert "already" in r2.json()["detail"].lower()


def test_checkout_without_checkin_fails(client, db):
    admin   = make_user(db, "adm3@att.com", role="Admin")
    society = make_society(db, "Attendance Society 3")
    staff   = _make_staff(db, society.id, "Guard Three")
    r = client.post(f"/api/v1/staff/attendance/{staff.id}/checkout",
                    json={}, headers=admin["headers"])
    assert r.status_code == 404


def test_checkin_checkout_working_hours(client, db):
    """After checkout, working_hours should be computed."""
    from app.modules.staff.models.staff import StaffAttendance, AttendanceStatus
    from datetime import datetime, timedelta
    admin   = make_user(db, "adm4@att.com", role="Admin")
    society = make_society(db, "Attendance Society 4")
    staff   = _make_staff(db, society.id, "Guard Four")

    # Manual attendance insertion to simulate 8h shift
    att = StaffAttendance(
        society_id=society.id, staff_id=staff.id,
        attendance_date=date.today(), status=AttendanceStatus.PRESENT,
        check_in_time=datetime.utcnow() - timedelta(hours=8),
    )
    db.add(att); db.commit()

    r = client.post(f"/api/v1/staff/attendance/{staff.id}/checkout",
                    json={}, headers=admin["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["working_hours"] is not None
    assert float(data["working_hours"]) >= 7.9  # ~8 hours


def test_duplicate_checkout_prevented(client, db):
    from app.modules.staff.models.staff import StaffAttendance, AttendanceStatus
    from datetime import datetime, timedelta
    admin   = make_user(db, "adm5@att.com", role="Admin")
    society = make_society(db, "Attendance Society 5")
    staff   = _make_staff(db, society.id, "Guard Five")

    att = StaffAttendance(
        society_id=society.id, staff_id=staff.id,
        attendance_date=date.today(), status=AttendanceStatus.PRESENT,
        check_in_time=datetime.utcnow() - timedelta(hours=9),
        check_out_time=datetime.utcnow(),  # already checked out
    )
    db.add(att); db.commit()

    r = client.post(f"/api/v1/staff/attendance/{staff.id}/checkout",
                    json={}, headers=admin["headers"])
    assert r.status_code == 409
