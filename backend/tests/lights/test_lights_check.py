"""The monthly lights check: 4 tube lights per floor, 3 spot lights per flat, each marked working or not with the date,
time and person, and replaced from the store."""
from uuid import UUID

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
        "manager": _member(db, "mgr@lights.test", "Manager", society, "Mona Manager"),
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


# ── The monthly report ───────────────────────────────────────────────────────

def _this_month():
    from app.utils.local_time import local_today, zone
    return local_today(zone(None)).strftime("%Y-%m")


def _report(client, rig, who, month=None):
    r = client.get(f"{API}/{rig['sid']}/report", params={"month": month} if month else {}, headers=who["headers"])
    assert r.status_code == 200, r.text
    return r.json()


def test_report_counts_what_was_checked_found_and_replaced_and_names_the_floors_not_checked(client, db, rig):
    db.add(Floor(wing_id=UUID(rig["wing"]), society_id=rig["society"].id, floor_number=3, floor_name="3rd Floor"))
    db.commit()
    # floor 2: all 4 tube lights (one bad), and the spot lights of only one of its two flats
    _check(client, rig, rig["electrician"], "tube", _tubes(["working", "working", "not_working", "working"]))
    f1 = str(rig["flats"]["201"].id)
    _check(client, rig, rig["electrician"], "spot", [
        {"flat_id": f1, "location": "hall", "status": "working"},
        {"flat_id": f1, "location": "bedroom", "status": "working"},
        {"flat_id": f1, "location": "kitchen", "status": "not_working"},
    ])
    bad = client.get(f"{API}/{rig['sid']}/not-working", headers=rig["admin"]["headers"]).json()["rows"]
    stair = next(r for r in bad if r["location"] == "stair_1")
    item = _stocked_item(client, rig, 3)
    assert client.post(f"{API}/point/{stair['id']}/replace", headers=rig["electrician"]["headers"],
                       json={"item_id": item["id"]}).status_code == 200

    rep = _report(client, rig, rig["admin"])
    assert rep["month"] == _this_month()
    # 7 lights checked; the staircase one was replaced after, so only the kitchen light is still bad
    assert rep["totals"] == {"checked": 7, "working": 6, "not_working": 1, "replaced": 1, "still_not_working": 1}
    floors = {f["floor_number"]: f for f in rep["floors"]}
    assert set(floors) == {2, 3}
    two = floors[2]
    assert two["flats"] == 2 and two["tube"]["expected"] == 4 and two["spot"]["expected"] == 6
    assert (two["tube"]["checked"], two["tube"]["working"]) == (4, 4)
    assert (two["spot"]["checked"], two["spot"]["not_working"]) == (3, 1)
    assert two["status"] == "partial"
    assert floors[3]["status"] == "not_checked" and floors[3]["flats"] == 1
    assert rep["floors_not_checked"] == 1 and rep["floors_partly_checked"] == 1


def test_a_floor_with_every_light_checked_is_done(client, db, rig):
    _check(client, rig, rig["electrician"], "tube", _tubes(["working"] * 4))
    spots = [{"flat_id": str(rig["flats"][n].id), "location": loc, "status": "working"}
             for n in ("201", "202") for loc in ("hall", "bedroom", "kitchen")]
    _check(client, rig, rig["electrician"], "spot", spots)
    # the floor's camera is part of "done" too
    assert _report(client, rig, rig["admin"])["floors"][0]["status"] == "partial"
    _check(client, rig, rig["electrician"], "camera", [{"location": "camera", "status": "working"}])
    floor = _report(client, rig, rig["admin"])["floors"][0]
    assert floor["status"] == "done" and floor["floor_number"] == 2
    assert floor["camera"] == {"expected": 1, "checked": 1, "working": 1, "not_working": 0}


def test_another_month_starts_empty_and_a_bad_month_is_refused(client, rig):
    _check(client, rig, rig["electrician"], "tube", _tubes(["working"] * 4))
    old = _report(client, rig, rig["admin"], "2020-01")
    assert old["totals"]["checked"] == 0 and old["floors"][0]["status"] == "not_checked"
    for bad in ("2026-13", "2026-1", "nonsense"):
        r = client.get(f"{API}/{rig['sid']}/report", params={"month": bad}, headers=rig["admin"]["headers"])
        assert r.status_code == 422, bad


def test_the_report_is_for_staff_of_this_society_only(client, rig):
    url = f"{API}/{rig['sid']}/report"
    assert client.get(url, headers=rig["resident"]["headers"]).status_code == 403
    assert client.get(url, headers=rig["other_admin"]["headers"]).status_code == 403


# ── Report filters: wing, floor, flat ────────────────────────────────────────

@pytest.fixture
def two_floors(db, client, rig):
    """Floor 2 (flats 201, 202) fully marked with 202's kitchen bad; floor 3 (flat 301) has one bad tube light."""
    db.add(Floor(wing_id=UUID(rig["wing"]), society_id=rig["society"].id, floor_number=3, floor_name="3rd Floor"))
    db.commit()
    _check(client, rig, rig["electrician"], "tube", _tubes(["working"] * 4), floor=2)
    spots = [{"flat_id": str(rig["flats"][n].id), "location": loc,
              "status": "not_working" if (n, loc) == ("202", "kitchen") else "working"}
             for n in ("201", "202") for loc in ("hall", "bedroom", "kitchen")]
    _check(client, rig, rig["electrician"], "spot", spots, floor=2)
    _check(client, rig, rig["electrician"], "tube", _tubes(["not_working", "working", "working", "working"]), floor=3)
    return rig


def _filtered(client, rig, **params):
    r = client.get(f"{API}/{rig['sid']}/report", params=params, headers=rig["admin"]["headers"])
    assert r.status_code == 200, r.text
    return r.json()


def test_report_can_be_narrowed_to_a_floor(client, two_floors):
    rep = _filtered(client, two_floors, wing_id=two_floors["wing"], floor_number=3)
    assert [f["floor_number"] for f in rep["floors"]] == [3]
    assert rep["totals"] == {"checked": 4, "working": 3, "not_working": 1, "replaced": 0, "still_not_working": 1}
    rep2 = _filtered(client, two_floors, floor_number=2)
    assert [f["floor_number"] for f in rep2["floors"]] == [2]
    assert rep2["totals"]["checked"] == 10 and rep2["totals"]["not_working"] == 1


def test_report_can_be_narrowed_to_a_wing(client, db, two_floors):
    from app.models.wing import Wing
    other = Wing(society_id=two_floors["society"].id, name="Wing B", code="B")      # make_wing always uses code "A"
    db.add(other)
    db.commit()
    db.add(Floor(wing_id=other.id, society_id=two_floors["society"].id, floor_number=1, floor_name="1st Floor"))
    db.commit()
    everything = _filtered(client, two_floors)
    assert {f["wing_name"] for f in everything["floors"]} == {"Wing A", "Wing B"}
    only_b = _filtered(client, two_floors, wing_id=str(other.id))
    assert [(f["wing_name"], f["status"]) for f in only_b["floors"]] == [("Wing B", "not_checked")]
    assert only_b["totals"]["checked"] == 0
    only_a = _filtered(client, two_floors, wing_id=two_floors["wing"])
    assert {f["wing_name"] for f in only_a["floors"]} == {"Wing A"} and only_a["totals"]["checked"] == 14


def test_report_for_one_flat_is_its_three_spot_lights(client, two_floors):
    flat = str(two_floors["flats"]["202"].id)
    rep = _filtered(client, two_floors, flat_id=flat)
    assert rep["totals"] == {"checked": 3, "working": 2, "not_working": 1, "replaced": 0, "still_not_working": 1}
    assert rep["flat"]["label"] == "202"
    lights = {x["location"]: x["status"] for x in rep["flat"]["lights"]}
    assert lights == {"hall": "working", "bedroom": "working", "kitchen": "not_working"}
    [floor] = rep["floors"]
    assert floor["floor_number"] == 2 and floor["tube"]["expected"] == 0 and floor["spot"]["expected"] == 3
    assert floor["status"] == "done"
    # a flat nobody has checked yet
    unchecked = _filtered(client, two_floors, flat_id=str(two_floors["flats"]["301"].id))
    assert unchecked["totals"]["checked"] == 0 and unchecked["floors"][0]["status"] == "not_checked"
    assert all(x["status"] is None for x in unchecked["flat"]["lights"])


def test_report_filters_refuse_what_is_not_this_societys(client, db, two_floors):
    from uuid import uuid4
    url = f"{API}/{two_floors['sid']}/report"
    h = two_floors["admin"]["headers"]
    assert client.get(url, params={"flat_id": str(uuid4())}, headers=h).status_code == 404
    assert client.get(url, params={"wing_id": str(uuid4())}, headers=h).status_code == 404
    other_flat = make_flat(db, make_wing(db, make_society(db, "Elsewhere").id, "Wing Z").id, "999")
    assert client.get(url, params={"flat_id": str(other_flat.id)}, headers=h).status_code == 404


# ── The camera on each floor ─────────────────────────────────────────────────

def test_a_floor_has_one_camera(client, rig):
    sheet = _sheet(client, rig, rig["electrician"], "camera")
    assert len(sheet["groups"]) == 1
    [point] = sheet["groups"][0]["points"]
    assert point["location"] == "camera" and point["label"] == "Floor camera" and point["status"] is None
    # only the camera is accepted for this kind
    assert _check(client, rig, rig["electrician"], "camera", [{"location": "hall", "status": "working"}]).status_code == 422


def test_a_camera_found_not_working_is_listed_and_can_be_put_right_without_a_store_item(client, rig):
    assert _check(client, rig, rig["electrician"], "camera",
                  [{"location": "camera", "status": "not_working"}]).status_code == 201
    bad = client.get(f"{API}/{rig['sid']}/not-working", headers=rig["admin"]["headers"]).json()
    assert bad["count"] == 1 and bad["camera"] == 1 and bad["tube"] == 0
    row = bad["rows"][0]
    assert row["label"] == "Floor camera" and row["floor_number"] == 2
    r = client.post(f"{API}/point/{row['id']}/replace", headers=rig["electrician"]["headers"], json={"note": "cable reset"})
    assert r.status_code == 200, r.text
    assert client.get(f"{API}/{rig['sid']}/not-working", headers=rig["admin"]["headers"]).json()["count"] == 0
    assert _sheet(client, rig, rig["admin"], "camera")["groups"][0]["points"][0]["status"] == "working"


def test_a_light_still_needs_its_store_item_to_be_replaced(client, rig):
    _check(client, rig, rig["electrician"], "tube", [{"location": "floor_1", "status": "not_working"}])
    row = client.get(f"{API}/{rig['sid']}/not-working", headers=rig["admin"]["headers"]).json()["rows"][0]
    r = client.post(f"{API}/point/{row['id']}/replace", headers=rig["electrician"]["headers"], json={})
    assert r.status_code == 422
    assert client.get(f"{API}/{rig['sid']}/not-working", headers=rig["admin"]["headers"]).json()["count"] == 1


# ── Common areas ─────────────────────────────────────────────────────────────

def _area(client, rig, name="Parking", items=None, who="manager", **extra):
    items = items if items is not None else [{"kind": "tube", "count": 4}, {"kind": "camera", "count": 2}]
    return client.post(f"{API}/{rig['sid']}/areas", headers=rig[who]["headers"],
                       json={"name": name, "items": items, **extra})


def _area_sheet(client, rig, area_id, who="electrician"):
    r = client.get(f"{API}/area/{area_id}/sheet", headers=rig[who]["headers"])
    assert r.status_code == 200, r.text
    return r.json()


def _area_check(client, rig, area_id, results, who="electrician"):
    return client.post(f"{API}/area/{area_id}/check", headers=rig[who]["headers"], json={"results": results})


def test_the_manager_sets_up_an_area_and_staff_cannot(client, rig):
    assert _area(client, rig, who="electrician").status_code == 403
    assert _area(client, rig, who="resident").status_code == 403
    r = _area(client, rig)
    assert r.status_code == 201, r.text
    # tube lights are listed before cameras whatever order they were given in
    assert [(i["kind"], i["count"]) for i in r.json()["items"]] == [("tube", 4), ("camera", 2)]
    assert [a["name"] for a in client.get(f"{API}/{rig['sid']}/areas", headers=rig["electrician"]["headers"]).json()] == ["Parking"]


def test_an_area_needs_a_name_things_to_check_and_sensible_counts(client, rig):
    assert _area(client, rig).status_code == 201
    assert _area(client, rig, name="parking").status_code == 409                      # the same name
    assert _area(client, rig, name="Lobby", items=[]).status_code == 422
    assert _area(client, rig, name="Lobby", items=[{"kind": "tube", "count": 0}]).status_code == 422
    assert _area(client, rig, name="Lobby", items=[{"kind": "fan", "count": 1}]).status_code == 422
    assert _area(client, rig, name="Lobby", items=[{"kind": "tube", "count": 2}, {"kind": "tube", "count": 3}]).status_code == 422
    assert _area(client, rig, name="Lobby", wing_id="00000000-0000-0000-0000-000000000000").status_code == 404


def test_an_area_sheet_numbers_what_there_is_more_than_one_of(client, rig):
    area = _area(client, rig, "Podium", [{"kind": "halogen", "count": 1}, {"kind": "camera", "count": 3}]).json()
    sheet = _area_sheet(client, rig, area["id"])
    assert [g["label"] for g in sheet["groups"]] == ["Halogens", "Cameras"]
    assert [p["label"] for p in sheet["groups"][0]["points"]] == ["Halogen"]
    assert [p["label"] for p in sheet["groups"][1]["points"]] == ["Camera 1", "Camera 2", "Camera 3"]
    assert all(p["status"] is None for g in sheet["groups"] for p in g["points"])


def test_staff_check_an_area_with_the_time_and_the_person(client, rig):
    area = _area(client, rig).json()
    r = _area_check(client, rig, area["id"], [
        {"location": "tube_1", "status": "working"}, {"location": "tube_2", "status": "not_working"},
        {"location": "camera_1", "status": "working"}])
    assert r.status_code == 201, r.text
    assert (r.json()["checked"], r.json()["not_working"]) == (3, 1)
    points = {p["location"]: p for g in _area_sheet(client, rig, area["id"])["groups"] for p in g["points"]}
    assert points["tube_2"]["status"] == "not_working" and points["tube_2"]["not_working_since"]
    assert points["tube_1"]["last_checked_by"] == "Eli Electrician" and points["tube_1"]["last_checked_at"]
    assert points["tube_3"]["status"] is None


def test_an_area_check_refuses_what_is_not_in_the_area(client, rig):
    area = _area(client, rig, "Parking", [{"kind": "tube", "count": 2}]).json()
    for bad in ("tube_3", "tube_0", "camera_1", "spot_1", "hall", "tube"):
        assert _area_check(client, rig, area["id"], [{"location": bad, "status": "working"}]).status_code == 422, bad
    assert _area_check(client, rig, area["id"], []).status_code == 422
    twice = [{"location": "tube_1", "status": "working"}, {"location": "tube_1", "status": "not_working"}]
    assert _area_check(client, rig, area["id"], twice).status_code == 422
    assert _area_check(client, rig, area["id"], [{"location": "tube_1", "status": "working"}], who="resident").status_code == 403


def test_a_light_found_bad_in_an_area_is_listed_and_replaced_from_the_store(client, rig):
    area = _area(client, rig, "Gym", [{"kind": "drum", "count": 3}, {"kind": "camera", "count": 1}]).json()
    _area_check(client, rig, area["id"], [{"location": "drum_2", "status": "not_working"},
                                          {"location": "camera_1", "status": "not_working"}])
    bad = client.get(f"{API}/{rig['sid']}/not-working", headers=rig["admin"]["headers"]).json()
    assert bad["count"] == 2 and bad["camera"] == 1 and bad["other"] == 1
    drum = next(r for r in bad["rows"] if r["kind"] == "drum")
    assert (drum["area_name"], drum["label"], drum["floor_number"], drum["flat_id"]) == ("Gym", "Drum light 2", None, None)
    assert next(r for r in bad["rows"] if r["kind"] == "camera")["label"] == "Camera"      # only one: no number
    # the drum light needs a store item, the camera does not
    assert client.post(f"{API}/point/{drum['id']}/replace", headers=rig["electrician"]["headers"], json={}).status_code == 422
    item = _stocked_item(client, rig, 2)
    assert client.post(f"{API}/point/{drum['id']}/replace", headers=rig["electrician"]["headers"],
                       json={"item_id": item["id"]}).status_code == 200
    assert _stock(client, rig, item) == 1
    cam = next(r for r in client.get(f"{API}/{rig['sid']}/not-working", headers=rig["admin"]["headers"]).json()["rows"])
    assert client.post(f"{API}/point/{cam['id']}/replace", headers=rig["electrician"]["headers"], json={}).status_code == 200


def test_changing_an_area_drops_the_lights_it_no_longer_has(client, rig):
    area = _area(client, rig, "Parking", [{"kind": "tube", "count": 4}, {"kind": "camera", "count": 1}]).json()
    _area_check(client, rig, area["id"], [{"location": "tube_4", "status": "not_working"},
                                          {"location": "camera_1", "status": "not_working"}])
    r = client.put(f"{API}/area/{area['id']}", headers=rig["manager"]["headers"],
                   json={"name": "Basement parking", "items": [{"kind": "tube", "count": 2}]})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Basement parking" and [(i["kind"], i["count"]) for i in r.json()["items"]] == [("tube", 2)]
    # the 4th tube light and the camera are gone from the lists
    assert client.get(f"{API}/{rig['sid']}/not-working", headers=rig["admin"]["headers"]).json()["count"] == 0
    assert [p["location"] for g in _area_sheet(client, rig, area["id"])["groups"] for p in g["points"]] == ["tube_1", "tube_2"]
    # and a camera that is no longer there cannot be marked
    assert _area_check(client, rig, area["id"], [{"location": "camera_1", "status": "working"}]).status_code == 422
    assert client.put(f"{API}/area/{area['id']}", headers=rig["electrician"]["headers"],
                      json={"name": "x2", "items": [{"kind": "tube", "count": 1}]}).status_code == 403


def test_deleting_an_area_takes_it_off_every_list_but_keeps_nothing_dangling(client, rig):
    area = _area(client, rig).json()
    _area_check(client, rig, area["id"], [{"location": "tube_1", "status": "not_working"}])
    assert client.delete(f"{API}/area/{area['id']}", headers=rig["electrician"]["headers"]).status_code == 403
    assert client.delete(f"{API}/area/{area['id']}", headers=rig["manager"]["headers"]).status_code == 204
    assert client.get(f"{API}/{rig['sid']}/areas", headers=rig["admin"]["headers"]).json() == []
    assert client.get(f"{API}/{rig['sid']}/not-working", headers=rig["admin"]["headers"]).json()["count"] == 0
    assert client.get(f"{API}/area/{area['id']}/sheet", headers=rig["admin"]["headers"]).status_code == 404
    assert _area(client, rig).status_code == 201                                        # the name is free again


def test_another_society_cannot_reach_an_area(client, rig):
    area = _area(client, rig).json()
    other = rig["other_admin"]["headers"]
    assert client.get(f"{API}/area/{area['id']}/sheet", headers=other).status_code == 403
    assert client.get(f"{API}/{rig['sid']}/areas", headers=other).status_code == 403
    assert client.post(f"{API}/area/{area['id']}/check", headers=other,
                       json={"results": [{"location": "tube_1", "status": "working"}]}).status_code == 403


def test_the_report_has_a_section_for_common_areas(client, rig):
    done = _area(client, rig, "Lobby", [{"kind": "spot", "count": 2}, {"kind": "camera", "count": 1}]).json()
    part = _area(client, rig, "Parking", [{"kind": "tube", "count": 4}, {"kind": "camera", "count": 2}]).json()
    _area(client, rig, "Gym", [{"kind": "drum", "count": 2}])                                    # never checked
    _area_check(client, rig, done["id"], [{"location": "spot_1", "status": "working"},
                                          {"location": "spot_2", "status": "working"},
                                          {"location": "camera_1", "status": "working"}])
    _area_check(client, rig, part["id"], [{"location": "tube_1", "status": "not_working"},
                                          {"location": "camera_1", "status": "working"}])
    rep = _report(client, rig, rig["admin"])
    by_name = {a["name"]: a for a in rep["areas"]}
    assert set(by_name) == {"Gym", "Lobby", "Parking"}
    assert (by_name["Lobby"]["status"], by_name["Parking"]["status"], by_name["Gym"]["status"]) == ("done", "partial", "not_checked")
    parking = {i["kind"]: i for i in by_name["Parking"]["items"]}
    assert (parking["tube"]["checked"], parking["tube"]["not_working"], parking["tube"]["expected"]) == (1, 1, 4)
    assert (parking["camera"]["checked"], parking["camera"]["expected"]) == (1, 2)
    assert rep["areas_not_checked"] == 1 and rep["areas_partly_checked"] == 1
    # the totals count the areas' lights as well as the floors'
    assert rep["totals"] == {"checked": 5, "working": 4, "not_working": 1, "replaced": 0, "still_not_working": 1}


def test_report_filters_decide_whether_areas_are_shown(client, db, rig):
    here = _area(client, rig, "Lobby - Wing A", [{"kind": "spot", "count": 1}], wing_id=rig["wing"]).json()
    _area(client, rig, "Podium", [{"kind": "camera", "count": 1}])                                # the whole society
    from app.models.wing import Wing
    b = Wing(society_id=rig["society"].id, name="Wing B", code="B")
    db.add(b)
    db.commit()
    elsewhere = _area(client, rig, "Lobby - Wing B", [{"kind": "spot", "count": 1}], wing_id=str(b.id)).json()
    assert {a["name"] for a in _report(client, rig, rig["admin"])["areas"]} == {"Lobby - Wing A", "Lobby - Wing B", "Podium"}
    only_a = client.get(f"{API}/{rig['sid']}/report", params={"wing_id": rig["wing"]}, headers=rig["admin"]["headers"]).json()
    assert [a["name"] for a in only_a["areas"]] == ["Lobby - Wing A"]
    by_floor = client.get(f"{API}/{rig['sid']}/report", params={"wing_id": rig["wing"], "floor_number": 2},
                          headers=rig["admin"]["headers"]).json()
    assert by_floor["areas"] == []
    by_flat = client.get(f"{API}/{rig['sid']}/report", params={"flat_id": str(rig["flats"]["201"].id)},
                         headers=rig["admin"]["headers"]).json()
    assert by_flat["areas"] == []
    assert here["wing_name"] == "Wing A" and elsewhere["wing_name"] == "Wing B"


def test_still_waiting_counts_every_wing_when_no_wing_is_chosen(client, db, rig):
    """Regression: a loop variable once overwrote the wing filter, so only one wing's faults were counted."""
    from app.models.wing import Wing
    b = Wing(society_id=rig["society"].id, name="Wing B", code="B")
    db.add(b)
    db.commit()
    db.add(Floor(wing_id=b.id, society_id=rig["society"].id, floor_number=1, floor_name="1st Floor"))
    db.commit()
    _check(client, rig, rig["electrician"], "tube", [{"location": "floor_1", "status": "not_working"}], floor=2)
    r = client.post(f"{API}/{rig['sid']}/check", headers=rig["electrician"]["headers"], json={
        "wing_id": str(b.id), "floor_number": 1, "kind": "tube",
        "results": [{"location": "floor_1", "status": "not_working"}]})
    assert r.status_code == 201, r.text
    assert _report(client, rig, rig["admin"])["totals"]["still_not_working"] == 2
