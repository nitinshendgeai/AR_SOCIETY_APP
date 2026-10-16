"""Phase 1 — payroll was reachable across societies (and by any staff for any colleague).

Every call below is made by society A's people against society B's records. Before the fix each of them
succeeded (read or wrote B's salary, corrections and monthly summaries).
"""
import uuid

import pytest

from tests.security.world import API, correction_body, salary_body

P = f"{API}/payroll"


def _refused(r):
    return r.status_code in (403, 404)


# ── society A's admin against society B ──────────────────────────────────────

def test_admin_of_a_cannot_read_b_salary(client, world):
    r = client.get(f"{P}/salary-structure/{world.staff_b.id}", headers=world.admin_a["headers"])
    assert _refused(r), r.text


def test_admin_of_a_cannot_set_b_salary(client, db, world):
    from app.modules.staff.models.payroll_readiness import StaffSalaryStructure
    before = db.query(StaffSalaryStructure).filter_by(staff_id=world.staff_b.id).count()
    for sid in (world.B.id, world.A.id):               # B's staff under B's id, and under the caller's own id
        r = client.post(f"{P}/salary-structure", json=salary_body(sid, world.staff_b.id, basic=1),
                        headers=world.admin_a["headers"])
        assert _refused(r) or r.status_code == 422, r.text
    assert db.query(StaffSalaryStructure).filter_by(staff_id=world.staff_b.id).count() == before


def test_admin_of_a_cannot_aggregate_or_read_b_monthly_summary(client, db, world):
    from app.modules.staff.models.payroll_readiness import MonthlyAttendanceSummary
    r = client.post(f"{P}/monthly-summary/{world.B.id}/{world.staff_b.id}/2026/10", headers=world.admin_a["headers"])
    assert _refused(r), r.text
    r = client.post(f"{P}/monthly-summary/{world.A.id}/{world.staff_b.id}/2026/10", headers=world.admin_a["headers"])
    assert _refused(r), r.text
    assert db.query(MonthlyAttendanceSummary).filter_by(staff_id=world.staff_b.id, month=10).count() == 0
    r = client.get(f"{P}/monthly-summary/{world.staff_b.id}/2026/9", headers=world.admin_a["headers"])
    assert _refused(r), r.text


def test_admin_of_a_cannot_finalize_b_summary(client, db, world):
    from app.modules.staff.models.payroll_readiness import MonthlyAttendanceSummary
    r = client.post(f"{P}/monthly-summary/{world.summary_b}/finalize", headers=world.admin_a["headers"])
    assert _refused(r), r.text
    db.expire_all()
    assert db.get(MonthlyAttendanceSummary, uuid.UUID(world.summary_b)).is_finalized is False


def test_a_cannot_list_or_file_corrections_in_b(client, db, world):
    from app.modules.staff.models.payroll_readiness import AttendanceCorrection
    h = world.admin_a["headers"]
    assert _refused(client.get(f"{P}/attendance-correction/society/{world.B.id}", headers=h))
    assert _refused(client.get(f"{P}/attendance-correction/staff/{world.staff_b.id}", headers=h))
    before = db.query(AttendanceCorrection).filter_by(society_id=world.B.id).count()
    r = client.post(f"{P}/attendance-correction", json=correction_body(world.B.id, world.staff_b.id, world.att_b.id), headers=h)
    assert _refused(r), r.text
    # naming one of A's own societies but B's staff and attendance must not slip through either
    r = client.post(f"{P}/attendance-correction", json=correction_body(world.A.id, world.staff_b.id, world.att_b.id), headers=h)
    assert _refused(r), r.text
    assert db.query(AttendanceCorrection).filter_by(society_id=world.B.id).count() == before


def test_a_manager_cannot_approve_or_reject_b_correction(client, db, world):
    from app.modules.staff.models.payroll_readiness import AttendanceCorrection, AttendanceCorrectionStatus
    h = world.manager_a["headers"]
    assert _refused(client.post(f"{P}/attendance-correction/{world.correction_b}/approve", headers=h))
    assert _refused(client.post(f"{P}/attendance-correction/{world.correction_b}/reject", json={"reason": "no"}, headers=h))
    db.expire_all()
    assert db.get(AttendanceCorrection, uuid.UUID(world.correction_b)).status == AttendanceCorrectionStatus.PENDING


# ── ownership inside one society ─────────────────────────────────────────────

def test_staff_can_file_for_self_but_not_for_a_colleague(client, world):
    h = world.security_a["headers"]                    # the login of staff_a
    own = client.post(f"{P}/attendance-correction", json=correction_body(world.A.id, world.staff_a.id, world.att_a.id), headers=h)
    assert own.status_code == 201, own.text
    other = client.post(f"{P}/attendance-correction", json=correction_body(world.A.id, world.staff_a2.id, world.att_a2.id), headers=h)
    assert other.status_code == 403, other.text


def test_staff_can_read_own_corrections_not_a_colleagues(client, world):
    h = world.security_a["headers"]
    assert client.get(f"{P}/attendance-correction/staff/{world.staff_a.id}", headers=h).status_code == 200
    assert client.get(f"{P}/attendance-correction/staff/{world.staff_a2.id}", headers=h).status_code == 403


def test_a_supervisor_may_file_for_any_staff_of_their_society(client, world):
    r = client.post(f"{P}/attendance-correction", json=correction_body(world.A.id, world.staff_a2.id, world.att_a2.id),
                    headers=world.supervisor_a["headers"])
    assert r.status_code == 201, r.text


# ── who may approve (role, not just society) ─────────────────────────────────

@pytest.mark.parametrize("who", ["resident_a", "security_a", "supervisor_a"])
def test_only_manager_and_above_decide_corrections(client, world, who):
    created = client.post(f"{P}/attendance-correction", json=correction_body(world.A.id, world.staff_a.id, world.att_a.id),
                          headers=world.manager_a["headers"]).json()["id"]
    h = getattr(world, who)["headers"]
    assert client.post(f"{P}/attendance-correction/{created}/approve", headers=h).status_code == 403
    assert client.post(f"{P}/attendance-correction/{created}/reject", json={"reason": "x"}, headers=h).status_code == 403


def test_resident_cannot_reach_salary_or_summaries(client, world):
    h = world.resident_a["headers"]
    assert client.get(f"{P}/salary-structure/{world.staff_a.id}", headers=h).status_code == 403
    assert client.post(f"{P}/salary-structure", json=salary_body(world.A.id, world.staff_a.id), headers=h).status_code == 403
    assert client.get(f"{P}/monthly-summary/{world.staff_a.id}/2026/9", headers=h).status_code == 403


# ── legitimate use is unchanged ──────────────────────────────────────────────

def test_society_b_runs_its_own_payroll_end_to_end(client, world):
    h = world.admin_b["headers"]
    assert client.get(f"{P}/salary-structure/{world.staff_b.id}", headers=h).json()["basic_salary"] == "15000.00"
    assert client.get(f"{P}/attendance-correction/society/{world.B.id}", headers=h).json()
    assert client.get(f"{P}/monthly-summary/{world.staff_b.id}/2026/9", headers=h).status_code == 200
    assert client.post(f"{P}/attendance-correction/{world.correction_b}/approve", headers=world.manager_b["headers"]).status_code == 200
    assert client.post(f"{P}/monthly-summary/{world.summary_b}/finalize", headers=h).status_code == 200


def test_a_salary_for_a_staff_member_of_another_society_is_refused_even_with_the_right_society_id(client, world):
    """The body's society must be the caller's and the staff member must belong to it."""
    r = client.post(f"{P}/salary-structure", json=salary_body(world.A.id, world.staff_a.id, basic=9000),
                    headers=world.admin_a["headers"])
    assert r.status_code == 201, r.text
    assert r.json()["society_id"] == str(world.A.id)


# ── the platform admin keeps its (explicit) cross-society reach ──────────────

def test_platform_admin_still_reaches_every_society(client, world):
    h = world.platform["headers"]
    assert client.get(f"{P}/salary-structure/{world.staff_b.id}", headers=h).status_code == 200
    assert client.get(f"{P}/attendance-correction/society/{world.B.id}", headers=h).status_code == 200
    assert client.get(f"{P}/attendance-correction/society/{world.A.id}", headers=h).status_code == 200
    assert client.get(f"{P}/monthly-summary/{world.staff_b.id}/2026/9", headers=h).status_code == 200
    r = client.post(f"{P}/salary-structure", json=salary_body(world.B.id, world.staff_b.id, basic=16000), headers=h)
    assert r.status_code == 201 and r.json()["society_id"] == str(world.B.id)
    # a platform admin must name a society that actually owns the staff member
    r = client.post(f"{P}/salary-structure", json=salary_body(world.A.id, world.staff_b.id), headers=h)
    assert r.status_code == 422, r.text
