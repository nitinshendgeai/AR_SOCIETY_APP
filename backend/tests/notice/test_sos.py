"""A resident's SOS: reaches security and the committee, stays off the neighbours' banner, one live SOS each."""
from app.models.notification import Notification
from app.models.resident import Resident, ResidentType
from tests.conftest import make_flat, make_society, make_user, make_wing

N = "/api/v1/notices"


def _login(db, email, role, society, flat=None):
    u = make_user(db, email, role=role, full_name=email.split("@")[0].title())
    u["user"].society_id = society.id
    if flat is not None:
        db.add(Resident(flat_id=flat.id, user_id=u["user"].id, full_name=email.split("@")[0],
                        resident_type=ResidentType.OWNER, is_primary=True))
    db.commit()
    return u


def _rig(db, tag):
    society = make_society(db, f"Sos {tag}")
    wing = make_wing(db, society.id, "S")
    f1, f2 = make_flat(db, wing.id, "1"), make_flat(db, wing.id, "2")
    guard = _login(db, f"sos.guard.{tag}@t.com", "Security Staff", society)
    admin = _login(db, f"sos.admin.{tag}@t.com", "Society Admin", society)
    r1 = _login(db, f"sos.r1.{tag}@t.com", "Resident", society, f1)
    r2 = _login(db, f"sos.r2.{tag}@t.com", "Resident", society, f2)
    return society, guard, admin, r1, r2


def _active(client, who, society):
    r = client.get(f"{N}/emergency/active/{society.id}", headers=who["headers"])
    assert r.status_code == 200, r.text
    return r.json()


def test_a_resident_raises_an_sos_that_names_their_flat(client, db):
    society, guard, admin, r1, r2 = _rig(db, "a")
    r = client.post(f"{N}/emergency/sos", json={"alert_type": "medical", "description": "Chest pain"}, headers=r1["headers"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["is_sos"] is True and body["alert_type"] == "medical"
    assert body["title"] == "SOS from S-1" and body["location"] == "S-1"
    assert "Chest pain" in body["description"]


def test_security_and_the_committee_are_told_the_neighbours_are_not(client, db):
    society, guard, admin, r1, r2 = _rig(db, "b")
    client.post(f"{N}/emergency/sos", json={"alert_type": "fire"}, headers=r1["headers"])
    got = lambda u: db.query(Notification).filter(Notification.user_id == u["user"].id, Notification.module == "emergency").count()
    assert got(guard) == 1 and got(admin) == 1
    assert got(r2) == 0 and got(r1) == 0


def test_the_sos_is_on_the_banner_for_responders_and_its_owner_only(client, db):
    society, guard, admin, r1, r2 = _rig(db, "c")
    client.post(f"{N}/emergency/sos", json={}, headers=r1["headers"])
    assert len(_active(client, guard, society)) == 1
    assert len(_active(client, admin, society)) == 1
    assert len(_active(client, r1, society)) == 1
    assert _active(client, r2, society) == []


def test_pressing_it_twice_does_not_raise_a_second_alert(client, db):
    society, guard, admin, r1, r2 = _rig(db, "d")
    a = client.post(f"{N}/emergency/sos", json={}, headers=r1["headers"]).json()
    b = client.post(f"{N}/emergency/sos", json={}, headers=r1["headers"]).json()
    assert a["id"] == b["id"]
    assert len(_active(client, guard, society)) == 1


def test_the_resident_can_end_their_own_sos_and_security_can_too(client, db):
    society, guard, admin, r1, r2 = _rig(db, "e")
    a = client.post(f"{N}/emergency/sos", json={}, headers=r1["headers"]).json()
    assert client.post(f"{N}/emergency/sos/{a['id']}/cancel", headers=r2["headers"]).status_code == 404   # not theirs
    ok = client.post(f"{N}/emergency/sos/{a['id']}/cancel", headers=r1["headers"])
    assert ok.status_code == 200 and ok.json()["status"] == "resolved"
    assert _active(client, guard, society) == []
    # a new one can be raised after the first ended
    b = client.post(f"{N}/emergency/sos", json={}, headers=r1["headers"]).json()
    assert b["id"] != a["id"]
    assert client.post(f"{N}/emergency/{b['id']}/resolve", json={"notes": "Attended"}, headers=guard["headers"]).status_code == 200


def test_only_the_four_sos_types_are_accepted(client, db):
    society, guard, admin, r1, r2 = _rig(db, "f")
    assert client.post(f"{N}/emergency/sos", json={"alert_type": "flood"}, headers=r1["headers"]).status_code == 422
    assert client.post(f"{N}/emergency/sos", json={"alert_type": "security_threat"}, headers=r1["headers"]).status_code == 201


def test_an_sos_in_one_society_is_invisible_in_another(client, db):
    society, guard, admin, r1, r2 = _rig(db, "g")
    other, oguard, oadmin, o1, o2 = _rig(db, "g2")
    client.post(f"{N}/emergency/sos", json={}, headers=r1["headers"])
    assert _active(client, oguard, other) == []
    assert client.get(f"{N}/emergency/active/{society.id}", headers=oguard["headers"]).status_code in (403, 404)


def test_ordinary_alerts_still_reach_everyone(client, db):
    society, guard, admin, r1, r2 = _rig(db, "h")
    r = client.post(f"{N}/emergency/", json={"alert_type": "fire", "title": "Fire drill"}, headers=admin["headers"])
    assert r.status_code == 201
    assert len(_active(client, r2, society)) == 1
