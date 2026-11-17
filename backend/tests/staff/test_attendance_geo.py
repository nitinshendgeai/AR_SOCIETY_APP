"""Staff attendance location check: staff check in or out only from a spot set up by the society (default 10 m radius).
The check runs on the server; `flag` records who was outside and `block` refuses them. Nothing changes until a spot exists."""
import pytest

from app.modules.staff.services.attendance_geo import distance_m
from tests.conftest import make_society, make_user
from tests.staff.test_attendance_self_service import _make_staff_with_login

A = "/api/v1/staff"
LAT, LNG = 19.0760, 72.8777          # the gate
M = 0.000009                          # about one metre of latitude, in degrees


def at(metres: float, accuracy: float = 5.0, **extra) -> dict:
    return {"location": {"latitude": LAT + metres * M, "longitude": LNG, "accuracy_m": accuracy, **extra}}


@pytest.fixture
def rig(db):
    society = make_society(db, "Geo Attendance Society")
    admin = make_user(db, "admin@geo.test", role="Society Admin")
    admin["user"].society_id = society.id
    manager = make_user(db, "manager@geo.test", role="Manager")
    manager["user"].society_id = society.id
    db.commit()
    guards = [_make_staff_with_login(db, society.id, f"guard{i}@geo.test", f"Guard {i}") for i in range(4)]
    return {"society": society, "admin": admin["headers"], "manager": manager["headers"], "guards": guards}


def _spot(client, rig, **over):
    r = client.post(f"{A}/attendance-geo/spots", headers=rig["admin"], json={
        "society_id": str(rig["society"].id), "name": "Main gate", "latitude": LAT, "longitude": LNG, **over})
    assert r.status_code == 201, r.text
    return r.json()


def _mode(client, rig, mode, accuracy=20):
    r = client.put(f"{A}/attendance-geo/{rig['society'].id}/settings", headers=rig["admin"],
                   json={"mode": mode, "max_accuracy_m": accuracy})
    assert r.status_code == 200, r.text


def _in(client, rig, i, body=None):
    staff, who = rig["guards"][i]
    return client.post(f"{A}/attendance/{staff.id}/checkin", json=body or {}, headers=who["headers"])


def _out(client, rig, i, body=None):
    staff, who = rig["guards"][i]
    return client.post(f"{A}/attendance/{staff.id}/checkout", json=body or {}, headers=who["headers"])


def test_the_distance_is_in_metres():
    assert distance_m(LAT, LNG, LAT + 100 * M, LNG) == pytest.approx(100, abs=1)
    assert distance_m(LAT, LNG, LAT, LNG) == 0


def test_nothing_changes_until_a_spot_exists(client, rig):
    assert client.get(f"{A}/attendance-geo/status", headers=rig["guards"][0][1]["headers"]).json()["enabled"] is False
    r = _in(client, rig, 0)                                       # no location sent, no spot set: as before
    assert r.status_code == 200 and r.json()["geo_in"] is None


def test_flag_mode_accepts_everyone_and_records_where_they_were(client, rig):
    _spot(client, rig)
    assert client.get(f"{A}/attendance-geo/status", headers=rig["guards"][0][1]["headers"]).json() == {
        "enabled": True, "mode": "flag", "max_accuracy_m": 20}

    inside = _in(client, rig, 0, at(4))
    assert inside.status_code == 200
    g = inside.json()["geo_in"]
    assert g["status"] == "inside" and g["spot_name"] == "Main gate" and g["distance_m"] == pytest.approx(4, abs=0.6)

    outside = _in(client, rig, 1, at(30))                         # 30 m away: still accepted, but marked
    assert outside.status_code == 200 and outside.json()["geo_in"]["status"] == "outside"
    assert outside.json()["geo_in"]["distance_m"] == pytest.approx(30, abs=0.8)

    none = _in(client, rig, 2)                                    # no location at all
    assert none.status_code == 200 and none.json()["geo_in"]["status"] == "no_location"
    vague = _in(client, rig, 3, at(2, accuracy=45))               # right place, but a poor reading
    assert vague.json()["geo_in"]["status"] == "low_accuracy"

    out = _out(client, rig, 0, at(6))
    assert out.status_code == 200 and out.json()["geo_out"]["status"] == "inside" and out.json()["geo_in"]["status"] == "inside"


def test_the_manager_sees_the_verdict_on_the_pending_list(client, rig, db):
    _spot(client, rig)
    _in(client, rig, 0, at(30))
    r = client.get(f"{A}/attendance/pending/{rig['society'].id}", headers=rig["manager"])
    assert r.status_code == 200
    assert [x["geo_in"]["status"] for x in r.json()] == ["outside"]


def test_a_mocked_location_is_never_inside(client, rig):
    _spot(client, rig)
    r = _in(client, rig, 0, at(1, mocked=True))
    assert r.status_code == 200 and r.json()["geo_in"]["status"] == "mocked"


def test_block_mode_refuses_check_in_and_check_out_outside(client, rig):
    _spot(client, rig)
    _mode(client, rig, "block")
    far = _in(client, rig, 0, at(30))
    assert far.status_code == 422 and "30 m from Main gate (allowed 10 m)" in far.json()["detail"]
    assert _in(client, rig, 0).status_code == 422                                  # no location
    assert "accurate to 45 m" in _in(client, rig, 0, at(2, accuracy=45)).json()["detail"]
    assert "mocked" in _in(client, rig, 0, at(1, mocked=True)).json()["detail"]

    assert _in(client, rig, 0, at(5)).status_code == 200                           # nothing was saved by the refusals
    leaving = _out(client, rig, 0, at(40))
    assert leaving.status_code == 422                                              # check-out follows the same rule...
    assert _out(client, rig, 0, at(5)).status_code == 200                          # ...and still works from the spot


def test_off_means_off(client, rig):
    _spot(client, rig)
    _mode(client, rig, "off")
    assert client.get(f"{A}/attendance-geo/status", headers=rig["guards"][0][1]["headers"]).json()["enabled"] is False
    r = _in(client, rig, 0, at(500))
    assert r.status_code == 200 and r.json()["geo_in"] is None


def test_the_nearest_of_several_spots_decides(client, rig):
    _spot(client, rig)
    _spot(client, rig, name="Tower B", latitude=LAT + 200 * M, longitude=LNG, radius_m=15)
    r = _in(client, rig, 0, at(205))                                               # 5 m from Tower B
    g = r.json()["geo_in"]
    assert g["status"] == "inside" and g["spot_name"] == "Tower B"


def test_who_may_set_up_and_who_may_read(client, rig):
    spot = _spot(client, rig)
    guard = rig["guards"][0][1]["headers"]
    sid = rig["society"].id
    assert client.get(f"{A}/attendance-geo/{sid}", headers=guard).status_code == 403          # staff don't see the setup
    cfg = client.get(f"{A}/attendance-geo/{sid}", headers=rig["manager"]).json()
    assert cfg["settings"] == {"mode": "flag", "max_accuracy_m": 20} and [s["name"] for s in cfg["spots"]] == ["Main gate"]
    body = {"mode": "block", "max_accuracy_m": 20}
    assert client.put(f"{A}/attendance-geo/{sid}/settings", json=body, headers=rig["manager"]).status_code == 403
    assert client.post(f"{A}/attendance-geo/spots", headers=rig["manager"],
                       json={"name": "x", "latitude": LAT, "longitude": LNG}).status_code == 403
    assert client.patch(f"{A}/attendance-geo/spots/{spot['id']}", json={"radius_m": 15}, headers=rig["admin"]).json()["radius_m"] == 15
    assert client.delete(f"{A}/attendance-geo/spots/{spot['id']}", headers=rig["admin"]).status_code == 204
    assert client.get(f"{A}/attendance-geo/{sid}", headers=rig["manager"]).json()["spots"] == []
    assert client.get(f"{A}/attendance-geo/status", headers=guard).json()["enabled"] is False   # no spot left


def test_bad_values_and_other_societies(client, rig, db):
    sid = rig["society"].id
    for bad in ({"radius_m": 2}, {"radius_m": 500}, {"latitude": 91}, {"longitude": -181}, {"name": ""}):
        r = client.post(f"{A}/attendance-geo/spots", headers=rig["admin"],
                        json={"society_id": str(sid), "name": "Gate", "latitude": LAT, "longitude": LNG, **bad})
        assert r.status_code == 422, bad
    assert client.put(f"{A}/attendance-geo/{sid}/settings", headers=rig["admin"],
                      json={"mode": "strict", "max_accuracy_m": 20}).status_code == 422
    other = make_society(db, "Other Geo Society")
    assert client.get(f"{A}/attendance-geo/{other.id}", headers=rig["manager"]).status_code == 403
    spot = _spot(client, rig)
    other_admin = make_user(db, "admin@other-geo.test", role="Society Admin")
    other_admin["user"].society_id = other.id
    db.commit()
    assert client.patch(f"{A}/attendance-geo/spots/{spot['id']}", json={"radius_m": 20}, headers=other_admin["headers"]).status_code == 403
