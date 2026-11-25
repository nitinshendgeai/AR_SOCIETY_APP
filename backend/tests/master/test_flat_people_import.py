"""Importing each flat's vehicles and family members from a sheet: every row checked with the form's own rules, a repeat
skipped, a bad row reported while the rest go in, and nothing written on a dry run."""
from datetime import date

import pytest

from app.models.resident import Resident, ResidentType
from app.models.tenant import Tenant
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleType
from app.models.wing import Wing
from app.services.flat_people_import import parse_relationship, parse_vehicle_type
from tests.conftest import make_flat, make_society, make_user, make_wing

VEH = "/api/v1/vehicles/import"
FAM = "/api/v1/residents/family-import"


@pytest.fixture
def rig(db):
    society = make_society(db, "People Import Society")
    admin = make_user(db, "pi-admin@x.test", role="Society Admin")
    admin["user"].society_id = society.id
    manager = make_user(db, "pi-mgr@x.test", role="Manager")
    manager["user"].society_id = society.id
    resident = make_user(db, "pi-res@x.test", role="Resident")
    resident["user"].society_id = society.id
    wing_a = make_wing(db, society.id, "Wing A")
    wing_b = Wing(society_id=society.id, name="Wing B", code="B")
    db.add(wing_b)
    db.commit()
    a101, a102, b201 = make_flat(db, wing_a.id, "101"), make_flat(db, wing_a.id, "102"), make_flat(db, wing_b.id, "201")
    other = make_society(db, "Other Import Society")
    other_flat = make_flat(db, make_wing(db, other.id, "Wing Z").id, "901")
    db.add_all([
        Resident(flat_id=a101.id, full_name="Asha Rao", resident_type=ResidentType.OWNER, is_primary=True),
        Tenant(flat_id=a102.id, full_name="Meena Shah", phone="9876500002"),
    ])
    db.commit()
    return {"h": admin["headers"], "mgr": manager["headers"], "res": resident["headers"], "a101": a101, "a102": a102,
            "b201": b201, "other_flat": other_flat, "society": society}


def _veh(**row):
    return {"wing": "A", "flat_number": "101", **row}


def _lines(rows):
    return [{**r, "line": i + 2} for i, r in enumerate(rows)]


# ── Reading cells ─────────────────────────────────────────────────────────────────────────────────────────────────────

def test_vehicle_types_are_read_the_way_people_write_them():
    cases = {"": VehicleType.CAR, "Car": VehicleType.CAR, "4W": VehicleType.CAR, "Four Wheeler": VehicleType.CAR,
             "Bike": VehicleType.MOTORCYCLE, "Two Wheeler": VehicleType.MOTORCYCLE, "2W": VehicleType.MOTORCYCLE,
             "Motor cycle": VehicleType.MOTORCYCLE, "Activa": VehicleType.SCOOTER, "Scooty": VehicleType.SCOOTER,
             "Cycle": VehicleType.BICYCLE, "Bicycle": VehicleType.BICYCLE, "Auto Rickshaw": VehicleType.AUTO,
             "truck": VehicleType.TRUCK, "SUV": VehicleType.CAR}
    for text, expected in cases.items():
        assert parse_vehicle_type(text)[0] == expected, text
    vtype, note = parse_vehicle_type("hovercraft")
    assert vtype == VehicleType.OTHER and "hovercraft" in note


def test_relationships_split_into_family_and_dependent():
    assert parse_relationship("Son") == ResidentType.DEPENDENT and parse_relationship("Daughter") == ResidentType.DEPENDENT
    assert parse_relationship("Wife") == ResidentType.FAMILY and parse_relationship("Father-in-law") == ResidentType.FAMILY
    assert parse_relationship("") == ResidentType.FAMILY and parse_relationship("Dependent") == ResidentType.DEPENDENT


# ── Vehicles ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_vehicles_dry_run_writes_nothing_then_the_import_adds_them(client, db, rig):
    rows = _lines([
        _veh(vehicle_number="mh 12-ab 1234", vehicle_type="4W", make="Honda", model="City", color="White",
             parking_slot="P-12", owner_name="asha rao"),
        _veh(vehicle_number="MH12CD5678", vehicle_type="Bike"),
        {"wing": "A", "flat_number": "102", "vehicle_number": "MH14EF0001", "vehicle_type": "Activa", "owner_name": "Meena Shah"},
        {"wing": "B", "flat_number": "201", "vehicle_number": "MH14GH0002", "vehicle_type": "weird", "owner_name": "Nobody"},
    ])
    dry = client.post(VEH, json={"rows": rows, "dry_run": True}, headers=rig["h"])
    assert dry.status_code == 200, dry.text
    assert [r["status"] for r in dry.json()] == ["created"] * 4
    assert db.query(Vehicle).count() == 0                                           # nothing written

    done = client.post(VEH, json={"rows": rows, "dry_run": False}, headers=rig["h"]).json()
    assert [r["status"] for r in done] == ["created"] * 4
    assert "not recognised" in done[3]["message"] and "not a resident or tenant" in done[3]["message"]

    cars = {v.vehicle_number: v for v in db.query(Vehicle).all()}
    assert set(cars) == {"MH12AB1234", "MH12CD5678", "MH14EF0001", "MH14GH0002"}     # numbers tidied: no spaces, upper case
    first = cars["MH12AB1234"]
    assert (first.vehicle_type, first.make, first.model, first.color, first.parking_slot) == (
        VehicleType.CAR, "Honda", "City", "White", "P-12")
    assert first.flat_id == rig["a101"].id and first.resident_id is not None and first.tenant_id is None   # owner linked
    assert cars["MH12CD5678"].vehicle_type == VehicleType.MOTORCYCLE and cars["MH12CD5678"].resident_id == first.resident_id   # no owner named: the primary resident
    assert cars["MH14EF0001"].tenant_id is not None and cars["MH14EF0001"].resident_id is None              # a tenant's vehicle
    assert cars["MH14GH0002"].vehicle_type == VehicleType.OTHER

    shown = client.get(f"/api/v1/vehicles/flat/{rig['a101'].id}", headers=rig["h"]).json()
    assert sorted(v["vehicle_number"] for v in shown) == ["MH12AB1234", "MH12CD5678"]


def test_owner_type_links_a_vehicle_to_the_tenant(client, db, rig):
    flat = {"wing": "A", "flat_number": "102"}
    rows = _lines([
        {**flat, "vehicle_number": "MH12TT0001", "owner_name": "meena shah", "owner_type": "Tenant"},
        {**flat, "vehicle_number": "MH12TT0002", "owner_type": "tenant"},                    # no name: the flat's one tenant
        {**flat, "vehicle_number": "MH12TT0003", "owner_name": "Meena Shah", "owner_type": "Resident"},
        {**flat, "vehicle_number": "MH12TT0004", "owner_type": "landlord"},
    ])
    out = client.post(VEH, json={"rows": rows, "dry_run": False}, headers=rig["h"]).json()
    assert [r["status"] for r in out] == ["created", "created", "created", "error"]
    assert "not a resident of this flat" in out[2]["message"] and "Owner type" in out[3]["message"]
    cars = {v.vehicle_number: v for v in db.query(Vehicle).all()}
    assert cars["MH12TT0001"].tenant_id is not None and cars["MH12TT0001"].resident_id is None
    assert cars["MH12TT0002"].tenant_id == cars["MH12TT0001"].tenant_id
    # a name that is no resident of the flat: the flat has no resident, only this one tenant, so it goes to them
    assert cars["MH12TT0003"].tenant_id == cars["MH12TT0001"].tenant_id and cars["MH12TT0003"].resident_id is None
    assert "linked to" in out[2]["message"]


def test_a_second_import_skips_what_is_there_and_repeats_are_caught(client, db, rig):
    rows = _lines([_veh(vehicle_number="MH12AB1234")])
    assert client.post(VEH, json={"rows": rows, "dry_run": False}, headers=rig["h"]).json()[0]["status"] == "created"

    again = client.post(VEH, json={"rows": rows, "dry_run": False}, headers=rig["h"]).json()
    assert again[0]["status"] == "skipped" and "already registered to this flat" in again[0]["message"]
    assert db.query(Vehicle).count() == 1

    mixed = _lines([
        {"wing": "A", "flat_number": "102", "vehicle_number": "MH12 AB 1234"},        # same plate, another flat
        _veh(vehicle_number="MH20ZZ0001"),
        _veh(vehicle_number="mh20-zz-0001"),                                          # the same plate twice in the file
    ])
    out = client.post(VEH, json={"rows": mixed, "dry_run": False}, headers=rig["h"]).json()
    assert out[0]["status"] == "error" and "already registered to flat" in out[0]["message"] and "101" in out[0]["message"]
    assert out[1]["status"] == "created"
    assert out[2]["status"] == "error" and "appears again (line 3" in out[2]["message"]


def test_bad_vehicle_rows_are_reported_and_the_rest_go_in(client, db, rig):
    rows = _lines([
        {"wing": "A", "flat_number": "999", "vehicle_number": "MH12AB0001"},          # no such flat
        _veh(vehicle_number=""),                                                      # no number
        _veh(vehicle_number="!!"),                                                    # not a plate
        {"flat_number": "101", "vehicle_number": "MH12AB0002"},                       # wing left out: only one flat 101
        {"wing": "A", "flat_number": "", "vehicle_number": "MH12AB0003"},
        {"wing": "Z", "flat_number": "901", "vehicle_number": "MH12AB0004"},          # another society's flat
    ])
    out = client.post(VEH, json={"rows": rows, "dry_run": False}, headers=rig["h"]).json()
    assert [r["status"] for r in out] == ["error", "error", "error", "created", "error", "error"]
    assert "No flat 999" in out[0]["message"] and "Vehicle number is required" in out[1]["message"]
    assert "valid vehicle number" in out[2]["message"] and "Flat number is required" in out[4]["message"]
    assert [v.vehicle_number for v in db.query(Vehicle).all()] == ["MH12AB0002"]


def test_only_the_committee_imports(client, rig):
    body = {"rows": _lines([_veh(vehicle_number="MH12AB1234")]), "dry_run": True}
    assert client.post(VEH, json=body, headers=rig["mgr"]).status_code == 403
    assert client.post(VEH, json=body, headers=rig["res"]).status_code == 403
    fam = {"rows": _lines([{"wing": "A", "flat_number": "101", "full_name": "Ravi Rao"}]), "dry_run": True}
    assert client.post(FAM, json=fam, headers=rig["mgr"]).status_code == 403
    assert client.post(FAM, json=fam, headers=rig["res"]).status_code == 403


# ── Family members ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_family_members_are_added_as_family_or_dependent_without_a_login(client, db, rig):
    rows = _lines([
        {"wing": "A", "flat_number": "101", "full_name": "Sunita Rao", "relationship": "Wife", "phone": "9876543210",
         "email": "sunita@x.test", "date_of_birth": "14/03/1982"},
        {"wing": "A", "flat_number": "101", "full_name": "Aarav Rao", "relationship": "Son", "date_of_birth": "2015-06-01"},
        {"wing": "B", "flat_number": "201", "full_name": "Kiran Patil"},
    ])
    dry = client.post(FAM, json={"rows": rows, "dry_run": True}, headers=rig["h"]).json()
    assert [r["status"] for r in dry] == ["created"] * 3
    assert db.query(Resident).filter(Resident.is_primary == False).count() == 0            # noqa: E712

    done = client.post(FAM, json={"rows": rows, "dry_run": False}, headers=rig["h"]).json()
    assert [r["status"] for r in done] == ["created"] * 3 and done[1]["message"] == "Added as Dependent"

    people = {r.full_name: r for r in db.query(Resident).all()}
    assert people["Sunita Rao"].resident_type == ResidentType.FAMILY and people["Sunita Rao"].date_of_birth == date(1982, 3, 14)
    assert people["Aarav Rao"].resident_type == ResidentType.DEPENDENT and people["Aarav Rao"].is_primary is False
    assert people["Kiran Patil"].flat_id == rig["b201"].id and people["Kiran Patil"].resident_type == ResidentType.FAMILY
    assert people["Sunita Rao"].user_id is None                                              # no login was made
    assert db.query(User).filter(User.email.like("%9876543210%")).count() == 0

    listed = client.get("/api/v1/residents/", params={"flat_id": str(rig["a101"].id)}, headers=rig["h"]).json()
    assert sorted(r["full_name"] for r in listed) == ["Aarav Rao", "Asha Rao", "Sunita Rao"]


def test_family_repeats_and_bad_rows(client, db, rig):
    rows = _lines([{"wing": "A", "flat_number": "101", "full_name": "Sunita Rao", "relationship": "Wife"}])
    client.post(FAM, json={"rows": rows, "dry_run": False}, headers=rig["h"])
    mixed = _lines([
        {"wing": "A", "flat_number": "101", "full_name": "  sunita   rao "},             # already there: spaces and case ignored
        {"wing": "A", "flat_number": "101", "full_name": "Asha Rao", "relationship": "Mother"},   # the owner's own name
        {"wing": "A", "flat_number": "101", "full_name": "Meera Rao", "phone": "12345"},          # not a mobile number
        {"wing": "A", "flat_number": "101", "full_name": "Neel Rao", "date_of_birth": "31/02/2010"},
        {"wing": "A", "flat_number": "101", "full_name": "Om Rao", "date_of_birth": "01/01/2999"},  # not born yet
        {"wing": "A", "flat_number": "101", "full_name": ""},
        {"wing": "A", "flat_number": "404", "full_name": "Lost Soul"},
        {"wing": "A", "flat_number": "101", "full_name": "Pia Rao"},
        {"wing": "A", "flat_number": "101", "full_name": "PIA RAO"},                              # twice in the file
    ])
    out = client.post(FAM, json={"rows": mixed, "dry_run": False}, headers=rig["h"]).json()
    assert [r["status"] for r in out] == ["skipped", "skipped", "error", "error", "error", "error", "error", "created", "error"]
    assert "already on the list" in out[0]["message"] and "already on the list" in out[1]["message"]
    assert "Name is required" in out[5]["message"] and "No flat 404" in out[6]["message"] and "appears again" in out[8]["message"]
    names = sorted(r.full_name for r in db.query(Resident).filter(Resident.flat_id == rig["a101"].id))
    assert names == ["Asha Rao", "Pia Rao", "Sunita Rao"]
