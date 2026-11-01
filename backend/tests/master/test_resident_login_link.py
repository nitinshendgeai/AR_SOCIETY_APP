"""Linking an existing app login to a resident, and unlinking it: how a login reaches a flat's bills."""
from tests.conftest import make_flat, make_society, make_user, make_wing

R = "/api/v1/residents"


def _rig(db, tag):
    society = make_society(db, f"Link Society {tag}")
    admin = make_user(db, f"link-admin-{tag}@x.test", role="Society Admin")
    admin["user"].society_id = society.id
    wing = make_wing(db, society.id, "A")
    flat = make_flat(db, wing.id, "101")
    login = make_user(db, f"link-login-{tag}@x.test", role="Resident", full_name="Existing Login")
    login["user"].society_id = society.id
    db.commit()
    return society, admin["headers"], flat, login


def _resident(client, h, flat, **extra):
    r = client.post(f"{R}/", headers=h, json={"flat_id": str(flat.id), "full_name": "Owner", "resident_type": "owner",
                                              **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_a_login_is_linked_to_a_resident_and_the_flat_follows_it(client, db):
    society, h, flat, login = _rig(db, "l1")
    res = _resident(client, h, flat)                                        # no mobile: no login was made for them
    assert res["user_id"] is None
    r = client.patch(f"{R}/{res['id']}", headers=h, json={"user_id": str(login["user"].id)})
    assert r.status_code == 200 and r.json()["user_id"] == str(login["user"].id)
    me = client.get(f"{R}/me", headers=login["headers"])                    # the login now has its flat
    assert me.status_code == 200 and me.json()["flat_id"] == str(flat.id)


def test_a_login_can_be_unlinked_and_an_edit_without_it_leaves_it_alone(client, db):
    society, h, flat, login = _rig(db, "l2")
    res = _resident(client, h, flat, user_id=str(login["user"].id))
    r = client.patch(f"{R}/{res['id']}", headers=h, json={"full_name": "Renamed Owner"})
    assert r.json()["user_id"] == str(login["user"].id)                      # not sent: untouched
    r = client.patch(f"{R}/{res['id']}", headers=h, json={"user_id": None})
    assert r.status_code == 200 and r.json()["user_id"] is None
    assert client.get(f"{R}/me", headers=login["headers"]).status_code == 404


def test_only_a_login_of_the_same_society_can_be_linked(client, db):
    society, h, flat, login = _rig(db, "l3")
    other = make_society(db, "Other Link Society l3")
    stranger = make_user(db, "link-stranger-l3@x.test", role="Resident")
    stranger["user"].society_id = other.id
    db.commit()
    res = _resident(client, h, flat)
    r = client.patch(f"{R}/{res['id']}", headers=h, json={"user_id": str(stranger["user"].id)})
    assert r.status_code == 404
