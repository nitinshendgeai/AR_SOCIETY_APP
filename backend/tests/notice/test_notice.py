"""Notice & communication tests — CRUD, acknowledge, RBAC."""
import pytest
from tests.conftest import make_user, make_society


def _create_notice(client, headers, society_id, title="Water Shutdown"):
    r = client.post(
        "/api/v1/notices/",
        json={
            "society_id": str(society_id),
            "title":      title,
            "content":    "Scheduled maintenance on Sunday 10am-2pm.",
            "category":   "maintenance",
            "priority":   "high",
        },
        headers=headers,
    )
    return r


def test_create_notice_success(client, db):
    admin   = make_user(db, "adm@notice.com", role="Admin")
    society = make_society(db, "Notice Society")
    r = _create_notice(client, admin["headers"], society.id)
    assert r.status_code == 201
    assert r.json()["title"] == "Water Shutdown"


def test_create_notice_committee_allowed(client, db):
    committee = make_user(db, "com@notice.com", role="Committee")
    society   = make_society(db, "Notice Society 2")
    r = _create_notice(client, committee["headers"], society.id, "AGM Meeting")
    assert r.status_code == 201


def test_create_notice_resident_forbidden(client, db):
    resident = make_user(db, "res@notice.com", role="Resident")
    society  = make_society(db, "Notice Society 3")
    r = _create_notice(client, resident["headers"], society.id, "Sneaky Notice")
    assert r.status_code == 403


def test_list_notices_by_society(client, db):
    admin   = make_user(db, "adm2@notice.com", role="Admin")
    society = make_society(db, "Notice Society 4")
    _create_notice(client, admin["headers"], society.id, "Gym Closed")
    _create_notice(client, admin["headers"], society.id, "Pool Maintenance")
    r = client.get(f"/api/v1/notices/society/{society.id}/all",
                   headers=admin["headers"])
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_acknowledge_notice(client, db):
    admin    = make_user(db, "adm3@notice.com", role="Admin")
    resident = make_user(db, "res2@notice.com", role="Resident")
    society  = make_society(db, "Notice Society 5")
    nr = _create_notice(client, admin["headers"], society.id, "Important Notice")
    notice_id = nr.json()["id"]
    # Publish first
    client.post(f"/api/v1/notices/{notice_id}/publish", headers=admin["headers"])
    r = client.post(
        f"/api/v1/notices/{notice_id}/acknowledge",
        json={"notes": "Noted"},
        headers=resident["headers"],
    )
    assert r.status_code in (200, 201)


def test_get_notice_by_id(client, db):
    admin   = make_user(db, "adm4@notice.com", role="Admin")
    society = make_society(db, "Notice Society 6")
    nr = _create_notice(client, admin["headers"], society.id, "Specific Notice")
    notice_id = nr.json()["id"]
    r = client.get(f"/api/v1/notices/{notice_id}", headers=admin["headers"])
    assert r.status_code == 200
    assert r.json()["id"] == notice_id


def test_unauthenticated_cannot_list_notices(client, db):
    r = client.get("/api/v1/notices/society/00000000-0000-0000-0000-000000000001/all")
    assert r.status_code in (401, 403)
