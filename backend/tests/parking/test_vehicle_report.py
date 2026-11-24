"""The vehicle report: registered vehicles, parking, the month's violations and fines, the month's gate movements and visitor
vehicles - narrowed to a wing or a flat, as a screen, a PDF and an Excel file."""
import io
from datetime import date, datetime, timedelta

import pytest

from app.models.flat import OccupancyStatus
from app.models.vehicle import Vehicle, VehicleType
from app.modules.parking.models.parking import (
    AccessType, ParkingAccessLog, ParkingAllocation, ParkingSlot, ParkingViolation, ParkingZone, SlotStatus, SlotType,
    ViolationType, VisitorParking, VisitorParkingStatus,
)
from tests.conftest import make_flat, make_society, make_user, make_wing

P = "/api/v1/parking"


def _login(db, email, role, society):
    who = make_user(db, email, role=role)
    who["user"].society_id = society.id
    db.commit()
    return who


@pytest.fixture
def rig(db):
    society = make_society(db, "Vehicle Report Society")
    other = make_society(db, "Elsewhere Society")
    wing_a, wing_b = make_wing(db, society.id, "A"), None
    from app.models.wing import Wing
    wing_b = Wing(society_id=society.id, name="B", code="B")
    db.add(wing_b)
    db.commit()
    a101, a102, a103 = make_flat(db, wing_a.id, "101"), make_flat(db, wing_a.id, "102"), make_flat(db, wing_a.id, "103")
    b201 = make_flat(db, wing_b.id, "201")
    for f in (a101, a102, b201):
        f.occupancy_status = OccupancyStatus.OWNER_OCCUPIED               # 103 stays vacant
    db.commit()

    today = date.today()
    v1 = Vehicle(society_id=society.id, flat_id=a101.id, vehicle_number="MH12AA1111", vehicle_type=VehicleType.CAR,
                 make="Honda", model="City", insurance_expiry=(today - timedelta(days=5)).isoformat())
    v2 = Vehicle(society_id=society.id, flat_id=a101.id, vehicle_number="MH12BB2222", vehicle_type=VehicleType.MOTORCYCLE,
                 insurance_expiry=(today + timedelta(days=10)).isoformat())
    v3 = Vehicle(society_id=society.id, flat_id=b201.id, vehicle_number="MH12CC3333", vehicle_type=VehicleType.CAR,
                 insurance_expiry=(today + timedelta(days=200)).isoformat())
    db.add_all([v1, v2, v3])
    db.flush()

    zone = ParkingZone(society_id=society.id, name="Basement", code="B1", total_slots=3)
    db.add(zone)
    db.flush()
    p1 = ParkingSlot(society_id=society.id, zone_id=zone.id, slot_number="P1", slot_type=SlotType.RESIDENT, status=SlotStatus.OCCUPIED)
    p2 = ParkingSlot(society_id=society.id, zone_id=zone.id, slot_number="P2", slot_type=SlotType.RESIDENT, status=SlotStatus.AVAILABLE)
    p3 = ParkingSlot(society_id=society.id, zone_id=zone.id, slot_number="P3", slot_type=SlotType.RESIDENT, status=SlotStatus.BLOCKED)
    db.add_all([p1, p2, p3])
    db.flush()
    db.add(ParkingAllocation(society_id=society.id, slot_id=p1.id, flat_id=a101.id, vehicle_id=v1.id,
                             allocation_type=SlotType.RESIDENT, start_date=today - timedelta(days=30),
                             end_date=today + timedelta(days=15)))

    now = datetime.utcnow()
    db.add_all([
        ParkingViolation(society_id=society.id, vehicle_number="MH12BB2222", vehicle_id=v2.id, violation_type=ViolationType.WRONG_SLOT,
                         fine_amount=500, description="In someone else's slot"),
        ParkingViolation(society_id=society.id, vehicle_number="MH12BB2222", vehicle_id=v2.id, violation_type=ViolationType.DOUBLE_PARKING,
                         is_resolved=True),
        ParkingViolation(society_id=society.id, vehicle_number="KA01ZZ9999", violation_type=ViolationType.UNAUTHORIZED),
        ParkingViolation(society_id=society.id, vehicle_number="MH12AA1111", vehicle_id=v1.id, violation_type=ViolationType.NO_PARKING,
                         created_at=datetime(2020, 1, 15, 6, 0)),
        # gate: two residents (one with no parking, so not let in), a visitor, a stranger
        ParkingAccessLog(society_id=society.id, vehicle_id=v2.id, vehicle_number="MH12BB2222", access_type=AccessType.ENTRY,
                         access_time=now - timedelta(minutes=30), is_authorized=True),
        ParkingAccessLog(society_id=society.id, vehicle_id=v3.id, vehicle_number="MH12CC3333", access_type=AccessType.ENTRY,
                         access_time=now - timedelta(minutes=20), is_authorized=False),
        ParkingAccessLog(society_id=society.id, vehicle_number="MH14VV0001", access_type=AccessType.ENTRY,
                         access_time=now - timedelta(minutes=10), is_authorized=True),
        ParkingAccessLog(society_id=society.id, vehicle_number="KA01ZZ9999", access_type=AccessType.EXIT,
                         access_time=now - timedelta(minutes=5), is_authorized=False),
        # visitor parking: one still inside past the hour given, one that came and went
        VisitorParking(society_id=society.id, vehicle_number="MH14VV0001", host_flat_id=a101.id, check_in_time=now - timedelta(minutes=90),
                       expected_duration_hours=1, status=VisitorParkingStatus.ACTIVE),
        VisitorParking(society_id=society.id, vehicle_number="MH14VV0002", host_flat_id=b201.id, check_in_time=now - timedelta(minutes=40),
                       check_out_time=now - timedelta(minutes=10), expected_duration_hours=4, status=VisitorParkingStatus.COMPLETED),
    ])
    db.commit()
    return {
        "society": society, "sid": str(society.id), "wing_a": wing_a, "wing_b": wing_b, "a101": a101, "b201": b201,
        "manager": _login(db, "mgr@vr.test", "Manager", society), "admin": _login(db, "adm@vr.test", "Society Admin", society),
        "guard": _login(db, "grd@vr.test", "Security Staff", society), "resident": _login(db, "res@vr.test", "Resident", society),
        "other_admin": _login(db, "oadm@vr.test", "Society Admin", other),
    }


def _get(client, rig, who="manager", **params):
    r = client.get(f"{P}/report/{rig['sid']}", params=params, headers=rig[who]["headers"])
    assert r.status_code == 200, r.text
    return r.json()


def test_the_report_has_the_four_parts(client, rig):
    rep = _get(client, rig)
    v, k, w, g = rep["vehicles"], rep["parking"], rep["violations"], rep["gate"]

    s = v["summary"]
    assert (s["total"], s["with_parking"], s["without_parking"]) == (3, 1, 2)
    assert s["by_type"] == {"Car": 2, "Motorcycle": 1}
    assert (s["insurance_expired"], s["insurance_soon"], s["insurance_missing"]) == (1, 1, 0)
    # insurance trouble comes first in the list
    assert [r["insurance"] for r in v["rows"]][:2] == ["expired", "soon"] or {r["insurance"] for r in v["rows"][:2]} == {"expired", "soon"}
    assert v["flats_without_vehicle"] == ["A 102"] and s["flats_without_vehicle"] == 1          # 103 is vacant

    assert (k["summary"]["slots"], k["summary"]["allotted"], k["summary"]["free"], k["summary"]["blocked"]) == (3, 1, 1, 1)
    assert [(f["flat"], f["vehicles"], f["without_parking"]) for f in k["flats_short"]] == [("A 101", 2, 1), ("B 201", 1, 1)]
    assert [e["slot"] for e in k["ending_soon"]] == ["P1"]

    assert (w["summary"]["total"], w["summary"]["open"], w["summary"]["resolved"]) == (3, 2, 1)       # last year's is not counted
    assert w["summary"]["by_type"]["Wrong slot"] == 1
    assert w["summary"]["fines_not_charged"] == 500 and w["summary"]["fines_charged"] == 0       # set, not yet put on a flat
    assert [(o["vehicle_number"], o["count"]) for o in w["repeat_offenders"]] == [("MH12BB2222", 2)]

    gs = g["summary"]
    assert (gs["total"], gs["entries"], gs["exits"]) == (4, 3, 1)
    assert (gs["residents"], gs["visitors"], gs["unknown"], gs["not_allowed"]) == (2, 1, 1, 2)
    assert (gs["visitor_inside"], gs["visitor_visits"], gs["visitor_overstayed"]) == (1, 2, 1)
    assert gs["visitor_avg_stay_minutes"] == 30             # only the visit that has ended has a length
    assert g["visitors_inside"][0]["vehicle_number"] == "MH14VV0001" and g["visitors_inside"][0]["overstayed"] is True


def test_a_wing_or_a_flat_narrows_every_part(client, rig):
    wing = _get(client, rig, wing_id=str(rig["wing_a"].id))
    assert wing["wing"] == "A" and wing["vehicles"]["summary"]["total"] == 2
    assert {r["vehicle_number"] for r in wing["vehicles"]["rows"]} == {"MH12AA1111", "MH12BB2222"}
    assert wing["violations"]["summary"]["total"] == 2                       # the stranger's plate belongs to no flat
    assert wing["gate"]["summary"]["total"] == 1 and wing["gate"]["rows"][0]["vehicle_number"] == "MH12BB2222"
    assert wing["gate"]["summary"]["visitor_inside"] == 1                    # the visitor is here for a flat of wing A

    flat = _get(client, rig, flat_id=str(rig["b201"].id))
    assert flat["flat"] == "B 201" and flat["vehicles"]["summary"]["total"] == 1
    assert flat["violations"]["summary"]["total"] == 0
    assert [r["vehicle_number"] for r in flat["gate"]["rows"]] == ["MH12CC3333"]
    assert flat["gate"]["summary"]["visitor_inside"] == 0


def test_another_month_and_a_wrong_month(client, rig):
    old = _get(client, rig, month="2020-01")
    assert old["month"] == "2020-01" and old["month_label"] == "January 2020"
    assert old["violations"]["summary"]["total"] == 1 and old["violations"]["rows"][0]["vehicle_number"] == "MH12AA1111"
    assert old["gate"]["summary"]["total"] == 0
    assert old["vehicles"]["summary"]["total"] == 3                          # vehicles and parking are as they are today
    for bad in ("2026-13", "2026-1", "soon"):
        r = client.get(f"{P}/report/{rig['sid']}", params={"month": bad}, headers=rig["manager"]["headers"])
        assert r.status_code == 422, bad


def test_unknown_wing_or_flat_and_other_societies_are_refused(client, db, rig):
    from uuid import uuid4
    h = rig["manager"]["headers"]
    assert client.get(f"{P}/report/{rig['sid']}", params={"wing_id": str(uuid4())}, headers=h).status_code == 404
    assert client.get(f"{P}/report/{rig['sid']}", params={"flat_id": str(uuid4())}, headers=h).status_code == 404
    elsewhere = make_flat(db, make_wing(db, rig["other_admin"]["user"].society_id, "Z").id, "900")
    assert client.get(f"{P}/report/{rig['sid']}", params={"flat_id": str(elsewhere.id)}, headers=h).status_code == 404
    assert client.get(f"{P}/report/{rig['sid']}", headers=rig["other_admin"]["headers"]).status_code == 403


def test_only_the_manager_and_above_may_read_it(client, rig):
    url = f"{P}/report/{rig['sid']}"
    assert client.get(url, headers=rig["resident"]["headers"]).status_code == 403
    assert client.get(url, headers=rig["guard"]["headers"]).status_code == 403
    assert client.get(url, headers=rig["manager"]["headers"]).status_code == 200
    assert client.get(url, headers=rig["admin"]["headers"]).status_code == 200
    assert client.get(url + "/file", headers=rig["guard"]["headers"]).status_code == 403


def test_the_printout_and_the_spreadsheet_carry_everything(client, rig):
    h = rig["manager"]["headers"]
    pdf = client.get(f"{P}/report/{rig['sid']}/file", params={"format": "pdf"}, headers=h)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    xlsx = client.get(f"{P}/report/{rig['sid']}/file", params={"format": "xlsx", "wing_id": str(rig["wing_a"].id)}, headers=h)
    assert xlsx.status_code == 200 and "spreadsheetml" in xlsx.headers["content-type"]
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(xlsx.content))
    assert wb.sheetnames == ["Summary", "Vehicles", "Parking", "Flats short of parking", "Violations", "Gate log", "Visitors inside"]
    plates = {row[0].value for row in wb["Vehicles"].iter_rows(min_row=6)}
    assert plates == {"MH12AA1111", "MH12BB2222"}                            # the wing's, not B's
    assert client.get(f"{P}/report/{rig['sid']}/file", params={"format": "doc"}, headers=h).status_code == 422


def test_a_plate_that_looks_like_a_formula_is_written_as_text(client, db, rig):
    db.add(Vehicle(society_id=rig["society"].id, flat_id=rig["b201"].id, vehicle_number="=SUM(1+1)"))
    db.commit()
    xlsx = client.get(f"{P}/report/{rig['sid']}/file", params={"format": "xlsx"}, headers=rig["manager"]["headers"])
    from openpyxl import load_workbook
    cells = [row[0] for row in load_workbook(io.BytesIO(xlsx.content))["Vehicles"].iter_rows(min_row=6)]
    formula = next(c for c in cells if c.value == "=SUM(1+1)")
    assert formula.data_type == "s"


def test_the_screen_shows_a_few_rows_and_says_how_many_there_are(client, db, rig):
    db.add_all([Vehicle(society_id=rig["society"].id, flat_id=rig["b201"].id, vehicle_number=f"MH99ZZ{i:04d}") for i in range(120)])
    db.commit()
    shown = _get(client, rig)["vehicles"]
    assert len(shown["rows"]) == 100 and shown["row_count"] == 123
    full = client.get(f"{P}/report/{rig['sid']}/file", params={"format": "xlsx"}, headers=rig["manager"]["headers"])
    from openpyxl import load_workbook
    assert sum(1 for _ in load_workbook(io.BytesIO(full.content))["Vehicles"].iter_rows(min_row=6)) == 123


def _ids(db, rig):
    return {v.vehicle_number: v.id for v in db.query(Vehicle).filter_by(society_id=rig["society"].id).all()}


def test_each_vehicle_row_carries_its_id_so_the_screen_can_deregister_it(client, db, rig):
    ids = _ids(db, rig)
    rows = _get(client, rig)["vehicles"]["rows"]
    assert {r["vehicle_number"]: r["id"] for r in rows} == {n: str(i) for n, i in ids.items()}


def test_vehicles_can_be_deregistered_together_freeing_their_parking(client, db, rig):
    ids = _ids(db, rig)
    admin = rig["admin"]["headers"]
    before = _get(client, rig)["vehicles"]["summary"]["total"]
    r = client.post("/api/v1/vehicles/deregister", headers=admin,
                    json={"vehicle_ids": [str(ids["MH12AA1111"]), str(ids["MH12BB2222"]), "00000000-0000-0000-0000-000000000000"]})
    assert r.status_code == 200 and r.json() == {"deregistered": 2, "not_found": 1}
    rep = _get(client, rig)["vehicles"]
    assert before == 3 and rep["summary"]["total"] == 1
    assert [x["vehicle_number"] for x in rep["rows"]] == ["MH12CC3333"]                 # only the third is left on the report
    db.expire_all()
    gone = db.query(Vehicle).filter_by(id=ids["MH12AA1111"]).one()
    assert gone.is_active is False and gone.rfid_tag is None                             # soft: the record stays
    p1 = db.query(ParkingSlot).filter_by(society_id=rig["society"].id, slot_number="P1").one()
    assert p1.status == SlotStatus.AVAILABLE                                             # its slot is free again
    alloc = db.query(ParkingAllocation).filter_by(vehicle_id=ids["MH12AA1111"]).one()
    assert alloc.status.value == "released"
    again = client.post("/api/v1/vehicles/deregister", headers=admin, json={"vehicle_ids": [str(ids["MH12AA1111"])]})
    assert again.json() == {"deregistered": 0, "not_found": 1}                           # already gone: counted, not an error


def test_only_committee_or_admin_in_the_same_society_may_deregister_in_bulk(client, db, rig):
    ids = _ids(db, rig)
    body = {"vehicle_ids": [str(ids["MH12CC3333"])]}
    assert client.post("/api/v1/vehicles/deregister", headers=rig["manager"]["headers"], json=body).status_code == 403
    assert client.post("/api/v1/vehicles/deregister", headers=rig["resident"]["headers"], json=body).status_code == 403
    other = client.post("/api/v1/vehicles/deregister", headers=rig["other_admin"]["headers"], json=body)
    assert other.status_code == 200 and other.json() == {"deregistered": 0, "not_found": 1}   # not their society's vehicle
    db.expire_all()
    assert db.query(Vehicle).filter_by(id=ids["MH12CC3333"]).one().is_active is True
    admin = rig["admin"]["headers"]
    assert client.post("/api/v1/vehicles/deregister", headers=admin, json={"vehicle_ids": []}).status_code == 422
    too_many = {"vehicle_ids": ["00000000-0000-0000-0000-%012d" % i for i in range(501)]}
    assert client.post("/api/v1/vehicles/deregister", headers=admin, json=too_many).status_code == 422
