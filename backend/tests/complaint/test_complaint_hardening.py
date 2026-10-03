"""Complaints: text is checked; numbers are per society; a complaint never
crosses a society; residents see only their own and never the staff's internal
notes; closing a complaint needs its reason."""
import pytest
from uuid import UUID as _UUID

from tests.conftest import make_user, make_society, make_wing, make_flat

C = "/api/v1/complaints"


def _in(db, user, society):
    user["user"].society_id = _UUID(str(society.id))
    db.commit()
    return user


@pytest.fixture
def rig(db):
    from app.models.resident import Resident, ResidentType
    society = make_society(db, "Help Society")
    wing = make_wing(db, society.id, "Wing H")
    flat = make_flat(db, wing.id, "H-101")
    flat2 = make_flat(db, wing.id, "H-102")
    admin = _in(db, make_user(db, "hadm@c.com", role="Society Admin"), society)
    mgr = _in(db, make_user(db, "hmgr@c.com", role="Manager"), society)
    res = _in(db, make_user(db, "hres@c.com", role="Resident"), society)
    res2 = _in(db, make_user(db, "hres2@c.com", role="Resident"), society)
    db.add_all([Resident(flat_id=flat.id, user_id=res["user"].id, full_name="A", resident_type=ResidentType.OWNER,
                         is_primary=True),
                Resident(flat_id=flat2.id, user_id=res2["user"].id, full_name="B", resident_type=ResidentType.OWNER,
                         is_primary=True)])
    db.commit()
    other = make_society(db, "Other Help Society")
    oadmin = _in(db, make_user(db, "hoadm@c.com", role="Society Admin"), other)
    omgr = _in(db, make_user(db, "homgr@c.com", role="Manager"), other)
    return dict(society=society, flat=flat, admin=admin, mgr=mgr, res=res, res2=res2, other=other, oadmin=oadmin,
                omgr=omgr)


def _body(rig, **kw):
    return {"title": "Tap leaking", "description": "Kitchen tap is leaking badly", "category": "plumbing",
            "society_id": str(rig["society"].id), **kw}


def _raise(client, rig, who="res", **kw):
    return client.post(f"{C}/", json=_body(rig, **kw), headers=rig[who]["headers"])


def test_complaint_text_is_checked(client, rig):
    assert _raise(client, rig, title="  ").status_code == 422
    assert _raise(client, rig, title="t" * 256).status_code == 422
    assert _raise(client, rig, description="   ").status_code == 422
    assert _raise(client, rig, description="d" * 5001).status_code == 422
    r = _raise(client, rig, title="  Tap   leaking ", description="  Leaks  ")
    assert r.status_code == 201, r.text
    assert r.json()["title"] == "Tap leaking" and r.json()["description"] == "Leaks"


def test_numbers_are_per_society(client, rig):
    a = _raise(client, rig, who="admin")
    b = client.post(f"{C}/", json={**_body(rig), "society_id": str(rig["other"].id)}, headers=rig["oadmin"]["headers"])
    assert a.status_code == 201 and b.status_code == 201, b.text
    assert a.json()["complaint_number"] == b.json()["complaint_number"] == "CMP-00001"
    c = _raise(client, rig, who="admin")
    assert c.json()["complaint_number"] == "CMP-00002"


def test_nothing_crosses_a_society(client, rig):
    cid = _raise(client, rig).json()["id"]
    oh = rig["oadmin"]["headers"]
    assert client.get(f"{C}/{cid}", headers=oh).status_code == 404
    assert client.post(f"{C}/{cid}/assign", json={"assigned_to": str(rig["omgr"]["user"].id)}, headers=rig["omgr"]["headers"]
                       ).status_code == 404
    assert client.post(f"{C}/{cid}/status", json={"status": "rejected", "rejection_reason": "x"}, headers=oh).status_code == 404
    assert client.post(f"{C}/{cid}/comments", json={"body": "hi"}, headers=oh).status_code == 404
    assert client.post(f"{C}/{cid}/attachments", json={"file_name": "a.png", "file_url": "https://x/a.png"},
                       headers=oh).status_code == 404
    assert client.get(f"{C}/society/{rig['society'].id}", headers=rig["omgr"]["headers"]).status_code == 403
    assert client.get(f"{C}/society/{rig['society'].id}/open", headers=rig["omgr"]["headers"]).status_code == 403
    # Filing for another society's flat or society
    r = client.post(f"{C}/", json={**_body(rig), "society_id": str(rig["other"].id)}, headers=rig["admin"]["headers"])
    assert r.status_code == 403
    r = client.post(f"{C}/", json={**_body(rig), "flat_id": "00000000-0000-0000-0000-000000000001"},
                    headers=rig["admin"]["headers"])
    assert r.status_code == 422


def test_residents_see_only_their_own(client, rig):
    cid = _raise(client, rig).json()["id"]
    assert client.get(f"{C}/{cid}", headers=rig["res"]["headers"]).status_code == 200
    assert client.get(f"{C}/{cid}", headers=rig["res2"]["headers"]).status_code == 404
    assert client.get(f"{C}/{cid}", headers=rig["mgr"]["headers"]).status_code == 200
    # Nor comment on, attach to or reopen someone else's
    assert client.post(f"{C}/{cid}/comments", json={"body": "me too"}, headers=rig["res2"]["headers"]).status_code == 404
    assert client.post(f"{C}/{cid}/reopen", json={"reason": "x"}, headers=rig["res2"]["headers"]).status_code == 404


def test_internal_notes_stay_with_staff(client, rig):
    cid = _raise(client, rig).json()["id"]
    # A resident can't make a private note; staff's private notes aren't shown to the resident
    r = client.post(f"{C}/{cid}/comments", json={"body": "hello", "is_internal": True}, headers=rig["res"]["headers"])
    assert r.status_code == 201 and r.json()["is_internal"] is False
    client.post(f"{C}/{cid}/comments", json={"body": "secret staff note", "is_internal": True}, headers=rig["mgr"]["headers"])
    seen = client.get(f"{C}/{cid}", headers=rig["res"]["headers"]).json()["comments"]
    assert [c["body"] for c in seen] == ["hello"]
    seen = client.get(f"{C}/{cid}", headers=rig["mgr"]["headers"]).json()["comments"]
    assert [c["body"] for c in seen] == ["hello", "secret staff note"]


def test_text_on_actions_is_checked(client, rig):
    cid = _raise(client, rig).json()["id"]
    h, m = rig["res"]["headers"], rig["mgr"]["headers"]
    assert client.post(f"{C}/{cid}/comments", json={"body": "  "}, headers=h).status_code == 422
    assert client.post(f"{C}/{cid}/comments", json={"body": "b" * 2001}, headers=h).status_code == 422
    assert client.post(f"{C}/{cid}/attachments", json={"file_name": " ", "file_url": "https://x/a.png"},
                       headers=h).status_code == 422
    assert client.post(f"{C}/{cid}/attachments", json={"file_name": "a.png", "file_url": "not a url"},
                       headers=h).status_code == 422
    assert client.post(f"{C}/{cid}/attachments", json={"file_name": "a.png", "file_url": "https://x/a.png",
                                                       "file_size": -5}, headers=h).status_code == 422
    assert client.post(f"{C}/{cid}/attachments", json={"file_name": "a.png", "file_url": "https://x/a.png",
                                                       "file_size": 1200}, headers=h).status_code == 201
    # Closing, rejecting and reopening each need their reason
    assert client.post(f"{C}/{cid}/assign", json={"assigned_to": str(rig["mgr"]["user"].id)}, headers=m).status_code in (200, 409)
    assert client.post(f"{C}/{cid}/status", json={"status": "rejected"}, headers=m).status_code == 422
    assert client.post(f"{C}/{cid}/status", json={"status": "rejected", "rejection_reason": "  "}, headers=m
                       ).status_code == 422


def test_resolving_needs_notes_and_reopen_needs_a_reason(client, rig):
    cid = _raise(client, rig).json()["id"]
    m, h = rig["mgr"]["headers"], rig["res"]["headers"]
    assert client.post(f"{C}/{cid}/status", json={"status": "in_progress"}, headers=m).status_code == 200
    assert client.post(f"{C}/{cid}/status", json={"status": "resolved"}, headers=m).status_code == 422
    ok = client.post(f"{C}/{cid}/status", json={"status": "resolved", "resolution_notes": " Washer replaced "}, headers=m)
    assert ok.status_code == 200 and ok.json()["resolution_notes"] == "Washer replaced"
    assert client.post(f"{C}/{cid}/reopen", json={"reason": " "}, headers=h).status_code == 422
    assert client.post(f"{C}/{cid}/reopen", json={"reason": "Still leaks"}, headers=h).status_code == 200


def test_assignee_must_be_active_staff_of_the_society(client, rig):
    cid = _raise(client, rig).json()["id"]
    m = rig["mgr"]["headers"]
    r = client.post(f"{C}/{cid}/assign", json={"assigned_to": str(rig["omgr"]["user"].id)}, headers=m)
    assert r.status_code == 422, r.text
    r = client.post(f"{C}/{cid}/assign", json={"assigned_to": "00000000-0000-0000-0000-000000000002"}, headers=m)
    assert r.status_code == 422
    r = client.post(f"{C}/{cid}/assign", json={"assigned_to": str(rig["mgr"]["user"].id), "notes": "n" * 1001}, headers=m)
    assert r.status_code == 422


def test_only_the_complainant_reopens(client, rig):
    cid = _raise(client, rig).json()["id"]
    m = rig["mgr"]["headers"]
    client.post(f"{C}/{cid}/status", json={"status": "in_progress"}, headers=m)
    client.post(f"{C}/{cid}/status", json={"status": "resolved", "resolution_notes": "Done"}, headers=m)
    # Other residents can't see it, so can't reopen it; the complainant and the committee can
    assert client.post(f"{C}/{cid}/reopen", json={"reason": "no"}, headers=rig["res2"]["headers"]).status_code == 404
    assert client.post(f"{C}/{cid}/reopen", json={"reason": "again"}, headers=rig["res"]["headers"]).status_code == 200


def test_list_paging_is_bounded(client, rig):
    m = rig["mgr"]["headers"]
    sid = rig["society"].id
    assert client.get(f"{C}/society/{sid}?limit=100000", headers=m).status_code == 422
    assert client.get(f"{C}/society/{sid}?skip=-1", headers=m).status_code == 422
    assert client.get(f"{C}/me/complaints?limit=0", headers=rig["res"]["headers"]).status_code == 422


def test_complaint_shows_who_raised_it_and_who_commented(client, rig):
    cid = _raise(client, rig).json()["id"]
    client.post(f"{C}/{cid}/comments", json={"body": "On it"}, headers=rig["mgr"]["headers"])
    j = client.get(f"{C}/{cid}", headers=rig["res"]["headers"]).json()
    assert j["raised_by_name"] == "Test User" and [c["author_name"] for c in j["comments"]] == ["Test User"]
