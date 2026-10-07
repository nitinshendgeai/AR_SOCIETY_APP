"""The notice board: who a notice is for, drafts and publishing, acknowledgements, keeping societies apart,
and emergency alerts."""
from datetime import datetime, timedelta

import pytest

from tests.conftest import make_flat, make_society, make_user


def make_wing(db, society_id, name):
    from app.models.wing import Wing
    w = Wing(society_id=society_id, name=name, code=name)
    db.add(w); db.commit(); db.refresh(w)
    return w

N = "/api/v1/notices"


def _member(db, email, role, society, name=None):
    who = make_user(db, email, role=role, full_name=name or email.split("@")[0])
    who["user"].society_id = society.id
    db.commit()
    return who


def _live_in(db, who, flat, kind="resident", resident_type="owner"):
    """Make `who` the occupant of `flat`."""
    from app.models.resident import Resident, ResidentType
    from app.models.tenant import Tenant
    u = who["user"]
    if kind == "resident":
        db.add(Resident(flat_id=flat.id, user_id=u.id, full_name=u.full_name or "Resident", phone="9000000001",
                        resident_type=ResidentType(resident_type), is_active=True))
    else:
        db.add(Tenant(flat_id=flat.id, user_id=u.id, full_name=u.full_name or "Tenant", phone="9000000002",
                      is_active=True))
    db.commit()


@pytest.fixture
def soc(db):
    """A society with two wings, an admin, an owner in A/101, a tenant in A/102, an owner in B/201, a guard."""
    society = make_society(db, "Notice Board Society")
    wing_a, wing_b = make_wing(db, society.id, "A"), make_wing(db, society.id, "B")
    f101, f102, f201 = make_flat(db, wing_a.id, "101"), make_flat(db, wing_a.id, "102"), make_flat(db, wing_b.id, "201")
    r = {
        "society": society, "wing_a": wing_a, "wing_b": wing_b, "f101": f101, "f102": f102, "f201": f201,
        "admin": _member(db, "admin@nb.test", "Society Admin", society, "Asha Admin"),
        "owner_a": _member(db, "owner.a@nb.test", "Resident", society, "Omkar Owner"),
        "tenant_a": _member(db, "tenant.a@nb.test", "Tenant", society, "Tara Tenant"),
        "owner_b": _member(db, "owner.b@nb.test", "Resident", society, "Bhaskar Owner"),
        "guard": _member(db, "guard@nb.test", "Security Staff", society, "Gopal Guard"),
        "committee": _member(db, "sec@nb.test", "Committee Secretary", society, "Sameer Secretary"),
    }
    _live_in(db, r["owner_a"], f101)
    _live_in(db, r["tenant_a"], f102, kind="tenant")
    _live_in(db, r["owner_b"], f201)
    return r


def _notice(client, who, society, **over):
    body = {"title": "Water shutdown", "content": "No water on Sunday 10am to 2pm.", "category": "water_shutdown",
            "priority": "high", **over}
    if "society_id" not in body:
        body["society_id"] = str(society.id)
    return client.post(f"{N}/", json=body, headers=who["headers"])


def _publish(client, who, notice_id):
    return client.post(f"{N}/{notice_id}/publish", headers=who["headers"])


def _board(client, who, society):
    r = client.get(f"{N}/society/{society.id}/mine", headers=who["headers"])
    assert r.status_code == 200, r.text
    return [n["title"] for n in r.json()]


# ── Audience ─────────────────────────────────────────────────────────────────

def test_everyone_notice_reaches_all_and_counts_the_audience(client, db, soc):
    n = _notice(client, soc["admin"], soc["society"], audience_type="all", title="AGM on Sunday").json()
    assert n["status"] == "draft" and n["total_audience"] == 0
    p = _publish(client, soc["admin"], n["id"])
    assert p.status_code == 200 and p.json()["status"] == "published"
    assert p.json()["total_audience"] == 6                       # everyone in the society
    for who in ("owner_a", "tenant_a", "owner_b", "guard", "committee", "admin"):
        assert _board(client, soc[who], soc["society"]) == ["AGM on Sunday"], who


def test_residents_only_leaves_out_staff_and_committee(client, db, soc):
    _publish(client, soc["admin"], _notice(client, soc["admin"], soc["society"], audience_type="all_residents",
                                           title="Lift service").json()["id"])
    assert _board(client, soc["owner_a"], soc["society"]) == ["Lift service"]
    assert _board(client, soc["tenant_a"], soc["society"]) == ["Lift service"]
    assert _board(client, soc["guard"], soc["society"]) == []
    assert _board(client, soc["committee"], soc["society"]) == []


def test_owners_and_tenants_are_told_apart(client, db, soc):
    _publish(client, soc["admin"], _notice(client, soc["admin"], soc["society"], audience_type="owners_only",
                                           title="Owners: transfer fee").json()["id"])
    _publish(client, soc["admin"], _notice(client, soc["admin"], soc["society"], audience_type="tenants_only",
                                           title="Tenants: police verification").json()["id"])
    assert _board(client, soc["owner_a"], soc["society"]) == ["Owners: transfer fee"]
    assert _board(client, soc["tenant_a"], soc["society"]) == ["Tenants: police verification"]


def test_a_wing_or_flats_only(client, db, soc):
    wing = _notice(client, soc["admin"], soc["society"], audience_type="specific_wings", title="Wing A: pipe repair",
                   target_wing_ids=[str(soc["wing_a"].id)]).json()
    assert _publish(client, soc["admin"], wing["id"]).json()["total_audience"] == 2        # owner and tenant of A
    flat = _notice(client, soc["admin"], soc["society"], audience_type="specific_flats", title="Flat 201: leak",
                   target_flat_ids=[str(soc["f201"].id)]).json()
    assert _publish(client, soc["admin"], flat["id"]).json()["total_audience"] == 1
    assert _board(client, soc["owner_a"], soc["society"]) == ["Wing A: pipe repair"]
    assert _board(client, soc["owner_b"], soc["society"]) == ["Flat 201: leak"]


def test_staff_security_and_committee_audiences(client, db, soc):
    for aud, title in (("all_staff", "Staff roster"), ("security_team", "Gate drill"), ("committee", "Meeting")):
        _publish(client, soc["admin"], _notice(client, soc["admin"], soc["society"], audience_type=aud, title=title,
                                               category="staff_notice").json()["id"])
    assert sorted(_board(client, soc["guard"], soc["society"])) == ["Gate drill", "Staff roster"]
    assert _board(client, soc["committee"], soc["society"]) == ["Meeting"]
    assert _board(client, soc["owner_a"], soc["society"]) == []


def test_a_resident_cannot_open_a_notice_that_is_not_for_them(client, db, soc):
    n = _notice(client, soc["admin"], soc["society"], audience_type="security_team", title="Gate drill").json()
    _publish(client, soc["admin"], n["id"])
    assert client.get(f"{N}/{n['id']}", headers=soc["guard"]["headers"]).status_code == 200
    assert client.get(f"{N}/{n['id']}", headers=soc["owner_a"]["headers"]).status_code == 404
    assert client.get(f"{N}/{n['id']}", headers=soc["admin"]["headers"]).status_code == 200      # the committee may open any


def test_drafts_expired_and_archived_notices_are_not_on_the_board(client, db, soc):
    draft = _notice(client, soc["admin"], soc["society"], audience_type="all", title="Draft").json()
    live = _notice(client, soc["admin"], soc["society"], audience_type="all", title="Live").json()
    _publish(client, soc["admin"], live["id"])
    old = _notice(client, soc["admin"], soc["society"], audience_type="all", title="Old",
                  expiry_date=(datetime.utcnow() + timedelta(hours=1)).isoformat()).json()
    _publish(client, soc["admin"], old["id"])
    assert sorted(_board(client, soc["owner_a"], soc["society"])) == ["Live", "Old"]
    from app.modules.notice.models.notice import Notice
    import uuid
    row = db.query(Notice).filter(Notice.id == uuid.UUID(old["id"])).first()
    row.expiry_date = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    assert _board(client, soc["owner_a"], soc["society"]) == ["Live"]
    assert client.post(f"{N}/{live['id']}/archive", headers=soc["admin"]["headers"]).json()["status"] == "archived"
    assert _board(client, soc["owner_a"], soc["society"]) == []
    assert draft["status"] == "draft"


def test_board_is_urgent_first_then_newest(client, db, soc):
    for title, prio in (("Routine", "normal"), ("Urgent", "urgent"), ("Also routine", "normal"), ("Soon", "high")):
        _publish(client, soc["admin"], _notice(client, soc["admin"], soc["society"], audience_type="all",
                                               title=title, priority=prio).json()["id"])
    assert _board(client, soc["owner_a"], soc["society"]) == ["Urgent", "Soon", "Also routine", "Routine"]


# ── Drafting and publishing ──────────────────────────────────────────────────

def test_a_draft_can_be_edited_published_once_and_a_published_notice_is_fixed(client, db, soc):
    h = soc["admin"]["headers"]
    n = _notice(client, soc["admin"], soc["society"], audience_type="all").json()
    e = client.patch(f"{N}/{n['id']}", headers=h, json={"title": "  Water shutdown (revised) ", "priority": "urgent",
                                                         "acknowledgement_required": True})
    assert e.status_code == 200 and e.json()["title"] == "Water shutdown (revised)" and e.json()["priority"] == "urgent"
    assert client.patch(f"{N}/{n['id']}", headers=h, json={"title": "  "}).status_code == 422
    assert _publish(client, soc["admin"], n["id"]).status_code == 200
    assert _publish(client, soc["admin"], n["id"]).status_code == 409
    assert client.patch(f"{N}/{n['id']}", headers=h, json={"title": "Changed"}).status_code == 409
    assert client.delete(f"{N}/{n['id']}", headers=h).status_code == 409


def test_a_draft_can_be_deleted_and_a_draft_cannot_be_archived(client, db, soc):
    h = soc["admin"]["headers"]
    n = _notice(client, soc["admin"], soc["society"]).json()
    assert client.post(f"{N}/{n['id']}/archive", headers=h).status_code == 409
    assert client.delete(f"{N}/{n['id']}", headers=h).status_code == 204
    assert client.get(f"{N}/{n['id']}", headers=h).status_code == 404
    assert n["id"] not in [x["id"] for x in client.get(f"{N}/society/{soc['society'].id}/all", headers=h).json()]


def test_input_is_checked(client, db, soc):
    assert _notice(client, soc["admin"], soc["society"], title="  ").status_code == 422
    assert _notice(client, soc["admin"], soc["society"], content="").status_code == 422
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    assert _notice(client, soc["admin"], soc["society"], expiry_date=past).status_code == 422
    assert _notice(client, soc["admin"], soc["society"], audience_type="specific_wings").status_code == 422
    assert _notice(client, soc["admin"], soc["society"], audience_type="specific_flats", target_flat_ids=[]).status_code == 422
    other = make_society(db, "Other Notice Society")
    foreign_wing = make_wing(db, other.id, "Z")
    assert _notice(client, soc["admin"], soc["society"], audience_type="specific_wings",
                   target_wing_ids=[str(foreign_wing.id)]).status_code == 422


def test_an_empty_audience_cannot_be_published(client, db, soc):
    empty_wing = make_wing(db, soc["society"].id, "C")          # nobody lives there
    n = _notice(client, soc["admin"], soc["society"], audience_type="specific_wings",
                target_wing_ids=[str(empty_wing.id)]).json()
    r = _publish(client, soc["admin"], n["id"])
    assert r.status_code == 422 and "Nobody" in r.text


def test_only_the_committee_writes_notices(client, db, soc):
    assert _notice(client, soc["owner_a"], soc["society"]).status_code == 403
    assert _notice(client, soc["guard"], soc["society"]).status_code == 403
    assert _notice(client, soc["committee"], soc["society"]).status_code == 201
    assert client.get(f"{N}/society/{soc['society'].id}/all", headers=soc["owner_a"]["headers"]).status_code == 403


# ── Acknowledgement ──────────────────────────────────────────────────────────

def test_acknowledging_and_the_report(client, db, soc):
    n = _notice(client, soc["admin"], soc["society"], audience_type="all_residents",
                acknowledgement_required=True).json()
    _publish(client, soc["admin"], n["id"])
    r = client.post(f"{N}/{n['id']}/acknowledge", json={"notes": "Noted"}, headers=soc["owner_a"]["headers"])
    assert r.status_code == 200
    # twice: refused; the board says it has been read
    assert client.post(f"{N}/{n['id']}/acknowledge", json={}, headers=soc["owner_a"]["headers"]).status_code == 409
    mine = client.get(f"{N}/society/{soc['society'].id}/mine", headers=soc["owner_a"]["headers"]).json()
    assert mine[0]["acknowledged"] is True
    assert client.get(f"{N}/society/{soc['society'].id}/mine", headers=soc["tenant_a"]["headers"]).json()[0]["acknowledged"] is False
    rep = client.get(f"{N}/{n['id']}/acknowledgements", headers=soc["admin"]["headers"]).json()
    assert (rep["total_audience"], rep["acknowledged"], rep["pending"], rep["rate_pct"]) == (3, 1, 2, 33.3)
    assert rep["acknowledgers"][0]["name"] == "Omkar Owner" and rep["acknowledgers"][0]["flat"] == "A / 101"
    assert sorted(p["name"] for p in rep["pending_people"]) == ["Bhaskar Owner", "Tara Tenant"]
    assert client.get(f"{N}/{n['id']}/acknowledgements", headers=soc["owner_a"]["headers"]).status_code == 403


def test_only_the_audience_can_acknowledge_a_published_notice(client, db, soc):
    n = _notice(client, soc["admin"], soc["society"], audience_type="security_team").json()
    assert client.post(f"{N}/{n['id']}/acknowledge", json={}, headers=soc["guard"]["headers"]).status_code == 409   # not published
    _publish(client, soc["admin"], n["id"])
    assert client.post(f"{N}/{n['id']}/acknowledge", json={}, headers=soc["owner_a"]["headers"]).status_code == 404
    assert client.post(f"{N}/{n['id']}/acknowledge", json={}, headers=soc["guard"]["headers"]).status_code == 200


def test_the_flat_given_must_be_the_residents_own(client, db, soc):
    n = _notice(client, soc["admin"], soc["society"], audience_type="all_residents").json()
    _publish(client, soc["admin"], n["id"])
    r = client.post(f"{N}/{n['id']}/acknowledge", json={"flat_id": str(soc["f201"].id)}, headers=soc["owner_a"]["headers"])
    assert r.status_code == 422


# ── Between societies ────────────────────────────────────────────────────────

def test_societies_are_kept_apart(client, db, soc):
    other = make_society(db, "Rival Society")
    rival = _member(db, "admin@rival.test", "Society Admin", other)
    n = _notice(client, soc["admin"], soc["society"], audience_type="all").json()
    _publish(client, soc["admin"], n["id"])
    h = rival["headers"]
    sid = soc["society"].id
    assert client.get(f"{N}/{n['id']}", headers=h).status_code == 404
    assert client.patch(f"{N}/{n['id']}", headers=h, json={"title": "x"}).status_code == 404
    assert client.post(f"{N}/{n['id']}/archive", headers=h).status_code == 404
    assert client.post(f"{N}/{n['id']}/acknowledge", json={}, headers=h).status_code == 404
    assert client.get(f"{N}/{n['id']}/acknowledgements", headers=h).status_code == 404
    for path in (f"/society/{sid}/all", f"/society/{sid}/mine", f"/society/{sid}/published",
                 f"/announcements/society/{sid}", f"/emergency/active/{sid}", f"/emergency/history/{sid}",
                 f"/comm-logs/{sid}"):
        assert client.get(N + path, headers=h).status_code == 403, path
    # nor write into it
    assert _notice(client, rival, soc["society"]).status_code == 403
    # a rival's own notice board has none of ours
    assert _board(client, rival, other) == []


def test_a_notice_without_a_society_goes_to_the_callers(client, db, soc):
    r = client.post(f"{N}/", headers=soc["admin"]["headers"], json={
        "title": "No society named", "content": "Body", "category": "general", "audience_type": "all"})
    assert r.status_code == 201 and r.json()["society_id"] == str(soc["society"].id)


# ── Emergency alerts ─────────────────────────────────────────────────────────

def _alert(client, who, society, **over):
    return client.post(f"{N}/emergency/", headers=who["headers"], json={
        "society_id": str(society.id), "alert_type": "fire", "title": "Fire in Wing B basement",
        "location": "Wing B parking", "description": "Evacuate by the stairs", **over})


def test_an_alert_reaches_residents_security_and_committee_and_can_be_resolved(client, db, soc):
    from app.models.notification import Notification
    r = _alert(client, soc["guard"], soc["society"])            # the guard on duty raises it
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "active" and body["reached"] == 6 and body["triggered_by_name"] == "Gopal Guard"
    notes = db.query(Notification).filter(Notification.module == "emergency").all()
    assert {str(n.user_id) for n in notes} == {str(soc[k]["user"].id) for k in
                                                ("owner_a", "tenant_a", "owner_b", "guard", "committee", "admin")}
    assert all("Fire in Wing B basement" in n.title for n in notes)
    # visible to every member while active
    for who in ("owner_a", "tenant_a", "guard"):
        active = client.get(f"{N}/emergency/active/{soc['society'].id}", headers=soc[who]["headers"]).json()
        assert [a["title"] for a in active] == ["Fire in Wing B basement"]
    done = client.post(f"{N}/emergency/{body['id']}/resolve", headers=soc["admin"]["headers"], json={"notes": "Put out"})
    assert done.status_code == 200 and done.json()["status"] == "resolved"
    assert client.post(f"{N}/emergency/{body['id']}/resolve", headers=soc["admin"]["headers"], json={}).status_code == 409
    assert client.get(f"{N}/emergency/active/{soc['society'].id}", headers=soc["owner_a"]["headers"]).json() == []
    hist = client.get(f"{N}/emergency/history/{soc['society'].id}", headers=soc["admin"]["headers"]).json()
    assert hist[0]["resolution_notes"] == "Put out"


def test_an_alert_can_leave_some_groups_out(client, db, soc):
    r = _alert(client, soc["admin"], soc["society"], notify_all_residents=False, notify_committee=False)
    assert r.json()["reached"] == 1                               # only the guard


def test_residents_cannot_raise_or_end_alerts_and_other_societies_cannot_touch_them(client, db, soc):
    assert _alert(client, soc["owner_a"], soc["society"]).status_code == 403
    a = _alert(client, soc["admin"], soc["society"]).json()
    assert client.post(f"{N}/emergency/{a['id']}/resolve", headers=soc["owner_a"]["headers"], json={}).status_code == 403
    other = make_society(db, "Another Society")
    rival = _member(db, "admin@another.test", "Society Admin", other)
    assert client.post(f"{N}/emergency/{a['id']}/resolve", headers=rival["headers"], json={}).status_code == 404
    assert _alert(client, rival, soc["society"]).status_code == 403
    assert _alert(client, soc["admin"], soc["society"], title="  ").status_code == 422
