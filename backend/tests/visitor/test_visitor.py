"""Visitor & gate management tests — entry/exit workflow, RBAC."""
import pytest
from tests.conftest import make_user, make_society, make_wing, make_flat


def _visitor_payload(society_id, flat_id=None):
    payload = {
        "name": "John Visitor",
        "mobile": "9876543210",
        "visitor_type": "guest",
        "purpose": "Meeting resident",
        "society_id": str(society_id),
    }
    if flat_id:
        payload["flat_id"] = str(flat_id)
    return payload


def _make_gate(client, admin_headers, society_id):
    r = client.post("/api/v1/visitors/gates",
                    json={
                        "society_id": str(society_id),
                        "name": "Main Gate",
                        "gate_type": "both",
                    },
                    headers=admin_headers)
    assert r.status_code == 201
    return r.json()


# ── Gate tests ────────────────────────────────────────────────────────────────

def test_create_gate_success(client, db):
    admin   = make_user(db, "adm@vis.com", role="Admin")
    society = make_society(db, "Visitor Society 1")
    r = client.post("/api/v1/visitors/gates",
                    json={"society_id": str(society.id), "name": "Gate 1", "gate_type": "both"},
                    headers=admin["headers"])
    assert r.status_code == 201
    assert r.json()["name"] == "Gate 1"


def test_non_admin_cannot_create_gate(client, db):
    security = make_user(db, "sec@vis.com", role="Security")
    society  = make_society(db, "Visitor Society 2")
    r = client.post("/api/v1/visitors/gates",
                    json={"society_id": str(society.id), "name": "Gate 2", "gate_type": "both"},
                    headers=security["headers"])
    assert r.status_code == 403


def test_list_gates(client, db):
    admin   = make_user(db, "adm2@vis.com", role="Admin")
    society = make_society(db, "Visitor Society 3")
    for i in range(2):
        client.post("/api/v1/visitors/gates",
                    json={"society_id": str(society.id), "name": f"Gate {i}", "gate_type": "both"},
                    headers=admin["headers"])
    r = client.get(f"/api/v1/visitors/gates/{society.id}", headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()) == 2


# ── Visitor workflow tests ────────────────────────────────────────────────────

def test_security_creates_visitor(client, db):
    admin    = make_user(db, "adm3@vis.com", role="Admin")
    security = make_user(db, "sec2@vis.com", role="Security")
    society  = make_society(db, "Visitor Society 4")

    r = client.post("/api/v1/visitors/",
                    json=_visitor_payload(society.id),
                    headers=security["headers"])
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "John Visitor"
    assert data["status"] == "pending"


def test_resident_cannot_create_visitor(client, db):
    """Visitors can only be created by Security or Admin."""
    resident = make_user(db, "res@vis.com", role="Resident")
    society  = make_society(db, "Visitor Society 5")
    r = client.post("/api/v1/visitors/",
                    json=_visitor_payload(society.id),
                    headers=resident["headers"])
    assert r.status_code == 403


def test_resident_approves_visitor(client, db):
    admin    = make_user(db, "adm4@vis.com", role="Admin")
    resident = make_user(db, "res2@vis.com", role="Resident")
    security = make_user(db, "sec3@vis.com", role="Security")
    society  = make_society(db, "Visitor Society 6")

    r = client.post("/api/v1/visitors/",
                    json=_visitor_payload(society.id),
                    headers=security["headers"])
    vid = r.json()["id"]

    r2 = client.post(f"/api/v1/visitors/{vid}/approve",
                     json={"notes": "Expected guest"},
                     headers=resident["headers"])
    assert r2.status_code == 200
    assert r2.json()["status"] == "approved"
    assert r2.json()["approved_at"] is not None


def test_resident_rejects_visitor(client, db):
    security = make_user(db, "sec4@vis.com", role="Security")
    resident = make_user(db, "res3@vis.com", role="Resident")
    society  = make_society(db, "Visitor Society 7")

    r = client.post("/api/v1/visitors/",
                    json=_visitor_payload(society.id),
                    headers=security["headers"])
    vid = r.json()["id"]

    r2 = client.post(f"/api/v1/visitors/{vid}/reject",
                     json={"reason": "Unknown person"},
                     headers=resident["headers"])
    assert r2.status_code == 200
    assert r2.json()["status"] == "rejected"
    assert r2.json()["rejection_reason"] == "Unknown person"


def test_check_in_visitor(client, db):
    admin    = make_user(db, "adm5@vis.com", role="Admin")
    security = make_user(db, "sec5@vis.com", role="Security")
    society  = make_society(db, "Visitor Society 8")

    r = client.post("/api/v1/visitors/",
                    json=_visitor_payload(society.id),
                    headers=security["headers"])
    vid = r.json()["id"]

    # Approve first
    client.post(f"/api/v1/visitors/{vid}/approve",
                json={"notes": ""}, headers=admin["headers"])

    # Check in
    r2 = client.post(f"/api/v1/visitors/{vid}/checkin",
                     json={"notes": "Visitor arrived"},
                     headers=security["headers"])
    assert r2.status_code == 200
    assert r2.json()["status"] == "checked_in"
    assert r2.json()["checked_in_at"] is not None


def test_check_out_visitor(client, db):
    admin    = make_user(db, "adm6@vis.com", role="Admin")
    security = make_user(db, "sec6@vis.com", role="Security")
    society  = make_society(db, "Visitor Society 9")

    r = client.post("/api/v1/visitors/",
                    json=_visitor_payload(society.id),
                    headers=security["headers"])
    vid = r.json()["id"]

    client.post(f"/api/v1/visitors/{vid}/approve",
                json={}, headers=admin["headers"])
    client.post(f"/api/v1/visitors/{vid}/checkin",
                json={}, headers=security["headers"])

    r2 = client.post(f"/api/v1/visitors/{vid}/checkout",
                     json={"notes": "Visitor left"},
                     headers=security["headers"])
    assert r2.status_code == 200
    assert r2.json()["status"] == "checked_out"
    assert r2.json()["checked_out_at"] is not None


def test_invalid_mobile_rejected(client, db):
    security = make_user(db, "sec7@vis.com", role="Security")
    society  = make_society(db, "Visitor Society 10")
    payload  = _visitor_payload(society.id)
    payload["mobile"] = "not-a-number"
    r = client.post("/api/v1/visitors/", json=payload, headers=security["headers"])
    assert r.status_code == 422


def test_list_visitors_for_society(client, db):
    admin    = make_user(db, "adm7@vis.com", role="Admin")
    security = make_user(db, "sec8@vis.com", role="Security")
    society  = make_society(db, "Visitor Society 11")

    for i in range(3):
        p = _visitor_payload(society.id)
        p["name"] = f"Visitor {i}"
        p["mobile"] = f"987654321{i}"
        client.post("/api/v1/visitors/", json=p, headers=security["headers"])

    r = client.get(f"/api/v1/visitors/society/{society.id}",
                   headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_pending_approvals_for_resident(client, db):
    security = make_user(db, "sec9@vis.com", role="Security")
    resident = make_user(db, "res4@vis.com", role="Resident")
    society  = make_society(db, "Visitor Society 12")
    wing     = make_wing(db, society.id, "V Wing")
    flat     = make_flat(db, wing.id, "V101")

    payload = _visitor_payload(society.id, flat.id)
    payload["resident_id"] = str(resident["user"].id)
    client.post("/api/v1/visitors/", json=payload, headers=security["headers"])

    r = client.get("/api/v1/visitors/me/pending-approvals",
                   headers=resident["headers"])
    assert r.status_code == 200
