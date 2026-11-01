"""The "Residents without a login" report: who can sign in, and for the ones who cannot, why."""
from app.models.resident import Resident
from tests.conftest import make_flat, make_society, make_user, make_wing

URL = "/api/v1/residents/login-status"


def _rig(db, tag):
    society = make_society(db, f"Login Status Society {tag}")
    admin = make_user(db, f"ls-admin-{tag}@x.test", role="Society Admin")
    admin["user"].society_id = society.id
    wing = make_wing(db, society.id, "A")
    flats = {n: make_flat(db, wing.id, n) for n in ("101", "102", "103", "104", "105", "106")}
    db.commit()
    return society, admin, flats


def _login(db, society, email, phone, status=None):
    u = make_user(db, email, role="Resident", full_name=f"Login {phone}")["user"]
    u.society_id, u.phone = society.id, phone
    if status is not None:
        u.status = status
    db.commit()
    return u


def test_each_resident_is_linked_unlinked_or_missing_a_login_or_a_mobile(client, db):
    from app.models.user import UserStatus
    society, admin, flats = _rig(db, "s1")
    linked = _login(db, society, "ls-linked-s1@x.test", "9000000001")
    disabled = _login(db, society, "ls-off-s1@x.test", "9000000002", UserStatus.SUSPENDED)
    exists = _login(db, society, "ls-exists-s1@x.test", "9000000003")
    people = [
        Resident(flat_id=flats["101"].id, full_name="Linked Owner", phone="9000000001", user_id=linked.id),
        Resident(flat_id=flats["102"].id, full_name="Disabled Owner", phone="9000000002", user_id=disabled.id),
        Resident(flat_id=flats["103"].id, full_name="Has Login Not Linked", phone="+91 90000-00003"),   # typed differently
        Resident(flat_id=flats["104"].id, full_name="No Login Yet", phone="9000000004"),
        Resident(flat_id=flats["105"].id, full_name="No Mobile"),
        Resident(flat_id=flats["106"].id, full_name="Moved Out", phone="9000000006", is_active=False),
    ]
    db.add_all(people)
    db.commit()
    r = client.get(URL, headers=admin["headers"])
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["summary"] == {"linked": 1, "login_disabled": 1, "login_unlinked": 1, "no_login": 1, "no_mobile": 1,
                              "total": 5, "needs_attention": 4}
    by_name = {x["full_name"]: x for x in out["residents"]}
    assert by_name["Linked Owner"]["status"] == "linked" and by_name["Linked Owner"]["login"]["id"] == str(linked.id)
    assert by_name["Disabled Owner"]["status"] == "login_disabled"
    assert by_name["Has Login Not Linked"]["status"] == "login_unlinked"
    assert by_name["Has Login Not Linked"]["login"]["id"] == str(exists.id)         # ready to link
    assert by_name["No Login Yet"]["status"] == "no_login" and by_name["No Login Yet"]["login"] is None
    assert by_name["No Mobile"]["status"] == "no_mobile" and by_name["No Mobile"]["phone"] is None
    assert "Moved Out" not in by_name                                                # only active residents
    assert by_name["Linked Owner"]["flat_label"] == "A / 101"


def test_filters_and_search_and_the_summary_still_counts_everyone(client, db):
    society, admin, flats = _rig(db, "s2")
    db.add_all([Resident(flat_id=flats["101"].id, full_name="Asha Rao", phone="9000000011"),
                Resident(flat_id=flats["102"].id, full_name="Vik Mehta")])
    db.commit()
    h = admin["headers"]
    only = client.get(URL, headers=h, params={"status": "no_mobile"}).json()
    assert [x["full_name"] for x in only["residents"]] == ["Vik Mehta"]
    assert only["summary"]["total"] == 2                                              # the summary is the whole society
    attention = client.get(URL, headers=h, params={"status": "needs_attention"}).json()
    assert len(attention["residents"]) == 2
    found = client.get(URL, headers=h, params={"search": "asha"}).json()
    assert [x["full_name"] for x in found["residents"]] == ["Asha Rao"]
    assert [x["full_name"] for x in client.get(URL, headers=h, params={"search": "A / 102"}).json()["residents"]] \
        == ["Vik Mehta"]
    assert client.get(URL, headers=h, params={"status": "nonsense"}).status_code == 422


def test_it_is_admin_only_and_never_shows_another_societys_residents(client, db):
    society, admin, flats = _rig(db, "s3")
    other, other_admin, other_flats = _rig(db, "s3b")
    db.add_all([Resident(flat_id=flats["101"].id, full_name="Mine"),
                Resident(flat_id=other_flats["101"].id, full_name="Theirs")])
    db.commit()
    names = [x["full_name"] for x in client.get(URL, headers=admin["headers"]).json()["residents"]]
    assert names == ["Mine"]
    resident = make_user(db, "ls-res-s3@x.test", role="Resident")
    resident["user"].society_id = society.id
    db.commit()
    assert client.get(URL, headers=resident["headers"]).status_code == 403
