"""Complaint module tests — lifecycle FSM, validation, RBAC."""
import pytest
from tests.conftest import make_user, make_society, make_wing, make_flat


def _complaint_payload(society_id):
    return {
        "title": "Water leak in kitchen",
        "description": "Pipe burst under the sink.",
        "category": "plumbing",
        "priority": "high",
        "society_id": str(society_id),
    }


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_complaint_success(client, db):
    resident = make_user(db, "res@cmp.com", role="Resident")
    society  = make_society(db, "Complaint Society 1")
    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id),
                    headers=resident["headers"])
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "open"
    assert data["complaint_number"].startswith("CMP-")
    assert data["raised_by"] == str(resident["user"].id)


def test_create_complaint_requires_auth(client, db):
    society = make_society(db, "Complaint Society Auth")
    r = client.post("/api/v1/complaints/", json=_complaint_payload(society.id))
    assert r.status_code in (401, 403)  # HTTPBearer returns 403 when no credentials


def test_unauthenticated_cannot_create_complaint(client, db):
    """No token at all must be rejected."""
    society = make_society(db, "Complaint Society Sec")
    r = client.post("/api/v1/complaints/", json=_complaint_payload(society.id))
    assert r.status_code in (401, 403)


def test_create_complaint_empty_title_rejected(client, db):
    resident = make_user(db, "res2@cmp.com", role="Resident")
    society  = make_society(db, "Complaint Society 2")
    payload  = _complaint_payload(society.id)
    payload["title"] = "   "
    r = client.post("/api/v1/complaints/", json=payload, headers=resident["headers"])
    assert r.status_code == 422


# ── Assign ────────────────────────────────────────────────────────────────────

def test_assign_complaint(client, db):
    admin   = make_user(db, "adm@cmp.com", role="Admin")
    staff   = make_user(db, "stf@cmp.com", role="Staff")
    society = make_society(db, "Complaint Society 3")

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id),
                    headers=admin["headers"])
    cid = r.json()["id"]

    r2 = client.post(f"/api/v1/complaints/{cid}/assign",
                     json={"assigned_to": str(staff["user"].id), "notes": "Please fix"},
                     headers=admin["headers"])
    assert r2.status_code == 200
    assert r2.json()["status"] == "assigned"
    assert r2.json()["assigned_to"] == str(staff["user"].id)


def test_resident_cannot_assign_complaint(client, db):
    resident = make_user(db, "res3@cmp.com", role="Resident")
    staff    = make_user(db, "stf2@cmp.com", role="Staff")
    society  = make_society(db, "Complaint Society 4")

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id),
                    headers=resident["headers"])
    cid = r.json()["id"]

    r2 = client.post(f"/api/v1/complaints/{cid}/assign",
                     json={"assigned_to": str(staff["user"].id)},
                     headers=resident["headers"])
    assert r2.status_code == 403


def test_invalid_transition_blocked(client, db):
    """Cannot go from OPEN → IN_PROGRESS (must go through ASSIGNED first)."""
    admin   = make_user(db, "adm2@cmp.com", role="Admin")
    society = make_society(db, "Complaint Society 5")

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id),
                    headers=admin["headers"])
    cid = r.json()["id"]

    r2 = client.post(f"/api/v1/complaints/{cid}/status",
                     json={"status": "in_progress"},
                     headers=admin["headers"])
    assert r2.status_code == 409


# ── Full lifecycle ────────────────────────────────────────────────────────────

def test_full_lifecycle_open_to_closed(client, db):
    admin   = make_user(db, "adm3@cmp.com", role="Admin")
    staff   = make_user(db, "stf3@cmp.com", role="Staff")
    society = make_society(db, "Complaint Society 6")

    # Create
    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id),
                    headers=admin["headers"])
    assert r.status_code == 201
    cid = r.json()["id"]

    # Assign
    client.post(f"/api/v1/complaints/{cid}/assign",
                json={"assigned_to": str(staff["user"].id)},
                headers=admin["headers"])

    # In progress
    client.post(f"/api/v1/complaints/{cid}/status",
                json={"status": "in_progress"},
                headers=staff["headers"])

    # Resolved
    client.post(f"/api/v1/complaints/{cid}/status",
                json={"status": "resolved", "resolution_notes": "Fixed the pipe."},
                headers=staff["headers"])

    # Close
    r_close = client.post(f"/api/v1/complaints/{cid}/status",
                          json={"status": "closed"},
                          headers=admin["headers"])
    assert r_close.status_code == 200
    assert r_close.json()["status"] == "closed"
    assert r_close.json()["closed_at"] is not None


def test_reopen_resolved_complaint(client, db):
    admin   = make_user(db, "adm4@cmp.com", role="Admin")
    staff   = make_user(db, "stf4@cmp.com", role="Staff")
    society = make_society(db, "Complaint Society 7")

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id),
                    headers=admin["headers"])
    cid = r.json()["id"]

    client.post(f"/api/v1/complaints/{cid}/assign",
                json={"assigned_to": str(staff["user"].id)},
                headers=admin["headers"])
    client.post(f"/api/v1/complaints/{cid}/status",
                json={"status": "in_progress"}, headers=staff["headers"])
    client.post(f"/api/v1/complaints/{cid}/status",
                json={"status": "resolved", "resolution_notes": "Fixed."},
                headers=staff["headers"])

    r_reopen = client.post(f"/api/v1/complaints/{cid}/reopen",
                           json={"reason": "Problem recurred"},
                           headers=admin["headers"])
    assert r_reopen.status_code == 200
    data = r_reopen.json()
    assert data["status"] == "reopened"
    assert data["reopen_count"] == 1


def test_cannot_reopen_open_complaint(client, db):
    admin   = make_user(db, "adm5@cmp.com", role="Admin")
    society = make_society(db, "Complaint Society 8")

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id),
                    headers=admin["headers"])
    cid = r.json()["id"]

    r2 = client.post(f"/api/v1/complaints/{cid}/reopen",
                     json={"reason": "Not resolved yet"},
                     headers=admin["headers"])
    assert r2.status_code == 409


def test_cannot_modify_closed_complaint(client, db):
    admin   = make_user(db, "adm6@cmp.com", role="Admin")
    staff   = make_user(db, "stf5@cmp.com", role="Staff")
    society = make_society(db, "Complaint Society 9")

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id),
                    headers=admin["headers"])
    cid = r.json()["id"]

    client.post(f"/api/v1/complaints/{cid}/assign",
                json={"assigned_to": str(staff["user"].id)},
                headers=admin["headers"])
    client.post(f"/api/v1/complaints/{cid}/status",
                json={"status": "in_progress"}, headers=staff["headers"])
    client.post(f"/api/v1/complaints/{cid}/status",
                json={"status": "resolved", "resolution_notes": "Done."},
                headers=staff["headers"])
    client.post(f"/api/v1/complaints/{cid}/status",
                json={"status": "closed"}, headers=admin["headers"])

    # Try to assign again — should fail (CLOSED has no valid transitions)
    r2 = client.post(f"/api/v1/complaints/{cid}/assign",
                     json={"assigned_to": str(staff["user"].id)},
                     headers=admin["headers"])
    assert r2.status_code == 409


# ── Comments ──────────────────────────────────────────────────────────────────

def test_add_comment_success(client, db):
    resident = make_user(db, "res4@cmp.com", role="Resident")
    society  = make_society(db, "Complaint Society 10")

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id),
                    headers=resident["headers"])
    cid = r.json()["id"]

    r2 = client.post(f"/api/v1/complaints/{cid}/comments",
                     json={"body": "When will this be fixed?", "is_internal": False},
                     headers=resident["headers"])
    assert r2.status_code == 201
    assert r2.json()["body"] == "When will this be fixed?"


def test_cannot_comment_on_closed_complaint(client, db):
    admin   = make_user(db, "adm7@cmp.com", role="Admin")
    staff   = make_user(db, "stf6@cmp.com", role="Staff")
    society = make_society(db, "Complaint Society 11")

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id),
                    headers=admin["headers"])
    cid = r.json()["id"]

    for step in [
        (f"/api/v1/complaints/{cid}/assign",
         {"assigned_to": str(staff["user"].id)}, admin["headers"]),
        (f"/api/v1/complaints/{cid}/status",
         {"status": "in_progress"}, staff["headers"]),
        (f"/api/v1/complaints/{cid}/status",
         {"status": "resolved", "resolution_notes": "Ok"}, staff["headers"]),
        (f"/api/v1/complaints/{cid}/status",
         {"status": "closed"}, admin["headers"]),
    ]:
        url, body, hdrs = step
        client.post(url, json=body, headers=hdrs)

    r2 = client.post(f"/api/v1/complaints/{cid}/comments",
                     json={"body": "Still broken", "is_internal": False},
                     headers=admin["headers"])
    assert r2.status_code == 409


# ── List endpoints ────────────────────────────────────────────────────────────

def test_list_society_complaints(client, db):
    admin   = make_user(db, "adm8@cmp.com", role="Admin")
    society = make_society(db, "Complaint Society 12")

    for i in range(3):
        payload = _complaint_payload(society.id)
        payload["title"] = f"Issue {i}"
        client.post("/api/v1/complaints/", json=payload, headers=admin["headers"])

    r = client.get(f"/api/v1/complaints/society/{society.id}",
                   headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_list_my_complaints(client, db):
    resident = make_user(db, "res5@cmp.com", role="Resident")
    society  = make_society(db, "Complaint Society 13")

    for i in range(2):
        p = _complaint_payload(society.id)
        p["title"] = f"My issue {i}"
        client.post("/api/v1/complaints/", json=p, headers=resident["headers"])

    r = client.get("/api/v1/complaints/me/complaints", headers=resident["headers"])
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_reject_complaint(client, db):
    admin   = make_user(db, "adm9@cmp.com", role="Admin")
    society = make_society(db, "Complaint Society 14")

    r = client.post("/api/v1/complaints/",
                    json=_complaint_payload(society.id),
                    headers=admin["headers"])
    cid = r.json()["id"]

    r2 = client.post(f"/api/v1/complaints/{cid}/status",
                     json={"status": "rejected", "rejection_reason": "Out of scope"},
                     headers=admin["headers"])
    assert r2.status_code == 200
    assert r2.json()["status"] == "rejected"
    assert r2.json()["rejection_reason"] == "Out of scope"
