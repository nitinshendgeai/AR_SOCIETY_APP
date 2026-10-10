"""Meetings and minutes, polls, documents."""
from datetime import date, timedelta

from app.models.notification import Notification
from app.models.resident import Resident, ResidentType
from tests.conftest import make_flat, make_society, make_user, make_wing

PDF = b"%PDF-1.4 minutes"


def _office(db, email, society):
    a = make_user(db, email, role="Society Admin")
    a["user"].society_id = society.id
    db.commit()
    return a


def _resident(db, email, society, flat):
    r = make_user(db, email, role="Resident")
    r["user"].society_id = society.id
    db.add(Resident(flat_id=flat.id, user_id=r["user"].id, full_name=email.split("@")[0],
                    resident_type=ResidentType.OWNER, is_primary=True))
    db.commit()
    return r


def _rig(db, tag):
    society = make_society(db, f"Gov {tag}")
    wing = make_wing(db, society.id, "W")
    f1, f2 = make_flat(db, wing.id, "1"), make_flat(db, wing.id, "2")
    return society, _office(db, f"gov.admin.{tag}@t.com", society), f1, f2


# ── Meetings ──────────────────────────────────────────────────────────────────

def test_meeting_minutes_are_private_until_published(client, db):
    society, admin, f1, _ = _rig(db, "m1")
    res = _resident(db, "gov.res.m1@t.com", society, f1)
    base = f"/api/v1/governance/meetings/society/{society.id}"

    r = client.post(base, json={"title": "Annual General Meeting", "meeting_type": "agm",
                                "meeting_date": str(date.today() + timedelta(days=10)),
                                "start_time": "18:30", "venue": "Clubhouse", "agenda": "Accounts"},
                    headers=admin["headers"])
    assert r.status_code == 201, r.text
    mid = r.json()["id"]
    assert r.json()["start_time"] == "18:30"
    # members were told
    note = db.query(Notification).filter(Notification.user_id == res["user"].id, Notification.module == "meeting").one()
    assert "Annual General Meeting" in note.title

    assert client.post(base, json={"title": "x", "meeting_date": str(date.today())},
                       headers=res["headers"]).status_code == 403

    saved = client.put(f"/api/v1/governance/meetings/{mid}/minutes", headers=admin["headers"], json={
        "minutes": "Accounts approved.", "publish": False,
        "attendees": [{"name": "Asha K", "flat_label": "W-1", "designation": "Chairman"}],
        "resolutions": [{"text": "Approve accounts", "proposed_by": "Asha", "outcome": "carried"}]})
    assert saved.status_code == 200 and saved.json()["status"] == "held"
    assert saved.json()["resolutions"][0]["number"] == 1

    seen = client.get(f"/api/v1/governance/meetings/{mid}", headers=res["headers"]).json()
    assert seen["minutes"] is None and seen["attendees"] == [] and seen["resolutions"] == []   # not published

    client.put(f"/api/v1/governance/meetings/{mid}/minutes", headers=admin["headers"], json={
        "minutes": "Accounts approved.", "publish": True,
        "attendees": [{"name": "Asha K"}], "resolutions": [{"text": "Approve accounts", "outcome": "carried"}]})
    seen = client.get(f"/api/v1/governance/meetings/{mid}", headers=res["headers"]).json()
    assert seen["minutes"] == "Accounts approved." and len(seen["resolutions"]) == 1 and seen["minutes_published"]


def test_meeting_validation_and_scope(client, db):
    society, admin, f1, _ = _rig(db, "m2")
    other = make_society(db, "Gov other")
    base = f"/api/v1/governance/meetings/society/{society.id}"
    assert client.post(base, json={"title": "x y", "meeting_type": "bogus", "meeting_date": str(date.today())},
                       headers=admin["headers"]).status_code == 422
    mid = client.post(base, json={"title": "Committee", "meeting_date": str(date.today()), "announce": False},
                      headers=admin["headers"]).json()["id"]
    bad = client.put(f"/api/v1/governance/meetings/{mid}/minutes", headers=admin["headers"],
                     json={"resolutions": [{"text": "t", "outcome": "maybe"}]})
    assert bad.status_code == 422
    other_admin = _office(db, "gov.admin.other@t.com", other)
    assert client.get(f"/api/v1/governance/meetings/{mid}", headers=other_admin["headers"]).status_code in (403, 404)
    assert client.get(base, headers=other_admin["headers"]).status_code in (403, 404)


# ── Polls ─────────────────────────────────────────────────────────────────────

def _poll(client, admin, society, **kw):
    body = {"question": "Repaint the building?", "options": ["Yes", "No"],
            "closes_on": str(date.today() + timedelta(days=5)), "results_after": "vote", **kw}
    r = client.post(f"/api/v1/governance/polls/society/{society.id}", json=body, headers=admin["headers"])
    assert r.status_code == 201, r.text
    return r.json()


def test_one_vote_per_flat_and_results_follow_the_poll_setting(client, db):
    society, admin, f1, f2 = _rig(db, "p1")
    a = _resident(db, "gov.a@t.com", society, f1)
    c = _resident(db, "gov.c@t.com", society, f2)
    poll = _poll(client, admin, society)
    yes = poll["options"][0]["id"]
    assert poll["options"][0]["votes"] is None and poll["results_visible"] is False

    r = client.post(f"/api/v1/governance/polls/{poll['id']}/vote", json={"option_id": yes}, headers=a["headers"])
    assert r.status_code == 200 and r.json()["results_visible"] and r.json()["my_option_id"] == yes
    assert r.json()["options"][0]["votes"] == 1 and r.json()["can_vote"] is False
    # a flat cannot vote twice (the vote is kept per flat, so another person in it could not either)
    assert client.post(f"/api/v1/governance/polls/{poll['id']}/vote", json={"option_id": yes},
                       headers=a["headers"]).status_code == 409
    no = poll["options"][1]["id"]
    out = client.post(f"/api/v1/governance/polls/{poll['id']}/vote", json={"option_id": no}, headers=c["headers"]).json()
    assert [o["votes"] for o in out["options"]] == [1, 1] and out["votes"] == 2 and out["flats"] == 2


def test_results_stay_hidden_until_close_when_set_so(client, db):
    society, admin, f1, _ = _rig(db, "p2")
    a = _resident(db, "gov.a2@t.com", society, f1)
    poll = _poll(client, admin, society, results_after="close")
    out = client.post(f"/api/v1/governance/polls/{poll['id']}/vote", json={"option_id": poll["options"][0]["id"]},
                      headers=a["headers"]).json()
    assert out["results_visible"] is False and out["options"][0]["votes"] is None and out["votes"] == 1
    closed = client.post(f"/api/v1/governance/polls/{poll['id']}/close", headers=admin["headers"]).json()
    assert closed["open"] is False and closed["results_visible"] and closed["options"][0]["votes"] == 1
    assert client.post(f"/api/v1/governance/polls/{poll['id']}/vote", json={"option_id": poll["options"][1]["id"]},
                       headers=a["headers"]).status_code == 409


def test_poll_rules(client, db):
    society, admin, f1, _ = _rig(db, "p3")
    res = _resident(db, "gov.r3@t.com", society, f1)
    base = f"/api/v1/governance/polls/society/{society.id}"
    ok = {"question": "Question?", "closes_on": str(date.today() + timedelta(days=2))}
    assert client.post(base, json={**ok, "options": ["Only one"]}, headers=admin["headers"]).status_code == 422
    assert client.post(base, json={**ok, "options": ["Same", "same"]}, headers=admin["headers"]).status_code == 422
    assert client.post(base, json={**ok, "options": ["A", "B"], "closes_on": str(date.today() - timedelta(days=1))},
                       headers=admin["headers"]).status_code == 422
    assert client.post(base, json={**ok, "options": ["A", "B"]}, headers=res["headers"]).status_code == 403
    poll = _poll(client, admin, society)
    # the admin has no flat in this society, so cannot vote
    assert client.post(f"/api/v1/governance/polls/{poll['id']}/vote", json={"option_id": poll["options"][0]["id"]},
                       headers=admin["headers"]).status_code == 403
    assert client.post(f"/api/v1/governance/polls/{poll['id']}/vote",
                       json={"option_id": "00000000-0000-0000-0000-000000000001"},
                       headers=res["headers"]).status_code == 422


# ── Documents ─────────────────────────────────────────────────────────────────

def _upload(client, admin, society, name="bylaws.pdf", ctype="application/pdf", data=PDF, **form):
    return client.post(f"/api/v1/governance/documents/society/{society.id}", headers=admin["headers"],
                       data={"title": "Bye-laws", "category": "bylaws", **form},
                       files={"file": (name, data, ctype)})


def test_documents_upload_list_download_and_visibility(client, db):
    society, admin, f1, _ = _rig(db, "d1")
    res = _resident(db, "gov.r4@t.com", society, f1)
    shared = _upload(client, admin, society)
    assert shared.status_code == 201, shared.text
    private = _upload(client, admin, society, title="Audit draft", visibility="committee")
    assert private.status_code == 201

    base = f"/api/v1/governance/documents/society/{society.id}"
    assert len(client.get(base, headers=admin["headers"]).json()) == 2
    seen = client.get(base, headers=res["headers"]).json()
    assert [d["id"] for d in seen] == [shared.json()["id"]]            # committee-only is not listed

    dl = client.get(f"/api/v1/governance/documents/{shared.json()['id']}/download", headers=res["headers"])
    assert dl.status_code == 200 and dl.content == PDF and dl.headers["content-type"] == "application/pdf"
    assert client.get(f"/api/v1/governance/documents/{private.json()['id']}/download",
                      headers=res["headers"]).status_code == 404

    assert client.delete(f"/api/v1/governance/documents/{shared.json()['id']}", headers=res["headers"]).status_code == 403
    assert client.delete(f"/api/v1/governance/documents/{shared.json()['id']}", headers=admin["headers"]).status_code == 204
    assert len(client.get(base, headers=admin["headers"]).json()) == 1


def test_document_upload_is_checked(client, db):
    society, admin, f1, _ = _rig(db, "d2")
    other = make_society(db, "Gov d2 other")
    assert _upload(client, admin, society, name="a.exe", ctype="application/x-msdownload").status_code == 415
    assert _upload(client, admin, society, data=b"").status_code == 422
    assert _upload(client, admin, society, data=b"x" * (10 * 1024 * 1024 + 1)).status_code == 413
    assert _upload(client, admin, society, category="nonsense").status_code == 422
    assert _upload(client, admin, other).status_code in (403, 404)       # another society
