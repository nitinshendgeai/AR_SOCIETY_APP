"""Society structure — wings, floors and flats: what the forms send must be
accepted, what is wrong must be refused with a clear message, and removing or
renumbering one part must not leave the rest pointing at nothing."""
from uuid import uuid4

from tests.conftest import make_flat, make_society, make_user, make_wing

API = "/api/v1"


def _rig(db, tag):
    """A society with an admin who belongs to it, one wing, and a second
    society to check isolation against."""
    society = make_society(db, f"Struct Society {tag}")
    admin = make_user(db, f"admin@struct{tag}.com", role="Society Admin")
    admin["user"].society_id = society.id
    db.commit()
    wing = make_wing(db, society.id, f"Wing {tag}")
    wing.code = tag.upper()
    db.commit()
    return society, admin["headers"], wing


def _wing(client, h, society, name, **extra):
    return client.post(f"{API}/wings/", json={"name": name, "society_id": str(society.id), **extra}, headers=h)


def _floor(client, h, society, wing, number, **extra):
    return client.post(f"{API}/floors/", json={"floor_number": number, "wing_id": str(wing.id),
                                               "society_id": str(society.id), **extra}, headers=h)


def _flat(client, h, wing, number, **extra):
    return client.post(f"{API}/flats/", json={"flat_number": number, "wing_id": str(wing.id), **extra}, headers=h)


# ── Flats ─────────────────────────────────────────────────────────────────────

def test_every_flat_type_the_form_offers_is_accepted(client, db):
    """The Add Flat form offers these; each must save."""
    _society, h, wing = _rig(db, "ft")
    for i, flat_type in enumerate(["1BHK", "2BHK", "3BHK", "4BHK", "Studio", "Duplex", "Penthouse", "Shop",
                                   "Office", "Other"]):
        r = _flat(client, h, wing, f"T{i}", flat_type=flat_type)
        assert r.status_code == 201, (flat_type, r.text)
        assert r.json()["flat_type"] == flat_type


def test_new_flat_starts_vacant_and_is_listed(client, db):
    society, h, wing = _rig(db, "nv")
    r = _flat(client, h, wing, "101", floor=1, area_sqft=850)
    assert r.status_code == 201, r.text
    assert r.json()["occupancy_status"] == "vacant"
    listed = client.get(f"{API}/flats/by-society/{society.id}", headers=h).json()
    assert [f["flat_number"] for f in listed] == ["101"]


def test_flat_number_is_trimmed_and_unique_per_wing(client, db):
    _society, h, wing = _rig(db, "fu")
    r = _flat(client, h, wing, "  A-101 ")
    assert r.status_code == 201 and r.json()["flat_number"] == "A-101"
    assert _flat(client, h, wing, "A-101").status_code == 409
    assert _flat(client, h, wing, " A-101").status_code == 409
    other = client.post(f"{API}/wings/", json={"name": "Other", "society_id": str(wing.society_id)}, headers=h).json()
    assert client.post(f"{API}/flats/", json={"flat_number": "A-101", "wing_id": other["id"]},
                       headers=h).status_code == 201


def test_flat_rejects_blank_number_and_nonsense_values(client, db):
    _society, h, wing = _rig(db, "fv")
    assert _flat(client, h, wing, "   ").status_code == 422
    assert _flat(client, h, wing, "").status_code == 422
    assert _flat(client, h, wing, "101", area_sqft=0).status_code == 422
    assert _flat(client, h, wing, "101", area_sqft=-5).status_code == 422
    assert _flat(client, h, wing, "101", flat_type="Castle").status_code == 422
    ok = _flat(client, h, wing, "101", floor=-1)  # basement
    assert ok.status_code == 201
    fid = ok.json()["id"]
    assert client.patch(f"{API}/flats/{fid}", json={"flat_number": " "}, headers=h).status_code == 422
    assert client.patch(f"{API}/flats/{fid}", json={"area_sqft": -1}, headers=h).status_code == 422


def test_edit_flat_changes_what_the_form_sends(client, db):
    society, h, wing = _rig(db, "fe")
    fid = _flat(client, h, wing, "101", floor=1).json()["id"]
    r = client.patch(f"{API}/flats/{fid}", json={
        "flat_number": "102", "floor": 2, "flat_type": "3BHK", "area_sqft": 1100.5, "remarks": "corner",
        "virtual_account_number": ""}, headers=h)
    assert r.status_code == 200, r.text
    got = client.get(f"{API}/flats/{fid}", headers=h).json()
    assert (got["flat_number"], got["floor"], got["flat_type"], got["area_sqft"], got["remarks"]) == (
        "102", 2, "3BHK", 1100.5, "corner")


def test_flat_cannot_be_deleted_while_people_or_dues_depend_on_it(client, db):
    from app.models.resident import Resident
    society, h, wing = _rig(db, "fd")
    empty = _flat(client, h, wing, "201").json()["id"]
    assert client.delete(f"{API}/flats/{empty}", headers=h).status_code == 204
    assert client.get(f"{API}/flats/{empty}", headers=h).status_code == 404
    # the number is free again
    assert _flat(client, h, wing, "201").status_code == 201

    lived_in = make_flat(db, wing.id, "202")
    db.add(Resident(full_name="Asha Rao", flat_id=lived_in.id, is_primary=True))
    db.commit()
    r = client.delete(f"{API}/flats/{lived_in.id}", headers=h)
    assert r.status_code == 409 and "resident" in r.json()["detail"].lower()
    assert client.get(f"{API}/flats/{lived_in.id}", headers=h).status_code == 200


# ── Floors ────────────────────────────────────────────────────────────────────

def test_floor_create_list_and_validation(client, db):
    society, h, wing = _rig(db, "fl")
    for n in (2, 0, -1, 1):
        assert _floor(client, h, society, wing, n).status_code == 201
    listed = client.get(f"{API}/floors/by-wing/{wing.id}", headers=h).json()
    assert [f["floor_number"] for f in listed] == [-1, 0, 1, 2]
    assert _floor(client, h, society, wing, 1).status_code == 409
    assert _floor(client, h, society, wing, 500).status_code == 422
    assert _floor(client, h, society, wing, -50).status_code == 422
    # A wing of another society is not found
    other_society, _h2, other_wing = _rig(db, "fl2")
    assert _floor(client, h, society, other_wing, 1).status_code == 404


def test_floor_flat_count_follows_the_flats_on_it(client, db):
    society, h, wing = _rig(db, "fc")
    fl = _floor(client, h, society, wing, 3).json()
    _flat(client, h, wing, "301", floor=3)
    _flat(client, h, wing, "302", floor=3)
    _flat(client, h, wing, "401", floor=4)
    assert client.get(f"{API}/floors/{fl['id']}", headers=h).json()["flat_count"] == 2


def test_renumbering_a_floor_moves_its_flats_with_it(client, db):
    society, h, wing = _rig(db, "fr")
    fl = _floor(client, h, society, wing, 3).json()
    a = _flat(client, h, wing, "301", floor=3).json()["id"]
    b = _flat(client, h, wing, "401", floor=4).json()["id"]
    r = client.patch(f"{API}/floors/{fl['id']}", json={"floor_number": 5}, headers=h)
    assert r.status_code == 200 and r.json()["flat_count"] == 1
    assert client.get(f"{API}/flats/{a}", headers=h).json()["floor"] == 5
    assert client.get(f"{API}/flats/{b}", headers=h).json()["floor"] == 4
    # Not onto a number the wing already has
    _floor(client, h, society, wing, 6)
    assert client.patch(f"{API}/floors/{fl['id']}", json={"floor_number": 6}, headers=h).status_code == 409


def test_floor_with_flats_cannot_be_deleted(client, db):
    society, h, wing = _rig(db, "fx")
    fl = _floor(client, h, society, wing, 2).json()
    flat = _flat(client, h, wing, "201", floor=2).json()["id"]
    r = client.delete(f"{API}/floors/{fl['id']}", headers=h)
    assert r.status_code == 409 and "flat" in r.json()["detail"].lower()
    assert client.delete(f"{API}/flats/{flat}", headers=h).status_code == 204
    assert client.delete(f"{API}/floors/{fl['id']}", headers=h).status_code == 204


# ── Wings ─────────────────────────────────────────────────────────────────────

def test_wing_validation(client, db):
    society, h, _wing0 = _rig(db, "wv")
    assert _wing(client, h, society, "   ").status_code == 422
    assert _wing(client, h, society, "B Block", total_floors=0).status_code == 422
    assert _wing(client, h, society, "B Block", total_floors=-3).status_code == 422
    r = _wing(client, h, society, "  B Block ", code="b", total_floors=12)
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "B Block" and r.json()["total_floors"] == 12
    assert _wing(client, h, society, "b block").status_code == 409
    assert _wing(client, h, society, "C Block", code="B").status_code == 409


def test_wings_are_listed_in_natural_order(client, db):
    society, h, _w = _rig(db, "wo")
    for name in ("Tower 10", "Tower 2", "Tower 1"):
        assert _wing(client, h, society, name).status_code == 201
    names = [w["name"] for w in client.get(f"{API}/wings/by-society/{society.id}", headers=h).json()]
    assert names == ["Tower 1", "Tower 2", "Tower 10", "Wing wo"]


def test_wing_with_flats_cannot_be_deleted_and_empty_one_takes_its_floors(client, db):
    society, h, wing = _rig(db, "wd")
    flat = _flat(client, h, wing, "101", floor=1).json()["id"]
    _floor(client, h, society, wing, 1)
    r = client.delete(f"{API}/wings/{wing.id}", headers=h)
    assert r.status_code == 409 and "flat" in r.json()["detail"].lower()
    assert client.delete(f"{API}/flats/{flat}", headers=h).status_code == 204
    assert client.delete(f"{API}/wings/{wing.id}", headers=h).status_code == 204
    # nothing of it is left behind
    assert client.get(f"{API}/floors/by-society/{society.id}", headers=h).json() == []
    assert client.get(f"{API}/wings/by-society/{society.id}", headers=h).json() == []
    assert client.get(f"{API}/floors/by-wing/{wing.id}", headers=h).status_code == 404


def test_a_deactivated_wing_can_be_activated_again(client, db):
    society, h, wing = _rig(db, "wa")
    flat = _flat(client, h, wing, "101").json()["id"]
    wings = f"{API}/wings/by-society/{society.id}"
    r = client.post(f"{API}/wings/{wing.id}/deactivate", headers=h)
    assert r.status_code == 200 and r.json()["is_active"] is False
    # Hidden from the pickers, still there to be found and switched on again
    assert client.get(wings, headers=h).json() == []
    assert [w["id"] for w in client.get(wings, params={"include_inactive": True}, headers=h).json()] == [str(wing.id)]
    # Its flats keep their residents and bills, so they stay; nothing new can be added to it
    assert [f["id"] for f in client.get(f"{API}/flats/by-society/{society.id}", headers=h).json()] == [flat]
    assert _flat(client, h, wing, "102").status_code == 409
    assert _floor(client, h, society, wing, 1).status_code == 409
    assert client.patch(f"{API}/wings/{wing.id}", json={"description": "Under repair"}, headers=h).status_code == 200

    r = client.post(f"{API}/wings/{wing.id}/activate", headers=h)
    assert r.status_code == 200 and r.json()["is_active"] is True
    assert [w["id"] for w in client.get(wings, headers=h).json()] == [str(wing.id)]
    assert _flat(client, h, wing, "102").status_code == 201


def test_activating_a_wing_whose_name_was_taken_meanwhile_is_refused(client, db):
    society, h, wing = _rig(db, "wt")
    assert client.post(f"{API}/wings/{wing.id}/deactivate", headers=h).status_code == 200
    assert _wing(client, h, society, wing.name).status_code == 201
    r = client.post(f"{API}/wings/{wing.id}/activate", headers=h)
    assert r.status_code == 409 and "already exists" in r.json()["detail"]


def test_a_deleted_wing_cannot_be_brought_back(client, db):
    society, h, wing = _rig(db, "wx")
    assert client.delete(f"{API}/wings/{wing.id}", headers=h).status_code == 204
    assert client.post(f"{API}/wings/{wing.id}/activate", headers=h).status_code == 404
    assert client.get(f"{API}/wings/by-society/{society.id}", params={"include_inactive": True},
                      headers=h).json() == []


# ── Who may do what, and whose data ───────────────────────────────────────────

def test_other_societies_structure_is_off_limits(client, db):
    society, h, wing = _rig(db, "iso")
    other_society, h2, other_wing = _rig(db, "iso2")
    flat = _flat(client, h2, other_wing, "101").json()["id"]
    assert client.get(f"{API}/flats/{flat}", headers=h).status_code == 404
    assert client.patch(f"{API}/flats/{flat}", json={"remarks": "x"}, headers=h).status_code in (403, 404)
    assert client.delete(f"{API}/flats/{flat}", headers=h).status_code in (403, 404)
    assert client.get(f"{API}/flats/by-society/{other_society.id}", headers=h).status_code == 403
    assert client.get(f"{API}/floors/by-society/{other_society.id}", headers=h).status_code == 403
    assert client.get(f"{API}/flats/by-wing/{other_wing.id}", headers=h).status_code == 404


def test_residents_cannot_change_the_structure(client, db):
    society, h, wing = _rig(db, "rb")
    res = make_user(db, "res@structrb.com", role="Resident")
    res["user"].society_id = society.id
    db.commit()
    rh = res["headers"]
    assert client.get(f"{API}/flats/by-society/{society.id}", headers=rh).status_code == 200
    assert _flat(client, rh, wing, "101").status_code == 403
    assert _floor(client, rh, society, wing, 1).status_code == 403
    assert _wing(client, rh, society, "X").status_code == 403
    assert client.delete(f"{API}/wings/{wing.id}", headers=rh).status_code == 403
    assert client.delete(f"{API}/flats/{uuid4()}", headers=rh).status_code == 403


# ── Society profile (the first step of the setup wizard) ─────────────────────

def test_society_profile_rules(client, db):
    society, h, _wing = _rig(db, "sp")
    url = f"{API}/societies/{society.id}"

    def patch(**fields):
        return client.patch(url, json=fields, headers=h)

    # Billing day and late fee stay in range
    for bad in ({"maintenance_day": 0}, {"maintenance_day": 29}, {"late_fee_percent": 101},
                {"late_fee_percent": -1}):
        assert patch(**bad).status_code == 422, bad
    assert patch(maintenance_day=28, late_fee_percent=0).status_code == 200

    # Identifiers as printed on bills and returns: checked, and tidied
    assert patch(pincode="40001").status_code == 422
    assert patch(pan_number="123").status_code == 422
    assert patch(gst_number="X").status_code == 422
    assert patch(contact_email="nope").status_code == 422
    assert patch(contact_phone="abc").status_code == 422
    r = patch(pincode="400 001", pan_number="abcde1234f", gst_number=" 27aaaaa0000a1z5 ",
              contact_email="Office@Society.IN", contact_phone="+91 98765-43210")
    assert r.status_code == 200, r.text
    got = r.json()
    assert (got["pincode"], got["pan_number"], got["gst_number"], got["contact_email"], got["contact_phone"]) == (
        "400001", "ABCDE1234F", "27AAAAA0000A1Z5", "office@society.in", "+919876543210")

    # A name is never blank, and never another society's
    assert patch(name="   ").status_code == 422
    other = make_society(db, "Some Other Society")
    r = patch(name=other.name)
    assert r.status_code == 409 and "already" in r.json()["detail"]
    assert patch(name=" New  Name  CHS ").json()["name"] == "New Name CHS"


# ── Users & Roles (the last step of the setup wizard) ────────────────────────

def test_creating_a_user_hands_over_the_temporary_password(client, db):
    from app.core.security import verify_password
    from app.models.role import Role
    from app.models.user import User
    society, h, _wing = _rig(db, "uc")
    db.add(Role(name="Resident"))
    db.commit()
    r = client.post(f"{API}/users/", json={"email": " New@Person.IN ", "full_name": "  Rahul   Sharma ",
                                          "phone": "+91 98765-43210", "role_name": "Resident"}, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "new@person.in" and body["full_name"] == "Rahul Sharma"
    assert body["phone"] == "+919876543210" and body["roles"] == ["Resident"]
    assert body["must_change_password"] is True and body["society_id"] == str(society.id)
    # the password shown is the one that was set
    user = db.query(User).filter_by(email="new@person.in").one()
    assert len(body["temporary_password"]) >= 10
    assert verify_password(body["temporary_password"], user.hashed_password)
    # …and only once: reading the user back doesn't show it
    assert "temporary_password" not in client.get(f"{API}/users/{body['id']}", headers=h).json()


def test_user_form_input_is_checked(client, db):
    from app.models.role import Role
    from app.models.user import UserRole, User
    society, h, _wing = _rig(db, "uv")
    db.add_all([Role(name="Resident"), Role(name="Platform Admin")])
    db.commit()

    def create(**kw):
        return client.post(f"{API}/users/", json={"email": "x@struct.in", "full_name": "X Person", **kw}, headers=h)

    assert create(full_name="   ").status_code == 422
    assert create(full_name="x" * 300).status_code == 422
    assert create(phone="abc").status_code == 422
    assert create(phone="9" * 40).status_code == 422
    assert create(email="not-an-email").status_code == 422
    # a role that isn't one of the society's is refused, not quietly invented
    r = create(role_name="Reseident")
    assert r.status_code == 422 and "Unknown role" in r.json()["detail"]
    assert db.query(Role).filter_by(name="Reseident").count() == 0
    # and the platform's own role isn't the society admin's to give
    assert create(role_name="Platform Admin").status_code == 403
    assert db.query(User).filter_by(email="x@struct.in").count() == 0
    ok = create(role_name="Resident")
    assert ok.status_code == 201
    assert create().status_code == 409                          # the email is taken
    assert client.post(f"{API}/users/{ok.json()['id']}/roles", json={"role_name": "Platform Admin"},
                       headers=h).status_code == 403
    assert db.query(UserRole).join(Role).filter(Role.name == "Platform Admin").count() == 0
    # editing keeps the same rules
    uid = ok.json()["id"]
    assert client.patch(f"{API}/users/{uid}", json={"full_name": " "}, headers=h).status_code == 422
    assert client.patch(f"{API}/users/{uid}", json={"phone": "12"}, headers=h).status_code == 422
    assert client.patch(f"{API}/users/{uid}", json={"full_name": "Rahul S", "phone": "98765 43210"},
                        headers=h).json()["phone"] == "9876543210"
