"""The monthly lights check: 4 tube lights per floor, 3 spot lights per flat, each marked working or not with the date,
time and person, and replaced from the store."""
import pytest

from app.models.floor import Floor
from tests.conftest import make_flat, make_society, make_user, make_wing

API = "/api/v1/light-checks"
INV = "/api/v1/inventory"
TUBES = ["floor_1", "floor_2", "stair_1", "stair_2"]


def _member(db, email, role, society, name=None):
    who = make_user(db, email, role=role, full_name=name or email.split("@")[0])
    who["user"].society_id = society.id
    db.commit()
    return who


@pytest.fixture
def rig(db):
    society = make_society(db, "Lights Society")
    other = make_society(db, "Other Lights Society")
    wing = make_wing(db, society.id, "Wing A")
    db.add(Floor(wing_id=wing.id, society_id=society.id, floor_number=2, floor_name="2nd Floor"))
    db.commit()
    flats = {n: make_flat(db, wing.id, n) for n in ("201", "202", "301")}
    for n, floor in (("201", 2), ("202", 2), ("301", 3)):
        flats[n].floor = floor
    db.commit()
    return {
        "society": society, "sid": str(society.id), "wing": str(wing.id), "flats": flats,
        "electrician": _member(db, "elec@lights.test", "Technical Staff", society, "Eli Electrician"),
        "admin": _member(db, "adm@lights.test", "Society Admin", society),
        "resident": _member(db, "res@lights.test", "Resident", society),
        "other_admin": _member(db, "adm@other-lights.test", "Society Admin", other),
    }


def _sheet(client, rig, who, kind, floor=2):
    r = client.get(f"{API}/{rig['sid']}/sheet", params={"wing_id": rig["wing"], "floor_number": floor, "kind": kind},
                   headers=who["headers"])
    assert r.status_code == 200, r.text
    return r.json()


def _check(client, rig, who, kind, results, floor=2):
    return client.post(f"{API}/{rig['sid']}/check", headers=who["headers"], json={
        "wing_id": rig["wing"], "floor_number": floor, "kind": kind, "results": results})


def _tubes(statuses):
    return [{"location": loc, "status": st} for loc, st in zip(TUBES, statuses)]


def test_a_floor_has_four_tube_lights_none_checked_yet(client, rig):
    sheet = _sheet(client, rig, rig["electrician"], "tube")
    assert len(sheet["groups"]) == 1
    points = sheet["groups"][0]["points"]
    assert [p["location"] for p in points] == TUBES
    assert [p["label"] for p in points][2] == "Staircase tube light 1"
    assert all(p["status"] is None and p["last_checked_at"] is None for p in points)


def test_a_flat_has_hall_bedroom_and_kitchen_spot_lights_and_only_this_floors_flats_are_listed(client, rig):
    sheet = _sheet(client, rig, rig["electrician"], "spot")
    assert [g["label"] for g in sheet["groups"]] == ["Flat 201", "Flat 202"]          # not 301, which is on floor 3
    assert [p["location"] for p in sheet["groups"][0]["points"]] == ["hall", "bedroom", "kitchen"]


def test_a_check_is_stamped_with_the_time_and_the_person(client, rig):
    r = _check(client, rig, rig["electrician"], "tube", _tubes(["working", "working", "not_working", "working"]))
    assert r.status_code == 201, r.text
    assert r.json()["checked"] == 4 and r.json()["not_working"] == 1 and r.json()["checked_at"]
    points = _sheet(client, rig, rig["admin"], "tube")["groups"][0]["points"]
    assert [p["status"] for p in points] == ["working", "working", "not_working", "working"]
    assert all(p["last_checked_at"] and p["last_checked_by"] == "Eli Electrician" for p in points)
    assert points[2]["not_working_since"] and points[0]["not_working_since"] is None


def test_spot_lights_are_checked_per_flat(client, rig):
    f1, f2 = str(rig["flats"]["201"].id), str(rig["flats"]["202"].id)
    r = _check(client, rig, rig["electrician"], "spot", [
        {"flat_id": f1, "location": "hall", "status": "working"},
        {"flat_id": f1, "location": "kitchen", "status": "not_working"},
        {"flat_id": f2, "location": "bedroom", "status": "not_working"},
    ])
    assert r.status_code == 201, r.text
    bad = client.get(f"{API}/{rig['sid']}/not-working", headers=rig["admin"]["headers"]).json()
    assert bad["count"] == 2 and bad["spot"] == 2 and bad["tube"] == 0
    assert {(r["flat_label"], r["label"]) for r in bad["rows"]} == {("201", "Kitchen"), ("202", "Bedroom")}


def test_a_flat_from_another_floor_or_a_wrong_location_is_refused(client, rig):
    other_floor = str(rig["flats"]["301"].id)
    assert _check(client, rig, rig["electrician"], "spot",
                  [{"flat_id": other_floor, "location": "hall", "status": "working"}]).status_code == 422
    assert _check(client, rig, rig["electrician"], "tube", [{"location": "hall", "status": "working"}]).status_code == 422
    assert _check(client, rig, rig["electrician"], "tube", []).status_code == 422


def test_checking_again_keeps_when_it_was_first_found_not_working(client, rig):
    _check(client, rig, rig["electrician"], "tube", [{"location": "stair_1", "status": "not_working"}])
    first = _sheet(client, rig, rig["admin"], "tube")["groups"][0]["points"][2]["not_working_since"]
    _check(client, rig, rig["electrician"], "tube", [{"location": "stair_1", "status": "not_working"}])
    again = _sheet(client, rig, rig["admin"], "tube")["groups"][0]["points"][2]["not_working_since"]
    assert first and first == again


def _stocked_item(client, rig, qty):
    h = rig["admin"]["headers"]
    item = client.post(f"{INV}/items", headers=h, json={"name": "LED tube 20W", "category": "electrical",
                                                         "unit_type": "piece", "minimum_stock": 1})
    assert item.status_code == 201, item.text
    item = item.json()
    if qty:
        assert client.post(f"{INV}/stock/in", headers=h, json={"item_id": item["id"], "quantity": qty}).status_code == 200
    return item


def _stock(client, rig, item):
    return client.get(f"{INV}/items/{item['id']}", headers=rig["admin"]["headers"]).json()["current_stock"]


def test_replacing_takes_one_from_the_store_and_marks_the_light_working(client, rig):
    _check(client, rig, rig["electrician"], "tube", [{"location": "floor_2", "status": "not_working"}])
    bad = client.get(f"{API}/{rig['sid']}/not-working", headers=rig["admin"]["headers"]).json()["rows"][0]
    item = _stocked_item(client, rig, 5)
    r = client.post(f"{API}/point/{bad['id']}/replace", headers=rig["electrician"]["headers"],
                    json={"item_id": item["id"]})
    assert r.status_code == 200, r.text
    assert _stock(client, rig, item) == 4
    assert client.get(f"{API}/{rig['sid']}/not-working", headers=rig["admin"]["headers"]).json()["count"] == 0
    point = _sheet(client, rig, rig["admin"], "tube")["groups"][0]["points"][1]
    assert point["status"] == "working" and point["not_working_since"] is None
    # a light that is working cannot be "replaced" again
    again = client.post(f"{API}/point/{bad['id']}/replace", headers=rig["electrician"]["headers"],
                        json={"item_id": item["id"]})
    assert again.status_code == 409 and _stock(client, rig, item) == 4


def test_with_no_stock_the_light_stays_not_working(client, rig):
    _check(client, rig, rig["electrician"], "tube", [{"location": "floor_1", "status": "not_working"}])
    bad = client.get(f"{API}/{rig['sid']}/not-working", headers=rig["admin"]["headers"]).json()["rows"][0]
    item = _stocked_item(client, rig, 0)
    r = client.post(f"{API}/point/{bad['id']}/replace", headers=rig["electrician"]["headers"],
                    json={"item_id": item["id"]})
    assert r.status_code == 409
    assert client.get(f"{API}/{rig['sid']}/not-working", headers=rig["admin"]["headers"]).json()["count"] == 1


def test_summary_counts_the_lights_checked(client, rig):
    _check(client, rig, rig["electrician"], "tube", _tubes(["working", "working", "not_working", "working"]))
    s = client.get(f"{API}/{rig['sid']}/summary", headers=rig["admin"]["headers"]).json()
    assert (s["total"], s["working"], s["not_working"]) == (4, 3, 1) and s["last_checked_at"]


def test_floors_of_a_wing_are_listed_for_the_picker(client, rig):
    r = client.get(f"{API}/{rig['sid']}/floors", params={"wing_id": rig["wing"]}, headers=rig["electrician"]["headers"])
    assert r.status_code == 200 and r.json() == [{"floor_number": 2, "name": "2nd Floor"}]


def test_residents_and_other_societies_are_kept_out(client, rig):
    url = f"{API}/{rig['sid']}/sheet"
    q = {"wing_id": rig["wing"], "floor_number": 2, "kind": "tube"}
    assert client.get(url, params=q, headers=rig["resident"]["headers"]).status_code == 403
    assert client.get(url, params=q, headers=rig["other_admin"]["headers"]).status_code == 403
    assert _check(client, rig, rig["resident"], "tube", _tubes(["working"] * 4)).status_code == 403
