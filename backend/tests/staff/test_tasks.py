"""Staff task FSM tests — creation, status transitions, RBAC."""
import pytest
from tests.conftest import make_user, make_society


def _make_staff(db, society_id, name="Worker"):
    from app.modules.staff.models.staff import Staff, StaffDepartment, StaffStatus
    staff = Staff(
        society_id=society_id, employee_code=f"EMP-{name[:4].upper()}",
        full_name=name, mobile=f"9{abs(hash(name)) % 999999999:09d}",
        department=StaffDepartment.MAINTENANCE, status=StaffStatus.ACTIVE,
    )
    db.add(staff); db.commit(); db.refresh(staff)
    return staff


def test_create_task_success(client, db):
    admin   = make_user(db, "admin@task.com", role="Admin")
    society = make_society(db, "Task Society")
    staff   = _make_staff(db, society.id)
    r = client.post(
        "/api/v1/staff/tasks",
        json={"society_id": str(society.id), "staff_id": str(staff.id),
              "title": "Fix water pump", "priority": "high"},
        headers=admin["headers"],
    )
    assert r.status_code == 201
    data = r.json()
    assert data["title"] == "Fix water pump"
    assert data["status"] == "assigned"


def test_create_task_requires_admin_or_committee(client, db):
    resident = make_user(db, "res@task.com", role="Resident")
    society  = make_society(db, "Task Society 2")
    staff    = _make_staff(db, society.id, "Worker2")
    r = client.post(
        "/api/v1/staff/tasks",
        json={"society_id": str(society.id), "staff_id": str(staff.id),
              "title": "Resident tries to assign task"},
        headers=resident["headers"],
    )
    assert r.status_code == 403


def test_task_status_assigned_to_acknowledged(client, db):
    admin   = make_user(db, "adm2@task.com", role="Admin")
    staff_u = make_user(db, "stf@task.com", role="Staff")
    society = make_society(db, "Task Society 3")
    staff   = _make_staff(db, society.id, "Worker3")
    # Create
    r = client.post(
        "/api/v1/staff/tasks",
        json={"society_id": str(society.id), "staff_id": str(staff.id),
              "title": "Clean lobby"},
        headers=admin["headers"],
    )
    assert r.status_code == 201
    task_id = r.json()["id"]
    # Acknowledge
    r2 = client.post(
        f"/api/v1/staff/tasks/{task_id}/status",
        json={"status": "acknowledged"},
        headers=staff_u["headers"],
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "acknowledged"


def test_task_invalid_transition_rejected(client, db):
    admin   = make_user(db, "adm3@task.com", role="Admin")
    society = make_society(db, "Task Society 4")
    staff   = _make_staff(db, society.id, "Worker4")
    r = client.post(
        "/api/v1/staff/tasks",
        json={"society_id": str(society.id), "staff_id": str(staff.id),
              "title": "Paint walls"},
        headers=admin["headers"],
    )
    task_id = r.json()["id"]
    # Skip directly to completed from assigned — invalid
    r2 = client.post(
        f"/api/v1/staff/tasks/{task_id}/status",
        json={"status": "completed"},
        headers=admin["headers"],
    )
    assert r2.status_code in (400, 409, 422)


def test_full_task_lifecycle(client, db):
    admin   = make_user(db, "adm4@task.com", role="Admin")
    society = make_society(db, "Task Society 5")
    staff   = _make_staff(db, society.id, "Worker5")
    # Create
    r = client.post(
        "/api/v1/staff/tasks",
        json={"society_id": str(society.id), "staff_id": str(staff.id),
              "title": "Full lifecycle task"},
        headers=admin["headers"],
    )
    task_id = r.json()["id"]
    for step in ["acknowledged", "in_progress", "completed"]:
        r = client.post(f"/api/v1/staff/tasks/{task_id}/status",
                        json={"status": step}, headers=admin["headers"])
        assert r.status_code == 200, f"Failed at step {step}: {r.text}"
        assert r.json()["status"] == step
    # Verify
    r = client.post(f"/api/v1/staff/tasks/{task_id}/status",
                    json={"status": "verified"}, headers=admin["headers"])
    assert r.status_code == 200
    assert r.json()["status"] == "verified"


def test_list_staff_tasks(client, db):
    admin   = make_user(db, "adm5@task.com", role="Admin")
    society = make_society(db, "Task Society 6")
    staff   = _make_staff(db, society.id, "Worker6")
    for i in range(3):
        client.post(
            "/api/v1/staff/tasks",
            json={"society_id": str(society.id), "staff_id": str(staff.id),
                  "title": f"Task {i}"},
            headers=admin["headers"],
        )
    r = client.get(f"/api/v1/staff/tasks/staff/{staff.id}",
                   headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()) >= 3


def test_unauthenticated_cannot_create_task(client, db):
    r = client.post("/api/v1/staff/tasks", json={"title": "Sneaky task"})
    assert r.status_code in (401, 403)
