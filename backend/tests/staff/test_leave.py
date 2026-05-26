"""Staff leave workflow tests."""
import pytest
from datetime import date, timedelta
from tests.conftest import make_user, make_society


def _make_staff(db, society_id, code="EMP-LV1"):
    from app.modules.staff.models.staff import Staff, StaffDepartment, StaffStatus
    staff = Staff(
        society_id=society_id, employee_code=code,
        full_name="Leave Tester", mobile="9123456789",
        department=StaffDepartment.HOUSEKEEPING, status=StaffStatus.ACTIVE,
    )
    db.add(staff); db.commit(); db.refresh(staff)
    return staff


def test_leave_application_success(client, db):
    admin   = make_user(db, "adm@leave.com", role="Admin")
    society = make_society(db, "Leave Society")
    staff   = _make_staff(db, society.id)
    today   = date.today()
    r = client.post(f"/api/v1/staff/leaves/{staff.id}", json={
        "society_id": str(society.id),
        "leave_type": "casual",
        "from_date":  str(today + timedelta(days=5)),
        "to_date":    str(today + timedelta(days=7)),
        "reason":     "Personal work",
    }, headers=admin["headers"])
    assert r.status_code in (200, 201)
    assert r.json()["total_days"] == 3
    assert r.json()["status"] == "pending"


def test_overlapping_leave_prevented(client, db):
    admin   = make_user(db, "adm2@leave.com", role="Admin")
    society = make_society(db, "Leave Society 2")
    staff   = _make_staff(db, society.id, "EMP-LV2")
    today   = date.today()
    base    = {"society_id": str(society.id), "leave_type": "sick"}

    # First leave
    client.post(f"/api/v1/staff/leaves/{staff.id}", json={
        **base, "from_date": str(today+timedelta(days=3)),
        "to_date": str(today+timedelta(days=5))
    }, headers=admin["headers"])

    # Overlapping leave
    r2 = client.post(f"/api/v1/staff/leaves/{staff.id}", json={
        **base, "from_date": str(today+timedelta(days=4)),
        "to_date": str(today+timedelta(days=6))
    }, headers=admin["headers"])
    assert r2.status_code == 409


def test_leave_to_before_from(client, db):
    admin   = make_user(db, "adm3@leave.com", role="Admin")
    society = make_society(db, "Leave Society 3")
    staff   = _make_staff(db, society.id, "EMP-LV3")
    today   = date.today()
    r = client.post(f"/api/v1/staff/leaves/{staff.id}", json={
        "society_id": str(society.id), "leave_type": "earned",
        "from_date": str(today+timedelta(days=5)),
        "to_date":   str(today+timedelta(days=3)),
    }, headers=admin["headers"])
    assert r.status_code == 422


def test_leave_approve_reject(client, db):
    admin   = make_user(db, "adm4@leave.com", role="Admin")
    society = make_society(db, "Leave Society 4")
    staff   = _make_staff(db, society.id, "EMP-LV4")
    today   = date.today()

    r = client.post(f"/api/v1/staff/leaves/{staff.id}", json={
        "society_id": str(society.id), "leave_type": "casual",
        "from_date": str(today+timedelta(days=10)),
        "to_date":   str(today+timedelta(days=10)),
    }, headers=admin["headers"])
    leave_id = r.json()["id"]

    # Approve
    r2 = client.post(f"/api/v1/staff/leaves/{leave_id}/approve",
                     json={}, headers=admin["headers"])
    assert r2.status_code == 200
    assert r2.json()["status"] == "approved"

    # Cannot approve again
    r3 = client.post(f"/api/v1/staff/leaves/{leave_id}/approve",
                     json={}, headers=admin["headers"])
    assert r3.status_code == 409
