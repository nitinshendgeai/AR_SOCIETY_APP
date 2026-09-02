"""Payroll readiness — attendance correction workflow tests."""
from datetime import date, datetime, timedelta
from tests.conftest import make_user, make_society


def _make_staff(db, society_id, name="Guard One"):
    from app.modules.staff.models.staff import Staff, StaffDepartment, StaffStatus
    staff = Staff(
        society_id=society_id, employee_code=f"EMP-{abs(hash(name)) % 100000}",
        full_name=name, mobile=f"9{hash(name) % 999999999:09d}",
        department=StaffDepartment.SECURITY, status=StaffStatus.ACTIVE,
    )
    db.add(staff); db.commit(); db.refresh(staff)
    return staff


def _make_attendance(db, society_id, staff_id, status="present"):
    from app.modules.staff.models.staff import StaffAttendance, AttendanceStatus
    att = StaffAttendance(
        society_id=society_id, staff_id=staff_id,
        attendance_date=date.today(), status=AttendanceStatus(status),
        check_in_time=datetime.utcnow() - timedelta(hours=8),
        check_out_time=datetime.utcnow(),
    )
    db.add(att); db.commit(); db.refresh(att)
    return att


def _correction_payload(society_id, staff_id, attendance_id, requested_status="half_day"):
    return {
        "society_id": str(society_id),
        "staff_id": str(staff_id),
        "attendance_id": str(attendance_id),
        "correction_date": str(date.today()),
        "reason": "Forgot to punch out on time, actually left early.",
        "requested_status": requested_status,
    }


def test_request_correction_success(client, db):
    admin   = make_user(db, "adm@payroll.com", role="Society Admin")
    society = make_society(db, "Payroll Society 1")
    staff   = _make_staff(db, society.id)
    att     = _make_attendance(db, society.id, staff.id)

    r = client.post("/api/v1/payroll/attendance-correction",
                    json=_correction_payload(society.id, staff.id, att.id),
                    headers=admin["headers"])
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "pending"
    assert data["original_status"] == "present"
    assert data["requested_status"] == "half_day"
    assert data["staff_name"] == staff.full_name


def test_request_correction_mismatched_staff_rejected(client, db):
    admin    = make_user(db, "adm2@payroll.com", role="Society Admin")
    society  = make_society(db, "Payroll Society 2")
    staff1   = _make_staff(db, society.id, "Guard A")
    staff2   = _make_staff(db, society.id, "Guard B")
    att      = _make_attendance(db, society.id, staff1.id)

    r = client.post("/api/v1/payroll/attendance-correction",
                    json=_correction_payload(society.id, staff2.id, att.id),
                    headers=admin["headers"])
    assert r.status_code == 400


def test_resident_cannot_request_correction(client, db):
    resident = make_user(db, "res@payroll.com", role="Resident")
    society  = make_society(db, "Payroll Society 3")
    staff    = _make_staff(db, society.id, "Guard C")
    att      = _make_attendance(db, society.id, staff.id)

    r = client.post("/api/v1/payroll/attendance-correction",
                    json=_correction_payload(society.id, staff.id, att.id),
                    headers=resident["headers"])
    assert r.status_code == 403


def test_approve_correction_applies_to_attendance(client, db):
    admin   = make_user(db, "adm3@payroll.com", role="Society Admin")
    society = make_society(db, "Payroll Society 4")
    staff   = _make_staff(db, society.id, "Guard D")
    att     = _make_attendance(db, society.id, staff.id)

    r = client.post("/api/v1/payroll/attendance-correction",
                    json=_correction_payload(society.id, staff.id, att.id),
                    headers=admin["headers"])
    correction_id = r.json()["id"]

    r2 = client.post(f"/api/v1/payroll/attendance-correction/{correction_id}/approve",
                     headers=admin["headers"])
    assert r2.status_code == 200
    assert r2.json()["status"] == "approved"

    from app.modules.staff.models.staff import StaffAttendance
    db.refresh(att)
    updated = db.query(StaffAttendance).filter(StaffAttendance.id == att.id).first()
    assert updated.status.value == "half_day"
    assert updated.is_manual_entry is True


def test_reject_correction_leaves_attendance_untouched(client, db):
    admin   = make_user(db, "adm4@payroll.com", role="Society Admin")
    society = make_society(db, "Payroll Society 5")
    staff   = _make_staff(db, society.id, "Guard E")
    att     = _make_attendance(db, society.id, staff.id)

    r = client.post("/api/v1/payroll/attendance-correction",
                    json=_correction_payload(society.id, staff.id, att.id),
                    headers=admin["headers"])
    correction_id = r.json()["id"]

    r2 = client.post(f"/api/v1/payroll/attendance-correction/{correction_id}/reject",
                     json={"reason": "Times already verified with the gate log."},
                     headers=admin["headers"])
    assert r2.status_code == 200
    assert r2.json()["status"] == "rejected"
    assert r2.json()["rejection_reason"] == "Times already verified with the gate log."

    from app.modules.staff.models.staff import StaffAttendance
    updated = db.query(StaffAttendance).filter(StaffAttendance.id == att.id).first()
    assert updated.status.value == "present"


def test_double_approve_rejected(client, db):
    admin   = make_user(db, "adm5@payroll.com", role="Society Admin")
    society = make_society(db, "Payroll Society 6")
    staff   = _make_staff(db, society.id, "Guard F")
    att     = _make_attendance(db, society.id, staff.id)

    r = client.post("/api/v1/payroll/attendance-correction",
                    json=_correction_payload(society.id, staff.id, att.id),
                    headers=admin["headers"])
    correction_id = r.json()["id"]
    client.post(f"/api/v1/payroll/attendance-correction/{correction_id}/approve",
                headers=admin["headers"])

    r2 = client.post(f"/api/v1/payroll/attendance-correction/{correction_id}/approve",
                     headers=admin["headers"])
    assert r2.status_code == 409


def test_list_corrections_by_staff(client, db):
    admin   = make_user(db, "adm6@payroll.com", role="Society Admin")
    society = make_society(db, "Payroll Society 7")
    staff   = _make_staff(db, society.id, "Guard G")
    att1    = _make_attendance(db, society.id, staff.id)

    client.post("/api/v1/payroll/attendance-correction",
                json=_correction_payload(society.id, staff.id, att1.id),
                headers=admin["headers"])

    r = client.get(f"/api/v1/payroll/attendance-correction/staff/{staff.id}",
                   headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["staff_id"] == str(staff.id)


def test_list_corrections_by_society(client, db):
    admin   = make_user(db, "adm7@payroll.com", role="Society Admin")
    society = make_society(db, "Payroll Society 8")
    staff   = _make_staff(db, society.id, "Guard H")
    att1    = _make_attendance(db, society.id, staff.id)

    client.post("/api/v1/payroll/attendance-correction",
                json=_correction_payload(society.id, staff.id, att1.id),
                headers=admin["headers"])

    r = client.get(f"/api/v1/payroll/attendance-correction/society/{society.id}",
                   headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()) == 1

    r2 = client.get(f"/api/v1/payroll/attendance-correction/society/{society.id}",
                    params={"status": "pending"}, headers=admin["headers"])
    assert r2.status_code == 200
    assert len(r2.json()) == 1
