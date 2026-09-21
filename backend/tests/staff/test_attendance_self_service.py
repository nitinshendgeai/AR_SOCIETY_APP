"""Staff self-service attendance — a plain staff member logs in with their
own auto-provisioned account and punches their own attendance, but cannot
punch or read anyone else's. Supervisor/admin on-behalf punching (the
original, tested behavior) must keep working unchanged."""
import pytest
from tests.conftest import make_user, make_society


def _make_staff_with_login(db, society_id, email, name="Guard Self"):
    from app.models.user import User, UserRole, UserStatus
    from app.models.role import Role
    from app.core.security import hash_password, create_access_token
    from app.modules.staff.models.staff import Staff, StaffDepartment, StaffStatus

    role = db.query(Role).filter(Role.name == "Security Staff").first()
    if not role:
        role = Role(name="Security Staff")
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
        full_name=name, mobile=f"9{hash(email) % 999999999:09d}",
        department=StaffDepartment.SECURITY, status=StaffStatus.ACTIVE,
        user_id=user.id,
    )
    db.add(staff); db.commit(); db.refresh(staff)

    token = create_access_token(str(user.id), {"roles": ["Security Staff"]})
    return staff, {"user": user, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def rig(db):
    society = make_society(db, "Self-Service Attendance Society")
    staff_a, guard_a = _make_staff_with_login(db, society.id, "guarda@self.io", "Guard A")
    staff_b, guard_b = _make_staff_with_login(db, society.id, "guardb@self.io", "Guard B")
    return {"society": society, "staff_a": staff_a, "guard_a": guard_a,
            "staff_b": staff_b, "guard_b": guard_b}


def test_staff_can_checkin_own_record(client, db, rig):
    r = client.post(
        f"/api/v1/staff/attendance/{rig['staff_a'].id}/checkin",
        json={}, headers=rig["guard_a"]["headers"],
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "present"


def test_staff_can_checkout_own_record(client, db, rig):
    client.post(f"/api/v1/staff/attendance/{rig['staff_a'].id}/checkin",
                json={}, headers=rig["guard_a"]["headers"])
    r = client.post(f"/api/v1/staff/attendance/{rig['staff_a'].id}/checkout",
                     json={}, headers=rig["guard_a"]["headers"])
    assert r.status_code == 200, r.text


def test_staff_can_view_own_attendance_history(client, db, rig):
    client.post(f"/api/v1/staff/attendance/{rig['staff_a'].id}/checkin",
                json={}, headers=rig["guard_a"]["headers"])
    r = client.get(f"/api/v1/staff/attendance/{rig['staff_a'].id}",
                    headers=rig["guard_a"]["headers"])
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1


def test_staff_cannot_checkin_another_staff(client, db, rig):
    r = client.post(
        f"/api/v1/staff/attendance/{rig['staff_b'].id}/checkin",
        json={}, headers=rig["guard_a"]["headers"],
    )
    assert r.status_code == 403, r.text


def test_staff_cannot_checkout_another_staff(client, db, rig):
    client.post(f"/api/v1/staff/attendance/{rig['staff_b'].id}/checkin",
                json={}, headers=rig["guard_b"]["headers"])
    r = client.post(f"/api/v1/staff/attendance/{rig['staff_b'].id}/checkout",
                     json={}, headers=rig["guard_a"]["headers"])
    assert r.status_code == 403, r.text


def test_staff_cannot_view_another_staffs_attendance(client, db, rig):
    client.post(f"/api/v1/staff/attendance/{rig['staff_b'].id}/checkin",
                json={}, headers=rig["guard_b"]["headers"])
    r = client.get(f"/api/v1/staff/attendance/{rig['staff_b'].id}",
                    headers=rig["guard_a"]["headers"])
    assert r.status_code == 403, r.text


def test_supervisor_can_still_checkin_on_behalf_of_staff(client, db, rig):
    """On-behalf/kiosk punching by a supervisor-or-above must be unaffected
    by the self-or-supervisor restriction added for plain staff."""
    admin = make_user(db, "adm@self.io", role="Society Admin")
    r = client.post(
        f"/api/v1/staff/attendance/{rig['staff_a'].id}/checkin",
        json={}, headers=admin["headers"],
    )
    assert r.status_code == 200, r.text
