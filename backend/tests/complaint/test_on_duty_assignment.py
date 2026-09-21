"""On-duty, department-aware complaint auto-assignment.

A complaint should reach someone who is actually present: the category
maps to a staff department (plumbing -> Plumbing, security -> Security,
etc.), and auto-assignment prefers an on-duty (checked in, not yet checked
out) staff member in that department over the FMC Manager. Falls back to
the Manager when nobody in the matching department is on duty, or when the
category has no department mapping (OTHER).
"""
import pytest
from tests.conftest import make_user, make_society


def _make_staff_with_login(db, society_id, email, department, name="Staffer"):
    from app.models.user import User, UserRole, UserStatus
    from app.models.role import Role
    from app.core.security import hash_password, create_access_token
    from app.modules.staff.models.staff import Staff, StaffStatus

    role_name = {
        "plumbing": "Technical Staff", "electrical": "Technical Staff",
        "technical": "Technical Staff", "security": "Security Staff",
        "housekeeping": "Housekeeping Staff", "amenities": "Gym Trainer",
    }.get(department.value, "Technical Staff")
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name)
        db.add(role); db.flush()

    user = User(
        email=email, full_name=name,
        hashed_password=hash_password("Staff@1234"),
        status=UserStatus.ACTIVE, society_id=society_id,
    )
    db.add(user); db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit(); db.refresh(user)

    staff = Staff(
        society_id=society_id, employee_code=f"EMP-{abs(hash(email)) % 999999:06d}",
        full_name=name, mobile=f"9{abs(hash(email)) % 999999999:09d}",
        department=department, status=StaffStatus.ACTIVE,
        user_id=user.id,
    )
    db.add(staff); db.commit(); db.refresh(staff)

    token = create_access_token(str(user.id), {"roles": [role_name]})
    return staff, {"user": user, "headers": {"Authorization": f"Bearer {token}"}}


def _complaint_payload(society_id, category="plumbing"):
    return {
        "title": "Test issue", "description": "Test description",
        "category": category, "priority": "high", "society_id": str(society_id),
    }


def test_complaint_routes_to_on_duty_department_staff(client, db):
    from app.modules.staff.models.staff import StaffDepartment

    resident = make_user(db, "res-ondty1@cmp.com", role="Resident")
    society  = make_society(db, "On-Duty Society 1")
    manager  = make_user(db, "mgr-ondty1@cmp.com", role="Manager")
    manager["user"].society_id = society.id
    db.commit()

    plumber, plumber_login = _make_staff_with_login(
        db, society.id, "plumber1@cmp.com", StaffDepartment.PLUMBING)
    client.post(f"/api/v1/staff/attendance/{plumber.id}/checkin",
                json={}, headers=plumber_login["headers"])

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id, "plumbing"),
                    headers=resident["headers"])
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "assigned"
    assert data["assigned_to"] == str(plumber_login["user"].id)


def test_complaint_falls_back_to_manager_when_nobody_on_duty(client, db):
    resident = make_user(db, "res-ondty2@cmp.com", role="Resident")
    society  = make_society(db, "On-Duty Society 2")
    manager  = make_user(db, "mgr-ondty2@cmp.com", role="Manager")
    manager["user"].society_id = society.id
    db.commit()

    from app.modules.staff.models.staff import StaffDepartment
    # Plumber exists but never checked in.
    _make_staff_with_login(db, society.id, "plumber2@cmp.com", StaffDepartment.PLUMBING)

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id, "plumbing"),
                    headers=resident["headers"])
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "assigned"
    assert data["assigned_to"] == str(manager["user"].id)


def test_checked_out_staff_not_picked(client, db):
    from app.modules.staff.models.staff import StaffDepartment

    resident = make_user(db, "res-ondty3@cmp.com", role="Resident")
    society  = make_society(db, "On-Duty Society 3")
    manager  = make_user(db, "mgr-ondty3@cmp.com", role="Manager")
    manager["user"].society_id = society.id
    db.commit()

    plumber, plumber_login = _make_staff_with_login(
        db, society.id, "plumber3@cmp.com", StaffDepartment.PLUMBING)
    client.post(f"/api/v1/staff/attendance/{plumber.id}/checkin",
                json={}, headers=plumber_login["headers"])
    client.post(f"/api/v1/staff/attendance/{plumber.id}/checkout",
                json={}, headers=plumber_login["headers"])

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id, "plumbing"),
                    headers=resident["headers"])
    assert r.status_code == 201
    data = r.json()
    # Checked-out plumber is not on duty -> falls back to the Manager.
    assert data["assigned_to"] == str(manager["user"].id)


def test_wrong_department_staff_not_picked(client, db):
    """An on-duty Security staffer shouldn't catch a plumbing complaint."""
    from app.modules.staff.models.staff import StaffDepartment

    resident = make_user(db, "res-ondty4@cmp.com", role="Resident")
    society  = make_society(db, "On-Duty Society 4")
    manager  = make_user(db, "mgr-ondty4@cmp.com", role="Manager")
    manager["user"].society_id = society.id
    db.commit()

    guard, guard_login = _make_staff_with_login(
        db, society.id, "guard-ondty4@cmp.com", StaffDepartment.SECURITY)
    client.post(f"/api/v1/staff/attendance/{guard.id}/checkin",
                json={}, headers=guard_login["headers"])

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id, "plumbing"),
                    headers=resident["headers"])
    assert r.status_code == 201
    data = r.json()
    assert data["assigned_to"] == str(manager["user"].id)


def test_other_category_has_no_department_mapping_goes_to_manager(client, db):
    from app.modules.staff.models.staff import StaffDepartment

    resident = make_user(db, "res-ondty5@cmp.com", role="Resident")
    society  = make_society(db, "On-Duty Society 5")
    manager  = make_user(db, "mgr-ondty5@cmp.com", role="Manager")
    manager["user"].society_id = society.id
    db.commit()

    # Even an on-duty plumber shouldn't catch an "other" complaint.
    plumber, plumber_login = _make_staff_with_login(
        db, society.id, "plumber5@cmp.com", StaffDepartment.PLUMBING)
    client.post(f"/api/v1/staff/attendance/{plumber.id}/checkin",
                json={}, headers=plumber_login["headers"])

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id, "other"),
                    headers=resident["headers"])
    assert r.status_code == 201
    assert r.json()["assigned_to"] == str(manager["user"].id)


def test_assigned_department_set_on_department_routed_complaint(client, db):
    from app.modules.staff.models.staff import StaffDepartment

    resident = make_user(db, "res-ondty6@cmp.com", role="Resident")
    society  = make_society(db, "On-Duty Society 6")

    guard, guard_login = _make_staff_with_login(
        db, society.id, "guard-ondty6@cmp.com", StaffDepartment.SECURITY)
    client.post(f"/api/v1/staff/attendance/{guard.id}/checkin",
                json={}, headers=guard_login["headers"])

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id, "security"),
                    headers=resident["headers"])
    assert r.status_code == 201
    data = r.json()
    assert data["assigned_to"] == str(guard_login["user"].id)


def test_manual_department_assign_picks_on_duty_staff(client, db):
    from app.modules.staff.models.staff import StaffDepartment

    resident = make_user(db, "res-ondty7@cmp.com", role="Resident")
    society  = make_society(db, "On-Duty Society 7")
    manager  = make_user(db, "mgr-ondty7@cmp.com", role="Manager")
    manager["user"].society_id = society.id
    db.commit()

    housekeeper, hk_login = _make_staff_with_login(
        db, society.id, "hk-ondty7@cmp.com", StaffDepartment.HOUSEKEEPING)
    client.post(f"/api/v1/staff/attendance/{housekeeper.id}/checkin",
                json={}, headers=hk_login["headers"])

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id, "other"),
                    headers=resident["headers"])
    cid = r.json()["id"]

    r2 = client.post("/api/v1/staff/complaints/assign-department",
                     json={"complaint_id": cid, "department": "housekeeping"},
                     headers=manager["headers"])
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert data["assigned_to"] == str(hk_login["user"].id)

    detail = client.get(f"/api/v1/complaints/{cid}", headers=manager["headers"])
    assert detail.json()["status"] == "assigned"
    assert detail.json()["assigned_to"] == str(hk_login["user"].id)


def test_manual_department_assign_no_one_on_duty_tags_department_only(client, db):
    resident = make_user(db, "res-ondty8@cmp.com", role="Resident")
    society  = make_society(db, "On-Duty Society 8")
    manager  = make_user(db, "mgr-ondty8@cmp.com", role="Manager")
    manager["user"].society_id = society.id
    db.commit()

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id, "other"),
                    headers=resident["headers"])
    cid = r.json()["id"]

    r2 = client.post("/api/v1/staff/complaints/assign-department",
                     json={"complaint_id": cid, "department": "electrical"},
                     headers=manager["headers"])
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert data["assigned_to"] is None
    assert "no one is currently on duty" in data["message"]


def test_manual_department_assign_rejects_unknown_department(client, db):
    resident = make_user(db, "res-ondty9@cmp.com", role="Resident")
    society  = make_society(db, "On-Duty Society 9")
    manager  = make_user(db, "mgr-ondty9@cmp.com", role="Manager")
    manager["user"].society_id = society.id
    db.commit()

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id, "other"),
                    headers=resident["headers"])
    cid = r.json()["id"]

    r2 = client.post("/api/v1/staff/complaints/assign-department",
                     json={"complaint_id": cid, "department": "not_a_real_dept"},
                     headers=manager["headers"])
    assert r2.status_code == 400
