"""Staff Management — CRUD and user-integration tests.

Covers:
- Create staff (basic)
- Create staff with email → auto-creates user account + temp password
- List staff (society-scoped, returns only the right society)
- Get staff by ID
- Update staff fields (name, status, address, notes)
- Deactivate staff (status → inactive)
- Staff hierarchy: manager → supervisor → guard
- Department filter
"""
import pytest
from tests.conftest import make_user, make_society


# ── Helpers ──────────────────────────────────────────────────────────────────

def _admin(db, suffix=""):
    return make_user(db, f"admin{suffix}@stafftest.com", role="Society Admin", full_name="Admin User")


def _create_staff(client, admin_headers, society_id, name="Rajan Sharma",
                  dept="security", mobile=None, email=None, extra=None):
    payload = {
        "society_id": str(society_id),
        "full_name": name,
        "mobile": mobile or f"9{abs(hash(name)) % 999999999:09d}",
        "department": dept,
    }
    if email:
        payload["email"] = email
    if extra:
        payload.update(extra)
    return client.post("/api/v1/staff/", json=payload, headers=admin_headers)


# ── Basic CRUD ───────────────────────────────────────────────────────────────

def test_create_staff_basic(client, db):
    admin   = _admin(db, "1")
    society = make_society(db, "Staff CRUD Society")

    r = _create_staff(client, admin["headers"], society.id)
    assert r.status_code == 201
    data = r.json()
    assert data["full_name"] == "Rajan Sharma"
    assert data["department"] == "security"
    assert data["employee_code"].startswith("EMP-")
    assert data["status"] in ("active", "probation")  # default is probation


def test_create_staff_with_address_and_notes(client, db):
    admin   = _admin(db, "2")
    society = make_society(db, "Staff Address Society")

    r = _create_staff(client, admin["headers"], society.id, name="Priya Nair",
                      extra={
                          "address": "12 MG Road, Pune",
                          "notes": "Reliable team member",
                          "emergency_contact_name": "Suresh Nair",
                          "emergency_contact_phone": "9876543210",
                      })
    assert r.status_code == 201
    data = r.json()
    assert data["address"] == "12 MG Road, Pune"
    assert data["notes"] == "Reliable team member"
    assert data["emergency_contact_name"] == "Suresh Nair"


def test_create_staff_with_email_creates_user(client, db):
    """Creating staff with an email must auto-create a User account."""
    admin   = _admin(db, "3")
    society = make_society(db, "Staff User Society")

    r = _create_staff(client, admin["headers"], society.id,
                      name="Mohan Das", email="mohan@test.com")
    assert r.status_code == 201
    data = r.json()
    assert data["user_id"] is not None, "user_id must be set"
    assert data["temp_password"] == "Staff@1234"
    # Verify the user can log in with the temp password
    login_r = client.post("/api/v1/auth/login",
                          json={"email": "mohan@test.com", "password": "Staff@1234"})
    assert login_r.status_code == 200, login_r.text


def test_create_staff_without_email_no_user(client, db):
    """Creating staff without email must NOT create a User."""
    admin   = _admin(db, "4")
    society = make_society(db, "Staff No Email Society")

    r = _create_staff(client, admin["headers"], society.id, name="Kiran Bose")
    assert r.status_code == 201
    data = r.json()
    assert data["user_id"] is None
    assert data["temp_password"] is None


def test_list_staff_society_scoped(client, db):
    """Staff listing must be filtered to the requested society."""
    admin    = _admin(db, "5")
    society1 = make_society(db, "Society Alpha")
    society2 = make_society(db, "Society Beta")

    _create_staff(client, admin["headers"], society1.id, name="Alice A", mobile="9000000001")
    _create_staff(client, admin["headers"], society1.id, name="Alice B", mobile="9000000002")
    _create_staff(client, admin["headers"], society2.id, name="Bob B",   mobile="9000000003")

    r1 = client.get(f"/api/v1/staff/society/{society1.id}", headers=admin["headers"])
    assert r1.status_code == 200
    names1 = [s["full_name"] for s in r1.json()]
    assert "Alice A" in names1 and "Alice B" in names1
    assert "Bob B" not in names1

    r2 = client.get(f"/api/v1/staff/society/{society2.id}", headers=admin["headers"])
    assert r2.status_code == 200
    names2 = [s["full_name"] for s in r2.json()]
    assert "Bob B" in names2
    assert "Alice A" not in names2 and "Alice B" not in names2


def test_get_staff_by_id(client, db):
    admin   = _admin(db, "6")
    society = make_society(db, "Get Staff Society")

    create_r = _create_staff(client, admin["headers"], society.id, name="Vijay Kumar")
    assert create_r.status_code == 201
    staff_id = create_r.json()["id"]

    r = client.get(f"/api/v1/staff/{staff_id}", headers=admin["headers"])
    assert r.status_code == 200
    assert r.json()["full_name"] == "Vijay Kumar"


def test_update_staff_name_and_status(client, db):
    admin   = _admin(db, "7")
    society = make_society(db, "Update Staff Society")

    create_r = _create_staff(client, admin["headers"], society.id, name="Suresh Patel")
    staff_id = create_r.json()["id"]

    r = client.patch(f"/api/v1/staff/{staff_id}",
                     json={"full_name": "Suresh Patel Jr", "status": "on_leave"},
                     headers=admin["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["full_name"] == "Suresh Patel Jr"
    assert data["status"] == "on_leave"


def test_deactivate_staff(client, db):
    admin   = _admin(db, "8")
    society = make_society(db, "Deactivate Staff Society")

    create_r = _create_staff(client, admin["headers"], society.id, name="Ramesh Gupta")
    staff_id = create_r.json()["id"]

    r = client.patch(f"/api/v1/staff/{staff_id}",
                     json={"status": "inactive"},
                     headers=admin["headers"])
    assert r.status_code == 200
    assert r.json()["status"] == "inactive"


def test_update_staff_address_and_notes(client, db):
    admin   = _admin(db, "9")
    society = make_society(db, "Address Notes Society")

    create_r = _create_staff(client, admin["headers"], society.id, name="Lakshmi Rao")
    staff_id = create_r.json()["id"]

    r = client.patch(f"/api/v1/staff/{staff_id}",
                     json={"address": "22 Park St", "notes": "Promoted to senior"},
                     headers=admin["headers"])
    assert r.status_code == 200
    data = r.json()
    assert data["address"] == "22 Park St"
    assert data["notes"] == "Promoted to senior"


# ── Hierarchy tests ───────────────────────────────────────────────────────────

def test_staff_reporting_hierarchy(client, db):
    """Manager → supervisor → guard chain should persist.

    reporting_manager_id is a FK to users.id, so managers/supervisors need
    user accounts. We create them with emails to trigger auto-user creation.
    """
    admin   = _admin(db, "10")
    society = make_society(db, "Hierarchy Society")

    mgr_r  = _create_staff(client, admin["headers"], society.id,
                            name="Head Manager", dept="admin", mobile="9100000001",
                            email="headmgr@hier.test")
    assert mgr_r.status_code == 201
    mgr_user_id = mgr_r.json()["user_id"]
    assert mgr_user_id is not None

    sup_r  = _create_staff(client, admin["headers"], society.id,
                            name="Sec Supervisor", dept="security", mobile="9100000002",
                            email="secsup@hier.test",
                            extra={"reporting_manager_id": mgr_user_id})
    assert sup_r.status_code == 201
    sup_user_id = sup_r.json()["user_id"]
    assert sup_r.json()["reporting_manager_id"] == mgr_user_id

    guard_r = _create_staff(client, admin["headers"], society.id,
                             name="Security Guard", dept="security", mobile="9100000003",
                             extra={"reporting_manager_id": sup_user_id})
    assert guard_r.status_code == 201
    assert guard_r.json()["reporting_manager_id"] == sup_user_id


def test_department_filter(client, db):
    """GET /staff/society/{id}/department/{dept} returns only that dept."""
    admin   = _admin(db, "11")
    society = make_society(db, "Department Filter Society")

    _create_staff(client, admin["headers"], society.id,
                  name="Security A", dept="security", mobile="9200000001")
    _create_staff(client, admin["headers"], society.id,
                  name="Security B", dept="security", mobile="9200000002")
    _create_staff(client, admin["headers"], society.id,
                  name="Housekeeping A", dept="housekeeping", mobile="9200000003")

    r = client.get(
        f"/api/v1/staff/society/{society.id}/department/security",
        headers=admin["headers"]
    )
    assert r.status_code == 200
    results = r.json()
    depts = {s["department"] for s in results}
    assert depts == {"security"}
    assert len(results) == 2


# ── Full org: 10-member hierarchy ────────────────────────────────────────────

def test_full_staff_hierarchy(client, db):
    """
    Create the full recommended hierarchy:
      1 Manager (admin dept)
      1 Security Supervisor
      2 Security Guards
      1 Housekeeping Supervisor
      2 Housekeeping Staff
      1 Technical Staff
      1 Gym Trainer
    Total: 9 staff → all should appear in list.

    reporting_manager_id is FK to users.id — managers/supervisors need email
    so they get auto-created user accounts.
    """
    admin   = _admin(db, "12")
    society = make_society(db, "Full Org Society")

    def _c(name, dept, mobile, email=None, reporting_user_id=None):
        extra = {}
        if reporting_user_id:
            extra["reporting_manager_id"] = reporting_user_id
        r = _create_staff(client, admin["headers"], society.id,
                          name=name, dept=dept, mobile=mobile,
                          email=email, extra=extra or None)
        assert r.status_code == 201, f"Failed to create {name}: {r.text}"
        return r.json()

    mgr      = _c("Org Manager",        "admin",        "9300000001", email="mgr@full.test")
    mgr_uid  = mgr["user_id"]
    sec_sup  = _c("Security Supervisor","security",     "9300000002", email="secsup@full.test",  reporting_user_id=mgr_uid)
    sup_uid  = sec_sup["user_id"]
    _c("Guard One",             "security",     "9300000003", reporting_user_id=sup_uid)
    _c("Guard Two",             "security",     "9300000004", reporting_user_id=sup_uid)
    hk_sup   = _c("HK Supervisor",     "housekeeping", "9300000005", email="hksup@full.test",   reporting_user_id=mgr_uid)
    hk_uid   = hk_sup["user_id"]
    _c("HK Staff One",          "housekeeping", "9300000006", reporting_user_id=hk_uid)
    _c("HK Staff Two",          "housekeeping", "9300000007", reporting_user_id=hk_uid)
    _c("Technical Staff",       "technical",    "9300000008", reporting_user_id=mgr_uid)
    _c("Gym Trainer",           "gym",          "9300000009", reporting_user_id=mgr_uid)

    r = client.get(f"/api/v1/staff/society/{society.id}", headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()) == 9
