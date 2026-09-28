"""The Manager runs the society's staff: the staff master, designations and
shifts, attendance, leaves, roster and checklist templates. Residents
still can't."""
from tests.conftest import make_society, make_user


def test_manager_runs_the_staff_module(client, db):
    society = make_society(db, "Manager Staff Society")
    h, sid = make_user(db, "mgr@staffmgr.io", role="Manager")["headers"], str(society.id)

    r = client.post("/api/v1/staff/", json={
        "society_id": sid, "full_name": "Ramesh Guard", "mobile": "9811100011", "department": "security",
    }, headers=h)
    assert r.status_code == 201, r.text
    staff_id = r.json()["id"]
    r = client.patch(f"/api/v1/staff/{staff_id}", json={"full_name": "Ramesh Gaikwad"}, headers=h)
    assert r.status_code == 200 and r.json()["full_name"] == "Ramesh Gaikwad", r.text

    for path in (f"/api/v1/staff/designations/{sid}", f"/api/v1/staff/shifts/{sid}",
                 f"/api/v1/staff/attendance/daily/{sid}?att_date=2026-09-27", f"/api/v1/staff/attendance/pending/{sid}",
                 f"/api/v1/staff/leaves/pending/{sid}", f"/api/v1/staff/roster/society/{sid}",
                 f"/api/v1/staff/tasks/society/{sid}", f"/api/v1/staff/society/{sid}/department/security"):
        assert client.get(path, headers=h).status_code == 200, path

    r = client.post("/api/v1/staff/checklist-templates", json={
        "society_id": sid, "department": "security", "name": "Night patrol",
        "items": [{"title": "Check gate lock"}],
    }, headers=h)
    assert r.status_code == 201, r.text


def test_resident_cannot_manage_staff(client, db):
    society = make_society(db, "Resident Staff Society")
    h, sid = make_user(db, "res@staffmgr.io", role="Resident")["headers"], str(society.id)
    r = client.post("/api/v1/staff/", json={
        "society_id": sid, "full_name": "X", "mobile": "9811100012", "department": "security",
    }, headers=h)
    assert r.status_code == 403
    assert client.get(f"/api/v1/staff/attendance/daily/{sid}?att_date=2026-09-27", headers=h).status_code == 403
