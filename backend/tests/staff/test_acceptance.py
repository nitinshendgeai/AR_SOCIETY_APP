"""
Staff Module — Full Acceptance Test Suite
==========================================
Covers all 8 test scenarios from the acceptance criteria:

  A. Staff creation + login account creation (8 staff members)
  B. First-login / must_change_password enforcement
  C. Attendance: punch-in, pending list, supervisor approval
  D. Duty lifecycle: assign → view → complete → verify
  E. Punch-out + checkout approval + working hours
  F. Role validation: supervisor dept enforcement
  G. Multi-tenant isolation: cross-society 403
"""
import pytest
from uuid import UUID as _UUID
from datetime import date, datetime, timedelta
from tests.conftest import make_user, make_society


# ── Shared helpers ────────────────────────────────────────────────────────────

def _seed_roles(db):
    """Ensure all staff roles exist in DB so auto-assignment can find them."""
    from app.models.role import Role
    for name in [
        "Society Admin", "Manager",
        "Security Supervisor", "Housekeeping Supervisor", "Technical Supervisor",
        "Security Staff", "Housekeeping Staff", "Technical Staff", "Gym Trainer",
    ]:
        if not db.query(Role).filter(Role.name == name).first():
            db.add(Role(name=name))
    db.commit()


def _to_uuid(v) -> _UUID:
    """Convert string or UUID to UUID object (SQLite requires UUID objects)."""
    return v if isinstance(v, _UUID) else _UUID(str(v))


def _create_staff(client, headers, society_id, full_name, mobile, email, dept):
    r = client.post(
        "/api/v1/staff/",
        json={"society_id": str(society_id), "full_name": full_name,
              "mobile": mobile, "email": email, "department": dept},
        headers=headers,
    )
    assert r.status_code == 201, f"create_staff failed for {full_name}: {r.text}"
    return r.json()


def _make_attendance(db, society_id, staff_id, checkin_hours_ago=8, with_checkout=False):
    """Insert a StaffAttendance record directly (bypasses route auth)."""
    from app.modules.staff.models.staff import StaffAttendance, AttendanceStatus
    att = StaffAttendance(
        society_id=_to_uuid(society_id),
        staff_id=_to_uuid(staff_id),
        attendance_date=date.today(),
        status=AttendanceStatus.PRESENT,
        check_in_time=datetime.utcnow() - timedelta(hours=checkin_hours_ago),
        check_out_time=datetime.utcnow() if with_checkout else None,
        working_hours=float(checkin_hours_ago) if with_checkout else None,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


def _set_society(db, user_obj, society_id):
    user_obj.society_id = _to_uuid(society_id)
    db.commit()
    db.refresh(user_obj)


# ── Test A: Staff Creation with Login Accounts ────────────────────────────────

class TestStaffCreation:
    """All 8 staff members can be created; each auto-generates a login account."""

    @pytest.fixture(autouse=True)
    def setup(self, client, db):
        _seed_roles(db)
        self.client = client
        self.db = db
        self.society = make_society(db, "Accept Society A")
        self.admin = make_user(db, "adm@accept.io", role="Society Admin")

    def _create(self, name, mobile, email, dept):
        return _create_staff(self.client, self.admin["headers"],
                             self.society.id, name, mobile, email, dept)

    def test_A1_security_supervisor_created(self):
        s = self._create("Rajan Kumar", "9811000001", "rajan@accept.io", "security")
        assert s["department"] == "security"
        assert s["user_id"] is not None, "Auto-account not created"
        u = self.client.get(f"/api/v1/users/{s['user_id']}", headers=self.admin["headers"])
        assert u.status_code == 200
        assert u.json()["must_change_password"] is True, "must_change_password should be True"

    def test_A2_all_eight_staff_types(self):
        """Create all 8 staff members and verify each has a login account."""
        all_staff = [
            ("Rajan Kumar",      "9811000011", "rajan2@accept.io",   "security"),
            ("Mohan Guard",      "9811000012", "mohan@accept.io",    "security"),
            ("Suresh Guard",     "9811000013", "suresh@accept.io",   "security"),
            ("Pita Hk Sup",      "9811000014", "pita@accept.io",     "housekeeping"),
            ("Gita Hk Staff",    "9811000015", "gita@accept.io",     "housekeeping"),
            ("Lata Hk Staff",    "9811000016", "lata@accept.io",     "housekeeping"),
            ("Ramesh Tech",      "9811000017", "ramesh@accept.io",   "technical"),
            ("Arjun Gym",        "9811000018", "arjun@accept.io",    "gym"),
        ]
        results = []
        for name, mobile, email, dept in all_staff:
            s = self._create(name, mobile, email, dept)
            assert s["user_id"] is not None, f"No user account for {name}"
            u = self.client.get(f"/api/v1/users/{s['user_id']}", headers=self.admin["headers"])
            assert u.json()["must_change_password"] is True, f"must_change_password not True for {name}"
            results.append(s)
        assert len(results) == 8

    def test_A3_login_account_has_correct_role_security(self):
        s = self._create("Guard Role", "9811000019", "grole@accept.io", "security")
        u = self.client.get(f"/api/v1/users/{s['user_id']}", headers=self.admin["headers"])
        roles = u.json()["roles"]
        assert "Security Staff" in roles, f"Expected 'Security Staff', got {roles}"

    def test_A4_gym_trainer_role(self):
        s = self._create("Gym Role", "9811000020", "gymrole@accept.io", "gym")
        u = self.client.get(f"/api/v1/users/{s['user_id']}", headers=self.admin["headers"])
        roles = u.json()["roles"]
        assert "Gym Trainer" in roles, f"Expected 'Gym Trainer', got {roles}"

    def test_A5_technical_staff_role(self):
        s = self._create("Tech Role", "9811000021", "techrole@accept.io", "technical")
        u = self.client.get(f"/api/v1/users/{s['user_id']}", headers=self.admin["headers"])
        roles = u.json()["roles"]
        assert "Technical Staff" in roles, f"Expected 'Technical Staff', got {roles}"


# ── Test B: First Login / Password Change Enforcement ─────────────────────────

class TestFirstLogin:
    """must_change_password is True after account creation and False after change_password."""

    @pytest.fixture(autouse=True)
    def setup(self, client, db):
        _seed_roles(db)
        self.client = client
        self.db = db
        self.society = make_society(db, "Accept Society B")
        self.admin = make_user(db, "adm2@accept.io", role="Society Admin")

    def test_B1_login_succeeds_with_temp_password(self):
        _create_staff(self.client, self.admin["headers"],
                      self.society.id, "Login Test", "9812000001",
                      "logintest@stafftest.io", "security")
        r = self.client.post("/api/v1/auth/login",
                             json={"email": "logintest@stafftest.io", "password": "Staff@1234"})
        assert r.status_code == 200, f"Login failed: {r.text}"
        data = r.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_B2_must_change_password_flag_true_on_creation(self):
        _create_staff(self.client, self.admin["headers"],
                      self.society.id, "Flag Test", "9812000002",
                      "flagtest@stafftest.io", "security")
        r = self.client.post("/api/v1/auth/login",
                             json={"email": "flagtest@stafftest.io", "password": "Staff@1234"})
        assert r.status_code == 200, f"Login failed: {r.text}"
        token = r.json()["access_token"]
        me = self.client.get("/api/v1/auth/me",
                             headers={"Authorization": f"Bearer {token}"})
        assert me.json()["must_change_password"] is True

    def test_B3_change_password_clears_flag(self):
        _create_staff(self.client, self.admin["headers"],
                      self.society.id, "Pwd Change", "9812000003",
                      "pwdchange@stafftest.io", "security")
        login = self.client.post("/api/v1/auth/login",
                                 json={"email": "pwdchange@stafftest.io", "password": "Staff@1234"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        cp = self.client.post("/api/v1/auth/change-password",
                              json={"current_password": "Staff@1234",
                                    "new_password": "NewPass@9876"},
                              headers=h)
        assert cp.status_code == 204, f"change_password failed: {cp.text}"

        login2 = self.client.post("/api/v1/auth/login",
                                  json={"email": "pwdchange@stafftest.io",
                                        "password": "NewPass@9876"})
        assert login2.status_code == 200
        token2 = login2.json()["access_token"]
        me = self.client.get("/api/v1/auth/me",
                             headers={"Authorization": f"Bearer {token2}"})
        assert me.json()["must_change_password"] is False, "must_change_password should be False after change"

    def test_B4_old_password_rejected_after_change(self):
        _create_staff(self.client, self.admin["headers"],
                      self.society.id, "Old Pwd", "9812000004",
                      "oldpwd@stafftest.io", "security")
        login = self.client.post("/api/v1/auth/login",
                                 json={"email": "oldpwd@stafftest.io", "password": "Staff@1234"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        self.client.post("/api/v1/auth/change-password",
                         json={"current_password": "Staff@1234", "new_password": "NewPass@9999"},
                         headers={"Authorization": f"Bearer {token}"})

        old_login = self.client.post("/api/v1/auth/login",
                                     json={"email": "oldpwd@stafftest.io", "password": "Staff@1234"})
        assert old_login.status_code == 401, "Old password should be rejected"


# ── Test C: Attendance Workflow ───────────────────────────────────────────────

class TestAttendanceWorkflow:
    """Punch-in → pending list → supervisor approval → status confirmed."""

    @pytest.fixture(autouse=True)
    def setup(self, client, db):
        _seed_roles(db)
        self.client = client
        self.db = db
        self.society = make_society(db, "Accept Society C")
        self.admin = make_user(db, "adm3@accept.io", role="Society Admin")
        self.supervisor = make_user(db, "sup@accept.io", role="Security Supervisor")
        _set_society(db, self.supervisor["user"], self.society.id)
        self.guard_staff = _create_staff(
            client, self.admin["headers"], self.society.id,
            "Guard C1", "9813000001", "guardc1@stafftest.io", "security",
        )

    def test_C1_supervisor_can_punch_in_guard(self):
        r = self.client.post(
            f"/api/v1/staff/attendance/{self.guard_staff['id']}/checkin",
            json={"notes": "On time"},
            headers=self.supervisor["headers"],
        )
        assert r.status_code == 200, f"Punch-in failed: {r.text}"
        data = r.json()
        assert data["status"] == "present"
        assert data["check_in_time"] is not None

    def test_C2_punch_in_appears_in_pending_list(self):
        self.client.post(
            f"/api/v1/staff/attendance/{self.guard_staff['id']}/checkin",
            json={}, headers=self.supervisor["headers"],
        )
        r = self.client.get(
            f"/api/v1/staff/attendance/pending/{self.society.id}",
            headers=self.admin["headers"],
        )
        assert r.status_code == 200, r.text
        assert len(r.json()) >= 1

    def test_C3_supervisor_approves_own_dept_checkin(self):
        att = _make_attendance(self.db, self.society.id, self.guard_staff["id"])
        r = self.client.post(
            f"/api/v1/staff/attendance/{att.id}/approve",
            json={"notes": "Verified"},
            headers=self.supervisor["headers"],
        )
        assert r.status_code == 200, f"Approve failed: {r.text}"
        data = r.json()
        assert data["is_approved"] is True
        assert data["approval_notes"] == "Verified"

    def test_C4_duplicate_approval_returns_409(self):
        att = _make_attendance(self.db, self.society.id, self.guard_staff["id"])
        self.client.post(f"/api/v1/staff/attendance/{att.id}/approve",
                         json={}, headers=self.supervisor["headers"])
        r2 = self.client.post(f"/api/v1/staff/attendance/{att.id}/approve",
                              json={}, headers=self.supervisor["headers"])
        assert r2.status_code == 409

    def test_C5_duplicate_checkin_prevented(self):
        self.client.post(
            f"/api/v1/staff/attendance/{self.guard_staff['id']}/checkin",
            json={}, headers=self.supervisor["headers"],
        )
        r2 = self.client.post(
            f"/api/v1/staff/attendance/{self.guard_staff['id']}/checkin",
            json={}, headers=self.supervisor["headers"],
        )
        assert r2.status_code == 409
        assert "already" in r2.json()["detail"].lower()


# ── Test D: Duty Lifecycle ────────────────────────────────────────────────────

class TestDutyLifecycle:
    """Supervisor assigns duty → staff views → staff completes → supervisor verifies."""

    @pytest.fixture(autouse=True)
    def setup(self, client, db):
        _seed_roles(db)
        self.client = client
        self.db = db
        self.society = make_society(db, "Accept Society D")
        self.admin = make_user(db, "adm4@accept.io", role="Society Admin")
        self.supervisor = make_user(db, "supd@accept.io", role="Security Supervisor")
        _set_society(db, self.supervisor["user"], self.society.id)
        self.guard_staff = _create_staff(
            client, self.admin["headers"], self.society.id,
            "Guard D1", "9814000001", "guardd1@stafftest.io", "security",
        )
        self.staff_user = make_user(db, "staffd@accept.io", role="Security Staff")

    def test_D1_supervisor_assigns_duty(self):
        r = self.client.post(
            "/api/v1/staff/duties",
            json={"society_id": str(self.society.id), "staff_id": self.guard_staff["id"],
                  "duty_name": "Gate Patrol", "duty_date": str(date.today()),
                  "start_time": "08:00:00", "end_time": "16:00:00"},
            headers=self.supervisor["headers"],
        )
        assert r.status_code == 201, f"Assign duty failed: {r.text}"
        duty = r.json()
        assert duty["duty_name"] == "Gate Patrol"
        assert duty["is_completed"] is False

    def test_D2_staff_can_view_assigned_duty(self):
        self.client.post(
            "/api/v1/staff/duties",
            json={"society_id": str(self.society.id), "staff_id": self.guard_staff["id"],
                  "duty_name": "Main Entrance", "duty_date": str(date.today()),
                  "start_time": "08:00:00", "end_time": "16:00:00"},
            headers=self.supervisor["headers"],
        )
        r = self.client.get(
            f"/api/v1/staff/duties/me/{self.guard_staff['id']}",
            headers=self.staff_user["headers"],
        )
        assert r.status_code == 200, f"View duties failed: {r.text}"
        duties = r.json()
        assert len(duties) >= 1
        assert any(d["duty_name"] == "Main Entrance" for d in duties)

    def test_D3_staff_can_complete_duty(self):
        assign_r = self.client.post(
            "/api/v1/staff/duties",
            json={"society_id": str(self.society.id), "staff_id": self.guard_staff["id"],
                  "duty_name": "Night Watch", "duty_date": str(date.today()),
                  "start_time": "20:00:00", "end_time": "08:00:00"},
            headers=self.supervisor["headers"],
        )
        duty_id = assign_r.json()["id"]
        r = self.client.post(
            f"/api/v1/staff/duties/{duty_id}/complete",
            headers=self.staff_user["headers"],
        )
        assert r.status_code == 200, f"Complete duty failed: {r.text}"
        assert r.json()["is_completed"] is True
        assert r.json()["completed_at"] is not None

    def test_D4_supervisor_verifies_completed_duty(self):
        assign_r = self.client.post(
            "/api/v1/staff/duties",
            json={"society_id": str(self.society.id), "staff_id": self.guard_staff["id"],
                  "duty_name": "Verify Test", "duty_date": str(date.today()),
                  "start_time": "08:00:00", "end_time": "16:00:00"},
            headers=self.supervisor["headers"],
        )
        duty_id = assign_r.json()["id"]
        self.client.post(f"/api/v1/staff/duties/{duty_id}/complete",
                         headers=self.staff_user["headers"])
        r = self.client.post(
            f"/api/v1/staff/duties/{duty_id}/verify",
            json={"notes": "Verified on round"},
            headers=self.supervisor["headers"],
        )
        assert r.status_code == 200, f"Verify duty failed: {r.text}"
        assert r.json()["verified_by"] is not None

    def test_D5_cannot_complete_already_completed_duty(self):
        assign_r = self.client.post(
            "/api/v1/staff/duties",
            json={"society_id": str(self.society.id), "staff_id": self.guard_staff["id"],
                  "duty_name": "Dup Complete", "duty_date": str(date.today()),
                  "start_time": "08:00:00", "end_time": "16:00:00"},
            headers=self.supervisor["headers"],
        )
        duty_id = assign_r.json()["id"]
        self.client.post(f"/api/v1/staff/duties/{duty_id}/complete",
                         headers=self.staff_user["headers"])
        r2 = self.client.post(f"/api/v1/staff/duties/{duty_id}/complete",
                              headers=self.staff_user["headers"])
        assert r2.status_code == 409


# ── Test E: Punch Out + Checkout Approval + Working Hours ────────────────────

class TestPunchOut:
    """Punch-out records working hours; supervisor approves checkout."""

    @pytest.fixture(autouse=True)
    def setup(self, client, db):
        _seed_roles(db)
        self.client = client
        self.db = db
        self.society = make_society(db, "Accept Society E")
        self.admin = make_user(db, "adm5@accept.io", role="Society Admin")
        self.supervisor = make_user(db, "supe@accept.io", role="Security Supervisor")
        _set_society(db, self.supervisor["user"], self.society.id)
        self.guard_staff = _create_staff(
            client, self.admin["headers"], self.society.id,
            "Guard E1", "9815000001", "guarde1@stafftest.io", "security",
        )

    def test_E1_checkout_computes_working_hours(self):
        _make_attendance(self.db, self.society.id, self.guard_staff["id"], checkin_hours_ago=8)
        r = self.client.post(
            f"/api/v1/staff/attendance/{self.guard_staff['id']}/checkout",
            json={"notes": "End of shift"},
            headers=self.supervisor["headers"],
        )
        assert r.status_code == 200, f"Checkout failed: {r.text}"
        data = r.json()
        assert data["check_out_time"] is not None
        assert data["working_hours"] is not None
        assert float(data["working_hours"]) >= 7.9, f"Expected ~8h, got {data['working_hours']}"

    def test_E2_overtime_computed_when_over_8h(self):
        _make_attendance(self.db, self.society.id, self.guard_staff["id"], checkin_hours_ago=9)
        r = self.client.post(
            f"/api/v1/staff/attendance/{self.guard_staff['id']}/checkout",
            json={}, headers=self.supervisor["headers"],
        )
        assert r.status_code == 200
        data = r.json()
        assert data["overtime_hours"] is not None
        assert float(data["overtime_hours"]) >= 0.9, f"Expected ~1h OT, got {data['overtime_hours']}"

    def test_E3_supervisor_approves_checkout(self):
        att = _make_attendance(self.db, self.society.id, self.guard_staff["id"],
                               checkin_hours_ago=8, with_checkout=True)
        r = self.client.post(
            f"/api/v1/staff/attendance/{att.id}/approve-checkout",
            json={"notes": "Checkout confirmed"},
            headers=self.supervisor["headers"],
        )
        assert r.status_code == 200, f"Checkout approval failed: {r.text}"
        data = r.json()
        assert data["is_checkout_approved"] is True
        assert data["checkout_approval_notes"] == "Checkout confirmed"

    def test_E4_checkout_without_checkin_fails(self):
        from app.modules.staff.models.staff import Staff, StaffDepartment, StaffStatus
        fresh_staff = Staff(
            society_id=self.society.id, employee_code="EMP-FRESH99",
            full_name="Fresh Guard", mobile="9815099999",
            department=StaffDepartment.SECURITY, status=StaffStatus.ACTIVE,
        )
        self.db.add(fresh_staff); self.db.commit()
        r = self.client.post(
            f"/api/v1/staff/attendance/{fresh_staff.id}/checkout",
            json={}, headers=self.supervisor["headers"],
        )
        assert r.status_code == 404

    def test_E5_full_attendance_closure(self):
        """Full cycle: checkin → checkout → approve checkin → approve checkout."""
        ci = self.client.post(
            f"/api/v1/staff/attendance/{self.guard_staff['id']}/checkin",
            json={}, headers=self.supervisor["headers"],
        )
        assert ci.status_code == 200
        att_id = ci.json()["id"]

        co = self.client.post(
            f"/api/v1/staff/attendance/{self.guard_staff['id']}/checkout",
            json={}, headers=self.supervisor["headers"],
        )
        assert co.status_code == 200
        assert co.json()["working_hours"] is not None

        ap_in = self.client.post(f"/api/v1/staff/attendance/{att_id}/approve",
                                 json={}, headers=self.supervisor["headers"])
        assert ap_in.status_code == 200
        assert ap_in.json()["is_approved"] is True

        ap_out = self.client.post(f"/api/v1/staff/attendance/{att_id}/approve-checkout",
                                  json={}, headers=self.supervisor["headers"])
        assert ap_out.status_code == 200
        assert ap_out.json()["is_checkout_approved"] is True


# ── Test F: Role Validation (Dept Enforcement) ────────────────────────────────

class TestRoleValidation:
    """
    Security Supervisor → security only.
    Housekeeping Supervisor → housekeeping + gym.
    Manager → all departments.
    """

    @pytest.fixture(autouse=True)
    def setup(self, client, db):
        _seed_roles(db)
        self.client = client
        self.db = db
        self.society = make_society(db, "Accept Society F")
        self.admin = make_user(db, "adm6@accept.io", role="Society Admin")

        self.sec_sup = make_user(db, "secsup@accept.io",  role="Security Supervisor")
        self.hk_sup  = make_user(db, "hksup@accept.io",   role="Housekeeping Supervisor")
        self.manager = make_user(db, "mgr@accept.io",     role="Manager")
        for u in [self.sec_sup, self.hk_sup, self.manager]:
            _set_society(db, u["user"], self.society.id)

        self.guard = _create_staff(client, self.admin["headers"], self.society.id,
                                   "Guard F1", "9816000001", "guardf1@stafftest.io", "security")
        self.hk_staff = _create_staff(client, self.admin["headers"], self.society.id,
                                      "Hk F1", "9816000002", "hkf1@stafftest.io", "housekeeping")
        self.gym_trainer = _create_staff(client, self.admin["headers"], self.society.id,
                                         "Gym F1", "9816000003", "gymf1@stafftest.io", "gym")
        self.tech = _create_staff(client, self.admin["headers"], self.society.id,
                                  "Tech F1", "9816000004", "techf1@stafftest.io", "technical")

    # ── Security Supervisor ────────────────────────────────────────────────────

    def test_F1_security_supervisor_approves_security_guard(self):
        att = _make_attendance(self.db, self.society.id, self.guard["id"])
        r = self.client.post(f"/api/v1/staff/attendance/{att.id}/approve",
                             json={}, headers=self.sec_sup["headers"])
        assert r.status_code == 200, f"Sec sup should approve security guard: {r.text}"
        assert r.json()["is_approved"] is True

    def test_F2_security_supervisor_cannot_approve_housekeeping(self):
        att = _make_attendance(self.db, self.society.id, self.hk_staff["id"])
        r = self.client.post(f"/api/v1/staff/attendance/{att.id}/approve",
                             json={}, headers=self.sec_sup["headers"])
        assert r.status_code == 403, f"Sec sup must NOT approve HK staff: {r.status_code}"

    def test_F3_security_supervisor_cannot_approve_gym(self):
        att = _make_attendance(self.db, self.society.id, self.gym_trainer["id"])
        r = self.client.post(f"/api/v1/staff/attendance/{att.id}/approve",
                             json={}, headers=self.sec_sup["headers"])
        assert r.status_code == 403

    def test_F4_security_supervisor_cannot_approve_technical(self):
        att = _make_attendance(self.db, self.society.id, self.tech["id"])
        r = self.client.post(f"/api/v1/staff/attendance/{att.id}/approve",
                             json={}, headers=self.sec_sup["headers"])
        assert r.status_code == 403

    # ── Housekeeping Supervisor ────────────────────────────────────────────────

    def test_F5_hk_supervisor_approves_housekeeping_staff(self):
        att = _make_attendance(self.db, self.society.id, self.hk_staff["id"])
        r = self.client.post(f"/api/v1/staff/attendance/{att.id}/approve",
                             json={}, headers=self.hk_sup["headers"])
        assert r.status_code == 200, f"HK sup should approve HK staff: {r.text}"
        assert r.json()["is_approved"] is True

    def test_F6_hk_supervisor_approves_gym_trainer(self):
        """Gym department is supervised by Housekeeping Supervisor."""
        att = _make_attendance(self.db, self.society.id, self.gym_trainer["id"])
        r = self.client.post(f"/api/v1/staff/attendance/{att.id}/approve",
                             json={}, headers=self.hk_sup["headers"])
        assert r.status_code == 200, f"HK sup should approve Gym Trainer: {r.text}"
        assert r.json()["is_approved"] is True

    def test_F7_hk_supervisor_cannot_approve_security(self):
        att = _make_attendance(self.db, self.society.id, self.guard["id"])
        r = self.client.post(f"/api/v1/staff/attendance/{att.id}/approve",
                             json={}, headers=self.hk_sup["headers"])
        assert r.status_code == 403

    def test_F8_hk_supervisor_cannot_approve_technical(self):
        att = _make_attendance(self.db, self.society.id, self.tech["id"])
        r = self.client.post(f"/api/v1/staff/attendance/{att.id}/approve",
                             json={}, headers=self.hk_sup["headers"])
        assert r.status_code == 403

    # ── Manager ───────────────────────────────────────────────────────────────

    def test_F9_manager_approves_security_guard(self):
        att = _make_attendance(self.db, self.society.id, self.guard["id"])
        r = self.client.post(f"/api/v1/staff/attendance/{att.id}/approve",
                             json={}, headers=self.manager["headers"])
        assert r.status_code == 200

    def test_F10_manager_approves_housekeeping_staff(self):
        att = _make_attendance(self.db, self.society.id, self.hk_staff["id"])
        r = self.client.post(f"/api/v1/staff/attendance/{att.id}/approve",
                             json={}, headers=self.manager["headers"])
        assert r.status_code == 200

    def test_F11_manager_approves_technical_staff(self):
        att = _make_attendance(self.db, self.society.id, self.tech["id"])
        r = self.client.post(f"/api/v1/staff/attendance/{att.id}/approve",
                             json={}, headers=self.manager["headers"])
        assert r.status_code == 200

    def test_F12_manager_approves_gym_trainer(self):
        att = _make_attendance(self.db, self.society.id, self.gym_trainer["id"])
        r = self.client.post(f"/api/v1/staff/attendance/{att.id}/approve",
                             json={}, headers=self.manager["headers"])
        assert r.status_code == 200

    # ── Checkout approval role validation ─────────────────────────────────────

    def test_F13_security_supervisor_approves_own_dept_checkout(self):
        att = _make_attendance(self.db, self.society.id, self.guard["id"], with_checkout=True)
        r = self.client.post(f"/api/v1/staff/attendance/{att.id}/approve-checkout",
                             json={}, headers=self.sec_sup["headers"])
        assert r.status_code == 200

    def test_F14_security_supervisor_cannot_approve_hk_checkout(self):
        att = _make_attendance(self.db, self.society.id, self.hk_staff["id"], with_checkout=True)
        r = self.client.post(f"/api/v1/staff/attendance/{att.id}/approve-checkout",
                             json={}, headers=self.sec_sup["headers"])
        assert r.status_code == 403


# ── Test G: Multi-Tenant Isolation ────────────────────────────────────────────

class TestMultiTenantIsolation:
    """Staff and attendance records from Society A are forbidden to Society B actors."""

    @pytest.fixture(autouse=True)
    def setup(self, client, db):
        _seed_roles(db)
        self.client = client
        self.db = db
        self.society_a = make_society(db, "Society Alpha")
        self.society_b = make_society(db, "Society Beta")

        self.admin_a = make_user(db, "adma@mt.io", role="Society Admin")
        self.admin_b = make_user(db, "admb@mt.io", role="Society Admin")
        _set_society(db, self.admin_a["user"], self.society_a.id)
        _set_society(db, self.admin_b["user"], self.society_b.id)

        self.sup_a = make_user(db, "supa@mt.io", role="Security Supervisor")
        self.sup_b = make_user(db, "supb@mt.io", role="Security Supervisor")
        _set_society(db, self.sup_a["user"], self.society_a.id)
        _set_society(db, self.sup_b["user"], self.society_b.id)

        self.guard_a = _create_staff(
            client, self.admin_a["headers"], self.society_a.id,
            "Guard A", "9817000001", "guarda@mt.io", "security",
        )
        self.guard_b = _create_staff(
            client, self.admin_b["headers"], self.society_b.id,
            "Guard B", "9817000002", "guardb@mt.io", "security",
        )

    def test_G1_supervisor_a_cannot_approve_society_b_attendance(self):
        """Society A supervisor cannot approve Society B attendance record."""
        att = _make_attendance(self.db, self.society_b.id, self.guard_b["id"])
        r = self.client.post(
            f"/api/v1/staff/attendance/{att.id}/approve",
            json={}, headers=self.sup_a["headers"],
        )
        assert r.status_code == 403, f"Cross-society approval must be blocked: {r.status_code} {r.text}"

    def test_G2_supervisor_b_cannot_approve_society_a_attendance(self):
        """Bidirectional: Society B supervisor cannot approve Society A records."""
        att = _make_attendance(self.db, self.society_a.id, self.guard_a["id"])
        r = self.client.post(
            f"/api/v1/staff/attendance/{att.id}/approve",
            json={}, headers=self.sup_b["headers"],
        )
        assert r.status_code == 403, f"Cross-society approval must be blocked (B→A): {r.text}"

    def test_G3_supervisor_a_cannot_approve_society_b_checkout(self):
        att = _make_attendance(self.db, self.society_b.id, self.guard_b["id"], with_checkout=True)
        r = self.client.post(
            f"/api/v1/staff/attendance/{att.id}/approve-checkout",
            json={}, headers=self.sup_a["headers"],
        )
        assert r.status_code == 403

    def test_G4_supervisor_a_can_approve_own_society_attendance(self):
        """Positive control: Society A supervisor can approve Society A record."""
        att = _make_attendance(self.db, self.society_a.id, self.guard_a["id"])
        r = self.client.post(
            f"/api/v1/staff/attendance/{att.id}/approve",
            json={}, headers=self.sup_a["headers"],
        )
        assert r.status_code == 200, f"Own society approval must succeed: {r.text}"

    def test_G5_staff_list_scoped_to_society(self):
        """Admin A sees only Society A staff; Guard B is invisible."""
        r = self.client.get(
            f"/api/v1/staff/society/{self.society_a.id}",
            headers=self.admin_a["headers"],
        )
        assert r.status_code == 200
        staff_ids = [s["id"] for s in r.json()]
        assert self.guard_a["id"] in staff_ids, "Guard A should be visible to Admin A"
        assert self.guard_b["id"] not in staff_ids, "Guard B must NOT be visible to Admin A"

    def test_G6_supervisor_can_punch_in_only_own_society_staff(self):
        """Society A supervisor can punch in Society A guard (positive control)."""
        r = self.client.post(
            f"/api/v1/staff/attendance/{self.guard_a['id']}/checkin",
            json={}, headers=self.sup_a["headers"],
        )
        assert r.status_code == 200, f"Same-society punch-in should succeed: {r.text}"
