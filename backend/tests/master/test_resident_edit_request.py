"""
Resident self-service edit requests.

A Resident cannot PATCH /residents/{id} directly (require_admin_committee) —
this covers the alternative path: submit a change request here, which only
takes effect once an Admin/Committee member approves it. Covers: create,
one-pending-at-a-time, no-profile-linked 404, Admin/Committee-only
list/approve/reject, approval applies changes, rejection leaves the
Resident untouched, and re-reviewing an already-reviewed request is blocked.
"""
import pytest
from uuid import UUID as _UUID
from tests.conftest import make_user, make_society, make_wing, make_flat


def _to_uuid(v) -> _UUID:
    return v if isinstance(v, _UUID) else _UUID(str(v))


def _set_society(db, user_obj, society_id):
    user_obj.society_id = _to_uuid(society_id)
    db.commit()
    db.refresh(user_obj)


@pytest.fixture
def setup(db):
    society = make_society(db, "Edit Request Society")
    admin = make_user(db, "editreq-admin@test.com", role="Society Admin")
    _set_society(db, admin["user"], society.id)
    wing = make_wing(db, society.id, "Wing E")
    flat = make_flat(db, wing.id, "E-101")
    return {"society": society, "admin": admin, "wing": wing, "flat": flat}


def _resident_with_login(db, client, admin_headers, flat_id, email, society_id):
    resident_user = make_user(db, email, role="Resident")
    _set_society(db, resident_user["user"], society_id)
    r = client.post("/api/v1/residents/", json={
        "flat_id": str(flat_id), "full_name": "Original Name",
        "phone": "9876500001", "user_id": str(resident_user["user"].id),
    }, headers=admin_headers)
    assert r.status_code == 201, r.text
    return resident_user, r.json()


def test_resident_can_fetch_own_profile(client, db, setup):
    resident_user, resident = _resident_with_login(
        db, client, setup["admin"]["headers"], setup["flat"].id, "res0@test.com", setup["society"].id)

    r = client.get("/api/v1/residents/me", headers=resident_user["headers"])
    assert r.status_code == 200
    assert r.json()["id"] == resident["id"]
    assert r.json()["full_name"] == "Original Name"


def test_me_404_when_no_resident_linked(client, db, setup):
    orphan_user = make_user(db, "orphan-me@test.com", role="Resident")
    _set_society(db, orphan_user["user"], setup["society"].id)
    r = client.get("/api/v1/residents/me", headers=orphan_user["headers"])
    assert r.status_code == 404


def test_resident_cannot_patch_directly(client, db, setup):
    resident_user, resident = _resident_with_login(
        db, client, setup["admin"]["headers"], setup["flat"].id, "res1@test.com", setup["society"].id)

    r = client.patch(f"/api/v1/residents/{resident['id']}",
                      json={"full_name": "Hacked Name"},
                      headers=resident_user["headers"])
    assert r.status_code == 403


def test_create_edit_request_success(client, db, setup):
    resident_user, resident = _resident_with_login(
        db, client, setup["admin"]["headers"], setup["flat"].id, "res2@test.com", setup["society"].id)

    r = client.post("/api/v1/residents/edit-requests",
                     json={"phone": "9876500002", "full_name": "Updated Name"},
                     headers=resident_user["headers"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["changes"] == {"phone": "9876500002", "full_name": "Updated Name"}
    assert body["resident_name"] == "Original Name"
    assert "E-101" in body["flat_display"]


def test_second_pending_request_rejected(client, db, setup):
    resident_user, _ = _resident_with_login(
        db, client, setup["admin"]["headers"], setup["flat"].id, "res3@test.com", setup["society"].id)

    r1 = client.post("/api/v1/residents/edit-requests", json={"phone": "9876500003"},
                      headers=resident_user["headers"])
    assert r1.status_code == 201
    r2 = client.post("/api/v1/residents/edit-requests", json={"phone": "9876500004"},
                      headers=resident_user["headers"])
    assert r2.status_code == 409


def test_no_resident_profile_returns_404(client, db, setup):
    orphan_user = make_user(db, "orphan@test.com", role="Resident")
    _set_society(db, orphan_user["user"], setup["society"].id)
    r = client.post("/api/v1/residents/edit-requests", json={"phone": "9876500005"},
                     headers=orphan_user["headers"])
    assert r.status_code == 404


def test_admin_lists_pending_requests(client, db, setup):
    resident_user, _ = _resident_with_login(
        db, client, setup["admin"]["headers"], setup["flat"].id, "res4@test.com", setup["society"].id)
    client.post("/api/v1/residents/edit-requests", json={"phone": "9876500006"},
                headers=resident_user["headers"])

    r = client.get("/api/v1/residents/edit-requests/pending", headers=setup["admin"]["headers"])
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["changes"]["phone"] == "9876500006"


def test_resident_cannot_list_pending(client, db, setup):
    resident_user, _ = _resident_with_login(
        db, client, setup["admin"]["headers"], setup["flat"].id, "res5@test.com", setup["society"].id)
    r = client.get("/api/v1/residents/edit-requests/pending", headers=resident_user["headers"])
    assert r.status_code == 403


def test_approve_applies_changes(client, db, setup):
    resident_user, resident = _resident_with_login(
        db, client, setup["admin"]["headers"], setup["flat"].id, "res6@test.com", setup["society"].id)
    created = client.post("/api/v1/residents/edit-requests",
                           json={"phone": "9876500007", "full_name": "Approved Name"},
                           headers=resident_user["headers"]).json()

    r = client.post(f"/api/v1/residents/edit-requests/{created['id']}/approve",
                     headers=setup["admin"]["headers"])
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    updated = client.get(f"/api/v1/residents/{resident['id']}", headers=setup["admin"]["headers"]).json()
    assert updated["phone"] == "9876500007"
    assert updated["full_name"] == "Approved Name"


def test_reject_leaves_resident_untouched(client, db, setup):
    resident_user, resident = _resident_with_login(
        db, client, setup["admin"]["headers"], setup["flat"].id, "res7@test.com", setup["society"].id)
    created = client.post("/api/v1/residents/edit-requests",
                           json={"phone": "9876500008"}, headers=resident_user["headers"]).json()

    r = client.post(f"/api/v1/residents/edit-requests/{created['id']}/reject",
                     json={"reason": "Phone number looks invalid"},
                     headers=setup["admin"]["headers"])
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    assert r.json()["rejection_reason"] == "Phone number looks invalid"

    unchanged = client.get(f"/api/v1/residents/{resident['id']}", headers=setup["admin"]["headers"]).json()
    assert unchanged["phone"] == "9876500001"


def test_cannot_review_already_reviewed_request(client, db, setup):
    resident_user, _ = _resident_with_login(
        db, client, setup["admin"]["headers"], setup["flat"].id, "res8@test.com", setup["society"].id)
    created = client.post("/api/v1/residents/edit-requests",
                           json={"phone": "9876500009"}, headers=resident_user["headers"]).json()

    client.post(f"/api/v1/residents/edit-requests/{created['id']}/approve", headers=setup["admin"]["headers"])
    r = client.post(f"/api/v1/residents/edit-requests/{created['id']}/approve", headers=setup["admin"]["headers"])
    assert r.status_code == 409


def test_list_mine_shows_own_history(client, db, setup):
    resident_user, _ = _resident_with_login(
        db, client, setup["admin"]["headers"], setup["flat"].id, "res9@test.com", setup["society"].id)
    client.post("/api/v1/residents/edit-requests", json={"phone": "9876500010"},
                headers=resident_user["headers"])

    r = client.get("/api/v1/residents/edit-requests/mine", headers=resident_user["headers"])
    assert r.status_code == 200
    assert len(r.json()) == 1
