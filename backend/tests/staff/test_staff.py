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
    temp = data["temp_password"]
    assert temp and temp != "Staff@1234", "each login gets its own random password, not a fixed default"
    # Verify the user can log in with the temp password
    login_r = client.post("/api/v1/auth/login",
                          json={"email": "mohan@test.com", "password": temp})
    assert login_r.status_code == 200, login_r.text
    # ...and the old fixed default no longer works
    old = client.post("/api/v1/auth/login", json={"email": "mohan@test.com", "password": "Staff@1234"})
    assert old.status_code == 401


def test_create_staff_without_email_gets_mobile_login(client, db):
    """Without an email the staff member's mobile number becomes the login (no email password)."""
    admin   = _admin(db, "4")
    society = make_society(db, "Staff No Email Society")

    r = _create_staff(client, admin["headers"], society.id, name="Kiran Bose")
    assert r.status_code == 201
    data = r.json()
    assert data["user_id"] is not None
    assert data["temp_password"] is None            # no email: the message carries the password
    assert data["login_message"] and "Login created" in data["login_message"]


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


def test_update_staff_email(client, db):
    admin   = _admin(db, "9b")
    society = make_society(db, "Update Staff Email Society")

    create_r = _create_staff(client, admin["headers"], society.id, name="Deepa Iyer")
    staff_id = create_r.json()["id"]
    assert create_r.json()["email"] is None

    r = client.patch(f"/api/v1/staff/{staff_id}",
                     json={"email": "deepa.iyer@example.com"},
                     headers=admin["headers"])
    assert r.status_code == 200
    assert r.json()["email"] == "deepa.iyer@example.com"


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


def test_reporting_loops_are_refused(client, db):
    admin   = _admin(db, "12")
    society = make_society(db, "Reporting Loop Society")
    h = admin["headers"]

    def mk(name, mobile, email, **extra):
        r = _create_staff(client, h, society.id, name=name, dept="technical", mobile=mobile,
                          email=email, extra=extra or None)
        assert r.status_code == 201, r.text
        return r.json()

    a = mk("Loop A", "9300000001", "loopa@loop.test")
    # Anyone with a login can be a reporting person, not only managers and supervisors.
    b = mk("Loop B", "9300000002", "loopb@loop.test", reporting_manager_id=a["user_id"])
    c = mk("Loop C", "9300000003", "loopc@loop.test", reporting_manager_id=b["user_id"])

    def set_manager(staff, manager_user_id):
        return client.patch(f"/api/v1/staff/{staff['id']}", json={"reporting_manager_id": manager_user_id}, headers=h)

    assert set_manager(a, a["user_id"]).status_code == 422          # themselves
    assert set_manager(a, b["user_id"]).status_code == 422          # A under B, who is under A
    assert set_manager(a, c["user_id"]).status_code == 422          # through a longer chain
    assert set_manager(c, a["user_id"]).status_code == 200          # a shorter, loop-free change
    assert set_manager(a, None).status_code == 200                  # clearing is fine


def test_staff_without_email_get_a_mobile_login(client, db):
    admin   = _admin(db, "13")
    society = make_society(db, "Staff Mobile Login Society")
    h = admin["headers"]

    g = _create_staff(client, h, society.id, name="Night Guard", dept="security", mobile="9400000001")
    assert g.status_code == 201, g.text
    body = g.json()
    assert body["user_id"] is not None
    assert "9400000001" in body["login_message"] and "Password:" in body["login_message"]
    # With the login they can be somebody's reporting person.
    r = _create_staff(client, h, society.id, name="Gate Helper", dept="security", mobile="9400000002",
                      extra={"reporting_manager_id": body["user_id"]})
    assert r.status_code == 201, r.text

    # With an email, the email is the login and the password comes back as before.
    e = _create_staff(client, h, society.id, name="Mail Guard", dept="security", mobile="9400000003",
                      email="mailguard@mobilelogin.test")
    assert e.json()["temp_password"] and e.json()["login_message"] is None


def test_create_login_for_existing_staff(client, db):
    admin   = _admin(db, "14")
    society = make_society(db, "Staff Add Login Society")
    h = admin["headers"]
    s = _create_staff(client, h, society.id, name="Old Guard", dept="security", mobile="9500000001")
    sid = s.json()["id"]
    # Simulate staff entered before logins were automatic.
    from app.modules.staff.models.staff import Staff
    st = db.get(Staff, sid if not isinstance(sid, str) else __import__("uuid").UUID(sid))
    st.user_id = None
    db.commit()

    r = client.post(f"/api/v1/staff/{sid}/login", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["user_id"] is not None and "9500000001" in r.json()["login_message"]  # relinked: the login already existed
    assert client.post(f"/api/v1/staff/{sid}/login", headers=h).status_code == 409


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
