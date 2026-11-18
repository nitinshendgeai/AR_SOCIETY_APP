"""A society's own roles: an admin adds a role (optionally starting from another's permissions and screens), renames it,
deletes it once nobody holds it, and gives it to the society's users. Only that society sees it; the standard roles stay
shared and can't be renamed or deleted here."""
import pytest

from app.models.role import Role
from tests.conftest import make_society, make_user, place_in

R = "/api/v1/roles"


@pytest.fixture
def rig(db):
    one, two = make_society(db, "Roles Society One"), make_society(db, "Roles Society Two")
    admin1 = place_in(db, make_user(db, "admin1@roles.test", role="Society Admin"), one)
    admin2 = place_in(db, make_user(db, "admin2@roles.test", role="Society Admin"), two)
    manager = place_in(db, make_user(db, "mgr@roles.test", role="Manager"), one)
    return {"one": one, "two": two, "a1": admin1, "a2": admin2, "manager": manager}


def _create(client, who, name="Gym Instructor", **body):
    return client.post(f"{R}/", json={"name": name, **body}, headers=who["headers"])


def _by_name(client, who):
    return {r["name"]: r for r in client.get(f"{R}/", headers=who["headers"]).json()}


def test_an_admin_adds_a_role_and_it_is_listed_as_the_societys_own(client, rig):
    r = _create(client, rig["a1"], description="  Runs the gym  ")
    assert r.status_code == 201, r.text
    assert (r.json()["name"], r.json()["description"], r.json()["is_custom"], r.json()["user_count"]) == \
        ("Gym Instructor", "Runs the gym", True, 0)
    roles = _by_name(client, rig["a1"])
    assert roles["Gym Instructor"]["is_custom"] is True
    assert roles["Manager"]["is_custom"] is False                      # the standard roles are shared
    assert roles["Manager"]["user_count"] == 1                          # held by one user of this society


def test_names_are_cleaned_and_must_not_clash(client, rig):
    assert _create(client, rig["a1"], "  Gym   Instructor ").json()["name"] == "Gym Instructor"
    assert _create(client, rig["a1"], "gym instructor").status_code == 409          # the society's own, any case
    assert _create(client, rig["a1"], "manager").status_code == 409                  # a standard role's name
    assert _create(client, rig["a1"], "Platform Admin").status_code == 409
    for bad in ("ab", "12345", "x" * 61, "   "):
        assert _create(client, rig["a1"], bad).status_code == 422, bad
    assert _create(client, rig["a1"], "Long note", description="x" * 501).status_code == 422


def test_only_an_admin_adds_roles(client, rig):
    assert _create(client, rig["manager"]).status_code == 403


def test_another_society_neither_sees_nor_touches_it_and_may_use_the_same_name(client, rig, db):
    role_id = _create(client, rig["a1"]).json()["id"]
    assert "Gym Instructor" not in _by_name(client, rig["a2"])
    assert client.patch(f"{R}/{role_id}", json={"name": "Stolen"}, headers=rig["a2"]["headers"]).status_code == 404
    assert client.delete(f"{R}/{role_id}", headers=rig["a2"]["headers"]).status_code == 404
    assert client.put(f"{R}/{role_id}/permissions", json={"permission_codes": []},
                      headers=rig["a2"]["headers"]).status_code == 404
    assert client.put(f"{R}/{role_id}/forms", json={"form_codes": []}, headers=rig["a2"]["headers"]).status_code == 404
    assert _create(client, rig["a2"]).status_code == 201                                  # each has its own
    matrix = [r["role_name"] for r in client.get(f"{R}/permission-matrix", headers=rig["a2"]["headers"]).json()]
    assert matrix.count("Gym Instructor") == 1
    assert db.query(Role).filter(Role.name == "Gym Instructor").count() == 2


def test_a_new_role_can_start_from_another_roles_permissions_and_screens(client, rig, db):
    manager = db.query(Role).filter(Role.name == "Manager").one()
    assert client.put(f"{R}/{manager.id}/permissions", json={"permission_codes": ["manager_above"]},
                      headers=rig["a1"]["headers"]).status_code == 200
    assert client.put(f"{R}/{manager.id}/forms", json={"form_codes": ["vendors", "assets"]},
                      headers=rig["a1"]["headers"]).status_code == 200
    r = _create(client, rig["a1"], "Assistant Manager", copy_from_role_id=str(manager.id))
    assert r.status_code == 201, r.text
    perms = {x["role_name"]: x["permission_codes"] for x in client.get(f"{R}/permission-matrix", headers=rig["a1"]["headers"]).json()}
    forms = {x["role_name"]: x["form_codes"] for x in client.get(f"{R}/form-matrix", headers=rig["a1"]["headers"]).json()}
    assert perms["Assistant Manager"] == ["manager_above"] and forms["Assistant Manager"] == ["assets", "vendors"]
    # copying leaves the source alone, and a role that doesn't exist is refused
    assert perms["Manager"] == ["manager_above"]
    assert _create(client, rig["a1"], "Nothing", copy_from_role_id="00000000-0000-0000-0000-000000000000").status_code == 404
    # the platform team's role is not a starting point for a society
    make_user(db, "pa@roles.test", role="Platform Admin")
    platform = db.query(Role).filter(Role.name == "Platform Admin").one()
    assert _create(client, rig["a1"], "Console", copy_from_role_id=str(platform.id)).status_code == 403


def test_a_new_role_starts_with_nothing_and_what_it_is_granted_takes_effect(client, rig, db):
    role = _create(client, rig["a1"]).json()
    forms = {x["role_name"]: x["form_codes"] for x in client.get(f"{R}/form-matrix", headers=rig["a1"]["headers"]).json()}
    assert forms["Gym Instructor"] == []
    assert client.put(f"{R}/{role['id']}/forms", json={"form_codes": ["amenities"]},
                      headers=rig["a1"]["headers"]).status_code == 200
    # give it to a user of the society: their screens come from it
    member = place_in(db, make_user(db, "gym@roles.test", role="Resident"), rig["one"])
    r = client.post(f"/api/v1/users/{member['user'].id}/roles", json={"role_name": "Gym Instructor"},
                    headers=rig["a1"]["headers"])
    assert r.status_code == 200, r.text
    assert "Gym Instructor" in r.json()["roles"]
    mine = client.get(f"{R}/forms/mine", headers=member["headers"]).json()["form_codes"]
    assert "amenities" in mine
    assert _by_name(client, rig["a1"])["Gym Instructor"]["user_count"] == 1


def test_rename_and_describe_a_role(client, rig):
    role = _create(client, rig["a1"]).json()
    r = client.patch(f"{R}/{role['id']}", json={"name": " Fitness Coach ", "description": ""}, headers=rig["a1"]["headers"])
    assert r.status_code == 200, r.text
    assert (r.json()["name"], r.json()["description"]) == ("Fitness Coach", None)
    other = _create(client, rig["a1"], "Librarian").json()
    assert client.patch(f"{R}/{other['id']}", json={"name": "fitness coach"}, headers=rig["a1"]["headers"]).status_code == 409
    assert client.patch(f"{R}/{other['id']}", json={"name": "Librarian"}, headers=rig["a1"]["headers"]).status_code == 200  # itself
    assert client.patch(f"{R}/{other['id']}", json={"name": "Manager"}, headers=rig["a1"]["headers"]).status_code == 409


def test_a_role_in_use_is_not_deleted_and_one_not_in_use_is(client, rig, db):
    role = _create(client, rig["a1"]).json()
    member = place_in(db, make_user(db, "gym2@roles.test", role="Resident"), rig["one"])
    client.post(f"/api/v1/users/{member['user'].id}/roles", json={"role_name": "Gym Instructor"},
                headers=rig["a1"]["headers"])
    r = client.delete(f"{R}/{role['id']}", headers=rig["a1"]["headers"])
    assert r.status_code == 409 and "1 user holds" in r.json()["detail"]
    client.delete(f"/api/v1/users/{member['user'].id}/roles/Gym Instructor", headers=rig["a1"]["headers"])
    assert client.delete(f"{R}/{role['id']}", headers=rig["a1"]["headers"]).status_code == 204
    assert "Gym Instructor" not in _by_name(client, rig["a1"])


def test_the_standard_roles_cannot_be_renamed_or_deleted(client, rig, db):
    manager = db.query(Role).filter(Role.name == "Manager").one()
    for call in (client.patch(f"{R}/{manager.id}", json={"name": "Boss"}, headers=rig["a1"]["headers"]),
                 client.delete(f"{R}/{manager.id}", headers=rig["a1"]["headers"])):
        assert call.status_code == 403 and "standard role" in call.json()["detail"]


def test_users_get_their_own_societys_role_when_names_repeat(client, rig, db):
    """Both societies have a 'Gym Instructor': assigning by name picks the caller's society's, not the other's."""
    one = _create(client, rig["a1"]).json()["id"]
    two = _create(client, rig["a2"]).json()["id"]
    member2 = place_in(db, make_user(db, "gym3@roles.test", role="Resident"), rig["two"])
    r = client.post(f"/api/v1/users/{member2['user'].id}/roles", json={"role_name": "Gym Instructor"},
                    headers=rig["a2"]["headers"])
    assert r.status_code == 200, r.text
    db.expire_all()
    held = {str(ur.role_id) for ur in member2["user"].user_roles}
    assert two in held and one not in held
