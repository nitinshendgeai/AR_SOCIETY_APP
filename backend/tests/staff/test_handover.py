"""Shift handover / takeover workflow tests."""
import pytest
from tests.conftest import make_user, make_society


def _make_staff(db, society_id, code, name):
    from app.modules.staff.models.staff import Staff, StaffDepartment, StaffStatus
    s = Staff(society_id=society_id, employee_code=code, full_name=name,
              mobile=f"90{abs(hash(code)) % 99999999:08d}",
              department=StaffDepartment.SECURITY, status=StaffStatus.ACTIVE)
    db.add(s); db.commit(); db.refresh(s)
    return s


def test_create_handover(client, db):
    admin   = make_user(db, "adm@hndov.com", role="Admin")
    society = make_society(db, "Handover Society")
    out     = _make_staff(db, society.id, "HND-001", "Guard Out")
    inc     = _make_staff(db, society.id, "HND-002", "Guard Inc")

    r = client.post("/api/v1/handovers/", json={
        "society_id":        str(society.id),
        "outgoing_staff_id": str(out.id),
        "incoming_staff_id": str(inc.id),
        "area":    "Main Gate",
        "summary": "All clear, 3 visitors inside.",
        "items": [
            {"item_type": "key",   "title": "Main Gate Keys", "quantity": 2},
            {"item_type": "visitor", "title": "Sharma Family still inside", "is_urgent": False},
        ]
    }, headers=admin["headers"])
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "draft"


def test_submit_and_accept_handover(client, db):
    admin   = make_user(db, "adm2@hndov.com", role="Admin")
    society = make_society(db, "Handover Society 2")
    out     = _make_staff(db, society.id, "HND-003", "Guard 3")
    inc     = _make_staff(db, society.id, "HND-004", "Guard 4")

    # Create
    create_r = client.post("/api/v1/handovers/", json={
        "society_id": str(society.id),
        "outgoing_staff_id": str(out.id),
        "incoming_staff_id": str(inc.id),
        "area": "Lobby", "summary": "Quiet shift."
    }, headers=admin["headers"])
    hid = create_r.json()["id"]

    # Submit
    submit_r = client.post(f"/api/v1/handovers/{hid}/submit",
                           headers=admin["headers"])
    assert submit_r.status_code == 200
    assert submit_r.json()["status"] == "submitted"

    # Accept
    accept_r = client.post(f"/api/v1/handovers/{hid}/accept",
                           json={"notes": "All received, keys count OK"},
                           headers=admin["headers"])
    assert accept_r.status_code == 200
    assert accept_r.json()["status"] == "accepted"


def test_cannot_submit_without_incoming_staff(client, db):
    admin   = make_user(db, "adm3@hndov.com", role="Admin")
    society = make_society(db, "Handover Society 3")
    out     = _make_staff(db, society.id, "HND-005", "Guard 5")

    create_r = client.post("/api/v1/handovers/", json={
        "society_id": str(society.id),
        "outgoing_staff_id": str(out.id),
        # NO incoming_staff_id
        "area": "Gate", "summary": "End of shift."
    }, headers=admin["headers"])
    hid = create_r.json()["id"]

    r = client.post(f"/api/v1/handovers/{hid}/submit",
                    headers=admin["headers"])
    assert r.status_code == 422


def test_dispute_and_resubmit(client, db):
    admin   = make_user(db, "adm4@hndov.com", role="Admin")
    society = make_society(db, "Handover Society 4")
    out     = _make_staff(db, society.id, "HND-006", "Guard 6")
    inc     = _make_staff(db, society.id, "HND-007", "Guard 7")

    # Create + submit
    r1 = client.post("/api/v1/handovers/", json={
        "society_id": str(society.id), "outgoing_staff_id": str(out.id),
        "incoming_staff_id": str(inc.id), "area": "B-Block", "summary": "Nothing to report"
    }, headers=admin["headers"])
    hid = r1.json()["id"]
    client.post(f"/api/v1/handovers/{hid}/submit", headers=admin["headers"])

    # Dispute
    r2 = client.post(f"/api/v1/handovers/{hid}/dispute",
                     json={"reason": "CCTV camera was not working — needs maintenance ticket"},
                     headers=admin["headers"])
    assert r2.status_code == 200
    assert r2.json()["status"] == "disputed"


def test_invalid_transition_blocked(client, db):
    """Cannot accept a DRAFT handover (must submit first)."""
    admin   = make_user(db, "adm5@hndov.com", role="Admin")
    society = make_society(db, "Handover Society 5")
    out     = _make_staff(db, society.id, "HND-008", "Guard 8")
    inc     = _make_staff(db, society.id, "HND-009", "Guard 9")

    r = client.post("/api/v1/handovers/", json={
        "society_id": str(society.id), "outgoing_staff_id": str(out.id),
        "incoming_staff_id": str(inc.id), "area": "C-Block", "summary": "Test"
    }, headers=admin["headers"])
    hid = r.json()["id"]

    # Try to accept directly from DRAFT (should fail)
    r2 = client.post(f"/api/v1/handovers/{hid}/accept",
                     json={"notes": "skip submit"}, headers=admin["headers"])
    assert r2.status_code == 409


def test_get_pending_handovers(client, db):
    admin   = make_user(db, "adm6@hndov.com", role="Admin")
    society = make_society(db, "Handover Society 6")
    out     = _make_staff(db, society.id, "HND-010", "Guard 10")
    inc     = _make_staff(db, society.id, "HND-011", "Guard 11")

    create_r = client.post("/api/v1/handovers/", json={
        "society_id": str(society.id), "outgoing_staff_id": str(out.id),
        "incoming_staff_id": str(inc.id), "area": "Gate", "summary": "End of day"
    }, headers=admin["headers"])
    hid = create_r.json()["id"]
    client.post(f"/api/v1/handovers/{hid}/submit", headers=admin["headers"])

    r = client.get(f"/api/v1/handovers/pending/{inc.id}", headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()) >= 1
