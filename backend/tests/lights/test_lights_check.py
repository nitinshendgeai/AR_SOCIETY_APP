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
    floor = _report(client, rig, rig["admin"])["floors"][0]
    assert floor["status"] == "done" and floor["floor_number"] == 2


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
