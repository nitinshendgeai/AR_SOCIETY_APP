"""Parking: who may touch which society's data, and whether the gate check tells the
truth — a vehicle is allowed in only while it holds parking *today*, however the parking
ended, and an approved visitor's vehicle is recognised."""
from datetime import date, timedelta

import pytest

from tests.conftest import make_society, make_user, make_wing, make_flat

S = "/api/v1"
TODAY = date.today()


def _bind(db, who, society_id):
    who["user"].society_id = society_id
    db.commit()


@pytest.fixture
def rig(db, client):
    society = make_society(db, "Gate Scope Society")
    other = make_society(db, "Other Gate Society")
    admin = make_user(db, "gs-admin@test.com", role="Society Admin")
    guard = make_user(db, "gs-guard@test.com", role="Security Staff")
    resident_login = make_user(db, "gs-res@test.com", role="Resident")
    for who in (admin, guard, resident_login):
        _bind(db, who, society.id)
    other_admin = make_user(db, "gs-oadmin@test.com", role="Society Admin")
    _bind(db, other_admin, other.id)

    wing = make_wing(db, society.id, "Wing S")
    flat = make_flat(db, wing.id, "S-101")
    flat2 = make_flat(db, wing.id, "S-102")
    ow = make_wing(db, other.id, "Wing O")
    oflat = make_flat(db, ow.id, "O-101")

    from app.models.resident import Resident
    from app.models.tenant import Tenant
    resident = Resident(flat_id=flat.id, full_name="Scope Resident")
    tenant = Tenant(flat_id=flat.id, full_name="Scope Tenant")
    db.add_all([resident, tenant])
    db.commit()
    return {"society": society, "other": other, "admin": admin, "guard": guard, "res_login": resident_login,
            "other_admin": other_admin, "flat": flat, "flat2": flat2, "oflat": oflat,
            "resident": resident, "tenant": tenant}


def _h(who):
    return who["headers"]


def _vehicle(client, rig, number, owner="resident", **kw):
    body = {"society_id": str(rig["society"].id), "flat_id": str(rig["flat"].id), "vehicle_number": number, **kw}
    body["resident_id" if owner == "resident" else "tenant_id"] = str(rig[owner].id)
    r = client.post(f"{S}/vehicles/", json=body, headers=_h(rig["admin"]))
    assert r.status_code == 201, r.text
    return r.json()


def _slot(client, headers, society_id, number):
    z = client.post(f"{S}/parking/zones", json={"society_id": str(society_id), "name": f"Z-{number}"}, headers=headers)
    assert z.status_code == 201, z.text
    s = client.post(f"{S}/parking/slots", json={"society_id": str(society_id), "zone_id": z.json()["id"],
                                                "slot_number": number}, headers=headers)
    assert s.status_code == 201, s.text
    return s.json()


def _allot(client, rig, vehicle, slot, **over):
    body = {"society_id": str(rig["society"].id), "slot_id": slot["id"], "flat_id": str(rig["flat"].id),
            "vehicle_id": vehicle["id"], "allocation_type": "resident", "start_date": str(TODAY)}
    body.update(over)
    return client.post(f"{S}/parking/allocations", json=body, headers=_h(rig["admin"]))


def _gate(client, rig, number):
    r = client.get(f"{S}/parking/gate/validate/{rig['society'].id}/{number}", headers=_h(rig["guard"]))
    assert r.status_code == 200, r.text
    return r.json()


# ── Society scope ─────────────────────────────────────────────────────────────

def test_a_societys_admin_and_guard_cannot_read_or_write_another_societys_parking(client, db, rig):
    other = rig["other"].id
    a, g = _h(rig["admin"]), _h(rig["guard"])
    assert client.get(f"{S}/parking/zones/{other}", headers=a).status_code == 403
    assert client.get(f"{S}/parking/slots/society/{other}", headers=a).status_code == 403
    assert client.get(f"{S}/parking/slots/available/{other}", headers=a).status_code == 403
    assert client.get(f"{S}/parking/allocations/society/{other}", headers=a).status_code == 403
    assert client.get(f"{S}/parking/vehicles/society/{other}", headers=a).status_code == 403
    assert client.post(f"{S}/parking/zones", json={"society_id": str(other), "name": "Hijack"}, headers=a).status_code == 403
    assert client.get(f"{S}/parking/access-log/society/{other}", headers=g).status_code == 403
    assert client.get(f"{S}/parking/violations/society/{other}", headers=g).status_code == 403
    assert client.get(f"{S}/parking/visitor/active/{other}", headers=g).status_code == 403
    assert client.post(f"{S}/parking/access-log", headers=g, json={
        "society_id": str(other), "vehicle_number": "MH12ZZ0001", "access_type": "entry"}).status_code == 403
    assert client.post(f"{S}/parking/violations", headers=g, json={
        "society_id": str(other), "vehicle_number": "MH12ZZ0001", "violation_type": "unauthorized"}).status_code == 403
    assert client.post(f"{S}/parking/visitor", headers=g, json={
        "society_id": str(other), "vehicle_number": "MH12ZZ0001"}).status_code == 403


def test_another_societys_records_are_not_found_by_id(client, db, rig):
    oslot = _slot(client, _h(rig["other_admin"]), rig["other"].id, "O-1")
    a = _h(rig["admin"])
    assert client.get(f"{S}/parking/slots/{oslot['id']}", headers=a).status_code == 404
    assert client.patch(f"{S}/parking/slots/{oslot['id']}", json={"notes": "x"}, headers=a).status_code == 404
    z = client.get(f"{S}/parking/zones/{rig['other'].id}", headers=_h(rig["other_admin"])).json()[0]
    assert client.get(f"{S}/parking/slots/zone/{z['id']}", headers=a).status_code == 404
    assert client.get(f"{S}/parking/allocations/flat/{rig['oflat'].id}", headers=a).status_code == 404
    # the owner still sees them
    assert client.get(f"{S}/parking/slots/{oslot['id']}", headers=_h(rig["other_admin"])).status_code == 200


def test_you_cannot_attach_another_societys_slot_zone_or_vehicle(client, db, rig):
    oslot = _slot(client, _h(rig["other_admin"]), rig["other"].id, "O-2")
    mine = _slot(client, _h(rig["admin"]), rig["society"].id, "S-1")
    veh = _vehicle(client, rig, "MH12SC0001")
    a = _h(rig["admin"])
    # my society, their slot
    assert _allot(client, rig, veh, oslot).status_code == 404
    # their zone for my slot
    oz = client.get(f"{S}/parking/zones/{rig['other'].id}", headers=_h(rig["other_admin"])).json()[0]
    assert client.post(f"{S}/parking/slots", headers=a, json={
        "society_id": str(rig["society"].id), "zone_id": oz["id"], "slot_number": "S-9"}).status_code == 404
    # my slot, their flat / a vehicle that doesn't exist here
    assert _allot(client, rig, veh, mine, flat_id=str(rig["oflat"].id)).status_code == 404
    assert _allot(client, rig, {"id": "00000000-0000-0000-0000-000000000000"}, mine).status_code == 404
    assert _allot(client, rig, veh, mine).status_code == 201


def test_a_plates_history_is_only_this_societys_and_a_platform_admin_names_the_society(client, db, rig):
    client.post(f"{S}/parking/access-log", headers=_h(rig["guard"]), json={
        "society_id": str(rig["society"].id), "vehicle_number": "MH12HI0001", "access_type": "entry"})
    other_guard = make_user(db, "gs-oguard@test.com", role="Security Staff")
    _bind(db, other_guard, rig["other"].id)
    client.post(f"{S}/parking/access-log", headers=_h(other_guard), json={
        "society_id": str(rig["other"].id), "vehicle_number": "MH12HI0001", "access_type": "exit"})
    mine = client.get(f"{S}/parking/access-log/vehicle/MH12HI0001", headers=_h(rig["guard"])).json()
    assert [row["access_type"] for row in mine] == ["entry"]
    platform = make_user(db, "gs-platform@test.com", role="Platform Admin")
    assert client.get(f"{S}/parking/access-log/vehicle/MH12HI0001", headers=_h(platform)).status_code == 400
    theirs = client.get(f"{S}/parking/access-log/vehicle/MH12HI0001?society_id={rig['other'].id}", headers=_h(platform))
    assert [row["access_type"] for row in theirs.json()] == ["exit"]


# ── The gate tells the truth ──────────────────────────────────────────────────

def test_the_gate_says_allowed_no_parking_or_unregistered(client, db, rig):
    slot = _slot(client, _h(rig["admin"]), rig["society"].id, "G-1")
    with_parking = _vehicle(client, rig, "MH12GT0001")
    _vehicle(client, rig, "MH12GT0002")
    assert _allot(client, rig, with_parking, slot).status_code == 201
    assert _gate(client, rig, "MH12GT0001")["status"] == "allowed"
    no_parking = _gate(client, rig, "MH12GT0002")
    assert (no_parking["status"], no_parking["authorized"], no_parking["category"]) == ("no_parking", False, "resident")
    unknown = _gate(client, rig, "MH12GT0003")
    assert (unknown["status"], unknown["authorized"]) == ("unregistered", False)


def test_a_plate_saved_with_spaces_is_still_found(client, db, rig):
    from app.models.vehicle import Vehicle
    db.add(Vehicle(society_id=rig["society"].id, flat_id=rig["flat"].id, vehicle_number="MH 12 AB 7777",
                   parking_slot="L-1"))
    db.commit()
    body = _gate(client, rig, "mh-12-ab-7777")
    assert body["status"] == "allowed" and body["parking_slot"] == "L-1"


def test_a_resident_moving_out_ends_their_cars_parking_and_frees_the_slot(client, db, rig):
    slot = _slot(client, _h(rig["admin"]), rig["society"].id, "M-1")
    car = _vehicle(client, rig, "MH12MO0001")
    assert _allot(client, rig, car, slot).status_code == 201
    assert _gate(client, rig, "MH12MO0001")["status"] == "allowed"
    r = client.post(f"{S}/occupancy/resident/move-out", headers=_h(rig["admin"]), json={
        "flat_id": str(rig["flat"].id), "resident_id": str(rig["resident"].id), "move_out_date": str(TODAY)})
    assert r.status_code == 200, r.text
    assert _gate(client, rig, "MH12MO0001")["status"] == "no_parking"
    free = client.get(f"{S}/parking/slots/available/{rig['society'].id}", headers=_h(rig["admin"])).json()
    assert "M-1" in [s["slot_number"] for s in free]
    assert client.get(f"{S}/parking/allocations/flat/{rig['flat'].id}", headers=_h(rig["admin"])).json() == []


def test_a_tenant_moving_out_ends_their_cars_parking_too(client, db, rig):
    slot = _slot(client, _h(rig["admin"]), rig["society"].id, "M-2")
    car = _vehicle(client, rig, "MH12MO0002", owner="tenant", parking_slot="M-2-OWN")
    assert _gate(client, rig, "MH12MO0002")["status"] == "allowed"
    assert _allot(client, rig, car, slot).status_code == 201
    r = client.post(f"{S}/occupancy/tenant/move-out", headers=_h(rig["admin"]), json={
        "flat_id": str(rig["flat"].id), "tenant_id": str(rig["tenant"].id), "move_out_date": str(TODAY)})
    assert r.status_code == 200, r.text
    assert _gate(client, rig, "MH12MO0002")["status"] == "no_parking"


def test_deregistering_a_vehicle_frees_its_slot(client, db, rig):
    slot = _slot(client, _h(rig["admin"]), rig["society"].id, "D-1")
    car = _vehicle(client, rig, "MH12DR0001")
    assert _allot(client, rig, car, slot).status_code == 201
    assert client.delete(f"{S}/vehicles/{car['id']}", headers=_h(rig["admin"])).status_code == 204
    free = client.get(f"{S}/parking/slots/available/{rig['society'].id}", headers=_h(rig["admin"])).json()
    assert "D-1" in [s["slot_number"] for s in free]
    assert _gate(client, rig, "MH12DR0001")["status"] == "unregistered"


def test_an_allocation_that_lapses_stops_letting_the_car_in_and_frees_the_slot(client, db, rig):
    from app.modules.parking.models.parking import AllocationStatus, ParkingAllocation
    slot = _slot(client, _h(rig["admin"]), rig["society"].id, "X-2")
    car = _vehicle(client, rig, "MH12EX0002")
    assert _allot(client, rig, car, slot, end_date=str(TODAY + timedelta(days=1))).status_code == 201
    assert _gate(client, rig, "MH12EX0002")["status"] == "allowed"
    alloc = db.query(ParkingAllocation).first()
    alloc.end_date = TODAY - timedelta(days=1)                   # time passes
    db.commit()
    gate = _gate(client, rig, "MH12EX0002")                      # the gate itself notices
    assert (gate["status"], gate["parking_slot"]) == ("no_parking", None)
    db.expire_all()
    assert db.query(ParkingAllocation).first().status == AllocationStatus.EXPIRED
    free = client.get(f"{S}/parking/slots/available/{rig['society'].id}", headers=_h(rig["admin"])).json()
    assert "X-2" in [s["slot_number"] for s in free]


def test_parking_that_has_not_started_does_not_let_the_car_in_yet(client, db, rig):
    slot = _slot(client, _h(rig["admin"]), rig["society"].id, "F-1")
    car = _vehicle(client, rig, "MH12FU0001")
    assert _allot(client, rig, car, slot, start_date=str(TODAY + timedelta(days=10))).status_code == 201
    assert _gate(client, rig, "MH12FU0001")["status"] == "no_parking"


def test_allotment_rules(client, db, rig):
    s1, s2 = (_slot(client, _h(rig["admin"]), rig["society"].id, n) for n in ("R-1", "R-2"))
    car = _vehicle(client, rig, "MH12RL0001")
    assert _allot(client, rig, car, s1).status_code == 201
    again = _allot(client, rig, car, s2)
    assert again.status_code == 409 and "already has parking" in str(again.json())
    other_flat = _allot(client, rig, car, s2, flat_id=str(rig["flat2"].id))
    assert other_flat.status_code in (409, 422)
    already_over = _allot(client, rig, _vehicle(client, rig, "MH12RL0002"), s2,
                          start_date=str(TODAY - timedelta(days=40)), end_date=str(TODAY - timedelta(days=10)))
    assert already_over.status_code == 422 and "already ended" in str(already_over.json())
    backwards = _allot(client, rig, _vehicle(client, rig, "MH12RL0003"), s2, end_date=str(TODAY - timedelta(days=5)))
    assert backwards.status_code == 422


def test_allotting_shows_the_slot_on_the_vehicle_and_releasing_takes_it_back(client, db, rig):
    slot = _slot(client, _h(rig["admin"]), rig["society"].id, "V-1")
    car = _vehicle(client, rig, "MH12VS0001")
    alloc = _allot(client, rig, car, slot).json()
    mine = client.get(f"{S}/vehicles/{car['id']}", headers=_h(rig["admin"])).json()
    assert mine["parking_slot"] == "V-1"
    assert client.post(f"{S}/parking/allocations/{alloc['id']}/release", headers=_h(rig["admin"])).status_code == 200
    assert client.get(f"{S}/vehicles/{car['id']}", headers=_h(rig["admin"])).json()["parking_slot"] is None
    assert _gate(client, rig, "MH12VS0001")["status"] == "no_parking"


# ── Visitors logged in the Visitors module ────────────────────────────────────

def _visitor(client, rig, mobile, plate):
    r = client.post(f"{S}/visitors/", headers=_h(rig["guard"]), json={
        "name": "Guest Person", "mobile": mobile, "society_id": str(rig["society"].id),
        "flat_id": str(rig["flat"].id), "purpose": "Family visit",
        "vehicle": {"vehicle_type": "car", "vehicle_number": plate}})
    assert r.status_code == 201, r.text
    return r.json()


def test_an_approved_visitors_vehicle_is_allowed_until_they_leave(client, db, rig):
    v = _visitor(client, rig, "9876501234", "MH 14 CD 5555")
    assert _gate(client, rig, "MH14CD5555")["status"] == "unregistered"           # still waiting for the resident
    assert client.post(f"{S}/visitors/{v['id']}/approve", json={}, headers=_h(rig["admin"])).status_code == 200
    body = _gate(client, rig, "MH14CD5555")
    assert (body["status"], body["category"], body["flat_number"]) == ("allowed", "visitor", "S-101")
    assert body["visitor_purpose"] == "Family visit"
    assert client.post(f"{S}/visitors/{v['id']}/checkin", json={}, headers=_h(rig["guard"])).status_code == 200
    assert _gate(client, rig, "MH14CD5555")["status"] == "allowed"
    assert client.post(f"{S}/visitors/{v['id']}/checkout", json={}, headers=_h(rig["guard"])).status_code == 200
    assert _gate(client, rig, "MH14CD5555")["status"] == "unregistered"


def test_a_rejected_visitors_vehicle_is_not_allowed(client, db, rig):
    v = _visitor(client, rig, "9876501235", "MH14CD6666")
    assert client.post(f"{S}/visitors/{v['id']}/reject", json={"reason": "Not expected"}, headers=_h(rig["admin"])).status_code == 200
    assert _gate(client, rig, "MH14CD6666")["status"] == "unregistered"


# ── The committee's list of vehicles and their parking ────────────────────────

def test_the_committee_sees_every_registered_vehicle_and_who_still_needs_parking(client, db, rig):
    slot = _slot(client, _h(rig["admin"]), rig["society"].id, "L-1")
    a = _vehicle(client, rig, "MH12LS0001")
    _vehicle(client, rig, "MH12LS0002", owner="tenant")
    _vehicle(client, rig, "MH12LS0003", parking_slot="OWN-7")
    assert _allot(client, rig, a, slot).status_code == 201
    base = f"{S}/parking/vehicles/society/{rig['society'].id}"
    allv = client.get(base, headers=_h(rig["admin"])).json()
    assert [v["vehicle_number"] for v in allv] == ["MH12LS0001", "MH12LS0002", "MH12LS0003"]
    row = {v["vehicle_number"]: v for v in allv}
    assert row["MH12LS0001"]["has_parking"] and row["MH12LS0001"]["parking_slot"] == "L-1"
    assert row["MH12LS0001"]["allocation_id"] and row["MH12LS0001"]["owner_name"] == "Scope Resident"
    assert row["MH12LS0001"]["flat_number"] == "S-101" and row["MH12LS0001"]["wing_name"] == "Wing S"
    assert row["MH12LS0002"]["category"] == "tenant" and not row["MH12LS0002"]["has_parking"]
    assert row["MH12LS0003"]["has_parking"] and row["MH12LS0003"]["allocation_id"] is None
    none = client.get(base + "?parking=none", headers=_h(rig["admin"])).json()
    assert [v["vehicle_number"] for v in none] == ["MH12LS0002"]
    held = client.get(base + "?parking=allotted", headers=_h(rig["admin"])).json()
    assert [v["vehicle_number"] for v in held] == ["MH12LS0001", "MH12LS0003"]
    assert client.get(base + "?parking=bogus", headers=_h(rig["admin"])).status_code == 422


def test_residents_and_guards_cannot_open_the_committees_vehicle_list(client, db, rig):
    base = f"{S}/parking/vehicles/society/{rig['society'].id}"
    assert client.get(base, headers=_h(rig["res_login"])).status_code == 403
    assert client.get(base, headers=_h(rig["guard"])).status_code == 403
