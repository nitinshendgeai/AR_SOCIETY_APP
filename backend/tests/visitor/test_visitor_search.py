"""Searching the society's visitor log on the server, so a guard finds a visitor beyond the latest page."""
import pytest

from app.modules.visitor.models.visitor import Visitor, VisitorVehicle
from tests.conftest import make_flat, make_society, make_user, make_wing, place_in


@pytest.fixture
def rig(db):
    society = make_society(db, "Visitor Search Society")
    guard = make_user(db, "vs-guard@x.test", role="Security Staff")
    place_in(db, guard, society)
    wing = make_wing(db, society.id, "A")
    flat_101, flat_202 = make_flat(db, wing.id, "101"), make_flat(db, wing.id, "202")
    rows = {
        "ramesh": Visitor(society_id=society.id, name="Ramesh Kumar", mobile="9876500001", purpose="Delivery of flowers",
                          flat_id=flat_101.id, pass_code="48151623"),
        "sunita": Visitor(society_id=society.id, name="Sunita Rao", mobile="9123400002", purpose="Plumber",
                          flat_id=flat_202.id),
        "driver": Visitor(society_id=society.id, name="Cab Driver", mobile="9000000003", purpose="Pickup"),
    }
    db.add_all(rows.values())
    db.flush()
    db.add(VisitorVehicle(visitor_id=rows["driver"].id, vehicle_number="MH 12 AB 1234"))
    # A visitor of another society that matches the same words must never appear.
    other = make_society(db, "Other Visitor Society")
    db.add(Visitor(society_id=other.id, name="Ramesh Outsider", mobile="9876599999", purpose="Delivery"))
    db.commit()
    return {"society": society, "h": guard["headers"], "url": f"/api/v1/visitors/society/{society.id}"}


def _names(client, rig, **params):
    r = client.get(rig["url"], params={"limit": 200, **params}, headers=rig["h"])
    assert r.status_code == 200, r.text
    return sorted(v["name"] for v in r.json())


def test_without_q_the_log_is_unchanged(client, rig):
    assert _names(client, rig) == ["Cab Driver", "Ramesh Kumar", "Sunita Rao"]
    assert _names(client, rig, q="") == ["Cab Driver", "Ramesh Kumar", "Sunita Rao"]
    assert _names(client, rig, q="   ") == ["Cab Driver", "Ramesh Kumar", "Sunita Rao"]


def test_search_by_name_mobile_purpose_flat_and_vehicle(client, rig):
    assert _names(client, rig, q="ramesh") == ["Ramesh Kumar"]            # name, any case; the other society's is not listed
    assert _names(client, rig, q="RAO") == ["Sunita Rao"]
    assert _names(client, rig, q="912340") == ["Sunita Rao"]               # part of the mobile number
    assert _names(client, rig, q="plumber") == ["Sunita Rao"]              # purpose
    assert _names(client, rig, q="101") == ["Ramesh Kumar"]                # flat number
    assert _names(client, rig, q="A-202") == ["Sunita Rao"]                # wing and flat, hyphen ignored
    assert _names(client, rig, q="a 101") == ["Ramesh Kumar"]              # and spaces
    assert _names(client, rig, q="mh12ab1234") == ["Cab Driver"]           # vehicle number, as typed without spaces
    assert _names(client, rig, q="mh 12-ab 1234") == ["Cab Driver"]        # or with them


def test_every_word_must_match_and_nothing_matching_is_an_empty_list(client, rig):
    assert _names(client, rig, q="ramesh delivery") == ["Ramesh Kumar"]
    assert _names(client, rig, q="ramesh plumber") == []
    assert _names(client, rig, q="zzzz") == []


def test_the_pass_code_is_not_searchable(client, rig):
    assert _names(client, rig, q="48151623") == []


def test_search_text_is_data_not_a_pattern(client, rig):
    # Symbols are dropped, as in the phone app, so a search of only symbols is a blank search: the whole log.
    assert _names(client, rig, q="%") == ["Cab Driver", "Ramesh Kumar", "Sunita Rao"]
    # A wildcard is never a wildcard: "r%h" would match "Ramesh" if it were, but it is just "rh".
    assert _names(client, rig, q="r%h") == []
    assert _names(client, rig, q="r_mesh") == []
    # SQL in the box is only text.
    assert _names(client, rig, q="' OR 1=1 --") == []


def test_paging_applies_to_the_matches(client, rig):
    r = client.get(rig["url"], params={"q": "a", "limit": 1}, headers=rig["h"])
    assert r.status_code == 200 and len(r.json()) == 1


def test_a_resident_cannot_read_the_society_log(client, db, rig):
    resident = make_user(db, "vs-res@x.test", role="Resident")
    place_in(db, resident, rig["society"])
    assert client.get(rig["url"], params={"q": "ramesh"}, headers=resident["headers"]).status_code in (401, 403)


def test_an_overlong_search_is_refused(client, rig):
    assert client.get(rig["url"], params={"q": "x" * 101}, headers=rig["h"]).status_code == 422
